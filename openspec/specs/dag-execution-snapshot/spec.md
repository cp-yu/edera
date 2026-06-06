---
capabilities:
  - cap.core.dag-execution-snapshot
---
# dag-execution-snapshot Specification

## Purpose
定义 DAG run 启动时创建不可变执行快照，以隔离运行期 DAG 配置、node 配置、entity type 副本和 handler resolver 的能力。
## Requirements
### Requirement: 创建 DAG 执行快照
系统 SHALL 在 DAG 启动时创建 `DagExecutionSnapshot`，包含该 DAG 执行所需的所有配置。

#### Scenario: 构建完整快照
- **WHEN** DagController 启动 DAG "my-dag"
- **THEN** 创建 `DagExecutionSnapshot` 包含：
  - `dag_config`: DAG 配置对象
  - `node_configs`: Node 配置字典
  - `entity_types`: Entity type 配置字典（副本）
  - `handler_resolver`: `DatabaseHandlerResolver` 实例

#### Scenario: 快照独立于后续变更
- **WHEN** 创建快照后数据库中安装了新 extension
- **THEN** 快照中的配置不变
- **THEN** 新 DAG 执行使用新快照，自动包含新 extension

### Requirement: 快照包含 handler resolver
快照 SHALL 包含 `DatabaseHandlerResolver` 实例，用于 handler 元数据查询。

#### Scenario: Resolver 在快照中
- **WHEN** 创建快照时传入数据库 session
- **THEN** 快照内部创建 `DatabaseHandlerResolver(session)`
- **THEN** NodeExecutor 通过快照访问 resolver

### Requirement: 快照包含 entity types 副本
快照 SHALL 复制 `AppConfig.entity_types` 字典，保证运行期间不受外部 reload 影响。

#### Scenario: 复制 entity types
- **WHEN** 创建快照时 `AppConfig.entity_types` 有 3 个 entity type
- **THEN** 快照内部存储这 3 个 entity type 的副本（shallow copy）

#### Scenario: Reload 不影响快照
- **WHEN** DAG 启动后调用 entity type reload API
- **THEN** `AppConfig.entity_types` 更新
- **THEN** 正在运行的 DAG 使用快照中的旧配置

### Requirement: 快照不可变
`DagExecutionSnapshot` SHALL 设计为不可变对象（frozen dataclass 或类似）。

#### Scenario: 快照字段不可修改
- **WHEN** 尝试修改快照的 `entity_types` 字段
- **THEN** 抛出 `FrozenInstanceError` 或类似异常

### Requirement: NodeExecutor 接收快照
`NodeExecutor` SHALL 接收 `DagExecutionSnapshot` 作为构造参数，不再接收 `handler_registry`。

#### Scenario: 使用快照构造
- **WHEN** 创建 `NodeExecutor(snapshot=snapshot, ...)`
- **THEN** executor 内部保存快照引用

#### Scenario: 从快照获取 resolver
- **WHEN** executor 需要加载 handler
- **THEN** 从 `self.snapshot.handler_resolver` 获取 resolver
- **THEN** 调用 `resolver.get(handler_name)` 查询元数据
