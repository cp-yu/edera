## ADDED Requirements

### Requirement: Executed node execution logs
系统 SHALL 为每个实际开始执行的 node run 生成可查询的 execution log。execution log 至少 MUST 包含系统生成的 summary，summary MUST 包含 `run_id`、`node_id`、`ok`、`status`、`error`、`failure_kind`、`payload_empty` 和可用的 `session_id` 或 raw log reference。未实际启动执行的节点 MUST NOT 因该要求被强制生成 execution log。

#### Scenario: Successful node with payload records log
- **WHEN** 节点实际执行并成功返回非空业务 payload
- **THEN** 系统 SHALL 写入 execution log，记录 `ok=true`、`status=succeeded` 和 `payload_empty=false`
- **AND** 系统 SHALL 继续按既有规则将业务 payload 写入 `node_outputs`

#### Scenario: Successful node without payload records log
- **WHEN** 节点实际执行并成功返回 `None`、空列表或空 payload
- **THEN** 系统 SHALL 写入 execution log，记录 `ok=true`、`status=succeeded` 和 `payload_empty=true`
- **AND** 系统 MUST NOT 仅为了可观测性创建业务 `NodeOutputEntity`

#### Scenario: Failed executed node records log
- **WHEN** 节点实际执行后因 handler exception、timeout、wait timeout 或 executor error 失败
- **THEN** 系统 SHALL 写入 execution log，记录 `ok=false`、`status=failed`、`error` 和 `failure_kind`
- **AND** 系统 MUST NOT 将失败摘要作为业务 payload 写入 `node_outputs`

#### Scenario: Unstarted node has no required log
- **WHEN** 节点因 required 上游失败而未进入执行路径
- **THEN** 系统 SHALL NOT 因本要求生成 execution log

### Requirement: Agent execution logs remain queryable
Agent 节点 SHALL 将实时 stdout、raw process log 和系统生成的 execution summary 纳入同一历史可查询日志语义。Agent 节点无论成功或失败，只要实际启动执行，就 MUST 有可查询 execution log。

#### Scenario: Successful agent keeps stdout and summary
- **WHEN** agent 节点实际执行、输出 stdout 并成功结束
- **THEN** 系统 SHALL 继续实时推送 stdout
- **AND** 系统 SHALL 将 stdout raw log 索引为可查询日志
- **AND** 系统 SHALL 写入 execution summary，包含 `ok=true` 和 `session_id`

#### Scenario: Failed agent keeps stdout and summary
- **WHEN** agent 节点实际执行、输出部分 stdout 后以非零状态或异常失败
- **THEN** 系统 SHALL 保留已产生的 stdout raw log 索引
- **AND** 系统 SHALL 写入 execution summary，包含 `ok=false`、失败原因和 `session_id`

#### Scenario: Agent without stdout still has summary
- **WHEN** agent 节点实际执行但没有输出 stdout
- **THEN** 系统 SHALL 写入 execution summary
- **AND** 用户 SHALL 能通过历史日志查询确认该 agent run 已执行并结束

### Requirement: Execution log storage boundary
系统 SHALL 使用 DB-backed log index 查询节点 execution logs。`log_index` MUST 能区分 execution summary 与 raw process log，并保持 run id、node id、path、size、digest 和 timestamps 可查询。完整 raw 日志内容 MUST 存储为文件，不得写入 runtime facts 表或 `node_outputs`。

#### Scenario: Execution summary log indexed
- **WHEN** 系统为已执行节点写入 execution summary
- **THEN** 系统 SHALL 将 summary 存储为文件或等价可读取记录
- **AND** 系统 SHALL 在 `log_index` 中记录 `run_id`、`node_id`、log kind、path、size、digest 和 timestamps

#### Scenario: Raw process log indexed
- **WHEN** agent 节点或其他执行路径产生 raw stdout/stderr 日志
- **THEN** 系统 SHALL 将 raw log 内容写入 `EDERA_DATA_DIR/sessions` 下的文件
- **AND** 系统 SHALL 在 `log_index` 中记录可查询索引

#### Scenario: Logs stay out of runtime facts and outputs
- **WHEN** 节点 execution log 或 raw process log 被持久化
- **THEN** 系统 MUST NOT 将完整日志内容写入 `dag_runs`、`node_runs`、`edge_inputs`、`source_recoveries`、`emit_records` 或 `node_outputs`

### Requirement: Runtime views show execution logs
Web Console Runtime tab 和 Node History SHALL 展示已执行节点的 execution logs。没有业务 output entities 不得被展示为唯一结果；如果节点已执行且无业务 output，界面仍 MUST 展示 execution logs。

#### Scenario: Runtime tab shows logs for empty output
- **WHEN** 用户在 Runtime tab 查看一个已执行成功但没有业务 output entity 的节点
- **THEN** 系统 SHALL 展示该节点的 execution summary log
- **AND** 系统 SHALL NOT 只展示“暂无输出”作为该节点的全部运行结果

#### Scenario: Runtime tab shows failure logs
- **WHEN** 用户在 Runtime tab 查看一个已执行失败的节点
- **THEN** 系统 SHALL 展示 NodeRun status/error
- **AND** 系统 SHALL 展示该节点的 execution summary log 和可用 raw process log

#### Scenario: Node history expands logs
- **WHEN** 用户在节点历史页面展开某个已执行 run
- **THEN** 系统 SHALL 展示该 run 的 NodeRun、output entities 和 execution logs

#### Scenario: Unstarted node does not require logs
- **WHEN** 用户查看因上游阻断而未实际执行的节点
- **THEN** 系统 SHALL NOT 要求该节点展示 execution logs
