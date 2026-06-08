## MODIFIED Requirements

### Requirement: manual 前缀直接 fire
系统 SHALL 识别 `manual:dag:<name>` 和 `manual:node:<dag_name>/<node_id>` 形式的事件名为保留前缀。Node trigger 的 `run_node_trigger` 方法 SHALL 支持 `append` 参数。

#### Scenario: manual:node 触发时支持追加模式
- **WHEN** 调用 `run_node_trigger("dag/node_1", payload, append=True)`
- **THEN** 系统 SHALL 将 `node_1` 加入 `appendNodes` 列表
