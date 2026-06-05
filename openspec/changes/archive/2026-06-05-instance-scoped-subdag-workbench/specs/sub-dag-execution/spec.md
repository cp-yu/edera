## ADDED Requirements

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
