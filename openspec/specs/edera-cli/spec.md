# edera-cli Specification

## Purpose
定义 `edera` 控制 CLI 的 binary 入口、子命令集合、身份声明、纯 gRPC 客户端契约和 mTLS 加载边界。
## Requirements
### Requirement: CLI binary 入口
系统 SHALL 提供名为 `edera` 的 CLI binary，作为 agent 和人类访问 Edera 控制面能力的统一入口。`edera` 是控制 CLI 的命令名，与 `edera-server`（后端引擎）、`edera-web`（网页 BFF）三个 console scripts 一同构成完整入口集合。本 capability 接替原 `rig-cli` + `rig-cli-full-crud`。

#### Scenario: CLI 可执行
- **WHEN** 用户或 agent 在终端执行 `edera --help`
- **THEN** 系统 SHALL 输出可用子命令列表（entity、node、dag、client、handler-validate）

#### Scenario: 版本查询
- **WHEN** 用户执行 `edera --version`
- **THEN** 系统 SHALL 输出当前版本号

#### Scenario: Console scripts 集合
- **WHEN** 检查包的 console scripts
- **THEN** 系统 SHALL 注册 `edera = "edera_core.cli:main"`、`edera-server = "edera_core.server:main"`、`edera-web = "edera_core.web.__main__:main"`
- **AND** 系统 SHALL NOT 注册名为 `rig` 的 console script

### Requirement: 身份声明
`edera` CLI SHALL 支持双身份模式：通过 `EDERA_IDENTITY` 环境变量设置默认身份，通过 `--identity` flag 覆盖。

#### Scenario: 环境变量身份
- **WHEN** 环境变量 `EDERA_IDENTITY=node:llm-analyze` 已设置，用户执行 `edera entity get stock:AAPL`
- **THEN** 系统 SHALL 以 `node:llm-analyze` 身份执行权限检查

#### Scenario: Flag 覆盖环境变量
- **WHEN** 环境变量 `EDERA_IDENTITY=node:llm-analyze` 已设置，用户执行 `edera --identity human entity get stock:AAPL`
- **THEN** 系统 SHALL 以 `human` 身份执行权限检查，忽略环境变量

#### Scenario: 无身份声明
- **WHEN** 未设置 `EDERA_IDENTITY` 且未传 `--identity`
- **THEN** 系统 SHALL 以 `human` 身份作为默认值

### Requirement: Entity 子命令
`edera entity` SHALL 提供 entity 的完整 CRUD 和查询操作（create、get、list、update、delete、query）。

#### Scenario: Entity create
- **WHEN** 用户执行 `edera entity create --type node --id my-node --attr handler=my_handler`
- **THEN** 系统 SHALL 创建 entity 并返回创建结果

#### Scenario: 获取单个 entity
- **WHEN** 用户执行 `edera entity get stock:AAPL`
- **THEN** 系统 SHALL 输出该 entity 的完整 attributes

#### Scenario: 列出指定类型的 entities
- **WHEN** 用户执行 `edera entity list --type stock`
- **THEN** 系统 SHALL 输出所有 type 为 stock 的 entity 列表

#### Scenario: 更新 entity 字段
- **WHEN** 用户执行 `edera entity update stock:AAPL --field sentiment --value bearish`
- **THEN** 系统 SHALL 更新该字段并持久化

#### Scenario: 查询 entity
- **WHEN** 用户执行 `edera entity query "type=analysis AND confidence>0.8"`
- **THEN** 系统 SHALL 通过 `EntityService.Query` rpc 返回满足条件的 entity 列表

#### Scenario: Entity delete
- **WHEN** 用户执行 `edera entity delete node:my-node`
- **THEN** 系统 SHALL 删除该 entity

### Requirement: Node 子命令
`edera node` SHALL 提供节点状态查询、停止、恢复和输出查看能力。

#### Scenario: 查询节点状态
- **WHEN** 用户执行 `edera node status llm-analyze`
- **THEN** 系统 SHALL 输出该节点当前状态（running、idle、failed）

#### Scenario: 停止节点
- **WHEN** 用户执行 `edera node stop llm-analyze`
- **THEN** 系统 SHALL 对该节点当前运行实例执行 soft stop

#### Scenario: 恢复节点
- **WHEN** 用户执行 `edera node resume llm-analyze --prompt "关注宏观经济因素"`
- **THEN** 系统 SHALL 找到该节点最近的 sandbox，以 `--continue` 模式启动 pi 并传入 prompt

