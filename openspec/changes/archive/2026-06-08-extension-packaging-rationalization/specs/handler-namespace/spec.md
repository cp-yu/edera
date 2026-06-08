## ADDED Requirements

### Requirement: Handler 使用命名空间路径格式

系统 SHALL 使用 `{package}.{handler}` 命名空间格式标识 handler。Handler 代码 MUST 安装到 `data/handlers/{package}.{handler}/` 目录。对于 workflow extension 内部的 provider，package 为顶层 workflow extension 名称。

#### Scenario: 独立扩展的 handler 命名空间

- **WHEN** 安装独立扩展 `uzi-skill`，其 manifest 声明 handler `legacy-script-adapter`
- **THEN** handler 代码 MUST 安装到 `data/handlers/uzi-skill.legacy-script-adapter/`
- **AND** handler 全名为 `uzi-skill.legacy-script-adapter`

#### Scenario: Workflow extension 内部 provider 的 handler 命名空间

- **WHEN** 安装 workflow extension `default-news-workflow`，其 `_providers/rss-fetcher` 声明 handler `fetch-rss`
- **THEN** handler 代码 MUST 安装到 `data/handlers/default-news-workflow.rss-fetcher/`
- **AND** handler 全名为 `default-news-workflow.rss-fetcher.fetch-rss`

#### Scenario: 命名空间路径唯一性

- **WHEN** 尝试安装两个扩展，它们的 handler 解析为相同命名空间路径
- **THEN** 系统 MUST 返回安装错误
- **AND** 错误消息 MUST 指出冲突的 handler 路径

### Requirement: DatabaseHandlerResolver 支持命名空间查找

DatabaseHandlerResolver MUST 支持通过 `{package}.{handler}` 格式查找 handler entry point。查找路径 SHALL 为 `SystemConfig.handlers_dir/{package}.{handler}/`。

#### Scenario: 查找独立扩展的 handler

- **WHEN** node 声明 `handler: "uzi-skill.legacy-script-adapter"`
- **THEN** DatabaseHandlerResolver MUST 在 `data/handlers/uzi-skill.legacy-script-adapter/` 查找 entry point
- **AND** 根据 manifest `entry` 字段加载 handler 模块

#### Scenario: 查找 workflow provider 的 handler

- **WHEN** node 声明 `handler: "default-news-workflow.rss-fetcher.fetch-rss"`
- **THEN** DatabaseHandlerResolver MUST 在 `data/handlers/default-news-workflow.rss-fetcher/` 查找 entry point
- **AND** 加载 handler 模块中名为 `fetch-rss` 的函数或类

#### Scenario: Handler 路径不存在时返回错误

- **WHEN** DatabaseHandlerResolver 查找不存在的 handler 路径
- **THEN** 系统 MUST 返回 handler 未找到错误
- **AND** 错误消息 MUST 包含尝试查找的完整路径

### Requirement: Handler 命名空间避免冲突

命名空间路径设计 SHALL 确保不同扩展的同名 handler 不会冲突。两个不同 package 的同名 handler MUST 解析为不同路径。

#### Scenario: 不同包的同名 handler 不冲突

- **WHEN** `package-a` 和 `package-b` 都包含名为 `reader` 的 handler
- **THEN** 它们 MUST 安装到 `data/handlers/package-a.reader/` 和 `data/handlers/package-b.reader/`
- **AND** 可同时存在并被不同 node 引用

#### Scenario: 同一包内不允许同名 handler

- **WHEN** 同一 workflow extension 的两个 provider 都声明名为 `fetch` 的 handler
- **THEN** 系统 MUST 返回安装错误
- **AND** 错误消息 MUST 指出包内 handler 名称冲突

### Requirement: Handler 命名空间在数据库中持久化

`installed_extensions.manifest_snapshot` 中的 handler 声明 MUST 包含完整命名空间路径。DagExecutionSnapshot MUST 使用命名空间路径解析 handler。

#### Scenario: Manifest snapshot 记录命名空间路径

- **WHEN** 安装 workflow extension `default-news-workflow`
- **THEN** `manifest_snapshot` MUST 包含 handler 列表，每个 handler name 为 `{package}.{provider}` 格式
- **AND** 不包含短名称（如仅 `rss-fetcher`）

#### Scenario: DagExecutionSnapshot 使用命名空间路径

- **WHEN** DAG run 启动时构建 DagExecutionSnapshot
- **THEN** snapshot 中的 handler resolver MUST 基于 `installed_extensions.manifest_snapshot` 的命名空间路径
- **AND** node executor 通过命名空间路径查找 handler
