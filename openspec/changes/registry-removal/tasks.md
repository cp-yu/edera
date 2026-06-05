# Implementation Tasks

### Task 1: 实现 DatabaseHandlerResolver

**Goal**: 创建 `DatabaseHandlerResolver` 类，从数据库查询 handler 元数据并计算文件路径。

**Files**:
- Create: `packages/core/src/edera_core/resolver.py`
- Test: `packages/core/tests/test_resolver.py`

**Requirements**:
- 实现 `DatabaseHandlerResolver` 类，接收数据库 session
- 实现 `get(handler_name)` 方法，查询 `installed_extensions` 表
- 解析 `manifest_snapshot.handlers` JSON 字段，匹配 handler name
- 计算 handler 文件路径：`handlers_dir / extension_name / handler_entry`
- Handler 不存在时抛出 `HandlerNotFoundError`

#### Checks

- [x] C1 验证查询已安装扩展的 handler
  - Verifies: `specs/database-handler-resolver/spec.md` / Requirement "从数据库查询 handler 元数据" / Scenario "查询已安装扩展的 handler"
  - Command: `pytest packages/core/tests/test_resolver.py::test_get_handler_from_installed_extension -v`
  - Expect: 测试通过，返回正确的 `HandlerMeta(path, function)`

- [x] C2 验证 handler 不存在抛出异常
  - Verifies: `specs/database-handler-resolver/spec.md` / Requirement "从数据库查询 handler 元数据" / Scenario "Handler 不存在"
  - Command: `pytest packages/core/tests/test_resolver.py::test_handler_not_found -v`
  - Expect: 测试通过，抛出 `HandlerNotFoundError`

- [x] C3 验证计算标准 handler 路径
  - Verifies: `specs/database-handler-resolver/spec.md` / Requirement "计算 handler 文件路径" / Scenario "计算标准 handler 路径"
  - Command: `pytest packages/core/tests/test_resolver.py::test_compute_handler_path -v`
  - Expect: 测试通过，路径为 `handlers_dir / extension_name / handler_entry`

- [x] C4 验证使用默认 function name
  - Verifies: `specs/database-handler-resolver/spec.md` / Requirement "提取 handler function name" / Scenario "使用默认 function"
  - Command: `pytest packages/core/tests/test_resolver.py::test_default_function_name -v`
  - Expect: 测试通过，返回 function name "run"

### Task 2: 实现 DagExecutionSnapshot

**Goal**: 创建 `DagExecutionSnapshot` 类，在 DAG 启动时创建配置快照。

**Files**:
- Create: `packages/core/src/edera_core/snapshot.py`
- Test: `packages/core/tests/test_snapshot.py`

**Requirements**:
- 实现 `DagExecutionSnapshot` frozen dataclass
- 包含字段：`dag_config`, `node_configs`, `entity_types`, `handler_resolver`
- `entity_types` 是 `AppConfig.entity_types` 的浅拷贝
- 快照不可变（frozen）

#### Checks

- [x] C5 验证构建完整快照
  - Verifies: `specs/dag-execution-snapshot/spec.md` / Requirement "创建 DAG 执行快照" / Scenario "构建完整快照"
  - Command: `pytest packages/core/tests/test_snapshot.py::test_create_snapshot -v`
  - Expect: 测试通过，快照包含所有必需字段

- [x] C6 验证快照包含 handler resolver
  - Verifies: `specs/dag-execution-snapshot/spec.md` / Requirement "快照包含 handler resolver" / Scenario "Resolver 在快照中"
  - Command: `pytest packages/core/tests/test_snapshot.py::test_snapshot_has_resolver -v`
  - Expect: 测试通过，`snapshot.handler_resolver` 是 `DatabaseHandlerResolver` 实例

