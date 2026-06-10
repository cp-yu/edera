## ADDED Requirements

### Requirement: 运行控制命令入口
`edera` CLI SHALL 提供运行控制相关命令入口，覆盖节点业务输出导出、DAG retry 临时输入和 source repair task 创建，并保持现有 JSON stdout 与错误 stderr 约定。

#### Scenario: node output export 命令可用
- **WHEN** 用户执行 `edera node output export --run-id run-1 --node reader --out payload.json`
- **THEN** CLI SHALL 将指定 run/node 的业务 output payload 写入 `payload.json`
- **AND** CLI SHALL 输出导出文件路径和导出条目摘要
- **AND** CLI MUST NOT 将 execution logs 写入该 payload 文件

#### Scenario: dag retry 传递临时输入
- **WHEN** 用户执行 `edera dag retry default --run-id run-1 --nodes reader --source-shared-inputs '{"symbol":"AAPL"}' --node-inputs '{"reader":{"limit":1}}' --append-nodes reader`
- **THEN** CLI SHALL 将 `sourceSharedInputs`、`nodeInputs` 和 `appendNodes` 传递给 retry 请求

#### Scenario: source repair task 命令可用
- **WHEN** 用户执行 `edera system repair-source rss-main`
- **THEN** CLI SHALL 请求 server 为 `rss-main` 创建 source repair task
- **AND** CLI SHALL 输出 task_id、task_path、source_name 和 created_at
