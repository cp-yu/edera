## MODIFIED Requirements

### Requirement: Local-only web binding
`edera-web` SHALL 提供 Edera HTTP API 服务器，默认监听 `127.0.0.1:8000`，仅提供 JSON API 端点。监听地址 SHALL 通过 `--bind`/`--port` flag 或 `EDERA_WEB_BIND`/`EDERA_WEB_PORT` 环境变量控制（flag 优先）。FastAPI / OpenAPI title SHALL 使用 `Edera`。

#### Scenario: Default local host API-only
- **WHEN** 用户以默认配置启动 `edera-web`
- **THEN** 系统 MUST 绑定 `127.0.0.1:8000`，仅提供 `/api/*` 路由，不提供 HTML 页面或静态文件

#### Scenario: 自定义 bind 地址
- **WHEN** 用户启动 `edera-web --bind 0.0.0.0 --port 8080`
- **THEN** 系统 SHALL 监听 `0.0.0.0:8080`

#### Scenario: env fallback
- **WHEN** 用户启动 `edera-web` 不带 flag，但 `EDERA_WEB_BIND=0.0.0.0` 与 `EDERA_WEB_PORT=8080` 已设置
- **THEN** 系统 SHALL 监听 `0.0.0.0:8080`

#### Scenario: API title
- **WHEN** 客户端读取 OpenAPI metadata
- **THEN** API title SHALL 为 `Edera`

#### Scenario: 不读 system.toml web 字段
- **WHEN** `edera-web` 启动
- **THEN** 进程 MUST NOT 读取 `config/system.toml` 中的 `web_host` 或 `web_port` 字段
- **AND** 配置目录加载逻辑 MUST NOT 出现在 `edera-web` 进程内