- [x] C7 验证快照复制 entity types
  - Verifies: `specs/dag-execution-snapshot/spec.md` / Requirement "快照包含 entity types 副本" / Scenario "复制 entity types"
  - Command: `pytest packages/core/tests/test_snapshot.py::test_snapshot_copies_entity_types -v`
  - Expect: 测试通过，快照的 `entity_types` 是独立副本

- [x] C8 验证快照不可变
  - Verifies: `specs/dag-execution-snapshot/spec.md` / Requirement "快照不可变" / Scenario "快照字段不可修改"
  - Command: `pytest packages/core/tests/test_snapshot.py::test_snapshot_immutable -v`
  - Expect: 测试通过，修改快照字段抛出 `FrozenInstanceError`

### Task 3: 重构 NodeExecutor 使用快照

**Goal**: 修改 `NodeExecutor` 接收 `DagExecutionSnapshot`，移除 `handler_registry` 参数。

**Files**:
- Modify: `packages/core/src/edera_core/node/executor.py`
- Test: `packages/core/tests/test_node_executor.py`

**Requirements**:
- 添加 `snapshot: DagExecutionSnapshot` 构造参数
- 移除 `handler_registry` 参数
- `_load_handler()` 改为调用 `snapshot.handler_resolver.get(name)`
- 保持 `_modules` 缓存机制不变

#### Checks

- [x] C9 验证使用快照构造 executor
  - Verifies: `specs/dag-execution-snapshot/spec.md` / Requirement "NodeExecutor 接收快照" / Scenario "使用快照构造"
  - Command: `pytest packages/core/tests/test_node_executor.py::test_executor_with_snapshot -v`
  - Expect: 测试通过，executor 接收快照参数

- [x] C10 验证从快照获取 resolver
  - Verifies: `specs/dag-execution-snapshot/spec.md` / Requirement "NodeExecutor 接收快照" / Scenario "从快照获取 resolver"
  - Command: `pytest packages/core/tests/test_node_executor.py::test_load_handler_from_snapshot -v`
  - Expect: 测试通过，使用 `snapshot.handler_resolver` 查询 handler

- [x] C11 验证加载扩展 handler
  - Verifies: `specs/node-executor/spec.md` / Requirement "Skill 加载" / Scenario "加载扩展 handler"
  - Command: `pytest packages/core/tests/test_node_executor.py::test_load_handler_from_database -v`
  - Expect: 测试通过，通过 resolver 查询元数据并加载 module

- [x] C12 验证模块缓存
  - Verifies: `specs/node-executor/spec.md` / Requirement "Dynamic handler loading" / Scenario "模块缓存"
  - Command: `pytest packages/core/tests/test_node_executor.py::test_module_cache -v`
  - Expect: 测试通过，同一 handler 第二次执行不查询 resolver

### Task 4: 修改 DagController 构建快照

**Goal**: 修改 `DagController` 在创建 DAG 执行时构建 `DagExecutionSnapshot`。

**Files**:
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Test: `packages/core/tests/test_dag_controller.py`

**Requirements**:
- 创建 DAG 执行时构建 `DagExecutionSnapshot`
- 快照包含 `dag_config`, `node_configs`, `entity_types` 副本, `handler_resolver`
- 传递快照给 `NodeExecutor` 而非 `handler_registry`

#### Checks

- [x] C13 验证构建快照传递给 executor
  - Verifies: `specs/dag-execution-snapshot/spec.md` / Requirement "创建 DAG 执行快照" / Scenario "构建完整快照"
  - Command: `pytest packages/core/tests/test_dag_controller.py::test_create_snapshot_for_dag_execution -v`
  - Expect: 测试通过，DagController 构建快照并传递给 NodeExecutor

- [x] C14 验证快照独立于后续变更
  - Verifies: `specs/dag-execution-snapshot/spec.md` / Requirement "创建 DAG 执行快照" / Scenario "快照独立于后续变更"
  - Command: `pytest packages/core/tests/test_dag_controller.py::test_snapshot_isolation -v`
  - Expect: 测试通过，DAG 启动后数据库变更不影响快照

