---
capabilities:
  - cap.core.edera-cli
---
# edera-cli Specification

## Purpose
定义 `edera` 控制 CLI 的 binary 入口、子命令集合、身份声明、纯 gRPC 客户端契约和 mTLS 加载边界。
## Requirements
### Requirement: CLI binary 入口
系统 SHALL 提供名为 `edera` 的 CLI binary，作为 agent 和人类访问 Edera 控制面能力的统一入口。`edera` 是控制 CLI 的命令名，与 `edera-server`（后端引擎）、`edera-web`（网页 BFF）三个 console scripts 一同构成完整入口集合。

#### Scenario: CLI 可执行
- **WHEN** 用户或 agent 在终端执行 `edera --help`
- **THEN** 系统 SHALL 输出可用子命令列表（entity、node、dag、event、system、client、handler-validate）

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
- **WHEN** 用户执行 `edera node output llm-analyzer --run-id abc123`
- **THEN** 系统 SHALL 通过 `NodeService.Output` rpc 返回该节点在指定 run 中的输出内容

### Requirement: DAG 子命令
`edera dag` SHALL 提供 DAG 运行、停止、重试和状态查询能力。`edera dag trigger` 命令已废弃，改为 `edera dag run`。

#### Scenario: DAG 手动运行
- **WHEN** 用户执行 `edera dag run my-dag --inputs '{"symbol": "AAPL"}'`
- **THEN** 系统 SHALL 调用 `DagService.Run` 启动 DAG 并返回 run_id

#### Scenario: DAG 停止
- **WHEN** 用户执行 `edera dag stop my-dag`
- **THEN** 系统 SHALL 调用 `DagService.Stop` 停止当前运行的 DAG

#### Scenario: DAG 重试
- **WHEN** 用户执行 `edera dag retry my-dag --run-id abc123 --nodes node1,node2`
- **THEN** 系统 SHALL 调用 `DagService.Retry` 从指定节点重新执行

#### Scenario: DAG 状态查询
- **WHEN** 用户执行 `edera dag status my-dag`
- **THEN** 系统 SHALL 输出当前 run_id、状态和节点执行情况

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
- **WHEN** 用户执行 `edera entity get`、`edera node status`、`edera dag run` 等任意数据子命令
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

### Requirement: event emit 子命令

`edera` CLI SHALL 新增 `event` 子命令组，包含 `emit` 子命令用于外部事件注入。

#### Scenario: edera event emit 命令

- **WHEN** 用户执行 `edera event emit "event:website-updated" --payload-json '{"url":"https://..."}'`
- **THEN** CLI 通过 mTLS 连接 edera-server，调用 `EventService.Emit` 注入事件

#### Scenario: edera event emit clear 事件

- **WHEN** 用户执行 `edera event emit "clear:event:market-open"`
- **THEN** CLI 调用 `EventService.Emit` 复位 bit

### Requirement: Event 子命令
`edera event` SHALL 提供事件注入能力。`edera trigger emit` 命令已废弃，改为 `edera event emit`。

#### Scenario: 事件注入
- **WHEN** 用户执行 `edera event emit market-open --payload '{"time": "09:30"}'`
- **THEN** 系统 SHALL 调用 `EventService.Emit` 注入事件到 EventGroup

#### Scenario: 带 source 的事件注入
- **WHEN** 用户执行 `edera event emit breaking-news --source external-api`
- **THEN** 系统 SHALL 在 emit 记录中标注 source 为 `external-api`

### Requirement: System 子命令
`edera system` SHALL 提供全局系统控制能力，包括 scheduler 暂停、恢复和状态查询。

#### Scenario: 暂停 scheduler
- **WHEN** 用户执行 `edera system pause-scheduler`
- **THEN** 系统 SHALL 调用 `SystemService.PauseScheduler` 暂停 TriggerExecutor

#### Scenario: 恢复 scheduler
- **WHEN** 用户执行 `edera system resume-scheduler`
- **THEN** 系统 SHALL 调用 `SystemService.ResumeScheduler` 恢复 TriggerExecutor

#### Scenario: Scheduler 状态查询
- **WHEN** 用户执行 `edera system scheduler-status`
- **THEN** 系统 SHALL 输出 scheduler 当前状态（running/paused）

### Requirement: Node 子命令使用 run_id
`edera node` 子命令 SHALL 使用 run_id 参数标识 DAG 执行实例。

#### Scenario: 查看节点输出使用 run_id
- **WHEN** 用户执行 `edera node output llm-analyzer --run-id abc123`
- **THEN** 系统 SHALL 查询该 run_id 下的节点输出

#### Scenario: 恢复节点使用 run_id
- **WHEN** 用户执行 `edera node resume llm-analyze --run-id abc123 --prompt "关注宏观经济因素"`
- **THEN** 系统 SHALL 找到该 run_id 的 sandbox 并恢复执行

### Requirement: Entity YAML 文件工作流

`edera entity` SHALL 支持完整 Entity 文档格式的 YAML import、export 和 template 命令。CLI 数据操作 MUST 通过 gRPC 调用 `edera-server`，MUST NOT 直接读取运行时配置目录作为 source of truth。

#### Scenario: Import entity from YAML file
- **WHEN** 用户执行 `edera entity import --file node.yaml`
- **THEN** CLI SHALL 通过 gRPC 将完整 Entity 文档提交给 server
- **AND** server SHALL 将 Entity 写入对应 DB table

#### Scenario: Export entity to YAML file
- **WHEN** 用户执行 `edera entity export node:reader --file node.yaml`
- **THEN** CLI SHALL 通过 gRPC 从 server 获取 Entity
- **AND** CLI SHALL 写出完整 Entity YAML 文档

#### Scenario: Export template from entity type
- **WHEN** 用户执行 `edera entity template --type node --file node.yaml`
- **THEN** CLI SHALL 通过 gRPC 请求 server 根据 EntityType 生成模板
- **AND** CLI SHALL 写出可被 `edera entity import --file` 消费的完整 Entity YAML 文档

#### Scenario: Reject invalid import file
- **WHEN** `edera entity import --file bad.yaml` 中缺少 `type` 或 `attributes`
- **THEN** 系统 MUST 拒绝导入并返回非零状态

### Requirement: Entity materialization maintenance commands

`edera entity-type` SHALL 提供普通 EntityType 字段物化维护命令，用于 plan、apply 和 inspect materialized fields。命令 MUST 通过 gRPC 调用 server，MUST NOT 直接修改数据库 schema。

#### Scenario: Plan field materialization
- **WHEN** 用户执行 `edera entity-type materialize plan stock --field code`
- **THEN** CLI SHALL 返回将要创建的列、索引和回填数量摘要

#### Scenario: Apply field materialization
- **WHEN** 用户执行 `edera entity-type materialize apply stock --field code`
- **THEN** server SHALL 物化该字段并更新 EntityType metadata

#### Scenario: Inspect materialized fields
- **WHEN** 用户执行 `edera entity-type materialize inspect stock`
- **THEN** CLI SHALL 展示 `stock` 的 materialized fields 和 deprecated fields

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

