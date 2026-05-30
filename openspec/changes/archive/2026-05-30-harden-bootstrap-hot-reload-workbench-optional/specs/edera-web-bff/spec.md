## MODIFIED Requirements

### Requirement: BFF cert 内存模式
`edera-web` 启动时 SHALL 从服务端本机 `EDERA_DATA_DIR/bootstrap.json` 读取实际 bootstrap endpoint，并调用该本机端口的 `SystemService.InitClient(common_name="bff:web-console")` 拿 client cert。PEM 内容仅保留在进程内存，MUST NOT 写入文件系统。

#### Scenario: 启动时拿 cert
- **WHEN** `edera-web` 启动且不处于 `EDERA_DEV=1`
- **THEN** 进程 SHALL 读取 `EDERA_DATA_DIR/bootstrap.json` 中的 `host` 和 `port`
- **AND** SHALL 调用该 endpoint 的 `SystemService.InitClient`，得到 BFF client cert/key/ca PEM
- **AND** SHALL 用该 cert 构造 `GrpcClient` 连 `EDERA_SERVER_ADDR`

#### Scenario: bootstrap 状态缺失
- **WHEN** `edera-web` 启动且 `bootstrap.json` 不存在、格式无效或缺少端口
- **THEN** 进程 SHALL 失败退出并报告 bootstrap 状态不可用

#### Scenario: cert 不落盘
- **WHEN** BFF cert 签发完成
- **THEN** 进程 MUST NOT 创建 `~/.edera/bff/` 或任何持久化目录
- **AND** SHALL NOT 设置 `EDERA_BFF_DIR` / `RIG_BFF_DIR` 环境变量

#### Scenario: 重启自愈
- **WHEN** `edera-web` 进程因任意原因重启
- **THEN** 进程 SHALL 重新读取 `bootstrap.json` 并调用 bootstrap 拿新 cert，不依赖任何持久化 cert 状态

### Requirement: 客户端 / 服务端拓扑
`edera-web` SHALL 与 `edera-server` 部署在同一台服务端主机；浏览器从客户端连接 `edera-web` HTTP 端口；CLI 在客户端机器直接连 `edera-server` gRPC 端口。

#### Scenario: 同机部署
- **WHEN** 部署 Edera 服务端
- **THEN** `edera-server` 与 `edera-web` SHALL 跑在同一主机
- **AND** `edera-web` SHALL 通过服务端本机 `bootstrap.json` 指向的 `127.0.0.1:{port}` bootstrap 端口拿 cert
- **AND** `edera-web` SHALL 通过 `EDERA_SERVER_ADDR`（通常 `127.0.0.1:9090`）连 `edera-server` 主端口

#### Scenario: bootstrap.json 不是远程协议
- **WHEN** 远程客户端需要执行 `edera client init`
- **THEN** `edera-web` 的 `bootstrap.json` discovery 机制 SHALL NOT 被用作远程自动发现协议

