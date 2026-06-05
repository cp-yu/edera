---
capabilities:
  - cap.core.grpc-graph-service
---
# grpc-graph-service Specification

## MODIFIED Requirements

### Requirement: GraphService DAG CRUD
`edera-server` SHALL 通过 `GraphService` 提供 DB-backed DAG Entity 的完整 CRUD 操作。所有验证逻辑（DAG name 格式、node 引用存在性、edge 合法性、entity permission 校验、sub-DAG nesting 校验）SHALL 在 server 端执行。DAG graph payload 的 GET、SAVE 和 SAVE response SHALL 保留 `DagNodeInstance.optional`、`DagNodeInstance.dag_ref`、`DagNodeInstance.input_mapping` 与 `DagEdge.optional`。

#### Scenario: 列出所有 DAG
- **WHEN** 客户端调用 `GraphService.ListDags`
- **THEN** server SHALL 返回 DB-backed DAG Entity 表中所有 DAG 名称列表

#### Scenario: 获取 DAG 详情
- **WHEN** 客户端调用 `GraphService.GetDag(name="uzi-skill")`
- **THEN** server SHALL 返回该 DAG 的完整状态（nodes with inspector_schema、edges、ui、entity_types、entities、entity_relations）序列化为 JSON string
- **AND** node instance payload SHALL 保留 `optional`
- **AND** sub-DAG node instance payload SHALL 保留 `dag_ref` 与 `input_mapping`
- **AND** edge payload SHALL 保留 `optional`

#### Scenario: DAG 不存在
- **WHEN** 客户端调用 `GraphService.GetDag(name="nonexistent")`
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误

#### Scenario: 创建 DAG
- **WHEN** 客户端调用 `GraphService.CreateDag(name="new-dag")`
- **THEN** server SHALL 验证 name 为 kebab-case，创建空 DAG Entity，返回创建结果

#### Scenario: 创建重复 DAG
- **WHEN** 客户端调用 `GraphService.CreateDag` 且同名 DAG 已存在
- **THEN** server SHALL 返回 gRPC ALREADY_EXISTS 错误

#### Scenario: 保存 DAG
- **WHEN** 客户端调用 `GraphService.SaveDag(name, json)` 携带合法 DAG payload
- **THEN** server SHALL 验证 DagConfig schema、entity_permissions 和 sub-DAG nesting，原子写入 DB-backed DAG Entity，返回保存后的 DAG 状态
- **AND** 保存后的 DAG 状态 SHALL 保留 `DagNodeInstance.optional`、`DagNodeInstance.dag_ref`、`DagNodeInstance.input_mapping` 与 `DagEdge.optional`

#### Scenario: 保存非法 DAG
- **WHEN** 客户端调用 `GraphService.SaveDag` 携带引用不存在 node type 的 payload
- **THEN** server SHALL 返回 gRPC INVALID_ARGUMENT 错误，包含验证失败详情

#### Scenario: 保存 sub-DAG 自引用 DAG
- **WHEN** 客户端调用 `GraphService.SaveDag(name="demo")` 且 payload 中包含 `type: "dag", dag_ref: "demo"` 的节点实例 'sub-1'
- **THEN** server SHALL 在写入 DB-backed DAG Entity 前返回 gRPC INVALID_ARGUMENT 错误，错误详情 MUST 包含：
  - 完整的循环路径，显示 DAG 名称和触发循环的节点实例 ID
  - 问题说明："Sub DAG 引用形成了循环"
  - 修复建议：列出可以移除或修改的节点实例
- **AND** server SHALL 保持原 DAG Entity 内容不变

#### Scenario: optional round-trip
- **WHEN** 客户端读取 DAG 后不修改 optional 字段并保存
- **THEN** server SHALL 在配置文件和保存响应中保留原有 node instance optional 与 edge optional 值

#### Scenario: sub-DAG instance round-trip
- **WHEN** 客户端读取包含 `dag_ref: "common-subdag"` 与 `input_mapping` 的 DAG 后不修改这些字段并保存
- **THEN** server SHALL 在保存后的 DAG 状态中保留原有 `dag_ref` 与 `input_mapping`