### Task 5: 修改 bootstrap 不再构建 Registry

**Goal**: 修改 `bootstrap.py` 的 `load_installed_extensions()`，不再构建 `HandlerRegistry` 和 `EntityTypeRegistry`。

**Files**:
- Modify: `packages/core/src/edera_core/bootstrap.py`
- Test: `packages/core/tests/test_bootstrap.py`

**Requirements**:
- `load_installed_extensions()` 返回扩展列表，不构建 Registry
- `BootstrapResult` 移除 `handler_registry` 和 `entity_type_registry` 字段
- Manifest 数据存储在 `manifest_snapshot` 字段

#### Checks

- [x] C15 验证 bootstrap 不构建 Registry
  - Verifies: `specs/extension-manifest-system/spec.md` / Requirement "Manifest 文件解析" / Scenario "解析完整 manifest"
  - Command: `pytest packages/core/tests/test_bootstrap.py::test_load_without_registry -v`
  - Expect: 测试通过，`load_installed_extensions()` 不返回 Registry

- [x] C16 验证 manifest 存储在数据库
  - Verifies: `specs/extension-manifest-system/spec.md` / Requirement "Manifest 文件解析" / Scenario "解析完整 manifest"
  - Command: `pytest packages/core/tests/test_bootstrap.py::test_manifest_in_database -v`
  - Expect: 测试通过，manifest 完整内容存储在 `installed_extensions.manifest_snapshot`

### Task 6: 实现 ReloadEntityTypes RPC

**Goal**: 实现 gRPC `ReloadEntityTypes` RPC，从数据库重新加载 entity type 配置。

**Files**:
- Modify: `proto/edera.proto`
- Modify: `packages/core/src/edera_core/grpc_config_service.py`
- Test: `packages/core/tests/test_grpc_config_service.py`

**Requirements**:
- 在 `proto/edera.proto` 添加 `ReloadEntityTypes` RPC 定义
- 实现 RPC handler，查询 `entity_types` 表
- 替换 `AppConfig.entity_types` 字典内容
- 记录 reload 日志

#### Checks

- [x] C17 验证调用 reload API
  - Verifies: `specs/runtime-entity-type-reload/spec.md` / Requirement "提供 reload entity types API" / Scenario "调用 reload API"
  - Command: `pytest packages/core/tests/test_grpc_config_service.py::test_reload_entity_types -v`
  - Expect: 测试通过，RPC 返回成功响应

- [x] C18 验证 reload 后新 DAG 使用新配置
  - Verifies: `specs/runtime-entity-type-reload/spec.md` / Requirement "提供 reload entity types API" / Scenario "Reload 后新 DAG 使用新配置"
  - Command: `pytest packages/core/tests/test_grpc_config_service.py::test_reload_affects_new_dag -v`
  - Expect: 测试通过，reload 后启动的 DAG 使用新 schema

- [x] C19 验证运行中的 DAG 隔离
  - Verifies: `specs/runtime-entity-type-reload/spec.md` / Requirement "Reload 不影响正在运行的 DAG" / Scenario "运行中的 DAG 隔离"
  - Command: `pytest packages/core/tests/test_grpc_config_service.py::test_reload_isolation -v`
  - Expect: 测试通过，reload 不影响正在运行的 DAG

### Task 7: 修改 graph_service 查询数据库

**Goal**: 修改 `graph_service.py` 的 `ListHandlers` 等方法，改为查询数据库而非 Registry。

**Files**:
- Modify: `packages/core/src/edera_core/graph_service.py`
- Test: `packages/core/tests/test_graph_service.py`

**Requirements**:
- `ListHandlers` 查询 `installed_extensions` 表
- 解析 `manifest_snapshot.handlers` 返回 handler 列表
- 移除对 `handler_registry` 的访问

#### Checks

