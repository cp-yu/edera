## Purpose

定义本机 Web 控制台基础能力，包括默认本机监听、浏览器访问、统一导航和 WebUI API 错误格式。
## Requirements
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

### Requirement: Console navigation
系统 SHALL 通过 JSON API 提供所有功能入口，前端 SPA 负责导航渲染。面向用户的浏览器界面 SHALL 统一称为 `Web Console` / 本机 Web 控制台。

#### Scenario: API-only service
- **WHEN** 客户端访问非 `/api/` 前缀的路径
- **THEN** 系统 SHALL 返回 404（前端路由由 nginx 处理）

#### Scenario: Web Console naming
- **WHEN** README 或活 OpenSpec 描述浏览器界面
- **THEN** 文档 SHALL 使用 `Web Console` 或本机 Web 控制台
- **AND** SHOULD NOT 使用 `WebConsole` 或 `WebUI`

### Requirement: JSON API error format
系统 SHALL 对所有 API 返回一致的错误结构，包含错误类型和可读消息。

#### Scenario: API validation error
- **WHEN** 客户端提交非法请求数据
- **THEN** 系统 MUST 返回非 2xx 状态码和包含错误消息的 JSON 响应

### Requirement: CORS middleware
系统 SHALL 提供 CORS 中间件支持前端开发服务器跨域访问。

#### Scenario: Allow dev server origin
- **WHEN** 前端开发服务器（`http://localhost:5173`）发送跨域请求
- **THEN** 系统 SHALL 返回正确的 CORS 响应头允许该请求

#### Scenario: Preflight OPTIONS request
- **WHEN** 浏览器发送 OPTIONS 预检请求
- **THEN** 系统 SHALL 返回 200 和正确的 `Access-Control-Allow-*` 头

