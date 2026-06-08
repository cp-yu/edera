## ADDED Requirements

### Requirement: InstallExtension RPC 支持 workflow extension

`ExtensionService.Install` RPC MUST 识别 manifest `type: workflow_extension` 并递归处理 `imports.providers` 和 `imports.libraries`。所有 glob patterns MUST 在安装时展开。

#### Scenario: 安装 handler provider extension

- **WHEN** gRPC client 调用 `InstallExtension(name="rss-fetcher")`
- **THEN** server SHALL 读取 `extensions/rss-fetcher/manifest.yaml`
- **AND** server SHALL 写入 `installed_extensions` 表
- **AND** server SHALL 复制 handler 代码到 `handlers_dir/rss-fetcher/`
- **AND** server SHALL 导入 manifest 声明的 entities

#### Scenario: 安装 workflow extension 递归处理 providers

- **WHEN** gRPC client 调用 `InstallExtension(name="default-news-workflow")` 且 manifest 包含 `type: workflow_extension`
- **THEN** server SHALL 展开 `imports.providers` 的 glob patterns
- **AND** server SHALL 递归读取每个 provider 的 manifest
- **AND** server SHALL 将每个 provider 的 handler 代码复制到 `handlers_dir/{package}.{provider}/`
- **AND** server SHALL 记录所有 provider handlers 到主扩展的 `manifest_snapshot`

#### Scenario: 安装 workflow extension 复制 libraries

- **WHEN** manifest 包含 `imports.libraries: ["_lib/*"]`
- **THEN** server SHALL 展开 glob pattern
- **AND** server SHALL 将每个 library 目录复制到 `handlers_dir/_libs/{package}.{library}/`
- **AND** server SHALL 记录 library 路径到 `manifest_snapshot`

#### Scenario: 安装时 glob pattern 无匹配

- **WHEN** manifest 包含 glob pattern 但无任何匹配路径
- **THEN** server MUST 拒绝安装
- **AND** 返回 gRPC error 包含未匹配的 pattern

#### Scenario: Provider 依赖解析失败

- **WHEN** provider manifest 声明 `depends: ["_lib/http_fetch"]` 但主扩展未在 `imports.libraries` 中包含该 library
- **THEN** server MUST 拒绝安装
- **AND** 返回 gRPC error 包含缺失的依赖路径
