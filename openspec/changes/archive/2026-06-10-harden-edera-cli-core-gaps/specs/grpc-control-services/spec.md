## ADDED Requirements

### Requirement: source repair task CLI 入口
`edera system` SHALL 提供 source repair task 创建命令，作为 `SystemService.CreateRepairTask` 的 CLI 入口。

#### Scenario: 为 escalated source 创建 repair task
- **WHEN** 用户执行 `edera system repair-source rss-main`
- **THEN** CLI SHALL 调用 source repair task 创建能力
- **AND** CLI SHALL 输出 task_id、task_path、source_name 和 created_at

#### Scenario: source 未 escalated
- **WHEN** 用户执行 `edera system repair-source rss-main` 且该 source 未处于 escalated 状态
- **THEN** CLI MUST 返回非零状态
- **AND** CLI SHALL 输出 server 返回的 FAILED_PRECONDITION 错误

#### Scenario: source 不存在
- **WHEN** 用户执行 `edera system repair-source missing-source`
- **THEN** CLI MUST 返回非零状态
- **AND** CLI SHALL 输出 server 返回的 NOT_FOUND 错误
