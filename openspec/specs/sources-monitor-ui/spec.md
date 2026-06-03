---
capabilities:
  - cap.web.sources-monitor-ui
---
# sources-monitor-ui Specification

## Purpose
此规约记录变更 frontend-react-spa 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Source health status display
系统 SHALL 展示所有信息源的健康状态摘要。

#### Scenario: View source health cards
- **WHEN** 用户进入信息源页面
- **THEN** 系统 SHALL 展示每个信息源的健康状态（成功率、最近失败原因、恢复状态）

#### Scenario: Highlight escalated sources
- **WHEN** 某信息源处于升级（escalated）状态
- **THEN** 系统 SHALL 以警告色高亮该信息源卡片

### Requirement: Source execution logs
系统 SHALL 展示信息源的执行日志列表。页面 SHALL 使用日志 payload 的 `status` 字段展示状态，并在 `started_at` 为空时使用 `ended_at` 或明确占位展示时间，MUST NOT 因字段不匹配或空时间渲染空白状态列、空白时间列。

#### Scenario: View execution logs
- **WHEN** 用户查看信息源页面且日志 payload 包含 `status`
- **THEN** 系统 SHALL 展示最近的执行日志，包含时间、状态和错误信息

#### Scenario: Filter logs by source
- **WHEN** 用户选择特定信息源
- **THEN** 系统 SHALL 仅展示该信息源的执行日志

#### Scenario: Display status from status field
- **WHEN** 信息源日志 payload 返回 `status` 而不返回 `node_status`
- **THEN** 信息源页面 SHALL 在状态列显示 `status`

#### Scenario: Display fallback time for source logs
- **WHEN** 信息源日志 payload 的 `started_at` 为空且 `ended_at` 非空
- **THEN** 信息源页面 SHALL 在时间列显示 `ended_at`

### Requirement: API error state display
系统 SHALL 在信息源健康度页面 API 请求失败时展示错误状态，而非永久显示"加载中..."。

#### Scenario: Source health API returns error
- **WHEN** `GET /api/sources/health` 请求失败
- **THEN** 系统 SHALL 展示错误提示信息，包含重试操作入口

### Requirement: Mutation error feedback
系统 SHALL 在 mutation 操作（运行 DAG、创建节点）失败时向用户展示错误信息。

#### Scenario: Run DAG mutation fails
- **WHEN** `POST /api/dags/{name}/run` 返回错误
- **THEN** 系统 SHALL 向用户展示包含错误原因的提示

#### Scenario: Create node mutation fails
- **WHEN** `POST /api/graph/dag/{name}/nodes` 返回错误
- **THEN** 系统 SHALL 向用户展示包含错误原因的提示

