## ADDED Requirements

### Requirement: Instance-scoped sub-DAG runtime view
Workbench Runtime 视图 SHALL 在 sub-DAG 实例视图中按 child `run_id` 展示内部节点状态。系统 MUST NOT 仅按 `dag_name` 或最近一次同名 DAG run 展示 sub-DAG 内部状态。

#### Scenario: Show child run node statuses
- **WHEN** 用户从 `dagA.nodeX` 进入 `common-subdag`
- **AND** `nodeX` 的运行记录包含 `sub_dag_run_id = child-1`
- **THEN** `common-subdag` Canvas SHALL 使用 `child-1` 的 node runs 渲染内部节点状态

#### Scenario: Do not leak sibling parent status
- **WHEN** `dagA.nodeX` 和 `dagB.nodeY` 同时引用 `common-subdag`
- **AND** `dagA.nodeX` 对应 child run 为 `child-a`
- **AND** `dagB.nodeY` 对应 child run 为 `child-b`
- **THEN** 用户从 `dagA.nodeX` 进入 sub-DAG 时 MUST 只看到 `child-a` 的内部节点状态
- **AND** MUST NOT 显示 `child-b` 的内部节点状态

#### Scenario: No child run yet
- **WHEN** 用户进入尚未执行过的 sub-DAG 节点实例
- **THEN** Runtime 视图 SHALL 展示无 child run 的空态
- **AND** MUST NOT fallback 到同名 DAG 的最近一次 run
