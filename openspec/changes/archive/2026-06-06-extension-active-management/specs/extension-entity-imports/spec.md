---
capabilities:
  - cap.core.extension-entity-imports
---
# extension-entity-imports Delta Specification

## MODIFIED Requirements

### Requirement: Extension manifest entity imports

系统 SHALL 支持 extension manifest 通过 `imports.entities` 声明一组待导入的 Entity YAML 路径。路径 MUST 相对该 extension 根目录（`extensions/<name>/`）解析，且每个文件 MUST 是完整 Entity 文档，包含 `type`、`id` 和 `attributes`。Entity 导入 SHALL 仅在扩展安装操作时执行，MUST NOT 在 bootstrap 启动时自动触发。

#### Scenario: 安装时导入 Entity

- **WHEN** 用户安装扩展 `foo`，manifest 包含 `imports.entities: ["dags/default/dag.yaml"]`
- **THEN** 安装流程 SHALL 读取 `extensions/foo/dags/default/dag.yaml` 并写入数据库
- **AND** 导入记录 SHALL 写入 `installed_extensions.import_records` JSON array

#### Scenario: Reject invalid import path

- **WHEN** manifest 的 `imports.entities` 包含绝对路径或包含 `..` 的路径
- **THEN** 系统 MUST 拒绝安装该扩展

### Requirement: Extension entity import records

系统 SHALL 使用 `installed_extensions.import_records` JSON array 记录每条 manifest import path 的导入结果。每条记录 MUST 包含 `import_path`、`entity_type`、`entity_id`、`entity_ref`、`content_digest`、`imported_entity_digest`、`status`。

#### Scenario: Record imported entity

- **WHEN** import path 对应的 Entity 在 DB 中不存在
- **THEN** importer SHALL 保存该 Entity
- **AND** 写入 import record `status = "imported"`

#### Scenario: Record existing entity without overwrite

- **WHEN** import path 对应的 Entity ref 已存在于 DB
- **THEN** importer MUST NOT 覆盖已有 Entity
- **AND** 写入 import record `status = "skipped_existing"`

### Requirement: Extension entity imports are idempotent

系统 SHALL 对每条 extension import path 执行一次性导入。已有 import record 时，重新安装 MUST 跳过该 import path。

#### Scenario: Skip already imported path

- **WHEN** `installed_extensions.import_records` 已包含 `import_path = "dags/default/dag.yaml"` 的记录
- **THEN** importer SHALL 跳过该 path
- **AND** MUST NOT 读取该 path 后覆盖 DB Entity

## ADDED Requirements

### Requirement: Import records 支持卸载

`import_records` SHALL 保存足够信息以支持扩展卸载时的 Entity 清理。

#### Scenario: purge 策略删除所有导入 Entity

- **WHEN** 卸载策略为 `purge`
- **THEN** 系统 SHALL 删除 `import_records` 中所有 `status = "imported"` 的 Entity，无论 digest 是否变化
- **AND** 系统 SHALL 删除 `import_records` 中所有 `status = "skipped_existing"` 对应的 Entity

#### Scenario: keep-modified 策略保留修改的 Entity

- **WHEN** 卸载策略为 `keep-modified` 且 import record 的 `status = "imported"` 且当前 DB Entity digest 不等于 `imported_entity_digest`
- **THEN** 系统 SHALL 保留该 Entity

#### Scenario: keep-modified 策略不删除 skipped_existing

- **WHEN** 卸载策略为 `keep-modified` 且 import record 的 `status = "skipped_existing"`
- **THEN** 系统 MUST NOT 删除该 Entity

## REMOVED Requirements

### Requirement: Extension import index supports future uninstall
**Reason**: 卸载逻辑已在 `extension-installation-lifecycle` 中完整定义，不再需要独立的 "future uninstall" 前瞻性要求。
**Migration**: 卸载功能直接由 `extension-installation-lifecycle` spec 的卸载策略承接。
