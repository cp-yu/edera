## ADDED Requirements

### Requirement: Local-only web binding
系统 SHALL 提供本机 Web 控制台，并且默认只监听 `127.0.0.1`。

#### Scenario: Default local host
- **WHEN** 用户以默认配置启动 Web 控制台
- **THEN** 系统 MUST 只绑定 `127.0.0.1`，不得默认绑定 `0.0.0.0`

#### Scenario: Local browser access
- **WHEN** 用户在本机浏览器访问 Web 控制台地址
- **THEN** 系统 SHALL 返回控制台页面和所需静态资源

### Requirement: Console navigation
系统 SHALL 提供统一导航入口，使用户可以访问结果、运行控制和配置编辑页面。

#### Scenario: Navigate console sections
- **WHEN** 用户打开控制台首页
- **THEN** 系统 SHALL 展示结果浏览、管道控制、配置编辑三个主要入口

### Requirement: JSON API error format
系统 SHALL 对 WebUI 使用的 API 返回一致的错误结构，包含错误类型和可读消息。

#### Scenario: API validation error
- **WHEN** 用户提交非法请求数据
- **THEN** 系统 MUST 返回非 2xx 状态码和包含错误消息的 JSON 响应
