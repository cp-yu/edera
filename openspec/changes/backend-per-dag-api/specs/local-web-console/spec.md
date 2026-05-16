## MODIFIED Requirements

### Requirement: Local-only web binding
系统 SHALL 提供本机 API 服务器，默认只监听 `127.0.0.1`，仅提供 JSON API 端点。

#### Scenario: Default local host API-only
- **WHEN** 用户以默认配置启动 Web 服务
- **THEN** 系统 MUST 只绑定 `127.0.0.1`，仅提供 `/api/*` 路由，不提供 HTML 页面或静态文件

### Requirement: Console navigation
系统 SHALL 通过 JSON API 提供所有功能入口，前端 SPA 负责导航渲染。

#### Scenario: API-only service
- **WHEN** 客户端访问非 `/api/` 前缀的路径
- **THEN** 系统 SHALL 返回 404（前端路由由 nginx 处理）

### Requirement: JSON API error format
系统 SHALL 对所有 API 返回一致的错误结构，包含错误类型和可读消息。

#### Scenario: API validation error
- **WHEN** 客户端提交非法请求数据
- **THEN** 系统 MUST 返回非 2xx 状态码和包含错误消息的 JSON 响应

## ADDED Requirements

### Requirement: CORS middleware
系统 SHALL 提供 CORS 中间件支持前端开发服务器跨域访问。

#### Scenario: Allow dev server origin
- **WHEN** 前端开发服务器（`http://localhost:5173`）发送跨域请求
- **THEN** 系统 SHALL 返回正确的 CORS 响应头允许该请求

#### Scenario: Preflight OPTIONS request
- **WHEN** 浏览器发送 OPTIONS 预检请求
- **THEN** 系统 SHALL 返回 200 和正确的 `Access-Control-Allow-*` 头

## REMOVED Requirements

### Requirement: Local browser access
**Reason**: 前端 SPA 由 nginx 独立托管，FastAPI 不再提供 HTML 页面和静态资源
**Migration**: 前端静态文件通过 nginx `try_files` 提供，API 通过 nginx `proxy_pass` 转发到 FastAPI
