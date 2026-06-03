---
capabilities:
  - cap.core.event-group-engine
---
# event-group-engine Specification

## Purpose
定义 Bit 持久化存储、bit 置位语义、fire 后自动 consume、bit→trigger 反向索引。
## Requirements
### Requirement: Bit 持久化存储

系统 SHALL 将 EventGroup 的 bit 状态持久化到数据库中。系统 MUST 在启动时从数据库恢复 bit 状态。

#### Scenario: 启动恢复 bit 状态

- **WHEN** edera-server 启动且数据库中存在已置位的 bit 记录
- **THEN** 系统在内存中恢复这些 bit 为置位状态，无需重新 emit

#### Scenario: bit 写操作落盘

- **WHEN** `emit("event:market-open")` 置位一个 bit
- **THEN** 系统在内存更新 bit 状态的同时写入数据库

### Requirement: bit 置位语义

系统 SHALL 通过 `emit("event:<name>")` 置位 bit，通过 `emit("clear:event:<name>")` 复位 bit。

#### Scenario: 置位 bit

- **WHEN** 调用 `emit("event:market-open")`
- **THEN** 系统将 `event:market-open` bit 置为 1

#### Scenario: 复位 bit

- **WHEN** 调用 `emit("clear:event:market-open")`
- **THEN** 系统将 `event:market-open` bit 置为 0

#### Scenario: 重复置位幂等

- **WHEN** 对已置位的 bit 再次调用 `emit("event:market-open")`
- **THEN** bit 保持置位状态，不产生副作用

### Requirement: fire 后自动 consume

系统 SHALL 在 trigger fire 后自动清除该 trigger 表达式中所有当前已置位的 bit。

#### Scenario: AND 表达式 consume

- **WHEN** trigger `wait_for: 'cron:"0 9 * * *" AND event:market-open'` fire
- **THEN** 系统清除 `cron:"0 9 * * *"` 和 `event:market-open` 两个 bit

#### Scenario: OR 表达式部分 consume

- **WHEN** trigger `wait_for: 'event:a OR event:b'` fire 时仅 `event:a` 置位
- **THEN** 系统清除 `event:a`，`event:b` 保持原状（未置位）

#### Scenario: 共享 bit first-wins

- **WHEN** trigger A 和 B 都监听 `event:price-drop`，A 先匹配 fire 并 consume bit
- **THEN** B 的表达式重新求值时 `event:price-drop` 已为 0，不会触发

### Requirement: bit→trigger 反向索引

系统 SHALL 维护从 bit 名称到引用该 bit 的 trigger 列表的反向索引，仅在 bit 状态变化时重新求值受影响的 trigger。

#### Scenario: 索引建立

- **WHEN** 加载 trigger entity 时解析其 `wait_for` 表达式
- **THEN** 系统将该 trigger 注册到表达式中每个 bit 名称对应的索引项

#### Scenario: 索引失效更新

- **WHEN** trigger entity 被修改或删除
- **THEN** 系统更新或移除该 trigger 在反向索引中的注册项
