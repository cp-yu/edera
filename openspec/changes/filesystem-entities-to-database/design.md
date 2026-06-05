## Context

当前系统已完成核心配置型 entities (node, dag, trigger, resource) 的数据库迁移（`db-backed-core-entities`），这些 entities 存储在专用表 `entity_node`, `entity_dag`, `entity_trigger`, `entity_resource` 中。但普通业务 entities（如 stock, rss-source, api-source）仍存储在 `config/entities.yaml` 文件中，entity relations 存储在 `config/entity-relations.yaml` 文件中。

现有机制：
- 系统已支持 ordinary entities 的数据库存储（按 entity type 动态创建表）
- `EntityStore` 已有统一的查询接口，但数据源混合（核心 entities 从数据库，普通 entities 从文件）
- `entity_types` 表已存在，存储所有 entity type 的 schema 和配置

系统约束：
- 启动时需要加载所有 entities 到 `EntityStore`
- Web Console 已有实体管理页面（需确认）
- Entity relations 用于表达 entities 之间的关系（如 stock 使用 rss-source）

## Goals / Non-Goals

**Goals:**
- 移除 `config/entities.yaml` 和 `config/entity-relations.yaml` 文件
- 所有 entities 和 relations 从数据库加载，统一数据源
- 提供 CLI 命令管理 entities 和 relations
- 提供 import/export 功能，支持批量迁移和备份
- 数据库迁移脚本，自动导入现有 YAML 数据

**Non-Goals:**
- 不修改核心 entities 的存储方式（已在专用表中）
- 不修改 entity type 的管理方式（已在 `entity_types` 表中）
- 不实现 entity 版本控制或历史记录
- 不实现 relation 的复杂查询优化（如图查询）

## Decisions

### Decision 1: Ordinary entities 使用现有的动态表机制

**决策**：继续使用现有的 ordinary entity tables 机制，按 entity type 创建动态表。

**备选方案**：
- A. 所有 ordinary entities 存储在单个大表中，用 `type` 字段区分 → 被拒绝：查询性能差，schema 验证困难
- B. 按 entity type 动态创建表 → **选择此方案**（已存在）

**选择理由**：
- 系统已有 `ensure_ordinary_entity_table()` 机制
- 每个 entity type 有独立的 schema，存储在独立表更合理
- 查询性能更好，支持针对性索引

### Decision 2: Entity relations 存储在单表

**决策**：创建 `entity_relations` 表，存储所有 entity relations。

表结构：
```sql
CREATE TABLE entity_relations (
    id TEXT PRIMARY KEY,
    from_entity_id TEXT NOT NULL,
    to_entity_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    metadata TEXT,  -- JSON
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(from_entity_id, to_entity_id, relation_type)
);
CREATE INDEX idx_entity_relations_from ON entity_relations(from_entity_id);
CREATE INDEX idx_entity_relations_to ON entity_relations(to_entity_id);
CREATE INDEX idx_entity_relations_type ON entity_relations(relation_type);
```

**备选方案**：
- A. 按 relation type 创建多个表 → 被拒绝：relation types 不固定，动态创建表复杂
- B. 单表存储 → **选择此方案**

**选择理由**：
- Relation 数据量相对较小（< 10000 条）
- 查询模式简单：通常按 entity ID 或 relation type 过滤
- 单表易于管理和迁移

### Decision 3: Entity 加载策略 - 按需预加载

**决策**：系统启动时不加载 entities，DAG 运行前预加载相关 entities 到内存，DAG 结束后清理缓存。查询结果包含缓存命中标识。

**备选方案**：
- A. 启动时全量加载到内存 → 被拒绝：entities 可能较多，启动时不需要全部加载
- B. 按需预加载 + DAG 生命周期缓存 → **选择此方案**
- C. 完全按需查询，无缓存 → 被拒绝：DAG 运行中查询仍有性能需求

**选择理由**：
- 查询不频繁，无需启动时全量加载
- DAG 运行前会预加载相关 entities，运行中查询快速
- DAG 结束后清理缓存，避免内存无限增长
- 非 DAG 上下文查询直接访问数据库，保持简洁

**实现机制**：

1. **缓存结构**：
   ```python
   # EntityStore.memory_entities 改为按 dag_run_id 分组
   memory_entities: dict[str, dict[str, EntityConfig]]  # {dag_run_id: {entity_id: entity}}
   ```

2. **查询结果包装**：
   ```python
   @dataclass
   class EntityQueryResult:
       entity: EntityConfig
       from_cache: bool          # 是否从缓存返回
       dag_run_id: str | None    # 关联的 DAG run ID（如果有）
   ```

3. **预加载逻辑**（DAG 运行前）：
   - 分析 DAG definition，提取所有直接引用的 entity refs（不包括 relations 传递引用）
   - 批量查询数据库加载这些 entities
   - 存入 `memory_entities[dag_run_id]`
   - 如果预加载失败（entity 不存在），直接失败，拒绝启动 DAG

4. **查询回退**（DAG 运行中）：
   - CLI/gRPC 查询时，通过上下文传递 `dag_run_id`
   - 优先查 `memory_entities[dag_run_id]`
     - 命中：返回 `EntityQueryResult(entity, from_cache=True, dag_run_id=...)`
   - 未命中则查数据库
     - 查到：返回 `EntityQueryResult(entity, from_cache=False, dag_run_id=None)`
     - 不缓存到 memory（保持简单设计）

5. **清理机制**（DAG 运行后）：
   - DAG 执行结束时（成功/失败/取消）触发
   - 删除 `memory_entities[dag_run_id]`

