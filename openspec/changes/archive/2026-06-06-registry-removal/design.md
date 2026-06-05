## Context

当前系统的 extension 管理采用双层架构：数据库存储扩展元数据（`installed_extensions` 表），启动时从数据库加载并构建静态的 `HandlerRegistry` 和 `EntityTypeRegistry` 作为内存索引。这个设计源自文件系统时代，当时需要扫描目录并缓存结果。

现在系统已经完成向数据库的迁移（`extension-active-management` change），数据库成为配置元数据的权威源。但 Registry 层仍然存在，造成两个核心问题：

1. **信息冗余**：数据库中的 `manifest_snapshot` 包含完整的 handler 列表和 entity type 定义，Registry 只是这些数据的静态快照
2. **运行时僵化**：Registry 被设计为 sealed/immutable，一旦构建无法修改，导致扩展的安装/卸载/更新必须重启系统才能生效

系统约束：
- Handler 脚本代码存储在文件系统 `handlers/` 目录，数据库只存储元数据
- 每个 handler module 通过 `importlib` 动态加载，加载后缓存在 `NodeExecutor._modules` 中
- DAG 执行需要保证配置一致性，不能在运行中被外部变更影响

利益相关者：
- Extension 开发者：希望快速迭代，安装后立即可用
- 运维人员：希望动态管理扩展，避免重启影响正在运行的 DAG
- 系统架构：希望简化架构，减少冗余层

## Goals / Non-Goals

**Goals:**
- 移除 `HandlerRegistry` 和 `EntityTypeRegistry`，消除静态快照层
- Handler 元数据从数据库按需查询，支持运行时动态变更
- DAG 执行时创建配置快照，保证运行期间的一致性隔离
- 保持 module 缓存机制，性能不下降（每个 handler 仍只查询/加载一次）
- Entity type 配置支持运行时 reload
- 扩展安装/卸载后无需重启，新 DAG 自动使用最新配置

**Non-Goals:**
- 不改变 handler 脚本的文件系统存储方式（仍在 `handlers/` 目录）
- 不修改 module 缓存策略（`_modules` 保持不变）
- 不实现正在运行的 DAG 的热更新（使用快照隔离）
- 不优化数据库查询性能（首个版本先验证架构，后续可加缓存层）

## Decisions

### Decision 1: Handler 元数据查询策略

**决策**：创建 `DatabaseHandlerResolver` 类，每次 DAG 启动时查询 `installed_extensions` 表，解析 `manifest_snapshot` JSON 字段获取 handler 列表。

**备选方案**：
- A. 启动时预加载所有 handler 元数据到内存索引 → 被拒绝：仍然是静态快照，不支持运行时变更
- B. 每次执行 node 时都查询数据库 → 被拒绝：性能差，数据库压力大
- C. DAG 启动时查询一次，创建快照 → **选择此方案**

**选择理由**：
- DAG 启动时查询一次，构建该 DAG 执行的配置快照
- 快照包含 `DatabaseHandlerResolver` 实例，内部持有数据库 session
- `NodeExecutor._load_handler()` 首次加载 handler 时调用 resolver 查询元数据
- 后续使用 `_modules` 缓存，不再查询数据库
- 性能影响：每个 handler 一次数据库查询（解析 JSON）+ 一次 `importlib.load`
- 正在运行的 DAG 使用旧快照，不受新安装的扩展影响

### Decision 2: Entity Type 配置管理

**决策**：保留 `AppConfig.entity_types` dict 作为内存缓存，启动时从数据库加载，提供 reload API 刷新。

**备选方案**：
- A. 完全移除缓存，每次使用时查询数据库 → 被拒绝：entity type 查询频繁，性能差
- B. 使用 LRU cache + TTL 自动过期 → 被拒绝：增加复杂度，缓存失效时机难以控制
- C. 手动 reload API → **选择此方案**

**选择理由**：
- Entity type 的查询频率远高于 handler（每次 entity 操作都可能查询 schema）
- 内存 dict 查询性能最优
- 提供明确的 reload API（`POST /admin/reload-entity-types`），用户控制刷新时机
- DAG 启动时复制 `entity_types` 到快照，保证运行期间不变

### Decision 3: DAG 执行快照隔离

**决策**：新增 `DagExecutionSnapshot` 类，在 `DagController` 创建 DAG 执行时构建，包含：
- `dag_config`: DAG 配置
- `node_configs`: Node 配置字典
- `entity_types`: Entity type 配置（dict 副本）
- `handler_resolver`: `DatabaseHandlerResolver` 实例

**选择理由**：
- 保证 DAG 运行期间配置不变，即使外部安装了新扩展
- 符合数据库事务隔离的语义
- 解决"正在运行的 DAG 怎么办"的问题：使用启动时的快照，不受影响