#### Scenario: 查看节点输出
- **WHEN** 用户执行 `edera node output llm-analyzer --cycle-id abc123`
- **THEN** 系统 SHALL 通过 `NodeService.Output` rpc 返回该节点在指定 cycle 中的输出内容

### Requirement: DAG 子命令
`edera dag` SHALL 提供 DAG 触发、状态查询和拓扑编辑能力。

#### Scenario: 触发 DAG 运行
- **WHEN** 用户执行 `edera dag trigger reflection-dag --payload '{"target":"llm-analyze"}'`
- **THEN** 系统 SHALL 创建新的 DAG run 并返回 cycle_id

#### Scenario: 触发 DAG 运行带 inputs
- **WHEN** 用户执行 `edera dag trigger my-dag --input ticker=00100.HK`
- **THEN** 系统 SHALL 通过 `DagService.Trigger` rpc 启动 DAG 并将 inputs 传递给运行时

#### Scenario: 查询 DAG 运行历史
- **WHEN** 用户执行 `edera dag status my-dag`
- **THEN** 系统 SHALL 返回该 DAG 的最近 10 次运行记录（cycle_id、状态、时间）

#### Scenario: 添加节点到 DAG
- **WHEN** 用户执行 `edera dag edit my-dag add-node --type fetch --alias fetcher-1`
- **THEN** 系统 SHALL 在 DAG 配置中添加该节点实例

#### Scenario: 添加边
- **WHEN** 用户执行 `edera dag edit my-dag add-edge --from node-a --to node-b`
- **THEN** 系统 SHALL 在 DAG 配置中添加该边

#### Scenario: 删除边
- **WHEN** 用户执行 `edera dag edit my-dag remove-edge --from node-a --to node-b`
- **THEN** 系统 SHALL 从 DAG 配置中删除该边

### Requirement: Client 一键初始化
`edera client init` SHALL 一键完成客户端配置，包括连接 bootstrap 端口、请求签发 client cert、保存到 `~/.edera/`。

#### Scenario: Client init 成功
- **WHEN** 用户执行 `edera client init --server 127.0.0.1:9091`
- **THEN** CLI SHALL 通过 `SystemService.InitClient` 请求签发 client cert
- **AND** CLI SHALL 将 cert 保存到 `~/.edera/client.crt`、`~/.edera/client.key`、`~/.edera/ca.crt`

#### Scenario: 远程 init 走 SSH 隧道
- **WHEN** server 部署在远程主机，用户希望执行 `client init`
- **THEN** 用户 SHALL 通过 SSH 隧道（如 `ssh -L 9091:localhost:9091 server.lan`）转发 bootstrap 端口
- **AND** 然后本地执行 `edera client init --server 127.0.0.1:9091`

### Requirement: 权限检查
`edera` CLI SHALL 通过 `edera-server` 在执行 entity 操作时检查调用者身份对应的 entity_permissions。

#### Scenario: 权限允许
- **WHEN** 身份为 `node:llm-analyze`，该节点配置 `entity_permissions: {stock: {sentiment: read-write}}`，执行 `edera entity update stock:AAPL --field sentiment --value bearish`
- **THEN** 系统 SHALL 允许操作并执行更新

#### Scenario: 权限拒绝
- **WHEN** 身份为 `node:llm-analyze`，该节点未配置对 `stock.code` 的写权限，执行 `edera entity update stock:AAPL --field code --value 001`
- **THEN** 系统 SHALL 拒绝操作并输出 "Permission denied: node:llm-analyze cannot write stock.code"

#### Scenario: Human 身份无限制
- **WHEN** 身份为 `human`，执行任意 entity 操作
- **THEN** 系统 SHALL 允许操作（human 身份不受 entity_permissions 限制）

### Requirement: 纯 gRPC 客户端契约
`edera` CLI SHALL 作为纯 gRPC client 连接 `edera-server`。所有 entity / node / dag 子命令 MUST 通过 gRPC 调用 server，MUST NOT 直接读取 `EntityStore` 或 config 目录。

#### Scenario: 所有数据操作走 gRPC
- **WHEN** 用户执行 `edera entity get`、`edera node status`、`edera dag trigger` 等任意数据子命令
- **THEN** CLI SHALL 通过 `GrpcClient` 调用 `edera-server`，不实例化 `EntityStore`、不调用 `load_app_config`

#### Scenario: handler-validate 离线特例
- **WHEN** 用户执行 `edera handler-validate <path>`
- **THEN** CLI SHALL 直接读取 handler 文件并执行 schema 校验，MUST NOT 连接 gRPC server

