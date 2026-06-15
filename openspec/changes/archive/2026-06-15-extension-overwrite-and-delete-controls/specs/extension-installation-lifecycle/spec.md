## MODIFIED Requirements

### Requirement: 扩展安装

系统 SHALL 支持从 `extensions/` 目录安装扩展到数据库。安装过程 MUST 将声明式内容写入数据库、将 handler 代码复制到配置的 `handlers_dir` 目录。对于 `type: workflow_extension`，系统 MUST 递归处理 `imports.providers` 并复制 `imports.libraries`。所有路径的 glob patterns MUST 在安装时展开。安装完成后，`handlers_dir/{package}.{handler}/` SHALL 成为该扩展 handler 代码的运行权威。默认安装路径遵循幂等语义；对已安装 extension 重新安装默认拒绝，用户 MUST 通过显式覆盖安装入口（`--overwrite`）触发非幂等替换。

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

#### Scenario: 默认重复安装已有扩展被拒绝

- **WHEN** 用户请求安装已存在于 `installed_extensions` 表中的扩展，且未指定覆盖
- **THEN** 系统 MUST 拒绝安装并提示扩展已安装
- **AND** 系统 MUST NOT 触发任何运行态变更

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

## ADDED Requirements

### Requirement: 扩展覆盖安装

系统 SHALL 支持对已安装 extension 执行覆盖安装（`--overwrite`）。覆盖安装 MUST 重建该扩展的全部运行态产物：drop 并重建 `ext_<name>_*` 扩展表、清空旧 `import_records` 并按新 manifest 全量重导 Entity、按现有逻辑重建 `handlers_dir` 与 `libs_dir` 下该扩展的命名空间目录、upsert `installed_extensions` 记录。覆盖安装 MUST NOT 触发依赖缺失放行（依赖检查仍生效）。覆盖安装完成后系统 SHALL 在返回结果中包含数据保留提醒，告知用户扩展表运行时数据已重建、如需保留请使用数据导入入口迁移。

#### Scenario: 覆盖安装重建扩展表与导入记录

- **WHEN** 用户对已安装扩展 `foo` 请求覆盖安装
- **THEN** 系统 SHALL 删除并重建 `ext_foo_*` 扩展表
- **AND** 系统 SHALL 清空 `foo` 的旧 `import_records` 并按当前 manifest 全量重导 Entity
- **AND** 系统 SHALL 重建 `handlers_dir/foo.*/` 与 `libs_dir/foo.*/` 命名空间目录
- **AND** 系统 SHALL upsert `installed_extensions` 中 `foo` 的记录

#### Scenario: 覆盖安装返回数据保留提醒

- **WHEN** 覆盖安装完成
- **THEN** 返回结果 SHALL 包含 `overwrite=true` 标志
- **AND** 返回结果 SHALL 包含数据保留提醒文本，指引使用数据导入入口恢复运行时数据

#### Scenario: 覆盖安装仍校验依赖

- **WHEN** 用户对已安装扩展 `foo` 请求覆盖安装，且 `foo` 的 manifest 声明了缺失的依赖
- **THEN** 系统 MUST 拒绝覆盖安装并报告缺失的依赖

#### Scenario: 覆盖安装对未安装扩展等价于普通安装

- **WHEN** 用户对未安装扩展 `bar` 请求覆盖安装
- **THEN** 系统 SHALL 执行普通安装流程
- **AND** 返回结果 SHALL 反映这是一次全新安装而非重建

### Requirement: 删除扩展源目录

系统 SHALL 提供删除 `extensions/<name>` 源目录的入口。该操作 MUST 仅针对未安装的 extension：若 `installed_extensions` 表存在该 name 的记录，系统 MUST 拒绝删除并提示先卸载。删除入口 MUST NOT 提供绕过该检查的强制参数。删除目标 MUST 为配置的 extensions 写入目录（extensions 搜索路径的末位）。

#### Scenario: 删除未安装扩展源目录

- **WHEN** 用户请求删除扩展 `foo` 且 `foo` 不在 `installed_extensions` 表中
- **AND** extensions 写入目录下存在 `extensions/foo/`
- **THEN** 系统 SHALL 删除 `extensions/foo/` 目录
- **AND** 返回结果 SHALL 确认目录已删除

#### Scenario: 删除已安装扩展被拒绝

- **WHEN** 用户请求删除扩展 `foo` 且 `foo` 存在于 `installed_extensions` 表中
- **THEN** 系统 MUST 拒绝删除并提示该扩展已安装、需先卸载
- **AND** 系统 MUST NOT 删除 `extensions/foo/` 目录

#### Scenario: 删除不存在的源目录

- **WHEN** 用户请求删除扩展 `foo` 且 extensions 写入目录下不存在 `extensions/foo/`
- **THEN** 系统 SHALL 报告源目录不存在

#### Scenario: 删除无强制参数

- **WHEN** 用户请求删除已安装扩展并附带任何强制标志
- **THEN** 系统 MUST 拒绝删除，不提供绕过「未安装」检查的路径

### Requirement: 导入扩展目录支持覆盖

系统 SHALL 支持将外部扩展目录或压缩包导入到 extensions 目录。当目标 `extensions/<name>` 已存在时，默认导入 MUST 被拒绝；用户 MUST 通过显式覆盖标志（`--overwrite`）触发替换，覆盖时系统 MUST 先删除已有目标目录再拷贝源目录，MUST NOT 采用目录合并以避免新旧文件残留。

#### Scenario: 导入到已存在目录默认被拒绝

- **WHEN** 用户导入扩展目录 `foo/` 且 `extensions/foo/` 已存在
- **THEN** 系统 MUST 拒绝导入并提示目录已存在
- **AND** 系统 MUST NOT 修改已有的 `extensions/foo/`

#### Scenario: 覆盖导入替换已有目录

- **WHEN** 用户导入扩展目录 `foo/` 并指定覆盖，且 `extensions/foo/` 已存在
- **THEN** 系统 SHALL 删除已有的 `extensions/foo/`
- **AND** 系统 SHALL 将源目录拷贝到 `extensions/foo/`

#### Scenario: 导入目录必须包含 manifest

- **WHEN** 用户导入的目录或压缩包不含 `manifest.yaml`
- **THEN** 系统 MUST 拒绝导入并报告缺失 manifest
