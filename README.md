# Edera

以 Entity 为统一原语、以 DAG 为执行模型的通用编排内核。

## 启动拓扑

服务端运行后端引擎和 Web BFF：

```bash
edera-server --config-dir ./config
EDERA_SERVER_ADDR=127.0.0.1:9090 edera-web
```

客户端 CLI 直接连接服务端 gRPC：

```bash
EDERA_SERVER_ADDR=server.lan:9090 edera entity list
```

首次初始化客户端证书时，bootstrap 端口只监听服务端本机 `127.0.0.1:9091`。远程客户端先建立 SSH 隧道：

```bash
ssh -L 9091:localhost:9091 server.lan
edera client init --server 127.0.0.1:9091
```

Web 默认监听 `127.0.0.1:8000`，可通过 `edera-web --bind/--port` 或 `EDERA_WEB_BIND`/`EDERA_WEB_PORT` 调整。

## MiniMax 信息获取验收

`config/portfolio.yaml` 内置 `minimax-docs` Web 信息源，用于从 MiniMax 官方公开文档验证非标准源信息获取、管道处理和 Web API 证据链展示。该验收不调用 MiniMax 付费 API，不需要 API key，也不会把凭据写入仓库。
