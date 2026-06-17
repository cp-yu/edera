## ADDED Requirements

### Requirement: Startup token is a broadcast window bit
The `startup` token SHALL be a valid Trigger `wait_for` expression token representing the system startup window. While the startup window is open, `startup` SHALL be present in `EventGroup`; outside the window, `startup` SHALL be absent.

The `startup` token SHALL be a broadcast bit: `EventGroup.consume()` SHALL skip `startup`, so multiple Trigger Entities waiting on `startup` SHALL all evaluate true and fire independently during the window. The `startup` bit SHALL be removed only by window expiry or by explicit `clear("startup")` at the next startup.

Triggers fired as a consequence of the `startup` token SHALL create `DagRun` records with `source = "startup"`.

#### Scenario: Startup token combines with cron in wait_for
- **WHEN** a Trigger Entity has `wait_for: 'startup AND cron:"0 9 * * *"'`, `DagController.start()` completes at 09:00:xx within the startup window, and the cron tick for `"0 9 * * *"` is emitted within the same window
- **THEN** the trigger SHALL fire exactly once
- **AND** the resulting `DagRun.source` SHALL be `"startup"`

#### Scenario: Startup token does not consume on fire
- **WHEN** two Trigger Entities both declare `wait_for: 'startup'`, and `DagController.start()` completes
- **THEN** both triggers SHALL fire
- **AND** the `EventGroup.consume()` call performed after each fire SHALL NOT remove `startup` from the active set

#### Scenario: Startup token evaluates false outside window
- **WHEN** the startup window has expired and a Trigger Entity has `wait_for: 'startup'`
- **THEN** the trigger SHALL NOT fire on subsequent unrelated emits
- **AND** the `startup` token SHALL be absent from `EventGroup.events`

## MODIFIED Requirements

### Requirement: Trigger Entity 定义

系统 SHALL 支持通过 Trigger Entity 定义触发规则。Trigger Entity MUST 包含 `wait_for`（布尔表达式字符串）、`target`（触发目标）和 `enabled`（启用状态，默认 true）字段。`wait_for` 表达式 token 来源 SHALL 限定为：`cron:"<spec>"`、`event:<name>`、`startup`，以及它们的布尔组合。

#### Scenario: 定义 cron 触发器

- **WHEN** 用户创建 Trigger Entity，`wait_for: 'cron:"0 9 * * *"'`，`target: "dag:morning-analysis"`
- **THEN** 系统在每天 09:00 cron bit 置位时触发 `dag:morning-analysis` 的执行

#### Scenario: 定义事件触发器

- **WHEN** 用户创建 Trigger Entity，`wait_for: 'event:config-changed'`，`target: "dag:config-validation"`
- **THEN** 系统在 `event:config-changed` bit 置位时触发 `dag:config-validation` 的执行

#### Scenario: 定义复合触发器

- **WHEN** 用户创建 Trigger Entity，`wait_for: 'cron:"0 9 * * *" AND (event:market-open OR event:breaking-news)'`，`target: "dag:morning-analysis"`
- **THEN** 系统在 cron bit 置位且 market-open 或 breaking-news 任一置位时触发执行

#### Scenario: 定义 clear target 触发器

- **WHEN** 用户创建 Trigger Entity，`wait_for: 'cron:"0 16 * * *"'`，`target: "clear:event:market-open"`
- **THEN** 系统在每天 16:00 复位 `event:market-open` bit

#### Scenario: 定义 startup 触发器

- **WHEN** 用户创建 Trigger Entity，`wait_for: 'startup'`，`target: "dag:bootstrap"`
- **THEN** 系统在 `DagController.start()` 完成后的 startup 窗口期内触发 `dag:bootstrap` 执行一次
- **AND** 产生的 `DagRun.source` SHALL 为 `"startup"`
