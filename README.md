# Edera

以 Entity 为统一原语、以 DAG 为执行模型的通用编排内核。

`Edera` 源自 `Entity`、`DAG`、`Execution`、`Runtime`、`Architecture` 的组合。`edera` 也有 ivy（常春藤）含义，项目借用其连接、攀附、延展的隐喻。

## 本机 Web 控制台

启动服务：

```bash
uv run edera
```

默认地址是 `http://127.0.0.1:8000`。`config/system.toml` 中的 `web_host` 固定校验为
`127.0.0.1`，默认不会绑定 `0.0.0.0` 或暴露公网。

控制台提供三个入口：

- 结果：最新简报、建议、证据 URL 和失败源。
- 管道：手动运行、暂停/恢复调度、停止当前运行和最近运行记录。
- 配置：编辑 `config/` 与 `skills/` 下的运行时配置，保存前执行校验。

## MiniMax 信息获取验收

`config/portfolio.yaml` 内置 `minimax-docs` Web 信息源，用于从 MiniMax 官方公开文档验证非标准源信息获取、管道处理和 Web API 证据链展示。该验收不调用 MiniMax 付费 API，不需要 API key，也不会把凭据写入仓库。
