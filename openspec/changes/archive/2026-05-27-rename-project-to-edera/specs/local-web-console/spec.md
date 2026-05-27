## MODIFIED Requirements

### Requirement: Local-only web binding
系统 SHALL 提供 Edera API 服务器，默认只监听 `127.0.0.1`，仅提供 JSON API 端点。FastAPI / OpenAPI title SHALL 使用 `Edera`。

#### Scenario: Default local host API-only
- **WHEN** 用户以默认配置启动 Web 服务
- **THEN** 系统 MUST 只绑定 `127.0.0.1`，仅提供 `/api/*` 路由，不提供 HTML 页面或静态文件

#### Scenario: API title
- **WHEN** 客户端读取 OpenAPI metadata
- **THEN** API title SHALL 为 `Edera`

### Requirement: Console navigation
系统 SHALL 通过 JSON API 提供所有功能入口，前端 SPA 负责导航渲染。面向用户的浏览器界面 SHALL 统一称为 `Web Console` / 本机 Web 控制台。

#### Scenario: API-only service
- **WHEN** 客户端访问非 `/api/` 前缀的路径
- **THEN** 系统 SHALL 返回 404（前端路由由 nginx 处理）

#### Scenario: Web Console naming
- **WHEN** README 或活 OpenSpec 描述浏览器界面
- **THEN** 文档 SHALL 使用 `Web Console` 或本机 Web 控制台
- **AND** SHOULD NOT 使用 `WebConsole` 或 `WebUI`
