---
capabilities:
  - cap.core.grpc-graph-service
---
# grpc-graph-service Specification

## Purpose
此规约记录变更 complete-web-grpc-routes 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: GraphService DAG CRUD
`edera-server` SHALL 通过 `GraphService` 提供 DAG 配置的完整 CRUD 操作。所有验证逻辑（DAG name 格式、node 引用存在性、edge 合法性、entity permission 校验）SHALL 在 server 端执行。DAG graph payload 的 GET、SAVE 和 SAVE response SHALL 保留 `DagNodeInstance.optional` 与 `DagEdge.optional`。

#### Scenario: 列出所有 DAG
- **WHEN** 客户端调用 `GraphService.ListDags`
- **THEN** server SHALL 返回 config/dags/ 目录下所有 DAG 名称列表

#### Scenario: 获取 DAG 详情
- **WHEN** 客户端调用 `GraphService.GetDag(name="uzi-skill")`
- **THEN** server SHALL 返回该 DAG 的完整状态（nodes with inspector_schema、edges、ui、entity_types、entities、entity_relations）序列化为 JSON string
- **AND** node instance payload SHALL 保留 `optional`
- **AND** edge payload SHALL 保留 `optional`

#### Scenario: DAG 不存在
- **WHEN** 客户端调用 `GraphService.GetDag(name="nonexistent")`
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误

#### Scenario: 创建 DAG
- **WHEN** 客户端调用 `GraphService.CreateDag(name="new-dag")`
- **THEN** server SHALL 验证 name 为 kebab-case，创建空 DAG 配置文件，返回创建结果

#### Scenario: 创建重复 DAG
- **WHEN** 客户端调用 `GraphService.CreateDag` 且同名 DAG 已存在
- **THEN** server SHALL 返回 gRPC ALREADY_EXISTS 错误

#### Scenario: 保存 DAG
- **WHEN** 客户端调用 `GraphService.SaveDag(name, json)` 携带合法 DAG payload
- **THEN** server SHALL 验证 DagConfig schema、entity_permissions，原子写入配置文件，返回保存后的 DAG 状态
- **AND** 保存后的 DAG 状态 SHALL 保留 `DagNodeInstance.optional` 与 `DagEdge.optional`

#### Scenario: 保存非法 DAG
- **WHEN** 客户端调用 `GraphService.SaveDag` 携带引用不存在 node type 的 payload
- **THEN** server SHALL 返回 gRPC INVALID_ARGUMENT 错误，包含验证失败详情

#### Scenario: optional round-trip
- **WHEN** 客户端读取 DAG 后不修改 optional 字段并保存
- **THEN** server SHALL 在配置文件和保存响应中保留原有 node instance optional 与 edge optional 值

### Requirement: GraphService Node-type CRUD
`edera-server` SHALL 通过 `GraphService` 提供 Node type 配置的完整 CRUD 操作。

#### Scenario: 获取所有 node type
- **WHEN** 客户端调用 `GraphService.ListNodeTypes`
- **THEN** server SHALL 返回 config/nodes/ 目录下所有 node type 列表（含 inspector_schema）

#### Scenario: 创建 node type
- **WHEN** 客户端调用 `GraphService.CreateNodeType(json)` 携带合法 NodeConfig payload
- **THEN** server SHALL 验证 NodeConfig schema，写入 config/nodes/{name}.yaml，返回创建结果

#### Scenario: 更新 node type
- **WHEN** 客户端调用 `GraphService.SaveNodeType(name, json)`
- **THEN** server SHALL 验证并原子写入 node 配置，同时保存关联的 handler 代码（如有）

#### Scenario: 删除被引用的 node type
- **WHEN** 客户端调用 `GraphService.DeleteNodeType(name)` 且该 type 被某 DAG 引用
- **THEN** server SHALL 返回 gRPC FAILED_PRECONDITION 错误

#### Scenario: 删除未引用的 node type
- **WHEN** 客户端调用 `GraphService.DeleteNodeType(name)` 且该 type 未被引用
- **THEN** server SHALL 删除 node 配置文件和关联的 handler 文件

#### Scenario: 在 DAG 中创建 node instance
- **WHEN** 客户端调用 `GraphService.CreateDagNode(dag_name, json)` 携带 node 定义
- **THEN** server SHALL 创建 node type 配置并将 instance 添加到目标 DAG

### Requirement: GraphService Skill CRUD
`edera-server` SHALL 通过 `GraphService` 提供 Skill 配置的完整 CRUD 操作。

#### Scenario: 列出所有 skill
- **WHEN** 客户端调用 `GraphService.ListSkills`
- **THEN** server SHALL 返回 config/skills/ 目录下所有 skill 配置

#### Scenario: 创建 skill
- **WHEN** 客户端调用 `GraphService.CreateSkill(json)` 携带 name、description、handler_code
- **THEN** server SHALL 写入 skill YAML 和 handler.py 文件

#### Scenario: 创建重复 skill
- **WHEN** 客户端调用 `GraphService.CreateSkill` 且同名 skill 已存在
- **THEN** server SHALL 返回 gRPC ALREADY_EXISTS 错误

#### Scenario: 更新 skill
- **WHEN** 客户端调用 `GraphService.SaveSkill(name, json)`
- **THEN** server SHALL 更新 skill YAML 和 handler.py 文件

#### Scenario: 删除 skill
- **WHEN** 客户端调用 `GraphService.DeleteSkill(name)`
- **THEN** server SHALL 删除 skill YAML 和关联的 handler.py 文件

### Requirement: GraphService Handler CRUD
`edera-server` SHALL 通过 `GraphService` 提供 Handler 代码的读写操作，handler 列表通过 `ListHandlers` 从 `bootstrap.handler_registry` 获取，handler 路径通过 registry 查找而非硬编码。

#### Scenario: 列出所有 handler
- **WHEN** 客户端调用 `GraphService.ListHandlers`
- **THEN** server SHALL 从 `handler_registry` 返回所有已注册 handler 的名称列表

#### Scenario: 读取 handler
- **WHEN** 客户端调用 `GraphService.GetHandler(name)`
- **THEN** server SHALL 通过 `handler_registry` 查找 handler 路径，返回 handler.py 文件内容

#### Scenario: handler 不在注册表中
- **WHEN** 客户端调用 `GraphService.GetHandler(name)` 且 handler 不在 registry 中或文件不存在
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误

#### Scenario: 保存 handler
- **WHEN** 客户端调用 `GraphService.SaveHandler(name, code)`
- **THEN** server SHALL 通过 `handler_registry` 查找 handler 路径，写入 handler.py 文件内容

#### Scenario: 保存 handler 不在注册表中
- **WHEN** 客户端调用 `GraphService.SaveHandler(name, code)` 且 handler 不在 registry 中
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误

### Requirement: GraphService runtime-status
`edera-server` SHALL 通过 `GraphService` 提供 DAG 运行时节点状态查询。

#### Scenario: 查询 runtime status
- **WHEN** 客户端调用 `GraphService.RuntimeStatus`
- **THEN** server SHALL 查询最近一次 DAG run 的各节点执行状态并返回

