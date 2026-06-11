---
capabilities:
  - cap.core.edera-cli
---
# edera-cli Delta Specification

## ADDED Requirements

### Requirement: CLI 输出模式
`edera` CLI SHALL 支持 `--output json|yaml|table` 全局输出模式。未指定 `--output` 时，CLI SHALL 保持现有 JSON stdout 行为。

#### Scenario: 默认 JSON 输出
- **WHEN** 用户执行 `edera query briefing latest`
- **THEN** CLI SHALL 将结果作为 JSON 写入 stdout

#### Scenario: YAML 输出
- **WHEN** 用户执行 `edera query briefing latest --output yaml`
- **THEN** CLI SHALL 将同一结果作为 YAML 写入 stdout

#### Scenario: 表格输出
- **WHEN** 用户执行 `edera source logs --limit 2 --output table`
- **THEN** CLI SHALL 将列表结果渲染为包含表头和行的文本表格
- **AND** 嵌套对象或数组 SHALL 作为 JSON 字符串保留在单元格中

#### Scenario: 不支持的输出模式
- **WHEN** 用户执行 `edera entity list --output xml`
- **THEN** CLI MUST 返回非零状态
- **AND** stderr SHALL 包含无效 `--output` 的错误信息

### Requirement: CLI watch 模式
`edera` CLI SHALL 为运行观察命令提供 `--watch` 模式。watch 模式 SHALL 按 `--interval` 指定的秒数重复查询并输出结果；未指定 `--watch-count` 时 SHALL 持续运行直到用户中断。

#### Scenario: 观察 DAG 运行状态
- **WHEN** 用户执行 `edera dag status default --watch --interval 1 --watch-count 2`
- **THEN** CLI SHALL 查询并输出 2 次 `default` DAG 状态

#### Scenario: 观察 runtime graph 状态
- **WHEN** 用户执行 `edera dag runtime-status --run-id run-1 --watch --watch-count 2`
- **THEN** CLI SHALL 查询并输出 2 次 `run-1` 的 runtime graph 状态

#### Scenario: 观察 scheduler 状态
- **WHEN** 用户执行 `edera system scheduler-status --watch --watch-count 2`
- **THEN** CLI SHALL 查询并输出 2 次 scheduler 状态

#### Scenario: 观察 source health
- **WHEN** 用户执行 `edera source health --watch --watch-count 2`
- **THEN** CLI SHALL 查询并输出 2 次 source health 摘要

### Requirement: CLI tail 模式
`edera` CLI SHALL 为日志类命令提供 `--tail` 模式。tail 模式 SHALL 重复查询最近日志，并只输出本次会话尚未输出过的日志项。

#### Scenario: 跟随节点执行日志
- **WHEN** 用户执行 `edera node logs reader --run-id run-1 --tail --interval 1 --watch-count 2`
- **THEN** CLI SHALL 重复查询节点 execution logs
- **AND** CLI SHALL 只输出未在本次 tail 会话中出现过的日志项

#### Scenario: 跟随 source execution logs
- **WHEN** 用户执行 `edera source logs --source-name rss-main --tail --watch-count 2`
- **THEN** CLI SHALL 重复查询 `rss-main` 的 source execution logs
- **AND** CLI SHALL 只输出未在本次 tail 会话中出现过的日志项

### Requirement: CLI 错误输出
`edera` CLI SHALL 将运行时错误作为结构化 JSON object 写入 stderr，并保持非零退出状态。错误对象 SHALL 包含 `error`、`type` 和 `detail` 字段。

#### Scenario: 缺少 server 地址
- **WHEN** 用户执行数据子命令但未设置 `EDERA_SERVER_ADDR` 且未传 `--server`
- **THEN** CLI SHALL 以非零状态退出
- **AND** stderr SHALL 包含 `{"error":...,"type":"ValueError","detail":"EDERA_SERVER_ADDR not set"}`

#### Scenario: gRPC 错误
- **WHEN** server 对 CLI 请求返回 gRPC 错误
- **THEN** CLI SHALL 以非零状态退出
- **AND** stderr SHALL 在 `detail` 字段中保留 server 返回的错误详情
