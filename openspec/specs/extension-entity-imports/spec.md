---
capabilities:
  - cap.core.extension-entity-imports
---
# extension-entity-imports Specification

## Purpose
此规约记录变更 extension-import-clean-runtime 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Extension manifest entity imports
系统 SHALL 支持 extension manifest 通过 `imports.entities` 声明一组待导入的 Entity YAML 路径。路径 MUST 相对该 extension 根目录解析，且每个文件 MUST 是完整 Entity 文档，包含 `type`、`id` 和 `attributes`。

#### Scenario: Load manifest import declarations
- **WHEN** `extensions/foo/manifest.yaml` 包含 `imports.entities: ["dags/default/dag.yaml"]`
- **THEN** bootstrap 结果 SHALL 保留该 import declaration
- **AND** bootstrap scan MUST NOT 在此阶段写入 DB entity

#### Scenario: Reject invalid import path
- **WHEN** manifest 的 `imports.entities` 包含绝对路径或包含 `..` 的路径
- **THEN** 系统 MUST 拒绝该 manifest

### Requirement: Extension entity import records
系统 SHALL 使用 `extension_imports` 表记录每条 manifest import path 的导入结果。记录 MUST 包含 extension name、extension version、import path、entity type、entity id、entity ref、content digest、imported entity digest、status 和 timestamps。

#### Scenario: Record imported entity
- **WHEN** import path 对应的 Entity 在 DB 中不存在
- **THEN** importer SHALL 保存该 Entity
- **AND** 写入 `extension_imports.status = "imported"`

#### Scenario: Record existing entity without overwrite
- **WHEN** import path 对应的 Entity ref 已存在于 DB
- **THEN** importer MUST NOT 覆盖已有 Entity
- **AND** 写入 `extension_imports.status = "skipped_existing"`

### Requirement: Extension entity imports are idempotent
系统 SHALL 对每条 extension import path 执行一次性导入。已有 `extension_imports` 记录时，后续启动或 hot reload MUST 跳过该 import path。

#### Scenario: Skip already imported path
- **WHEN** `extension_imports` 已存在 `extension_name = "foo"` 且 `import_path = "dags/default/dag.yaml"` 的记录
- **THEN** importer SHALL 跳过该 path
- **AND** MUST NOT 读取该 path 后覆盖 DB Entity

### Requirement: Extension import index supports future uninstall
`extension_imports` SHALL 保存足够信息以支持后续 extension 内容卸载。卸载时只有 `status = "imported"` 且当前 entity digest 未被用户修改的 Entity MAY 被默认删除；`skipped_existing` Entity MUST NOT 被删除。

#### Scenario: Imported modified entity retained by default
- **WHEN** extension import record 的 `status = "imported"` 且当前 DB Entity digest 不等于 `imported_entity_digest`
- **THEN** 后续 extension uninstall 默认 SHALL 保留该 Entity

#### Scenario: Skipped existing entity never owned
- **WHEN** extension import record 的 `status = "skipped_existing"`
- **THEN** 后续 extension uninstall MUST NOT 删除该 Entity

