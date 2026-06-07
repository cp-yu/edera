---
capabilities:
  - cap.trigger-system
---
# trigger-system Specification

## Purpose
定义 Trigger Entity 定义、触发目标、事件记录可观测、Trigger enabled 字段。
## Requirements
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

系统 SHALL 支持触发 DAG、DAG-scoped Node 或 clear bit。触发目标 MUST 通过 `target` 字段指定，格式为 `dag:<name>` / `node:<dag_name>/<node_id>` / `clear:event:<name>`。系统 MUST NOT 支持通过 `node:<id>` 全局扫描所有 DAG 反查 Node。

#### Scenario: 触发 DAG 执行

- **WHEN** Trigger 的 `target` 为 `dag:default`
- **THEN** Trigger Executor 启动 `dag:default` 的一次完整执行

#### Scenario: 触发 DAG-scoped 单 Node 执行

- **WHEN** Trigger 的 `target` 为 `node:analysis/fetch-news`
- **THEN** Trigger Executor SHALL 在 DAG `analysis` 内解析 `fetch-news`
- **AND** DagController SHALL 为 DAG `analysis` 构建 execution closure 后执行该 Node

#### Scenario: 拒绝全局 Node target

- **WHEN** Trigger 的 `target` 为 `node:<id>`
- **THEN** 系统 SHALL 拒绝该 target 格式

#### Scenario: 触发 clear bit

- **WHEN** Trigger 的 `target` 为 `clear:event:market-open`
- **THEN** Trigger Executor 复位 `event:market-open` bit

### Requirement: 事件记录可观测

系统 SHALL 将事件的发生和消费记录到 run metadata Entity 中，确保可观测性。

#### Scenario: 事件触发记录

- **WHEN** 一个事件被产生并触发了 Trigger
- **THEN** 系统在 run metadata Entity 中记录事件名称、产生时间、消费时间和触发的目标

### Requirement: Trigger enabled 字段

系统 SHALL 支持 Trigger Entity 的 `enabled` 字段（默认 true）。disabled 的 trigger MUST 跳过表达式求值。

#### Scenario: disabled trigger 不触发

- **WHEN** trigger entity 的 `enabled` 为 false，且其 wait_for 表达式中所有 bit 已置位
- **THEN** 系统不求值该表达式，不 fire

#### Scenario: 一次性 trigger 自动 disable

- **WHEN** trigger 的 `wait_for` 包含精确日期 cron（如 `cron:"0 9 30 5 *"`）且 fire 成功
- **THEN** 系统自动将该 trigger 的 `enabled` 设为 false

