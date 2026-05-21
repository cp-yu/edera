## MODIFIED Requirements

### Requirement: Read runtime configuration

系统 SHALL 从现有 `config/` 和 `skills/` 目录读取可编辑配置，并通过 WebUI 展示。

#### Scenario: View system config

- **WHEN** 用户打开配置页面
- **THEN** 系统 SHALL 直接展示 System 配置编辑器（TOML 文本），无 tab 切换

#### Scenario: View node and dag config

- **WHEN** 用户打开 Node 或 DAG 配置页面
- **THEN** 系统 SHALL 展示对应 YAML 内容或等价结构化字段

### Requirement: Validate before save

系统 MUST 在写入配置文件前校验配置内容。

#### Scenario: Invalid system config rejected

- **WHEN** 用户提交不符合 SystemConfig schema 的配置
- **THEN** 系统 MUST 拒绝保存并返回校验错误

#### Scenario: Invalid dag rejected

- **WHEN** 用户提交引用不存在 Node 或形成环的 DAG 配置
- **THEN** 系统 MUST 拒绝保存并返回 DAG 校验错误

#### Scenario: Invalid node rejected

- **WHEN** 用户提交缺少 skill 或 I/O 类型不匹配的 Node 配置
- **THEN** 系统 MUST 拒绝保存并返回校验错误
