## ADDED Requirements

### Requirement: Manifest 支持 type: workflow_extension 类型声明

Extension manifest MUST 支持 `type` 字段用于标识扩展类型。有效值 SHALL 包括 `workflow_extension` 和 `handler_provider`。当 `type: workflow_extension` 时，系统 MUST 识别并处理 `imports.providers` 和 `imports.libraries` 字段。

#### Scenario: 识别 workflow_extension 类型

- **WHEN** manifest 包含 `type: workflow_extension`
- **THEN** 系统 MUST 解析 `imports.providers` 字段
- **AND** 系统 MUST 解析 `imports.libraries` 字段

#### Scenario: 缺少 type 字段时默认为 handler_provider

- **WHEN** manifest 不包含 `type` 字段
- **THEN** 系统 MUST 视为 `type: handler_provider`
- **AND** 忽略 `imports.providers` 和 `imports.libraries` 字段

#### Scenario: 不支持的 type 值返回错误

- **WHEN** manifest 包含 `type: unknown_type`
- **THEN** 系统 MUST 返回安装错误
- **AND** 错误消息 MUST 列出支持的 type 值

### Requirement: Workflow extension 支持 imports.providers 声明

Workflow extension manifest MUST 支持 `imports.providers` 字段，用于声明包内的 handler provider 扩展列表。每个 provider 路径 SHALL 相对于扩展根目录。系统 MUST 递归读取每个 provider 的 manifest 并安装其 handlers。

#### Scenario: 安装 workflow extension 时递归安装 providers

- **WHEN** manifest 包含 `imports.providers: ["_providers/rss-fetcher", "_providers/api-fetcher"]`
- **THEN** 系统 MUST 读取 `_providers/rss-fetcher/manifest.yaml`
- **AND** 安装该 provider 的 handlers 到 `data/handlers/{package}.rss-fetcher/`
- **AND** 对 `_providers/api-fetcher` 重复相同流程

#### Scenario: Provider manifest 不存在时安装失败

- **WHEN** `imports.providers` 包含路径但对应 `manifest.yaml` 不存在
- **THEN** 系统 MUST 返回安装错误
- **AND** 错误消息 MUST 包含缺失的 manifest 路径

#### Scenario: Provider depends 相对路径解析

- **WHEN** provider manifest 包含 `depends: ["_lib/http_fetch"]`
- **THEN** 系统 MUST 解析为包级相对路径 `{package}/_lib/http_fetch`
- **AND** 在 `imports.libraries` 中查找对应的 library

### Requirement: Workflow extension 支持 imports.libraries 声明

Workflow extension manifest MUST 支持 `imports.libraries` 字段，用于声明包内的共享库列表。每个 library 路径 SHALL 相对于扩展根目录。系统 MUST 复制 library 目录到 `data/libs/{package}.{library_name}/`。

#### Scenario: 安装 workflow extension 时复制 libraries

- **WHEN** manifest 包含 `imports.libraries: ["_lib/http_fetch"]`
- **THEN** 系统 MUST 复制 `_lib/http_fetch/` 目录到 `data/libs/{package}.http_fetch/`
- **AND** 保留目录结构和所有文件

#### Scenario: Library 目录不存在时安装失败

- **WHEN** `imports.libraries` 包含路径但对应目录不存在
- **THEN** 系统 MUST 返回安装错误
- **AND** 错误消息 MUST 包含缺失的 library 路径

#### Scenario: 卸载时清理已安装的 libraries

- **WHEN** 执行 `edera extension uninstall <name>`
- **THEN** 系统 MUST 删除 `data/libs/{package}.*` 下所有该包的 libraries
- **AND** 如果 library 被其他扩展依赖，MUST 返回错误并拒绝卸载

### Requirement: Provider handler 使用命名空间路径

Workflow extension 内部 provider 的 handler MUST 安装到 `data/handlers/{package}.{provider}/`。Handler name 在数据库中记录为 `{package}.{provider}.{handler}`。DatabaseHandlerResolver MUST 支持命名空间路径查找。

#### Scenario: Provider handler 安装到命名空间路径

- **WHEN** 安装 `default-news-workflow` 包的 `_providers/rss-fetcher`
- **THEN** handler 代码 MUST 复制到 `data/handlers/default-news-workflow.rss-fetcher/`
- **AND** `installed_extensions.manifest_snapshot` MUST 记录 handler name 为 `default-news-workflow.rss-fetcher.fetch-rss`

#### Scenario: Handler resolver 查找命名空间路径

- **WHEN** node 引用 handler `default-news-workflow.rss-fetcher.fetch-rss`
- **THEN** DatabaseHandlerResolver MUST 在 `data/handlers/default-news-workflow.rss-fetcher/` 查找 handler entry
- **AND** 加载并执行该 handler

#### Scenario: 命名空间路径避免同名冲突

- **WHEN** 两个不同包都包含名为 `reader` 的 provider
- **THEN** 它们 MUST 安装到不同路径 `data/handlers/package1.reader/` 和 `data/handlers/package2.reader/`
- **AND** 互不冲突
