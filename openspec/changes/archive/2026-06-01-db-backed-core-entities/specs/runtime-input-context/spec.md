## MODIFIED Requirements

### Requirement: Runtime facts storage model
系统 SHALL 使用具体 runtime tables 存储已提交运行事实，并通过 Entity API/CLI 将这些运行事实投影为 runtime entities。运行中调度状态 SHALL 以内存 runtime snapshot 和 runner state 为准。系统 MUST NOT 将 `edge_inputs` 或 `source_recoveries` 存入 `node_outputs`。

#### Scenario: Project runtime facts as entities
- **WHEN** 用户通过 API 或 CLI 查询某个 run 的 runtime facts
- **THEN** 系统 SHALL 将底层 `dag_runs`、`node_runs`、`edge_inputs` 和 `source_recoveries` 行投影为 runtime entities

#### Scenario: Keep business outputs separate
- **WHEN** 节点产出业务 payload
- **THEN** 系统 SHALL 继续将业务输出写入 `node_outputs`，并 MUST NOT 将 runtime facts 混入业务输出表

#### Scenario: Active runtime state stays in memory
- **WHEN** DAG runner 正在调度节点、聚合 payload 或判断 edge 状态
- **THEN** 系统 SHALL 使用内存中的 runtime state 和 committed snapshot 作决策
- **AND** runtime tables SHALL 只作为提交事实和查询投影来源