#### Scenario: client init 与 edera-server 特例
- **WHEN** 用户执行 `edera client init` 或 `edera-server` 命令
- **THEN** 命令 SHALL 不通过 gRPC 主端口；`client init` 走 bootstrap 端口，`edera-server` 自身即 server

### Requirement: gRPC Client mTLS 加载
`edera` CLI SHALL 作为 gRPC client 连接 `edera-server`。证书加载语义：gRPC client 层 SHALL 仅从环境变量读取 PEM 内容，不读文件系统；文件读取由 CLI 入口层在 dispatch 子命令前显式完成（针对 human-facing 子命令）。

#### Scenario: gRPC 连接 server
- **WHEN** 用户执行任意 `edera` 数据子命令
- **THEN** CLI SHALL 通过 gRPC 连接 `edera-server`，使用 mTLS 认证

#### Scenario: gRPC client 层只看环境变量
- **WHEN** `GrpcClient` 实例化（非 `EDERA_DEV` 模式）
- **THEN** 系统 SHALL 仅从 `EDERA_CLIENT_CERT` / `EDERA_CLIENT_KEY` / `EDERA_CA_CERT` 环境变量读取 PEM 内容
- **AND** SHALL NOT 访问 `~/.edera/` 或任何文件系统路径

#### Scenario: 环境变量 PEM 内容缺失即失败
- **WHEN** `EDERA_CLIENT_CERT`、`EDERA_CLIENT_KEY`、`EDERA_CA_CERT` 任一环境变量未设置，且未启用 `EDERA_DEV` 模式
- **THEN** `GrpcClient` SHALL 抛出 `FileNotFoundError`（或等价错误），SHALL NOT 静默回退到任何文件路径

#### Scenario: 人类 CLI 入口显式注入
- **WHEN** 用户执行 human-facing 子命令（如 `edera entity list`），且环境变量 `EDERA_CLIENT_CERT` 等未预先设置
- **THEN** CLI 入口层 SHALL 在调用 `GrpcClient` 前读取 `~/.edera/client.crt`、`~/.edera/client.key`、`~/.edera/ca.crt` 内容并写入对应环境变量

#### Scenario: 环境变量已设置时不覆盖
- **WHEN** 用户执行 human-facing 子命令，且 `EDERA_CLIENT_CERT` 环境变量已显式设置
- **THEN** CLI 入口层 SHALL NOT 读取 `~/.edera/client.crt`，SHALL 保留环境变量原值

#### Scenario: bootstrap 子命令跳过注入
- **WHEN** 用户执行 `edera client init` 或 `edera-server` 子命令
- **THEN** CLI 入口层 SHALL NOT 读取 `~/.edera/` 文件，SHALL NOT 写入 `EDERA_CLIENT_CERT` 等环境变量

### Requirement: 服务端连接环境变量
`edera` CLI SHALL 使用 `EDERA_SERVER_ADDR` 环境变量或 `--server` flag 指定连接 `edera-server` 的地址，无默认值。

#### Scenario: 通过 env 指定 server addr
- **WHEN** 环境变量 `EDERA_SERVER_ADDR=server.lan:9090` 已设置
- **THEN** CLI SHALL 连接 `server.lan:9090`

#### Scenario: 通过 flag 覆盖
- **WHEN** 环境变量 `EDERA_SERVER_ADDR=a.lan:9090` 已设置，用户执行 `edera --server b.lan:9090 entity list`
- **THEN** CLI SHALL 连接 `b.lan:9090`，忽略环境变量

#### Scenario: 未设置 server addr 即失败
- **WHEN** 用户执行任意数据子命令，但 `EDERA_SERVER_ADDR` 未设置且未传 `--server`
- **THEN** CLI SHALL 输出错误 "EDERA_SERVER_ADDR not set" 并以非零状态退出

### Requirement: handler-validate 离线工具
`edera handler-validate <path>` SHALL 在不连接 server 的情况下校验 handler 文件的 schema 合法性。

#### Scenario: 合法 handler 文件
- **WHEN** 用户执行 `edera handler-validate extensions/my-handler/handler.py`，文件 schema 合法
- **THEN** 系统 SHALL 输出 "ok" 并以 0 状态退出

#### Scenario: 非法 handler 文件
- **WHEN** 用户执行 `edera handler-validate <path>`，文件 schema 不合法
- **THEN** 系统 SHALL 输出错误信息列表并以非零状态退出