6. **非 DAG 查询**：
   - 无 `dag_run_id` 上下文时，直接查询数据库
   - 返回 `EntityQueryResult(entity, from_cache=False, dag_run_id=None)`

### Decision 4: CLI 命令设计 - 通用列过滤 + Relation 别名

**决策**：Entity CLI 支持通用列过滤，Relation 提供简短别名作为语法糖。

```bash
# 通用形式（适用所有 entity types）
edera entity list --type <type> [--filter <column>=<value>]...
edera entity create --type <type> --attributes <json>
edera entity delete <entity-id>
edera entity import <file.yaml>
edera entity export [--type <type>] -o <file.yaml>

# 示例：查询 relations
edera entity list --type relation --filter from_entity_id=stock:00700.HK --filter relation_type=uses-source

# Relation 别名（简化常用操作）
edera relation list [--from <id>] [--to <id>] [--type <type>]
edera relation create --from <id> --to <id> --type <type>
edera relation delete <relation-id>
edera relation import <file.yaml>
edera relation export -o <file.yaml>

# 别名等价转换
edera relation list --from X --to Y --type Z
  ↓
edera entity list --type relation --filter from_entity_id=X --filter to_entity_id=Y --filter relation_type=Z
```

**备选方案**：
- A. 为每个 entity type 设计专用 CLI → 被拒绝：维护成本高，无法扩展
- B. 只提供通用 entity CLI → 被拒绝：relation 操作频繁，冗长语法影响用户体验
- C. 通用 CLI + 高频操作别名 → **选择此方案**

**选择理由**：
- Entity 本质上是表，from/to/type 只是列名，通用设计更合理
- `--filter` 机制适用所有 entity types，未来无需为新 type 定制 CLI
- Relation 别名提升常用场景用户体验（`--from` 比 `--filter from_entity_id=` 简洁）
- 别名是薄包装层，底层统一实现，维护成本低

### Decision 5: 数据库迁移策略 - 手动一次性迁移

**决策**：不提供自动迁移脚本，使用 `edera entity import` 和 `edera relation import` CLI 命令手动执行一次性迁移。

**备选方案**：
- A. 启动时自动检测并迁移 YAML 文件 → 被拒绝：系统还在开发阶段，无历史负担，无需自动化
- B. 手动调用 CLI 命令完成迁移 → **选择此方案**

**选择理由**：
- 当前还在开发阶段，没有生产环境负担
- 开发团队可以直接操作数据库，无需自动化
- 简化代码，减少启动时的复杂逻辑
- CLI import/export 功能已经足够完成迁移

**迁移步骤**（开发环境手动执行一次）：
```bash
# 1. 导入 entities
edera entity import config/entities.yaml

# 2. 导入 relations
edera relation import config/entity-relations.yaml

# 3. 验证导入结果
edera entity list
edera relation list

# 4. 备份原文件（可选）
mv config/entities.yaml config/entities.yaml.backup
mv config/entity-relations.yaml config/entity-relations.yaml.backup
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| [YAML 数据格式不兼容] → 提供 schema 验证，导入前检查格式；导入失败时保留原文件，记录详细错误 |
| [Entity ID 冲突] → 导入时检查 ID 唯一性；冲突时报错并跳过该 entity |
| [Relation 引用的 entity 不存在] → 导入时验证 entity 存在性；不存在时记录警告并跳过该 relation |
| [DAG 预加载失败] → 预加载时验证所有引用的 entities 存在；失败时拒绝启动 DAG 并报告缺失的 entities |
| [缓存未及时清理导致内存泄漏] → DAG 执行结束时（成功/失败/取消）必须触发清理；异常退出时通过 finally 块保证清理 |
| [内存占用增加] → 仅 DAG 运行时按需缓存，非 DAG 查询不缓存；缓存按 dag_run_id 隔离，生命周期短 |
| [Web Console 需要适配] → 检查现有实体管理页面是否存在；如不存在，需新增页面 |

## Migration Plan

### 阶段 1：数据库表和 Repository

1. 新增 `EntityRelation` model（`storage/entities.py`）
2. 新增 entity 和 relation CRUD 函数（`storage/repository.py`）
3. 新增 `EntityQueryResult` 包装类

### 阶段 2：修改 EntityStore

1. `EntityStore.memory_entities` 改为按 dag_run_id 分组的缓存结构
2. 新增预加载逻辑：DAG 运行前加载相关 entities
3. 修改查询接口：返回 `EntityQueryResult`，支持缓存命中标识
4. 新增清理逻辑：DAG 结束后清理缓存
5. 移除文件系统加载逻辑（`config/loader.py`）

### 阶段 3：CLI 和 gRPC

1. 新增 `edera entity` 和 `edera relation` CLI 命令
2. 新增 gRPC service（`EntityService`, `RelationService`）
3. 实现 import/export 功能
4. CLI 查询支持传递 `dag_run_id` 上下文

### 阶段 4：Web Console（可选）

1. 检查现有实体管理页面
2. 如不存在，新增实体管理页面
3. 支持 CRUD 操作

### 阶段 5：清理和测试

1. 移除 `config/entities.yaml` 和 `config/entity-relations.yaml` 引用
2. 更新文档和示例
3. 完整的集成测试（包括预加载、缓存命中、清理机制）

### 手动迁移步骤

首次部署时，开发团队手动执行：
```bash
edera entity import config/entities.yaml
edera relation import config/entity-relations.yaml
edera entity list  # 验证
mv config/entities.yaml config/entities.yaml.backup
mv config/entity-relations.yaml config/entity-relations.yaml.backup
```
