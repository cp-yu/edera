## ADDED Requirements

### Requirement: API error state display
系统 SHALL 在信息源健康度页面 API 请求失败时展示错误状态，而非永久显示"加载中..."。

#### Scenario: Source health API returns error
- **WHEN** `GET /api/sources/health` 请求失败
- **THEN** 系统 SHALL 展示错误提示信息，包含重试操作入口

### Requirement: Mutation error feedback
系统 SHALL 在 mutation 操作（运行 DAG、创建节点）失败时向用户展示错误信息。

#### Scenario: Run DAG mutation fails
- **WHEN** `POST /api/pipeline/dag/{name}/run` 返回错误
- **THEN** 系统 SHALL 向用户展示包含错误原因的提示

#### Scenario: Create node mutation fails
- **WHEN** `POST /api/graph/dag/{name}/nodes` 返回错误
- **THEN** 系统 SHALL 向用户展示包含错误原因的提示
