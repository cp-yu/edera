## ADDED Requirements

### Requirement: Read portfolio config via dedicated endpoint
系统 SHALL 提供 `GET /api/config/portfolio` 端点，返回 portfolio 配置文件的原始 YAML 文本内容。

#### Scenario: Read portfolio config successfully
- **WHEN** 前端请求 `GET /api/config/portfolio`
- **THEN** 系统 SHALL 返回 `{ "content": "<yaml text>" }` 格式的响应

#### Scenario: Portfolio config file missing
- **WHEN** `config/portfolio.yaml` 文件不存在
- **THEN** 系统 MUST 返回 404 错误，包含 `not_found` 错误类型

### Requirement: Read system config via dedicated endpoint
系统 SHALL 提供 `GET /api/config/system` 端点，返回 system 配置文件的原始 TOML 文本内容。

#### Scenario: Read system config successfully
- **WHEN** 前端请求 `GET /api/config/system`
- **THEN** 系统 SHALL 返回 `{ "content": "<toml text>" }` 格式的响应

#### Scenario: System config file missing
- **WHEN** `config/system.toml` 文件不存在
- **THEN** 系统 MUST 返回 404 错误，包含 `not_found` 错误类型
