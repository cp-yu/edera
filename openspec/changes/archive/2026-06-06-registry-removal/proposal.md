<!-- smart-routing: design-summary-found, input-length=27, decision=proceed -->

## Why

当前系统在启动时从数据库加载扩展元数据后，构建静态的 HandlerRegistry 和 EntityTypeRegistry 作为内存快照。这些 Registry 一旦 sealed/immutable 后无法修改，导致运行时无法动态安装、卸载或更新扩展，必须重启整个系统才能生效。数据库已经是配置元数据的权威源，Registry 层造成了信息冗余和架构僵化。需要移除 Registry 层，改为按需从数据库查询，实现真正的运行时动态扩展管理。

## What Changes

- **BREAKING**: 移除 `HandlerRegistry` 和 `EntityTypeRegistry` 类及其静态构建逻辑
- **BREAKING**: `NodeExecutor` 不再接收 `handler_registry` 参数，改为接收 `DagExecutionSnapshot`
- 新增 `DatabaseHandlerResolver` 类，按需从 `installed_extensions.manifest_snapshot` 查询 handler 元数据
- 新增 `DagExecutionSnapshot` 类，在 DAG 启动时创建配置快照，包含 handler resolver 和 entity types
- `AppConfig.entity_types` 从启动时只读改为支持运行时 reload
- 新增 entity type reload API：`POST /admin/reload-entity-types`
- `DagController` 在创建 DAG 执行时构建快照而非传递 bootstrap
- `bootstrap.py` 的 `load_installed_extensions()` 不再构建 Registry，仅返回扩展元数据
- Module 缓存机制（`NodeExecutor._modules`）保持不变，每个 handler 仍只加载一次
- Extension 安装/卸载后无需重启，下次 DAG 执行自动使用最新配置

## Capabilities

### New Capabilities
- `database-handler-resolver`: 从数据库按需查询 handler 元数据，计算 handler 文件路径
- `dag-execution-snapshot`: DAG 执行时的配置快照隔离机制，保证运行一致性
- `runtime-entity-type-reload`: 运行时刷新 entity type 配置的 API

### Modified Capabilities
- `extension-manifest-system`: bootstrap 流程不再构建 HandlerRegistry 和 EntityTypeRegistry，改为提供查询接口
- `node-executor`: 移除对 HandlerRegistry 的依赖，改为使用 DagExecutionSnapshot 中的 handler resolver

## Impact

- `packages/core/src/edera_core/registry.py`: 移除 `HandlerRegistry` 和 `EntityTypeRegistry` 类
- `packages/core/src/edera_core/bootstrap.py`: `load_installed_extensions()` 不再构建 Registry
- `packages/core/src/edera_core/node/executor.py`: 重构 `_load_handler()` 使用 database resolver
- `packages/core/src/edera_core/dag_controller.py`: 创建 DAG 执行时构建 `DagExecutionSnapshot`
- `packages/core/src/edera_core/engine.py`: 移除空 Registry 初始化
- `packages/core/src/edera_core/graph_service.py`: `ListHandlers` 等方法改为查询数据库
- `packages/core/src/edera_core/hot_reload.py`: 适配无 Registry 的热重载流程
- `packages/core/src/edera_core/config/loader.py`: 适配无 EntityTypeRegistry 的配置加载
- `proto/edera.proto`: 新增 entity type reload RPC
- 所有使用 `HandlerRegistry` 的测试需要重写，使用 database fixture
