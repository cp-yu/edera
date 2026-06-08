## ADDED Requirements

### Requirement: DatabaseHandlerResolver 支持命名空间路径查找

DatabaseHandlerResolver MUST 支持通过 `{package}.{handler}` 格式查找 handler entry point。查找路径 SHALL 为 `SystemConfig.handlers_dir/{package}.{handler}/`。对于 workflow extension 内部的 providers，package 为顶层 workflow extension 名称。

#### Scenario: 解析独立扩展的 handler

- **WHEN** node 声明 `handler: "uzi-skill.legacy-script-adapter"`
- **THEN** resolver MUST 在 `handlers_dir/uzi-skill.legacy-script-adapter/` 查找 entry point
- **AND** 根据 manifest `entry` 字段加载 handler 模块

#### Scenario: 解析 workflow provider 的 handler

- **WHEN** node 声明 `handler: "default-news-workflow.rss-fetcher"`
- **THEN** resolver MUST 在 `handlers_dir/default-news-workflow.rss-fetcher/` 查找 entry point
- **AND** 加载 handler 模块

#### Scenario: 命名空间路径不存在时返回错误

- **WHEN** resolver 查找不存在的命名空间路径
- **THEN** 系统 MUST 返回 handler 未找到错误
- **AND** 错误消息 MUST 包含尝试查找的完整路径

#### Scenario: Handler 路径从 manifest_snapshot 读取

- **WHEN** DagExecutionSnapshot 构建 handler resolver
- **THEN** resolver MUST 从 `installed_extensions.manifest_snapshot` 读取 handler 声明
- **AND** handler 声明 MUST 包含完整命名空间路径（如 `{package}.{provider}` for workflow providers）
