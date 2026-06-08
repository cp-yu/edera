# extension-glob-imports Specification

## Purpose
此规约记录变更 extension-packaging-rationalization 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Manifest imports 支持 glob patterns

Extension manifest 的 `imports.entities` 字段 SHALL 支持 glob patterns 用于批量匹配 entity 文件路径。系统 MUST 在扩展安装时展开 glob patterns 并记录实际导入的文件列表到 `installed_extensions.import_records`。

#### Scenario: 使用 ** 递归匹配所有 entity 文件

- **WHEN** manifest 包含 `imports.entities: ["entities/**/*.yaml"]`
- **THEN** 系统 MUST 递归匹配 `entities/` 下所有子目录的 `.yaml` 文件
- **AND** 导入所有匹配的 entity 实例

#### Scenario: 使用 * 匹配一级子目录

- **WHEN** manifest 包含 `imports.providers: ["_providers/*/manifest.yaml"]`
- **THEN** 系统 MUST 匹配 `_providers/` 下每个一级子目录的 `manifest.yaml`
- **AND** 不递归匹配二级及以下目录

#### Scenario: Glob 展开失败时安装报错

- **WHEN** manifest 包含 glob pattern 但无匹配文件
- **THEN** 系统 MUST 返回安装错误
- **AND** 错误消息 MUST 包含未匹配的 pattern

#### Scenario: 混合使用 glob 和显式路径

- **WHEN** manifest 包含 `imports.entities: ["entities/**/*.yaml", "seeds/special.yaml"]`
- **THEN** 系统 MUST 展开 glob pattern 并合并显式路径
- **AND** 导入所有匹配文件和显式指定文件

### Requirement: Glob 展开结果记录到 import_records

系统 SHALL 在扩展安装时将 glob patterns 展开为具体文件列表，并记录到 `installed_extensions.import_records` JSON 字段。每条记录 MUST 包含 `path`, `status`, `digest` 字段。

#### Scenario: 安装成功后 import_records 包含展开的文件列表

- **WHEN** 使用 glob pattern `entities/**/*.yaml` 安装扩展
- **THEN** `import_records` MUST 包含所有匹配的具体文件路径
- **AND** 每个文件记录 MUST 包含 `status: "imported"` 和 SHA256 `digest`

#### Scenario: 卸载时根据 import_records 清理 entities

- **WHEN** 执行 `edera extension uninstall <name>`
- **THEN** 系统 MUST 读取 `import_records` 中的文件列表
- **AND** 删除所有 `status: "imported"` 的 entity 实例

### Requirement: Glob pattern 语义兼容 Python glob 模块

系统 SHALL 使用 Python 标准库 `glob.glob(pattern, recursive=True)` 展开 patterns。支持的 pattern 语法 MUST 包括 `*`（单级通配）、`**`（递归通配）、`?`（单字符通配）。

#### Scenario: ** 启用递归匹配

- **WHEN** pattern 包含 `**`
- **THEN** 系统 MUST 传递 `recursive=True` 给 `glob.glob`
- **AND** 匹配所有层级的子目录

#### Scenario: 不支持的 pattern 语法返回错误

- **WHEN** pattern 包含 shell 不支持的语法（如 `{a,b}`）
- **THEN** 系统 MUST 返回错误
- **AND** 错误消息 MUST 提示使用支持的 pattern 语法
