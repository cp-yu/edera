## ADDED Requirements

### Requirement: Create node and add to DAG
系统 SHALL 提供 `POST /api/graph/dag/{name}/nodes` 端点，创建新节点配置文件并将其加入指定 DAG 的节点列表。

#### Scenario: Create node successfully
- **WHEN** 前端提交合法的节点定义（含 name、type、input_type、output_type）
- **THEN** 系统 SHALL 创建节点 YAML 文件、将节点名追加到 DAG 的 nodes 列表、并返回创建后的节点数据

#### Scenario: Node name conflicts with existing node
- **WHEN** 提交的节点 name 与已有节点文件同名
- **THEN** 系统 MUST 返回 409 错误，包含 `conflict` 错误类型

#### Scenario: Target DAG not found
- **WHEN** 指定的 DAG name 不存在于 `config/dags/` 目录
- **THEN** 系统 MUST 返回 404 错误，包含 `not_found` 错误类型
