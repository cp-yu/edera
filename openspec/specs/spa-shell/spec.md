---
capabilities:
  - cap.web.local-web-console
---
# spa-shell Specification

## Purpose
此规约记录变更 frontend-react-spa 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: SPA routing
系统 SHALL 使用 React Router v6 提供客户端路由，默认路径 `/` 重定向到 `/workbench`。

#### Scenario: Navigate to workbench
- **WHEN** 用户访问根路径 `/`
- **THEN** 系统 SHALL 重定向到 `/workbench` 页面

#### Scenario: Direct URL access
- **WHEN** 用户直接访问 `/results/advices/123`
- **THEN** 系统 SHALL 渲染对应的建议详情页面（由 nginx `try_files` 支持 SPA fallback）

### Requirement: Global navigation
系统 SHALL 提供侧边栏导航，包含工作台、结果、信息源、配置四个入口。

#### Scenario: Navigate between sections
- **WHEN** 用户点击侧边栏导航项
- **THEN** 系统 SHALL 切换到对应页面，当前导航项高亮显示

### Requirement: Theme switching
系统 SHALL 支持暗色和亮色主题切换，用户偏好持久化到 localStorage。

#### Scenario: Toggle theme
- **WHEN** 用户点击主题切换按钮
- **THEN** 系统 SHALL 立即切换所有 UI 元素的配色方案

#### Scenario: Persist theme preference
- **WHEN** 用户切换主题后刷新页面
- **THEN** 系统 SHALL 恢复用户上次选择的主题

### Requirement: API client layer
系统 SHALL 提供类型安全的 API 客户端，统一处理请求/响应和错误。

#### Scenario: API request with error
- **WHEN** API 返回非 2xx 状态码
- **THEN** 系统 SHALL 解析错误响应并通过 toast 通知用户

#### Scenario: API base URL configuration
- **WHEN** 应用在开发环境运行
- **THEN** 系统 SHALL 使用 Vite 环境变量配置的 API base URL（默认 `http://localhost:8000`）

