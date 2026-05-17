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
系统 SHALL 展示信息源的执行日志列表。

#### Scenario: View execution logs
- **WHEN** 用户查看信息源页面
- **THEN** 系统 SHALL 展示最近的执行日志，包含时间、状态和错误信息

#### Scenario: Filter logs by source
- **WHEN** 用户选择特定信息源
- **THEN** 系统 SHALL 仅展示该信息源的执行日志

