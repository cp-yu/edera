---
capabilities:
  - cap.core.trigger-expression-language
---
# trigger-expression-language Specification

## Purpose
此规约记录变更 trigger-system-redesign 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 布尔表达式语法

系统 SHALL 支持以自由布尔表达式字符串定义 trigger 的 `wait_for` 条件。表达式 MUST 支持 `AND`、`OR` 运算符和括号分组。

#### Scenario: 简单 OR 表达式

- **WHEN** trigger 的 `wait_for` 为 `event:price-drop OR event:volume-spike`
- **THEN** 系统在 `event:price-drop` 或 `event:volume-spike` 任一 bit 置位时求值为 true

#### Scenario: 简单 AND 表达式

- **WHEN** trigger 的 `wait_for` 为 `cron:"0 9 * * *" AND event:market-open`
- **THEN** 系统仅在 cron bit 和 market-open bit 同时置位时求值为 true

#### Scenario: 括号嵌套表达式

- **WHEN** trigger 的 `wait_for` 为 `cron:"0 9 * * *" AND (event:market-open OR event:breaking-news)`
- **THEN** 系统在 cron bit 置位且 market-open 或 breaking-news 任一置位时求值为 true

#### Scenario: 单一 token 表达式

- **WHEN** trigger 的 `wait_for` 为 `cron:"*/30 * * * *"`
- **THEN** 系统在该 cron bit 置位时求值为 true

### Requirement: cron token 引号语义

系统 SHALL 使用引号包裹 cron 表达式中的 5 字段值以消除空格歧义。格式 MUST 为 `cron:"<minute> <hour> <dom> <month> <dow>"`。

#### Scenario: cron token 解析

- **WHEN** 表达式解析器遇到 `cron:"0 9 * * 1-5"`
- **THEN** 系统将其识别为单一 cron token，内部值为 `0 9 * * 1-5`

#### Scenario: 非法 cron 格式拒绝

- **WHEN** 表达式中出现 `cron:0 9 * * *`（无引号）
- **THEN** 解析器 MUST 报告语法错误

### Requirement: 表达式求值时机

系统 SHALL 在相关 bit 状态变化时重新求值引用该 bit 的 trigger 表达式。系统 MUST 维护 bit→trigger 反向索引以避免全量扫描。

#### Scenario: bit 变化触发求值

- **WHEN** `emit("event:market-open")` 置位 `event:market-open` bit
- **THEN** 系统仅重新求值 `wait_for` 表达式中包含 `event:market-open` 的 trigger

#### Scenario: 无关 bit 变化不触发求值

- **WHEN** `emit("event:unrelated")` 置位一个无 trigger 引用的 bit
- **THEN** 系统不执行任何 trigger 表达式求值

