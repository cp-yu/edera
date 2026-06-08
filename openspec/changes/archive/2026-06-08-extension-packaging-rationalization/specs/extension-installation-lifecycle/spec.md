## MODIFIED Requirements

### Requirement: 扩展安装

系统 SHALL 支持从 `extensions/` 目录安装扩展到数据库。安装过程 MUST 将声明式内容写入数据库、将 handler 代码复制到配置的 `handlers_dir` 目录。对于 `type: workflow_extension`，系统 MUST 递归处理 `imports.providers` 并复制 `imports.libraries`。所有路径的 glob patterns MUST 在安装时展开。安装完成后，`handlers_dir/{package}.{handler}/` SHALL 成为该扩展 handler 代码的运行权威。

#### Scenario: 安装完整扩展

- **WHEN** 用户请求安装 `extensions/rss-fetcher` 且该扩展未安装
- **THEN** 系统 SHALL 读取 `extensions/rss-fetcher/manifest.yaml`
- **AND** 系统 SHALL 写入 `installed_extensions` 表
- **AND** 系统 SHALL 将 handler 代码复制到 `handlers_dir/rss-fetcher/`
- **AND** 系统 SHALL 将 `_lib/` 依赖复制到 `handlers_dir/_lib/`（如尚未存在）
- **AND** 系统 SHALL 创建扩展表（如 manifest 声明了 `storage.tables`）
- **AND** 系统 SHALL 导入 Entity 实例（如 manifest 声明了 `imports.entities`）

#### Scenario: 安装前校验依赖

- **WHEN** 扩展 manifest 声明 `depends: [rss-fetcher]` 且 `rss-fetcher` 尚未安装
- **THEN** 系统 MUST 拒绝安装并报告缺失的依赖

#### Scenario: 安装前校验 manifest

- **WHEN** `extensions/<name>/manifest.yaml` 不存在或缺少必填字段
- **THEN** 系统 MUST 拒绝安装并报告错误

#### Scenario: 重复安装已有扩展

- **WHEN** 用户请求安装已存在于 `installed_extensions` 表中的扩展
- **THEN** 系统 MUST 拒绝安装并提示扩展已安装

#### Scenario: Entity 导入遵循幂等语义

- **WHEN** 安装时 import path 对应的 Entity ref 已存在于数据库
- **THEN** importer MUST NOT 覆盖已有 Entity
- **AND** 该条记录 `status` SHALL 为 `"skipped_existing"`

#### Scenario: 安装 workflow extension 时递归处理 providers

- **WHEN** 用户请求安装 `type: workflow_extension` 的扩展
- **THEN** 系统 MUST 展开 `imports.providers` 的 glob patterns
- **AND** 对每个匹配的 provider 目录读取其 `manifest.yaml`
- **AND** 将 provider 的 handler 代码复制到 `handlers_dir/{package}.{provider}/`
- **AND** 记录 provider 的 handler 声明到主扩展的 `manifest_snapshot`

#### Scenario: 安装 workflow extension 时复制 libraries

- **WHEN** 用户请求安装 `type: workflow_extension` 且 manifest 包含 `imports.libraries`
- **THEN** 系统 MUST 展开 `imports.libraries` 的 glob patterns
- **AND** 将每个匹配的 library 目录复制到 `handlers_dir/_libs/{package}.{library}/`
- **AND** 记录 library 路径到 `manifest_snapshot`

#### Scenario: 安装时展开 imports.entities glob patterns

- **WHEN** manifest 包含 `imports.entities: ["entities/**/*.yaml"]`
- **THEN** 系统 MUST 展开 glob pattern 为具体文件列表
- **AND** 导入所有匹配的 Entity 实例
- **AND** 记录每个导入的具体文件路径到 `import_records`

#### Scenario: Provider 相对路径依赖解析

- **WHEN** provider manifest 包含 `depends: ["_lib/http_fetch"]`
- **THEN** 系统 MUST 解析为包级相对路径 `{package}/_lib/http_fetch`
- **AND** 在主扩展的 `imports.libraries` 中查找对应 library
- **AND** 如果未找到 MUST 拒绝安装并报告缺失依赖
