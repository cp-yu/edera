## MODIFIED Requirements

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
