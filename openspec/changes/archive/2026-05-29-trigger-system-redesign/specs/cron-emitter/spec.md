## ADDED Requirements

### Requirement: cron 时钟 emitter 内置

系统 SHALL 在 edera-server 进程内运行 cron 时钟 emitter，按 trigger entity 表达式中声明的所有 cron token 自动 emit 对应事件。emitter 精度 MUST 为分钟级。

#### Scenario: cron tick 自动 emit

- **WHEN** 系统时钟到达某 trigger 表达式中 `cron:"0 9 * * *"` 声明的时间点
- **THEN** cron emitter 调用 `emit("cron:\"0 9 * * *\"")` 置位对应 bit

#### Scenario: 多 trigger 共享 cron token 仅置位一次

- **WHEN** 多个 trigger 的表达式都包含 `cron:"0 9 * * *"`
- **THEN** cron emitter 在 09:00 仅 emit 一次，所有相关 trigger 的反向索引同时被通知

### Requirement: 错过 tick 不补跑

系统 SHALL 跳过停机期间错过的 cron tick，不在重启时补 emit。

#### Scenario: 停机期间错过 tick

- **WHEN** edera-server 在 08:50 停机，09:00 的 cron tick 错过，09:30 启动
- **THEN** 系统不 emit 错过的 09:00 事件；下次 emit 等到下一个 tick 时间点（如次日 09:00）

#### Scenario: 启动后立即扫描下次 tick

- **WHEN** edera-server 启动并加载 trigger entity
- **THEN** cron emitter 为每个 cron token 计算下次触发时间并注册到内部时钟

### Requirement: trigger 配置变更动态生效

系统 SHALL 在 trigger entity 变更时重新扫描所有 cron token，更新 cron emitter 的注册表。

#### Scenario: 新增 trigger 立即生效

- **WHEN** 用户通过 Web Console 创建一个含 `cron:"*/15 * * * *"` 的 trigger
- **THEN** cron emitter 立即注册该 cron token，下个 15 分钟整点开始 emit

#### Scenario: 删除 trigger 取消注册

- **WHEN** 用户删除某 trigger entity，且该表达式中的 cron token 不再被任何 trigger 引用
- **THEN** cron emitter 从注册表中移除该 cron token
