# edera-web-bff Specification

## Purpose
定义 `edera-web` 网页 BFF 的纯 gRPC client 角色、启动配置、BFF cert 内存模式和服务端部署拓扑。

## Requirements

### Requirement: edera-web 纯 BFF 角色
`edera-web` SHALL 作为纯 BFF（Backend for Frontend）运行，进程内 MUST NOT 实例化 `PipelineController`，所有数据操作 MUST 通过 gRPC 调用 `edera-server`。

#### Scenario: create_app 单一签名
- **WHEN** 检查 `web/app.py` 的 `create_app` 函数签名
- **THEN** 函数 SHALL 仅接受 `grpc_client` 参数，MUST NOT 接受 `controller` 或 `config_dir`、`handler_registry` 参数

#### Scenario: 不实例化 controller
- **WHEN** `edera-web` 启动
- **THEN** 进程 MUST NOT 实例化 `PipelineController`，MUST NOT 调用 `load_app_config`

#### Scenario: 必须依赖 edera-server
- **WHEN** `edera-web` 启动但 `EDERA_SERVER_ADDR` 未设置
- **THEN** 进程 SHALL 输出错误 "EDERA_SERVER_ADDR not set" 并以非零状态退出

### Requirement: 配置无知契约
`edera-web` 进程 SHALL NOT 读取 `config/` 目录或 `system.toml`。所有面向前端的 entity types、DAG 定义等元数据 MUST 通过 gRPC 拉取。

#### Scenario: 不读 config 目录
- **WHEN** `edera-web` 启动
- **THEN** 进程 MUST NOT 调用 `load_app_config`，MUST NOT 读取 `config/system.toml` 中的 `web_host`/`web_port`

#### Scenario: Entity types 通过 gRPC 拉
- **WHEN** 浏览器通过 BFF 请求 entity types 列表
- **THEN** BFF SHALL 通过 `EntityService.List(type="entity_type")` 调用 `edera-server`，不在本地缓存配置目录内容

### Requirement: BFF cert 内存模式
`edera-web` 启动时 SHALL 调用本地 `127.0.0.1:9091` bootstrap 端口的 `SystemService.InitClient(common_name="bff:web-console")` 拿 client cert，PEM 内容仅保留在进程内存，MUST NOT 写入文件系统。

#### Scenario: 启动时拿 cert
- **WHEN** `edera-web` 启动
- **THEN** 进程 SHALL 调用 `127.0.0.1:9091` 的 `SystemService.InitClient`，得到 BFF client cert/key/ca PEM
- **AND** SHALL 用该 cert 构造 `GrpcClient` 连 `EDERA_SERVER_ADDR`

#### Scenario: cert 不落盘
- **WHEN** BFF cert 签发完成
- **THEN** 进程 MUST NOT 创建 `~/.edera/bff/` 或任何持久化目录
- **AND** SHALL NOT 设置 `EDERA_BFF_DIR` / `RIG_BFF_DIR` 环境变量

#### Scenario: 重启自愈
- **WHEN** `edera-web` 进程因任意原因重启
- **THEN** 进程 SHALL 重新调用 bootstrap 拿新 cert，不依赖任何持久化状态

### Requirement: --bind 与 --port 配置
`edera-web` 启动时 SHALL 接受 `--bind`/`--port` flag，未传时回退到 `EDERA_WEB_BIND`/`EDERA_WEB_PORT` 环境变量，再无则使用默认值 `127.0.0.1:8000`。

#### Scenario: 默认监听
- **WHEN** `edera-web` 启动且既未传 flag 也未设 env
- **THEN** 进程 SHALL 监听 `127.0.0.1:8000`

#### Scenario: flag 优先
- **WHEN** 用户启动 `edera-web --bind 0.0.0.0 --port 8080`，且 `EDERA_WEB_BIND=192.168.1.10` 已设置
- **THEN** 进程 SHALL 监听 `0.0.0.0:8080`，忽略环境变量

#### Scenario: env fallback
- **WHEN** 用户启动 `edera-web` 不带 flag，但 `EDERA_WEB_BIND=0.0.0.0` 与 `EDERA_WEB_PORT=8080` 已设置
- **THEN** 进程 SHALL 监听 `0.0.0.0:8080`

### Requirement: 客户端 / 服务端拓扑
`edera-web` SHALL 与 `edera-server` 部署在同一台服务端主机；浏览器从客户端连接 `edera-web` HTTP 端口；CLI 在客户端机器直接连 `edera-server` gRPC 端口。

#### Scenario: 同机部署
- **WHEN** 部署 Edera 服务端
- **THEN** `edera-server` 与 `edera-web` SHALL 跑在同一主机
- **AND** `edera-web` SHALL 通过 `127.0.0.1:9091` bootstrap 端口拿 cert
- **AND** `edera-web` SHALL 通过 `EDERA_SERVER_ADDR`（通常 `127.0.0.1:9090`）连 `edera-server` 主端口
