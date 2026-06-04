## ADDED Requirements

### Requirement: Node execution logs command
`edera node` SHALL 提供按 `run_id` 查看节点 execution logs 的命令。该命令 SHALL 通过 gRPC 查询 server，MUST NOT 直接读取本地日志文件或数据库。

#### Scenario: 查看节点执行日志
- **WHEN** 用户执行 `edera node logs llm-analyzer --run-id abc123`
- **THEN** CLI SHALL 通过 gRPC 查询该 run 中该节点的 execution logs
- **AND** CLI SHALL 输出 execution summary 和可用 raw log reference

#### Scenario: 无业务输出仍可看日志
- **WHEN** 用户执行 `edera node logs reader --run-id abc123`，且该节点已执行但没有业务 output entity
- **THEN** CLI SHALL 输出该节点的 execution summary log

#### Scenario: 节点输出命令保持业务语义
- **WHEN** 用户执行 `edera node output reader --run-id abc123`
- **THEN** CLI SHALL 只返回业务 output 内容
- **AND** CLI MUST NOT 将 execution logs 作为 output 返回
