## ADDED Requirements

### Requirement: Agent payload 显式导出 CLI
`edera node output export` SHALL 支持 agent 将指定 run/node 的业务 output payload 显式导出到文件，避免依赖 prompt 自动携带完整上游 payload。

#### Scenario: 导出指定节点 payload
- **WHEN** agent 执行 `edera node output export --run-id run-1 --node reader --out payload.json`
- **THEN** CLI SHALL 查询 `run-1` 中 `reader` 的业务 output
- **AND** CLI SHALL 将业务 output payload 写入 `payload.json`

#### Scenario: 导出不包含 execution logs
- **WHEN** agent 执行 `edera node output export --run-id run-1 --node reader --out payload.json`
- **THEN** `payload.json` MUST NOT 包含 execution logs
- **AND** execution logs SHALL 继续通过 `edera node logs reader --run-id run-1` 查询

#### Scenario: 缺少导出目标
- **WHEN** agent 执行 `edera node output export --run-id run-1 --node reader`
- **THEN** CLI MUST 返回非零状态
- **AND** CLI SHALL 提示缺少 `--out`
