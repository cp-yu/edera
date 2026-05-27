## MODIFIED Requirements

### Requirement: Agent 短期证书签发
Daemon 启动 agent 节点前，SHALL 使用内部 CA 签发短期 client cert，CN 为 `node:{instance_id}`，TTL 对齐节点 timeout。签发后 SHALL 将 PEM 内容保持在内存中，通过环境变量注入 subprocess，不写入文件系统。

#### Scenario: Agent 节点证书签发
- **WHEN** daemon 启动 agent 节点 `llm-analyzer`
- **THEN** daemon SHALL 签发 client cert，CN=`node:llm-analyzer`，TTL=节点 timeout

#### Scenario: 证书通过环境变量注入 PEM 内容
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `RIG_CLIENT_CERT` SHALL 包含签发的 client cert PEM 文本内容（非文件路径）

#### Scenario: 私钥通过环境变量注入 PEM 内容
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `RIG_CLIENT_KEY` SHALL 包含签发的 client key PEM 文本内容（非文件路径）

#### Scenario: CA cert 通过环境变量注入 PEM 内容
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `RIG_CA_CERT` SHALL 包含 daemon CA cert PEM 文本内容

#### Scenario: 证书不落盘
- **WHEN** daemon 完成 agent cert 签发
- **THEN** daemon SHALL 不将 cert 或 key 写入文件系统

#### Scenario: Resume 重新签发
- **WHEN** 用户调用 resume API 恢复已停止的 agent 节点
- **THEN** daemon SHALL 重新签发新的短期 cert（新 TTL），不复用旧 cert
