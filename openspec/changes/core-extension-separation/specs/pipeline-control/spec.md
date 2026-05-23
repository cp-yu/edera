## MODIFIED Requirements

### Requirement: Manual run control

系统 SHALL 支持用户从 Web 控制台或 API 手动运行指定 DAG。Handler 注册 MUST 从 bootstrap registry 获取，MUST NOT 硬编码 handler 字典。

#### Scenario: Start manual run for named DAG

- **WHEN** 没有该 DAG 的运行中任务且用户触发手动运行
- **THEN** 系统 SHALL 从 handler registry 构建 executor，启动指定 DAG 并返回新 cycle_id

#### Scenario: Reject concurrent run for same DAG

- **WHEN** 指定 DAG 已有运行中任务且用户再次触发手动运行
- **THEN** 系统 MUST 拒绝并返回当前运行中的 cycle_id

