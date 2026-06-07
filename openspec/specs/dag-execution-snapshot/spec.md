---
capabilities:
  - cap.core.dag-execution-snapshot
---
# dag-execution-snapshot Specification

## Purpose
定义 DAG run 启动时创建不可变执行快照，以隔离运行期 DAG 配置、node 配置、entity type 副本和 handler resolver 的能力。
## Requirements
### Requirement: 创建 DAG 执行快照
系统 SHALL 在 DAG 启动时创建 `DagExecutionSnapshot`，包含该 DAG 执行所需的所有配置。`DagExecutionSnapshot` SHALL 包含 `DAG execution closure`，该闭包 MUST 由 root DAG、reachable sub-DAGs 和 referenced node types 组成。系统 MUST NOT 将系统内所有 DAG 或 Node type 放入单次执行快照。

#### Scenario: 构建闭包快照
- **WHEN** DagController 启动 DAG "my-dag"
- **THEN** 创建 `DagExecutionSnapshot` 包含：
  - `dag_closure`: root DAG、reachable sub-DAGs 和 referenced node types
  - `entity_types`: Entity type 配置字典（副本）
  - `handler_resolver`: `DatabaseHandlerResolver` 实例
  - `extension_table_names`: extension storage table mapping 副本
  - `skills`: 本次 run 所需 Skill 配置副本

#### Scenario: 快照独立于后续变更
- **WHEN** 创建快照后数据库中安装了新 extension 或修改了 DAG/Node/EntityType/Skill
- **THEN** 快照中的配置不变
- **THEN** 新 DAG 执行使用新快照，自动包含 DB 中已提交的新配置

#### Scenario: 快照不包含无关 DAG
- **WHEN** DagController 启动 DAG "dag-a"，且系统中存在不被 "dag-a" 引用的 DAG "dag-b"
- **THEN** `DagExecutionSnapshot.dag_closure` MUST NOT 包含 "dag-b"

### Requirement: 快照包含 handler resolver
快照 SHALL 包含 `DatabaseHandlerResolver` 实例，用于 handler 元数据查询。该 resolver MUST 在 run start 时冻结已启用 extension 的 handler metadata。

#### Scenario: Resolver 在快照中
- **WHEN** 创建快照时传入数据库 session
- **THEN** 快照内部创建 `DatabaseHandlerResolver.snapshot(session)`
- **THEN** NodeExecutor 通过快照访问 resolver

### Requirement: 快照包含 entity types 副本
快照 SHALL 从 DB-backed `entity_types` 元数据复制 EntityType 配置字典，保证运行期间不受后续 DB 变更影响。

#### Scenario: 复制 entity types
- **WHEN** 创建快照时 DB 中有 3 个 entity type
- **THEN** 快照内部存储这 3 个 entity type 的副本

#### Scenario: EntityType 变更不影响快照
- **WHEN** DAG 启动后 DB 中 EntityType 元数据被修改
- **THEN** 正在运行的 DAG 使用快照中的旧 EntityType 配置

### Requirement: 快照不可变
`DagExecutionSnapshot` SHALL 设计为不可变对象（frozen dataclass 或类似）。

#### Scenario: 快照字段不可修改
- **WHEN** 尝试修改快照的 `entity_types` 字段
- **THEN** 抛出 `FrozenInstanceError` 或类似异常

### Requirement: NodeExecutor 接收快照
`NodeExecutor` SHALL 接收 `DagExecutionSnapshot` 作为构造参数，不再接收 `handler_registry` 或从 `RuntimeControlSnapshot` 读取执行配置。

#### Scenario: 使用快照构造
- **WHEN** 创建 `NodeExecutor(snapshot=snapshot, ...)`
- **THEN** executor 内部保存快照引用

#### Scenario: 从快照获取 resolver
- **WHEN** executor 需要加载 handler
- **THEN** 从 `self.snapshot.handler_resolver` 获取 resolver
- **THEN** 调用 `resolver.get(handler_name)` 查询元数据

#### Scenario: 从快照获取 extension table mapping
- **WHEN** handler 调用 `ctx.storage.table("items")`
- **THEN** NodeExecutor SHALL 使用 `DagExecutionSnapshot.extension_table_names` 解析真实表名

### Requirement: DAG execution closure 构建
系统 SHALL 由 `DagController` 在 run start 构建 `DAG execution closure`。该构建 MUST 从 root DAG 开始递归解析 reachable sub-DAGs，收集所有 referenced node types，并在执行开始前完成。

#### Scenario: 包含 reachable sub-DAG
- **WHEN** root DAG 包含 `type: "dag", dag_ref: "child"` 的节点
- **THEN** `DAG execution closure` SHALL 包含 root DAG、child DAG 和两个 DAG 引用的所有 node types

#### Scenario: 缺失 node type 阻断启动
- **WHEN** root DAG 或 reachable sub-DAG 引用不存在的 node type
- **THEN** DagController SHALL 在创建 `DagExecutionSnapshot` 前拒绝启动 run

#### Scenario: 闭包检测 sub-DAG 循环
- **WHEN** root DAG reachable sub-DAG 链形成循环
- **THEN** DagController SHALL 拒绝创建 `DagExecutionSnapshot` 并返回循环路径错误

