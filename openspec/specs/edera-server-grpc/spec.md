---
capabilities:
  - cap.core.edera-server-grpc
---
# edera-server-grpc Specification

## Purpose
定义 `edera-server` 后端引擎的 gRPC service、mTLS、bootstrap 端口、证书签发、数据目录和 dev 模式语义。
## Requirements
### Requirement: gRPC Service 定义
`edera-server` SHALL 暴露 gRPC 服务，包含 `EntityService`、`DagService`、`NodeService`、`SystemService`、`GraphService`、`ConfigService`、`QueryService`、`EventService` 八个 service。`PipelineService` 已废弃，职责分散到 `DagService`、`EventService`、`SystemService`。Proto package 为 `edera.v1`，文件路径 `proto/edera.proto`。

#### Scenario: EntityService 提供 CRUD
- **WHEN** 客户端调用 `EntityService.Create`
- **THEN** server SHALL 创建 entity 并返回创建结果

#### Scenario: EntityService 提供 Query
- **WHEN** 客户端调用 `EntityService.Query` 携带表达式 `type=analysis AND confidence>0.8`
- **THEN** server SHALL 解析表达式并返回满足条件的 entity 列表

#### Scenario: EntityService 保留 List
- **WHEN** 客户端调用 `EntityService.List` 携带 `EntityQuery{type: "stock"}`
- **THEN** server SHALL 返回该类型的所有 entity，不解析任何表达式

#### Scenario: DagService 提供运行和查询
- **WHEN** 客户端调用 `DagService.Run`
- **THEN** server SHALL 启动 DAG 执行并返回 `DagRunRef{run_id: "..."}`

#### Scenario: DagService 提供停止和重试
- **WHEN** 客户端调用 `DagService.Stop` 或 `DagService.Retry`
- **THEN** server SHALL 执行对应操作并返回结果

#### Scenario: EventService 提供事件注入
- **WHEN** 客户端调用 `EventService.Emit`
- **THEN** server SHALL 注入事件到 EventGroup 并触发 trigger 表达式评估

#### Scenario: SystemService 提供 scheduler 控制
- **WHEN** 客户端调用 `SystemService.PauseScheduler`
- **THEN** server SHALL 暂停 TriggerExecutor 的 cron 循环

#### Scenario: GraphService 注册到 server
- **WHEN** `edera-server` 启动
- **THEN** server SHALL 通过 `add_GraphServiceServicer_to_server` 注册 GraphService 实现

#### Scenario: ConfigService 注册到 server
- **WHEN** `edera-server` 启动
- **THEN** server SHALL 通过 `add_ConfigServiceServicer_to_server` 注册 ConfigService 实现

#### Scenario: QueryService 注册到 server
- **WHEN** `edera-server` 启动
- **THEN** server SHALL 通过 `add_QueryServiceServicer_to_server` 注册 QueryService 实现

#### Scenario: EventService 注册到 server
- **WHEN** `edera-server` 启动
- **THEN** server SHALL 通过 `add_EventServiceServicer_to_server` 注册 EventService 实现

#### Scenario: Proto package 为 edera.v1
- **WHEN** 检查 `proto/edera.proto` 文件
- **THEN** 文件 SHALL 声明 `package edera.v1`
- **AND** SHALL NOT 包含任何 `rig.v1` 引用

### Requirement: Vendor 生成的 pb2
`edera-server` 与 client 端依赖的 protobuf 生成代码 SHALL vendor 至 `packages/core/src/edera_core/proto/`，跟踪入 git。MUST NOT 在启动时通过 `grpc_tools.protoc` 动态生成到 tempdir。

#### Scenario: pb2 文件入库
- **WHEN** 检查 `packages/core/src/edera_core/proto/`
- **THEN** 目录 SHALL 包含 `__init__.py`、`edera_pb2.py`、`edera_pb2_grpc.py`
- **AND** 三个文件 SHALL 跟踪在 git 中

#### Scenario: 重生成命令
- **WHEN** 开发者修改 `proto/edera.proto`
- **THEN** 开发者 SHALL 执行 `scripts/gen_proto.sh` 重生成 pb2 文件
- **AND** SHALL 将更新后的 pb2 文件提交至 git

#### Scenario: 启动不调用 protoc
- **WHEN** `edera-server` 启动
- **THEN** server SHALL 直接 import `edera_core.proto` 子包，MUST NOT 调用 `grpc_tools.protoc`

### Requirement: mTLS 传输安全
`edera-server` SHALL 使用 mTLS 进行传输加密和客户端身份认证。Server SHALL 持有 server cert，客户端 SHALL 持有 client cert。

#### Scenario: 客户端证书验证
- **WHEN** 客户端连接 server 但未提供有效 client cert
- **THEN** server SHALL 拒绝连接

