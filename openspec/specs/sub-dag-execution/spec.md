# sub-dag-execution Specification

## Purpose
此规约记录变更 everything-is-entity 引入的行为，请在后续同步或归档前补全正式 Purpose。
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

