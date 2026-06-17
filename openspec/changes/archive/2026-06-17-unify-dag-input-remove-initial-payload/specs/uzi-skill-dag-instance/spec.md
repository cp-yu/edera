## MODIFIED Requirements

### Requirement: ticker 通过 initial_payload 传入

主 DAG 运行时 SHALL 通过 `sourceSharedInputs: {"ticker": "<code>"}` 接收股票代码。preflight 节点从 `sourceSharedInputs` 提取 ticker，并通过主 DAG 边将 preflight 输出传递给 `data_collection` Sub DAG。

#### Scenario: 手动触发传入 ticker

- **WHEN** 用户调用 `POST /api/dags/uzi-skill-analysis/run` 并传入 `{"sourceSharedInputs": {"ticker": "300470.SZ"}}`
- **THEN** 主 DAG source 节点的 `sourceSharedInputs` MUST 为 `{"ticker": "300470.SZ"}`

#### Scenario: ticker 经 preflight 输出传递到 Sub DAG

- **WHEN** `data_collection` Sub DAG 节点启动
- **THEN** preflight 的输出（包含 ticker 信息）SHALL 经 `input_mapping` 映射到该 Sub DAG 的 `sourceSharedInputs`