- [x] C20 验证 ListHandlers 查询数据库
  - Verifies: `specs/database-handler-resolver/spec.md` / Requirement "从数据库查询 handler 元数据" / Scenario "查询已安装扩展的 handler"
  - Command: `pytest packages/core/tests/test_graph_service.py::test_list_handlers_from_database -v`
  - Expect: 测试通过，返回所有已安装扩展的 handler 列表

### Task 8: 移除 Registry 类

**Goal**: 移除 `registry.py` 中的 `HandlerRegistry` 和 `EntityTypeRegistry` 类。

**Files**:
- Modify: `packages/core/src/edera_core/registry.py`

**Requirements**:
- 删除 `HandlerRegistry` 类定义
- 删除 `EntityTypeRegistry` 类定义
- 删除 `HandlerEntry` 类（如果不再使用）

#### Checks

- [x] C21 验证 Registry 类已移除
  - Verifies: `specs/extension-manifest-system/spec.md` / Requirement "Manifest 文件解析" / Scenario "解析完整 manifest"
  - Evidence: `packages/core/src/edera_core/registry.py`
  - Expect: 文件不包含 `class HandlerRegistry` 和 `class EntityTypeRegistry`

- [x] C22 验证没有导入 Registry 的代码
  - Verifies: `specs/extension-manifest-system/spec.md` / Requirement "Manifest 文件解析" / Scenario "解析完整 manifest"
  - Command: `grep -r "from edera_core.registry import.*Registry" packages/core/src --include="*.py"`
  - Expect: 无结果，所有 Registry 导入已移除

### Task 9: 更新 Engine 和 hot_reload

**Goal**: 修改 `engine.py` 和 `hot_reload.py`，移除对 Registry 的使用。

**Files**:
- Modify: `packages/core/src/edera_core/engine.py`
- Modify: `packages/core/src/edera_core/hot_reload.py`
- Test: `packages/core/tests/test_engine.py`
- Test: `packages/core/tests/test_hot_reload.py`

**Requirements**:
- `Engine` 不再初始化空 Registry
- `hot_reload` 不再更新 `entity_type_registry`
- 使用数据库查询替代 Registry 访问

#### Checks

- [x] C23 验证 Engine 不使用 Registry
  - Verifies: `specs/extension-manifest-system/spec.md` / Requirement "Manifest 文件解析" / Scenario "解析完整 manifest"
  - Command: `pytest packages/core/tests/test_engine.py::test_engine_without_registry -v`
  - Expect: 测试通过，Engine 不依赖 Registry

- [x] C24 验证 hot reload 不更新 Registry
  - Verifies: `specs/extension-manifest-system/spec.md` / Requirement "Manifest 文件解析" / Scenario "解析完整 manifest"
  - Command: `pytest packages/core/tests/test_hot_reload.py::test_hot_reload_without_registry -v`
  - Expect: 测试通过，hot reload 不访问 Registry

### Task 10: 更新所有测试

**Goal**: 更新所有使用 `HandlerRegistry` 的测试，改为使用 database fixture 和 `DagExecutionSnapshot`。

**Files**:
- Modify: `packages/core/tests/test_*.py`
- Create: `packages/core/tests/fixtures/snapshot_fixtures.py`

**Requirements**:
- 创建测试辅助函数 `create_test_snapshot()`
- 创建 `mock_handler_resolver()` fixture
- 更新所有测试使用新 fixture

#### Checks

- [x] C25 验证所有测试通过
  - Verifies: `specs/node-executor/spec.md` / Requirement "接收执行快照" / Scenario "使用快照构造 executor"
  - Command: `pytest packages/core/tests/ -v`
  - Expect: 所有测试通过，无失败或跳过

- [x] C26 验证测试覆盖率
  - Verifies: `specs/database-handler-resolver/spec.md` / Requirement "从数据库查询 handler 元数据" / Scenario "查询已安装扩展的 handler"
  - Command: `pytest packages/core/tests/ --cov=edera_core --cov-report=term`
  - Expect: resolver.py 和 snapshot.py 覆盖率 >= 80%
