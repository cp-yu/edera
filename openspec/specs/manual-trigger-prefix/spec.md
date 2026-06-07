---
capabilities:
  - cap.core.manual-trigger-prefix
---
# manual-trigger-prefix Specification

## Purpose
定义 manual 前缀直接 fire、manual 前缀禁止用户在 wait_for 中引用。
## Requirements
### Requirement: manual 前缀直接 fire

系统 SHALL 识别 `manual:dag:<name>` 和 `manual:node:<dag_name>/<node_id>` 形式的事件名为保留前缀。emit 此类事件时 MUST 不经过 wait_for 表达式匹配，直接 fire 对应目标。系统 MUST NOT 支持 `manual:node:<id>` 形式的全局 node 反查。

#### Scenario: manual:dag 直接 fire DAG

- **WHEN** 调用 `emit("manual:dag:default")`
- **THEN** 系统直接调用 DAG runner 启动 `dag:default` 的一次执行，不查询任何 trigger entity

#### Scenario: manual:node 直接 fire DAG-scoped Node

- **WHEN** 调用 `emit("manual:node:analysis/fetch-news")`
- **THEN** 系统直接 fire `node:analysis/fetch-news`
- **AND** DagController SHALL 在 DAG `analysis` 内解析并执行该 node

#### Scenario: manual:node legacy target 被拒绝

- **WHEN** 调用 `emit("manual:node:<node-id>")`
- **THEN** 系统 SHALL 返回 invalid target 错误

#### Scenario: manual 事件不置位 bit

- **WHEN** 调用 `emit("manual:dag:default")`
- **THEN** 系统不置位任何 EventGroup bit；该事件不出现在 `event_group_bits` 表中

### Requirement: manual 前缀禁止用户在 wait_for 中引用

系统 SHALL 拒绝 trigger entity 的 `wait_for` 表达式中包含 `manual:` 前缀的 token。

#### Scenario: 校验拒绝 manual 前缀

- **WHEN** 用户保存一个 `wait_for: 'manual:dag:default'` 的 trigger entity
- **THEN** 系统返回校验错误，提示 manual 是保留前缀仅用于 emit

