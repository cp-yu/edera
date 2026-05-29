## MODIFIED Requirements

### Requirement: Trigger Entity 定义

系统 SHALL 支持通过 Trigger Entity 定义触发规则。Trigger Entity MUST 包含 `wait_for`（布尔表达式字符串）、`target`（触发目标）和 `enabled`（启用状态，默认 true）字段。

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

### Requirement: 触发目标

系统 SHALL 支持触发 DAG、Node 或 clear bit。触发目标 MUST 通过 `target` 字段指定，格式为 `dag:<name>` / `node:<id>` / `clear:event:<name>`。

#### Scenario: 触发 DAG 执行

- **WHEN** Trigger 的 `target` 为 `dag:default`
- **THEN** Trigger Executor 启动 `dag:default` 的一次完整执行

#### Scenario: 触发单 Node 执行

- **WHEN** Trigger 的 `target` 为 `node:<id>`
- **THEN** Trigger Executor 直接执行该 Node

#### Scenario: 触发 clear bit

- **WHEN** Trigger 的 `target` 为 `clear:event:market-open`
- **THEN** Trigger Executor 复位 `event:market-open` bit

## ADDED Requirements

### Requirement: Trigger enabled 字段

系统 SHALL 支持 Trigger Entity 的 `enabled` 字段（默认 true）。disabled 的 trigger MUST 跳过表达式求值。

#### Scenario: disabled trigger 不触发

- **WHEN** trigger entity 的 `enabled` 为 false，且其 wait_for 表达式中所有 bit 已置位
- **THEN** 系统不求值该表达式，不 fire

#### Scenario: 一次性 trigger 自动 disable

- **WHEN** trigger 的 `wait_for` 包含精确日期 cron（如 `cron:"0 9 30 5 *"`）且 fire 成功
- **THEN** 系统自动将该 trigger 的 `enabled` 设为 false

## REMOVED Requirements

### Requirement: 事件组机制
**Reason**: 被 `event-group-engine` 和 `trigger-expression-language` 两个新 capability 替代
**Migration**: 原 `{mode: AND/OR, events: [...]}` 结构改为自由布尔表达式字符串

### Requirement: 事件源注册
**Reason**: 事件源注册分散到 `cron-emitter`、`node-emits-declaration`、`config-hot-reload`、`entity-instance-crud-api` 各自的 spec 中
**Migration**: 各事件源在各自 capability spec 中定义 emit 行为
