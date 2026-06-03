## ADDED Requirements

### Requirement: emit 驱动 WaitRegistry 求值
`TriggerExecutor.emit()` 在置位 bit 后，除遍历 trigger 反向索引外，MUST 额外重新求值 `WaitRegistry` 中所有挂起等待者的 `wait_for` 表达式。表达式被满足的等待者 SHALL 以最近的 emit payload 被唤醒（`Future.set_result`）。WaitRegistry 是 run 内挂起 wait 节点的唤醒入口，与启动新 run 的 `fire()` 路径并列。

#### Scenario: emit 唤醒挂起等待者
- **WHEN** WaitRegistry 中存在等待 `event:approve:abc` 的挂起节点，客户端 `emit("event:approve:abc", payload)`
- **THEN** 系统置位 bit 后 SHALL 求值命中该等待者并以 payload 唤醒它

#### Scenario: emit 无匹配等待者
- **WHEN** WaitRegistry 中无任何等待者的表达式被新置位的 bit 满足
- **THEN** 系统 SHALL 仅完成既有 bit 置位与 trigger 求值，不唤醒任何节点

#### Scenario: emit 同时驱动 trigger 与 waiter
- **WHEN** 一次 emit 既满足某 Trigger Entity 的 `wait_for`，又满足某挂起 wait 节点的 `wait_for`
- **THEN** 系统 SHALL 既 fire trigger target，又唤醒挂起 wait 节点
