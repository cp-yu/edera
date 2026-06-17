---
capabilities:
  - cap.core.sub-dag-execution
---
# sub-dag-execution Specification

## Purpose
定义 子 DAG 作为 Node 执行、子 DAG 错误传播、递归深度限制、Dag 节点类型支持等能力。
## Requirements
### Requirement: 子 DAG 作为 Node 执行

系统 SHALL 支持将 DAG Entity 作为 Node 嵌套在父 DAG 中执行。子 DAG 对父 DAG MUST 表现为黑盒 Node。

#### Scenario: 子 DAG 正常执行

- **WHEN** 父 DAG 中一个节点引用了另一个 DAG Entity
- **THEN** DAG Runner 递归执行子 DAG，将父节点的输入传给子 DAG 的 source 节点，子 DAG sink 节点的输出作为父节点的输出返回

#### Scenario: 子 DAG input/output 映射

- **WHEN** 子 DAG 有 2 个 source 节点和 1 个 sink 节点
- **THEN** 父节点的输入传给所有 source 节点，sink 节点的输出作为父节点的唯一输出

### Requirement: 子 DAG 错误传播

子 DAG 内部失败时，MUST 向父 DAG 报告聚合后的错误状态，MUST NOT 暴露内部拓扑细节（debug 模式除外）。

#### Scenario: 子 DAG 内部节点失败（正常模式）

- **WHEN** 子 DAG 内部一个节点执行失败，导致子 DAG 整体无法产出有效输出
- **THEN** 父 DAG 收到该节点的失败状态和聚合错误信息，不包含子 DAG 内部拓扑细节

#### Scenario: 子 DAG 内部节点失败（debug 模式）

- **WHEN** 子 DAG 内部一个节点执行失败，且系统处于 debug 模式
- **THEN** 父 DAG 收到完整的子 DAG 内部执行信息，包含每个内部节点的状态

#### Scenario: 子 DAG 部分成功

- **WHEN** 子 DAG 内部部分节点失败但 sink 节点仍能产出有效输出
- **THEN** 父 DAG 收到成功状态和输出，子 DAG 内部的部分失败记录到 run metadata

### Requirement: 递归深度限制

系统 SHALL 限制子 DAG 嵌套的递归深度，MUST 通过 `system.toml` 的 `max_dag_depth` 配置，默认值为 3。

#### Scenario: 递归深度在限制内

- **WHEN** DAG A 嵌套 DAG B，DAG B 嵌套 DAG C，`max_dag_depth: 3`
- **THEN** 系统正常执行三层嵌套

#### Scenario: 递归深度超限

- **WHEN** DAG 嵌套深度超过 `max_dag_depth` 配置值
- **THEN** 系统拒绝执行并返回明确错误信息，指出超限的 DAG 引用链

#### Scenario: 检测循环嵌套

- **WHEN** DAG A 嵌套 DAG B，DAG B 又嵌套 DAG A
- **THEN** 系统在加载时检测到循环嵌套并拒绝加载，报告循环引用链

### Requirement: Dag 节点类型支持
系统 SHALL 支持 `type: dag` 的节点，该节点引用另一个 DAG 作为子图执行。Dag 节点 SHALL 包含 `dag_ref` 字段（目标 DAG 名称）和 `input_mapping` 字段（输入参数映射）。`input_mapping` SHALL 支持 `dict[str, str]` 或 `str` 类型。

#### Scenario: Dag 节点配置加载
- **WHEN** 节点配置 `type: dag` 且 `dag_ref: target-dag`
- **THEN** 系统 SHALL 将该节点识别为子 DAG 节点

#### Scenario: input_mapping 为 dict 类型
- **WHEN** dag 节点的 `input_mapping` 为 `{symbol: "output.symbol", date: "output.date"}`
- **THEN** 系统 SHALL 使用该 dict 映射父节点输出到子 DAG 的 `sourceSharedInputs`

#### Scenario: input_mapping 为 entity 引用
- **WHEN** dag 节点的 `input_mapping` 为 `"entity://scoring-mapping"`
- **THEN** 系统 SHALL 从 entity store 读取该 InputMapping entity，使用其 `shared`、`nodes`、`append_nodes` 字段生成子 DAG 的输入参数

### Requirement: 子 DAG 递归执行
Executor 执行 dag 节点时，SHALL 递归调用 DagRunner 执行目标 DAG。子 DAG 的执行 SHALL 与父 DAG 的执行隔离，拥有独立的调度状态。

#### Scenario: 递归调用 DagRunner
- **WHEN** executor 执行 dag 节点
- **THEN** 系统 SHALL 创建新的 DagRunner 实例执行目标 DAG

### Requirement: 独立 run_id
子 DAG 执行 SHALL 生成独立的 `run_id`，不复用父 DAG 的 run_id。子 DAG 的执行记录 SHALL 包含 `parent_run_id` 和 `parent_node` 字段关联父级。

#### Scenario: 子 DAG 生成独立 run_id
- **WHEN** dag 节点触发子 DAG 执行
- **THEN** 子 DAG SHALL 生成新的 UUID 作为 run_id

#### Scenario: 父子关联记录
- **WHEN** 子 DAG 执行记录被创建
- **THEN** 记录 SHALL 包含 `parent_run_id`（父 DAG 的 run_id）和 `parent_node`（dag 节点的 instance_id）

### Requirement: Source/Sink 接口映射
子 DAG 的 source 节点 SHALL 作为外部输入接口，sink 节点 SHALL 作为外部输出接口。Dag 节点的上游输出 SHALL 经 `input_mapping` 映射到子 DAG 的 `sourceSharedInputs`，不 SHALL 作为入口 payload 直接传递给所有 source 节点。子 DAG 的 sink 节点输出 SHALL 作为 dag 节点的输出。

#### Scenario: 上游输出映射到子 DAG source
- **WHEN** dag 节点接收上游输出
- **THEN** 该输出 SHALL 通过 `input_mapping` 映射到子 DAG 的 `sourceSharedInputs`，由子 DAG source 节点接收

#### Scenario: 子 DAG sink 输出作为节点输出
- **WHEN** 子 DAG 的 sink 节点执行完成
- **THEN** 其输出 SHALL 作为 dag 节点的输出传递给下游

### Requirement: Parent instance to child run association
子 DAG 作为节点执行时，系统 SHALL 记录可从父 DAG run 和父节点实例解析到 child DAG run 的关联。该关联 MUST 足以区分多个父节点实例引用同一个子 DAG 的并发或历史执行。

#### Scenario: Parent node records child run
- **WHEN** 父 DAG run `parent-1` 中节点实例 `nodeX` 执行 sub-DAG `common-subdag`
- **THEN** `nodeX` 的运行记录或输出 metadata SHALL 包含 child run 标识
- **AND** child run SHALL 对应 `common-subdag` 的独立 `run_id`

#### Scenario: Associations are instance-specific
- **WHEN** `dagA.nodeX` 和 `dagB.nodeY` 都执行 `common-subdag`
- **THEN** 系统 SHALL 能分别解析 `dagA.nodeX` 的 child run 与 `dagB.nodeY` 的 child run
- **AND** 两个解析结果 MUST NOT 因 `dag_ref` 相同而合并