#### Scenario: 从证书 CN 提取身份
- **WHEN** 客户端连接成功，cert CN 为 `node:llm-analyzer`
- **THEN** server SHALL 提取身份为 `node:llm-analyzer`，用于权限判断

### Requirement: Agent 短期证书签发
Server 启动 agent 节点前，SHALL 使用内部 CA 签发短期 client cert，CN 为 `node:{instance_id}`，TTL 对齐节点 timeout。签发后 SHALL 将 PEM 内容保持在内存中，通过环境变量注入 subprocess，不写入文件系统。

#### Scenario: Agent 节点证书签发
- **WHEN** server 启动 agent 节点 `llm-analyzer`
- **THEN** server SHALL 签发 client cert，CN=`node:llm-analyzer`，TTL=节点 timeout

#### Scenario: 证书通过环境变量注入 PEM 内容
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `EDERA_CLIENT_CERT` SHALL 包含签发的 client cert PEM 文本内容（非文件路径）

#### Scenario: 私钥通过环境变量注入 PEM 内容
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `EDERA_CLIENT_KEY` SHALL 包含签发的 client key PEM 文本内容（非文件路径）

#### Scenario: CA cert 通过环境变量注入 PEM 内容
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `EDERA_CA_CERT` SHALL 包含 server CA cert PEM 文本内容

#### Scenario: 证书不落盘
- **WHEN** server 完成 agent cert 签发
- **THEN** server SHALL 不将 cert 或 key 写入文件系统

#### Scenario: Resume 重新签发
- **WHEN** 用户调用 resume API 恢复已停止的 agent 节点
- **THEN** server SHALL 重新签发新的短期 cert（新 TTL），不复用旧 cert

### Requirement: BFF 短期证书签发
`edera-server` SHALL 通过实际绑定的本机 bootstrap 端口接受本机 BFF 进程的 cert 请求，签发 CN 为 `bff:web-console` 的短期 client cert，TTL 7 天，通过 gRPC 响应返回 PEM 内容。

#### Scenario: BFF 启动时拿 cert
- **WHEN** 同机 `edera-web` 进程启动并调用 `bootstrap.json` 中记录的 `127.0.0.1:{port}` 的 `SystemService.InitClient(common_name="bff:web-console")`
- **THEN** server SHALL 签发 CN=`bff:web-console`、TTL=7 天的 client cert
- **AND** SHALL 通过 gRPC 响应返回 cert/key/ca PEM 文本

### Requirement: Bootstrap 端口硬绑 localhost
`edera-server` 的 bootstrap bind 地址 SHALL 硬绑 `127.0.0.1`，MUST NOT 接受任何 env 或 flag 配置外暴露。Bootstrap port SHALL 默认从 `9091` 开始有界退避到首个可用端口。Server SHALL 将实际绑定的本机 bootstrap endpoint 写入 `EDERA_DATA_DIR/bootstrap.json`，供同机 BFF 读取。远程客户端首次拿 cert 必须按实际端口建立 SSH 隧道。

#### Scenario: Bootstrap 监听限制
- **WHEN** `edera-server` 启动
- **THEN** bootstrap server SHALL 监听 `127.0.0.1:{port}`
- **AND** `{port}` SHALL 是有界 fallback 范围内首个可用端口
- **AND** SHALL NOT 监听 `0.0.0.0` 或任何外部网卡地址

#### Scenario: 不接受 bootstrap bind 配置
- **WHEN** 用户尝试通过环境变量或 flag 配置 bootstrap 监听地址
- **THEN** server SHALL 忽略该配置，继续硬绑 `127.0.0.1`

#### Scenario: Bootstrap 端口退避
- **WHEN** `127.0.0.1:9091` 已被占用且 fallback 范围内存在可用端口
- **THEN** bootstrap server SHALL 绑定 fallback 范围内首个可用端口
- **AND** server SHALL 记录实际端口到 `EDERA_DATA_DIR/bootstrap.json`

#### Scenario: Bootstrap 状态文件
- **WHEN** bootstrap server 成功启动
- **THEN** `EDERA_DATA_DIR/bootstrap.json` SHALL 包含 `host` 为 `127.0.0.1` 和实际 `port`
- **AND** 文件 MUST NOT 包含 token、cert、key 或 `EDERA_SERVER_ADDR`

#### Scenario: Bootstrap 端口耗尽
- **WHEN** fallback 范围内所有 bootstrap 端口均不可用
- **THEN** `edera-server` SHALL 启动失败并报告 bootstrap 端口不可用

#### Scenario: 远程客户端通过 SSH 隧道
- **WHEN** 远程客户端首次执行 `edera client init`
- **THEN** 用户 SHALL 先按服务端实际 bootstrap port 建立 SSH 隧道
- **AND** 然后客户端连隧道本地端口拿 cert

