## ADDED Requirements

### Requirement: Dag 节点类型支持
系统 SHALL 支持 `type: dag` 的节点，该节点引用另一个 DAG 作为子图执行。Dag 节点 SHALL 包含 `dag_ref` 字段（目标 DAG 名称）和 `input_mapping` 字段（输入参数映射）。

#### Scenario: Dag 节点配置加载
- **WHEN** 节点配置 `type: dag` 且 `dag_ref: target-dag`
- **THEN** 系统 SHALL 将该节点识别为子 DAG 节点

### Requirement: 子 DAG 递归执行
Executor 执行 dag 节点时，SHALL 递归调用 DagRunner 执行目标 DAG。子 DAG 的执行 SHALL 与父 DAG 的执行隔离，拥有独立的调度状态。

#### Scenario: 递归调用 DagRunner
- **WHEN** executor 执行 dag 节点
- **THEN** 系统 SHALL 创建新的 DagRunner 实例执行目标 DAG

### Requirement: 独立 Cycle ID
子 DAG 执行 SHALL 生成独立的 `cycle_id`，不复用父 DAG 的 cycle_id。子 DAG 的执行记录 SHALL 包含 `parent_cycle_id` 和 `parent_node` 字段关联父级。

#### Scenario: 子 DAG 生成独立 cycle_id
- **WHEN** dag 节点触发子 DAG 执行
- **THEN** 子 DAG SHALL 生成新的 UUID 作为 cycle_id

#### Scenario: 父子关联记录
- **WHEN** 子 DAG 执行记录被创建
- **THEN** 记录 SHALL 包含 `parent_cycle_id`（父 DAG 的 cycle_id）和 `parent_node`（dag 节点的 instance_id）

### Requirement: Source/Sink 接口映射
子 DAG 的 source 节点 SHALL 作为外部输入接口，sink 节点 SHALL 作为外部输出接口。Dag 节点的上游输出 SHALL 映射到子 DAG 的 source 节点，子 DAG 的 sink 节点输出 SHALL 作为 dag 节点的输出。

#### Scenario: 上游输出映射到子 DAG source
- **WHEN** dag 节点接收上游输出
- **THEN** 该输出 SHALL 通过 `input_mapping` 映射到子 DAG 的 source 节点

#### Scenario: 子 DAG sink 输出作为节点输出
- **WHEN** 子 DAG 的 sink 节点执行完成
- **THEN** 其输出 SHALL 作为 dag 节点的输出传递给下游

## MODIFIED Requirements

### Requirement: 递归深度限制
系统 SHALL 限制子 DAG 的递归深度，默认最大深度为 3 层。超过限制时 SHALL 拒绝执行并返回错误。

#### Scenario: 递归深度超限拒绝
- **WHEN** dag 节点嵌套深度超过配置的最大值
- **THEN** 系统 SHALL 拒绝执行并返回 "max recursion depth exceeded" 错误

### Requirement: 子 DAG 节点历史独立记录
子 DAG 内部每个节点的执行 SHALL 有独立的历史记录，历史查询的颗粒度 SHALL 到 node 级别，而非整个 dag 节点。

#### Scenario: 子 DAG 节点历史可查
- **WHEN** 查询某个 cycle_id 的节点执行历史
- **THEN** 系统 SHALL 返回该 cycle 下所有节点的执行记录，包括子 DAG 内部节点

## MODIFIED Requirements
