---
capabilities:
  - cap.core.extension-entity-imports
---
# extension-entity-imports Specification

## Purpose
定义 Extension manifest entity imports、Extension entity import records、Extension entity imports are idempotent、Extension import index supports future uninstall。
## Requirements
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

系统 SHALL 使用 `installed_extensions.import_records` JSON array 记录每条 manifest import path 的导入结果。每条记录 MUST 包含 `import_path`、`entity_type`、`entity_id`、`entity_ref`、`content_digest`、`imported_entity_digest`、`status`。默认安装路径对已存在的 Entity ref 标记为 `"skipped_existing"`；覆盖安装路径 SHALL 清空旧 `import_records` 并按当前 manifest 全量重导，已存在的 Entity MUST 被新版本内容覆盖并标记为 `"imported"`。

#### Scenario: Record imported entity

- **WHEN** import path 对应的 Entity 在 DB 中不存在
- **THEN** importer SHALL 保存该 Entity
- **AND** 写入 import record `status = "imported"`

#### Scenario: Record existing entity without overwrite on default install

- **WHEN** 默认安装时 import path 对应的 Entity ref 已存在于 DB
- **THEN** importer MUST NOT 覆盖已有 Entity
- **AND** 写入 import record `status = "skipped_existing"`

#### Scenario: Overwrite install replaces existing entity

- **WHEN** 覆盖安装时 import path 对应的 Entity ref 已存在于 DB
- **THEN** importer SHALL 用当前 manifest 的 Entity 内容覆盖已有 Entity
- **AND** 写入 import record `status = "imported"`

#### Scenario: Overwrite install resets import records

- **WHEN** 用户对已安装扩展请求覆盖安装
- **THEN** 系统 SHALL 清空该扩展的旧 `import_records`
- **AND** 按当前 manifest 全量重新导入并重建 `import_records`

### Requirement: Extension entity imports are idempotent

系统 SHALL 对每条 extension import path 在默认安装路径下执行一次性导入。默认安装路径下，已有 import record 时重新安装 MUST 跳过该 import path。覆盖安装路径不受幂等约束：系统 MUST 清空旧 import_records 并对当前 manifest 的全部 import path 重新导入。

#### Scenario: Skip already imported path on default install

- **WHEN** 默认安装且 `installed_extensions.import_records` 已包含 `import_path = "dags/default/dag.yaml"` 的记录
- **THEN** importer SHALL 跳过该 path
- **AND** MUST NOT 读取该 path 后覆盖 DB Entity

#### Scenario: Overwrite install re-imports all paths

- **WHEN** 覆盖安装且旧 `import_records` 已包含若干 path 记录
- **THEN** importer SHALL 清空旧记录
- **AND** 对当前 manifest 的全部 import path 重新执行导入
- **AND** MUST NOT 因旧记录存在而跳过任何 path

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

