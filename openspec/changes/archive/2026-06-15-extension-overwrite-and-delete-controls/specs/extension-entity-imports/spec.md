## MODIFIED Requirements

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