### Requirement: 主端口 bind 与 SAN 配置
`edera-server` 主端口 bind 地址 SHALL 由 `EDERA_SERVER_BIND` 环境变量控制（default `0.0.0.0:9090`），server cert SAN SHALL 由 `EDERA_SERVER_PUBLIC_HOST` 环境变量控制。

#### Scenario: 默认 bind 0.0.0.0:9090
- **WHEN** `edera-server` 启动且未设置 `EDERA_SERVER_BIND`
- **THEN** server SHALL 监听 `0.0.0.0:9090`

#### Scenario: 自定义 bind 地址
- **WHEN** 环境变量 `EDERA_SERVER_BIND=192.168.1.10:9090` 已设置
- **THEN** server SHALL 监听 `192.168.1.10:9090`

#### Scenario: SAN 由 PUBLIC_HOST 控制
- **WHEN** 环境变量 `EDERA_SERVER_PUBLIC_HOST=edera.lan` 已设置，server cert 不存在
- **THEN** server SHALL 签发 server cert，SAN 包含 `edera.lan` 与 `localhost`

#### Scenario: SAN 不匹配触发重签
- **WHEN** 已存在 `server.crt` 的 SAN 与 `EDERA_SERVER_PUBLIC_HOST` 不匹配
- **THEN** server SHALL 用新 SAN 重签 server.crt，旧 client cert（由原 CA 签发）继续有效

### Requirement: 数据目录与配置目录
`edera-server` SHALL 使用 `EDERA_DATA_DIR` 环境变量管理 daemon 数据目录（default `~/.local/share/edera-server/`），使用 `EDERA_CONFIG_DIR` 环境变量或 `--config-dir` flag 指定配置目录（无 default，flag-first + env-fallback）。

#### Scenario: 默认数据目录
- **WHEN** `edera-server` 启动且未设置 `EDERA_DATA_DIR`
- **THEN** server SHALL 使用 `~/.local/share/edera-server/` 作为数据目录

#### Scenario: 自定义数据目录
- **WHEN** 环境变量 `EDERA_DATA_DIR=/var/lib/edera-server` 已设置
- **THEN** server SHALL 使用该路径作为数据目录

#### Scenario: 配置目录 flag 优先
- **WHEN** 用户启动 `edera-server --config-dir ./config`，且环境变量 `EDERA_CONFIG_DIR=/etc/edera/config` 已设置
- **THEN** server SHALL 使用 `./config`，忽略环境变量

#### Scenario: 配置目录 env fallback
- **WHEN** 用户启动 `edera-server` 不带 `--config-dir`，但环境变量 `EDERA_CONFIG_DIR=/etc/edera/config` 已设置
- **THEN** server SHALL 使用 `/etc/edera/config`

#### Scenario: 配置目录缺失即失败
- **WHEN** 用户启动 `edera-server` 既未传 `--config-dir` 也未设置 `EDERA_CONFIG_DIR`
- **THEN** server SHALL 输出错误并以非零状态退出

### Requirement: Dev 模式
`edera-server` SHALL 支持 dev 模式（`EDERA_DEV=1`），在该模式下 SHALL 放宽安全限制，支持本地开发场景。dev 模式 SHALL 是单一布尔开关，不假装环境枚举。

#### Scenario: Dev 模式允许无证书连接
- **WHEN** server 运行在 `EDERA_DEV=1`，且客户端连接未提供 client cert
- **THEN** server SHALL 允许连接，身份默认为 `human:dev`

#### Scenario: Dev + 外部监听冲突警告
- **WHEN** server 启动时同时检测到 `EDERA_DEV=1` 与 `EDERA_SERVER_BIND` 指向非 `127.0.0.1` 地址
- **THEN** server SHALL 输出 WARN 日志提示该组合不安全

### Requirement: 权限判断
Server SHALL 根据客户端身份（从 cert CN 提取）查找对应的 `entity_permissions`，执行权限校验。

#### Scenario: Agent 节点权限校验
- **WHEN** 客户端身份为 `node:llm-analyzer`，调用 `EntityService.Update`
- **THEN** server SHALL 查找该节点的 `entity_permissions`，校验是否允许写入目标字段

### Requirement: DagRunRef 使用 run_id
Proto message `DagRunRef` SHALL 使用 `run_id` 字段标识 DAG 执行实例，不再使用 `cycle_id`。

#### Scenario: DagRunRef 字段定义
- **WHEN** 检查 `proto/edera.proto` 中的 `DagRunRef` message
- **THEN** message SHALL 包含 `string run_id = 1;` 字段
- **AND** SHALL NOT 包含 `cycle_id` 字段

#### Scenario: DagService.Run 返回 run_id
- **WHEN** 客户端调用 `DagService.Run`
- **THEN** server SHALL 返回 `DagRunRef{run_id: "<uuid>"}`

