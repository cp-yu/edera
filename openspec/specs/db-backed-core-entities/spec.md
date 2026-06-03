---
capabilities:
  - cap.core.db-backed-core-entities
---
# db-backed-core-entities Specification

## Purpose
定义 核心配置型 Entity 使用 DB source of truth、核心 Entity 固定 per-type tables、EntityType DB 元数据、YAML 文件降级为 import/export/template 格式等能力。
## Requirements
### Requirement: 核心配置型 Entity 使用 DB source of truth

系统 SHALL 将 `node`、`dag`、`trigger`、`resource` 作为核心配置型 Entity 存储在 SQLite 中。运行时读取、CLI 数据操作和 Web Console 展示 MUST 以 DB 为唯一 source of truth，MUST NOT 从 YAML/config 文件读取这些类型的运行时状态。

#### Scenario: 运行时从 DB 读取核心 Entity
- **WHEN** `edera-server` 启动并构建 runtime snapshot
- **THEN** 系统 SHALL 从 DB 读取 `node`、`dag`、`trigger` 和 `resource`
- **AND** 系统 MUST NOT 从 YAML 配置文件读取这些 core Entity 类型作为 runtime source

#### Scenario: DB 写入后替换 committed snapshot
- **WHEN** 用户通过 CLI 或 Web Console 修改核心配置型 Entity
- **THEN** 系统 SHALL 基于 DB 状态构建新的 committed runtime snapshot
- **AND** 只有构建成功后才替换当前运行视图

### Requirement: 核心 Entity 固定 per-type tables

系统 SHALL 为核心类型创建固定 per-type tables：`entity_node`、`entity_dag`、`entity_trigger`、`entity_resource`。这些表 MUST 按当前核心模型完全列化核心字段；`attributes_json` MAY 作为兼容扩展槽存在，但核心运行读取路径 MUST 使用列化字段。

#### Scenario: 核心字段列化
- **WHEN** 系统保存 `type: node` 的核心字段
- **THEN** 系统 SHALL 将当前核心模型字段写入 `entity_node` 的列
- **AND** 系统 MUST NOT 要求 runtime snapshot 从 `attributes_json` 解析核心字段

#### Scenario: 核心表与输出表分离
- **WHEN** Node 产出 `type: analysis` 的输出型 Entity
- **THEN** 系统 SHALL 继续写入 `node_outputs`
- **AND** 系统 MUST NOT 将输出型 Entity 写入核心配置型 per-type tables

### Requirement: EntityType DB 元数据

系统 SHALL 在 DB 中维护 `entity_types` 元数据，记录核心类型的 schema、schema version、table mapping、business id field、display template 和 protection metadata。核心类型定义的运行时读取 MUST 来自该表。

#### Scenario: 读取核心 EntityType 元数据
- **WHEN** EntityStore 需要解析 `node` 的 business id 或 display template
- **THEN** 系统 SHALL 从 DB-backed `entity_types` 元数据读取定义

#### Scenario: Protected metadata preserved
- **WHEN** `node`、`dag`、`trigger` 或 `resource` 被标记为 system protected
- **THEN** 系统 SHALL 在 DB 元数据中保留该保护属性

### Requirement: YAML 文件降级为 import/export/template 格式

系统 SHALL 支持完整 Entity 文档格式的 YAML import、export 和 template。YAML 文件 MAY 用于 CLI `--file` 输入输出，但 MUST NOT 作为核心配置型 Entity 的运行时 source of truth。

#### Scenario: 导入完整 Entity YAML
- **WHEN** 用户执行 `edera entity import --file node.yaml`
- **THEN** 系统 SHALL 读取 YAML 中的 `type`、`id` 和 `attributes`
- **AND** 系统 SHALL 将该 Entity 持久化到对应 DB per-type table

#### Scenario: 导出完整 Entity YAML
- **WHEN** 用户执行 `edera entity export node:reader --file node.yaml`
- **THEN** 系统 SHALL 从 DB 读取该 Entity
- **AND** 系统 SHALL 写出包含 `type`、`id` 和 `attributes` 的完整 YAML 文档

#### Scenario: 根据 EntityType 导出模板
- **WHEN** 用户执行 `edera entity template --type node --file node.yaml`
- **THEN** 系统 SHALL 根据 DB 中的 EntityType schema 生成完整 Entity YAML 模板
- **AND** 模板 SHALL 包含 `type`、`id`、`attributes`、必填字段占位和 business id 字段占位

### Requirement: Raw log 文件索引

系统 SHALL 将 raw stdout/stderr 或大体积 agent 过程日志存储为文件，并在 DB 中保存 `log_index`。`log_index` MUST 至少包含 run id、node id、path、size、digest 和 timestamps。

#### Scenario: Raw log 文件落盘
- **WHEN** 节点运行产生 raw stdout/stderr 日志
- **THEN** 系统 SHALL 将日志内容写入 `EDERA_DATA_DIR/sessions` 下的文件
- **AND** 系统 SHALL 在 `log_index` 中记录可查询索引

#### Scenario: Raw log 不写入 runtime facts 表
- **WHEN** raw 日志内容超过结构化摘要范围
- **THEN** 系统 MUST NOT 将完整 raw 日志写入 `dag_runs`、`node_runs`、`edge_inputs`、`source_recoveries` 或 `emit_records`

### Requirement: Core runtime does not generate configuration entities
系统 MUST NOT 在 runtime snapshot、runtime config materialization 或 startup 流程中根据已有 DAG 自动生成 `node`、`dag`、`trigger` 或 `resource` 实例。核心配置型 Entity 的运行时来源 SHALL 是 DB 中已经存在的 Entity。

#### Scenario: Materialization does not create default cron trigger
- **WHEN** DB 中存在一个 DAG Entity 且不存在对应 Trigger Entity
- **THEN** `materialize_runtime_app_config()` MUST NOT 创建 `<dag>-default-cron` Trigger Entity

#### Scenario: Snapshot install does not create default cron trigger
- **WHEN** `DagController.install_snapshot()` 构建 runtime snapshot
- **THEN** 系统 MUST NOT 创建任何新的 Trigger Entity
