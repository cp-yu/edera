---
capabilities:
  - cap.core.manual-trigger-prefix
---
# manual-trigger-prefix Specification

## Purpose
定义 manual 前缀直接 fire、manual 前缀禁止用户在 wait_for 中引用。
## Requirements
### Requirement: manual 前缀直接 fire
系统 SHALL 识别 `manual:dag:<name>` 和 `manual:node:<dag_name>/<node_id>` 形式的事件名为保留前缀。Node trigger 的 `run_node_trigger` 方法 SHALL 支持 `append` 参数。

#### Scenario: manual:node 触发时支持追加模式
- **WHEN** 调用 `run_node_trigger("dag/node_1", payload, append=True)`
- **THEN** 系统 SHALL 将 `node_1` 加入 `appendNodes` 列表

### Requirement: manual 前缀禁止用户在 wait_for 中引用

系统 SHALL 拒绝 trigger entity 的 `wait_for` 表达式中包含 `manual:` 前缀的 token。

#### Scenario: 校验拒绝 manual 前缀

- **WHEN** 用户保存一个 `wait_for: 'manual:dag:default'` 的 trigger entity
- **THEN** 系统返回校验错误，提示 manual 是保留前缀仅用于 emit

