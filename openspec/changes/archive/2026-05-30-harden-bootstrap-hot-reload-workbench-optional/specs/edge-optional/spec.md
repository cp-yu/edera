## MODIFIED Requirements

### Requirement: 节点级 Optional 语法糖
`DagNodeInstance` 和 `NodeConfig` SHALL 支持 `optional` 布尔字段（默认 false）。节点级 optional 不是独立执行语义；它 SHALL 在构图阶段作为 edge optional 的语法糖展开：`DagNodeInstance.optional` 等价于当前 DAG 中该节点实例的所有出边均标记为 optional，`NodeConfig.optional` 等价于该 node type 的所有实例出边均标记为 optional。实际执行判定 SHALL 只使用 effective edge optional。

#### Scenario: 节点实例 optional 展开为出边 optional
- **WHEN** 当前 DAG 中节点实例 A 配置 `optional: true`，且有出边 A→B 和 A→C
- **THEN** 系统 SHALL 将两条边均视为 `optional: true`

#### Scenario: 节点类型 optional 展开为出边 optional
- **WHEN** 节点类型 T 配置 `optional: true`，且实例 A 的 type 为 T
- **THEN** 系统 SHALL 将 A 的所有出边均视为 `optional: true`

#### Scenario: effective edge optional 判定
- **WHEN** 存在边 A→B
- **THEN** 系统 SHALL 使用 `DagEdge(A,B).optional OR DagNodeInstance(A).optional OR NodeConfig(type_of_A).optional` 计算该边的 effective optional

#### Scenario: 节点 optional 不创建第二套运行语义
- **WHEN** 节点实例或节点类型声明 `optional: true`
- **THEN** Executor SHALL 按 effective edge optional 处理该节点的出边
- **AND** SHALL NOT 引入独立的 node optional 调度规则