### Decision 4: Handler 路径计算方式

**决策**：数据库存储 `extension_name` 和 `handler.entry`（相对路径），运行时计算绝对路径：
```python
handler_path = handlers_dir / extension_name / handler_entry
```

**备选方案**：
- A. 数据库存储绝对路径 → 被拒绝：`handlers_dir` 可能变化，路径硬编码不灵活
- B. 数据库存储相对路径，运行时计算 → **选择此方案**

**选择理由**：
- `handlers_dir` 可配置（默认 `handlers/`，可通过配置修改）
- 扩展导出/导入时路径无关性更好

### Decision 5: Module 缓存保持不变

**决策**：`NodeExecutor._modules` 缓存机制完全保留，不做任何修改。

**选择理由**：
- Module 缓存是性能关键路径，已经过验证
- Handler 元数据查询只影响首次加载，后续使用缓存
- 扩展卸载时可通过 `_modules.pop(handler_name)` 清理缓存（可选，不影响正确性）

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| [数据库查询增加首次加载延迟] → Module 缓存保证每个 handler 只查询一次；如果成为瓶颈，后续可在 `DatabaseHandlerResolver` 内部增加内存索引 |
| [DAG 快照隔离导致新扩展对正在运行的 DAG 不可见] → 这是设计目标，保证运行一致性；新 DAG 始终使用最新配置；文档明确说明此行为 |
| [Extension 变更与文件系统不同步] → 安装流程保证原子性：写数据库 → 复制代码 → commit；卸载时先禁用（`enabled=false`）再删除文件 |
| [Entity type reload 时机不明确] → 提供明确的 reload API，由用户/管理员决定何时刷新；未来可考虑 watch 数据库变更自动 reload |
| [测试需要大量重写] → 提供测试辅助函数 `create_test_snapshot()` 和 `mock_handler_resolver()`，简化测试数据注入 |
| [`manifest_snapshot` JSON 解析性能] → 当前扩展数量少（< 50），JSON 解析开销可忽略；如果成为瓶颈，可将 handlers 列表单独存储到表中 |
| [正在运行的 NodeExecutor 不感知扩展变更] → 这是设计目标；如果需要强制更新，可通过停止 DAG + 重新启动实现 |

## Migration Plan

### 阶段 1：新增组件（向后兼容）

1. 新增 `DatabaseHandlerResolver` 类（`packages/core/src/edera_core/resolver.py`）
2. 新增 `DagExecutionSnapshot` 类（`packages/core/src/edera_core/snapshot.py`）
3. 新增 entity type reload RPC（`proto/edera.proto`）
4. `NodeExecutor` 同时支持旧参数（`handler_registry`）和新参数（`snapshot`）

### 阶段 2：切换调用方（Breaking Change）

1. `DagController` 改为构建 `DagExecutionSnapshot` 传递给 `NodeExecutor`
2. `bootstrap.load_installed_extensions()` 停止构建 Registry，改为返回扩展列表
3. `graph_service.py` 的 `ListHandlers` 等方法改为查询数据库
4. 更新所有测试，使用新的测试辅助函数

### 阶段 3：清理旧代码

1. 移除 `HandlerRegistry` 和 `EntityTypeRegistry` 类（`registry.py`）
2. 移除 `NodeExecutor` 的 `handler_registry` 参数
3. 移除 `BootstrapResult` 中的 `handler_registry` 和 `entity_type_registry` 字段
4. 清理所有对 `scan_extensions()` 的残留引用

### Rollback 策略

如果发现严重问题需要回滚：
1. 恢复 `registry.py` 文件
2. 恢复 `bootstrap.py` 的 Registry 构建逻辑
3. 恢复 `NodeExecutor` 的 `handler_registry` 参数
4. 使用 git revert 回退相关 commits

由于是 Breaking Change，建议在测试环境充分验证后再部署到生产。

## Open Questions

1. **是否需要为 `DatabaseHandlerResolver` 增加内存缓存层？**
   - 当前设计依赖 module 缓存，如果 handler 数量极大（> 1000），可能需要在 resolver 内部增加 LRU cache
   - 建议：先实现无缓存版本，通过性能测试决定是否需要

2. **Entity type reload 是否需要事件通知机制？**
   - 当前设计是手动 reload API，未来是否需要 watch 数据库变更自动刷新？
   - 建议：先实现手动 reload，根据实际使用反馈决定是否需要自动机制

3. **`manifest_snapshot` 是否需要拆分为独立的 handlers 表？**
   - 当前 JSON 字段包含完整 manifest，如果 handler 数量极大，JSON 解析可能成为瓶颈
   - 建议：保持当前设计，如果性能测试发现问题再考虑拆分
