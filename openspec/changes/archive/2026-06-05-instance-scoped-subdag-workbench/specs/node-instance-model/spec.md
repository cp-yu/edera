## ADDED Requirements

### Requirement: Sub-DAG instance fields
DAG YAML 实例对象 SHALL 支持 sub-DAG 节点所需的 `dag_ref` 和 `input_mapping` 字段。多个实例 MAY 引用同一个 `dag_ref`，但每个实例仍 MUST 使用独立 `id`。

#### Scenario: Save sub-DAG instance fields
- **WHEN** 系统保存 sub-DAG 节点实例
- **THEN** DAG YAML SHALL 将该实例序列化为包含 `id`、`type: "dag"`、`dag_ref`、`input_mapping`、`alias` 和 `config` 的对象

#### Scenario: Multiple sub-DAG instances share target
- **WHEN** 用户在同一 DAG 中创建两个引用 `common-subdag` 的 sub-DAG 节点实例
- **THEN** 系统 SHALL 为两个实例保存不同的 `id`
- **AND** 两个实例 MAY 保存相同的 `dag_ref`

#### Scenario: Preserve sub-DAG instance fields in draft save
- **WHEN** Workbench 自动保存包含 sub-DAG 节点实例的 DAG 草稿
- **THEN** 保存 payload SHALL 保留该实例的 `dag_ref` 与 `input_mapping`
