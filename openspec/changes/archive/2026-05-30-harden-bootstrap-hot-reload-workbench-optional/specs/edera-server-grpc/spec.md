## MODIFIED Requirements

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

