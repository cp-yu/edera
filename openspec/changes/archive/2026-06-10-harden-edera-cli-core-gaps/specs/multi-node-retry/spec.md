## ADDED Requirements

### Requirement: CLI retry 临时输入参数
`edera dag retry` SHALL 支持与 DAG run 相同的临时输入参数，用于在 retry 时传递 `sourceSharedInputs`、`nodeInputs` 和 `appendNodes`。

#### Scenario: retry 传递 sourceSharedInputs
- **WHEN** 用户执行 `edera dag retry my-dag --nodes reader --source-shared-inputs '{"entity":"entity://fix"}'`
- **THEN** retry 请求 SHALL 包含 `sourceSharedInputs={"entity":"entity://fix"}`

#### Scenario: retry 传递 nodeInputs 和 appendNodes
- **WHEN** 用户执行 `edera dag retry my-dag --nodes analyzer --node-inputs '{"analyzer":{"test_mode":true}}' --append-nodes analyzer`
- **THEN** retry 请求 SHALL 包含 `nodeInputs={"analyzer":{"test_mode":true}}`
- **AND** retry 请求 SHALL 包含 `appendNodes=["analyzer"]`

#### Scenario: retry 临时输入 JSON 非法
- **WHEN** 用户执行 `edera dag retry my-dag --node-inputs '{bad-json}'`
- **THEN** CLI MUST 返回非零状态
- **AND** CLI SHALL 输出 JSON 解析错误
