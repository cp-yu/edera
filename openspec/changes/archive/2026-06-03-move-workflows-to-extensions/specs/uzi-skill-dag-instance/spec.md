## MODIFIED Requirements

### Requirement: DAG 拓扑声明

系统 SHALL 在 `extensions/uzi-skill/` package 的 manifest imports 中声明完整的 UZI-Skill 分析管道 Entity，包含 preflight、22 fetcher、scoring 链、21 renderer 和 assemble 节点。

每个 DAG 实例 SHALL 使用对应业务语义的 `uzi-*` node type，并设置非空 `alias` 作为 WebConsole 展示标签。相近业务 node type MAY 复用同一个 handler，但 MUST NOT 将所有实例的 `type` 直接声明为通用 handler 名称。

#### Scenario: DAG 配置可加载
- **WHEN** 系统启动、执行 `extensions/uzi-skill/manifest.yaml` imports 并从 DB-backed Entity 加载 `uzi-skill-analysis`
- **THEN** DagGraph MUST 包含所有声明的节点和边，无加载错误

#### Scenario: 拓扑验证通过
- **WHEN** 对加载的 DagGraph 执行 `topological_layers()` 验证
- **THEN** MUST 无环检测通过，所有节点可达

#### Scenario: WebConsole 展示业务节点
- **WHEN** WebConsole 加载 `uzi-skill-analysis` DAG
- **THEN** 每个实例 MUST 返回具体 `uzi-*` type_name 和非空 alias，而不是全部显示为 `legacy-script-adapter`

## ADDED Requirements

### Requirement: UZI-Skill workflow extension imports
`extensions/uzi-skill/manifest.yaml` SHALL import the UZI-Skill workflow-owned Entity files: `uzi-skill-analysis` DAG, all `uzi-*` node definitions required by that DAG, `uzi-skill-analysis-default-cron` Trigger Entity, and `v8_isolate` Resource Entity. The manifest MUST keep `legacy-script-adapter` handler registration.

#### Scenario: Manifest imports UZI workflow entities
- **WHEN** bootstrap scans `extensions/uzi-skill/manifest.yaml`
- **THEN** manifest `imports.entities` SHALL include the UZI DAG Entity, UZI node Entity files, UZI cron trigger Entity, and `v8_isolate` Resource Entity
- **AND** HandlerRegistry MUST still contain `legacy-script-adapter`

#### Scenario: Resource entity imported
- **WHEN** UZI-Skill imports are applied to an empty DB
- **THEN** Entity Store SHALL contain Resource Entity `v8_isolate`
- **AND** its `permits` attribute MUST equal 1

### Requirement: UZI-Skill trigger is imported
The UZI-Skill workflow package SHALL import `uzi-skill-analysis-default-cron`. The trigger MUST keep `wait_for = cron:"*/30 * * * *"`, `target = dag:uzi-skill-analysis`, and `enabled = true`.

#### Scenario: Imported UZI trigger targets DAG
- **WHEN** extension imports 已执行
- **THEN** Trigger registry SHALL include `uzi-skill-analysis-default-cron`
- **AND** the trigger target MUST be `dag:uzi-skill-analysis`

#### Scenario: UZI cron expression preserved
- **WHEN** Trigger Entity `uzi-skill-analysis-default-cron` is loaded from DB
- **THEN** `wait_for` MUST equal `cron:"*/30 * * * *"`
- **AND** `enabled` MUST be true

### Requirement: Top-level UZI workflow config is no longer authoritative
迁移完成后，`config/dags/uzi-skill-analysis.yaml`、UZI workflow 的 `config/nodes/uzi-*.yaml` 文件、`config/triggers/uzi-skill-analysis-default-cron.yaml` 和 `config/entities.yaml` 中的 `v8_isolate` resource MUST NOT remain as runtime-authoritative sources for the UZI workflow. Runtime SHALL load these migrated entities from DB records created or skipped by extension imports.

#### Scenario: No top-level UZI DAG source
- **WHEN** repository configuration is inspected after migration
- **THEN** `config/dags/uzi-skill-analysis.yaml` MUST be absent or ignored by runtime loading
- **AND** `extensions/uzi-skill/manifest.yaml` MUST be the manifest source for importing the `uzi-skill-analysis` DAG Entity

#### Scenario: Runtime loads imported UZI workflow
- **WHEN** runtime materialization builds the DAG registry after extension imports
- **THEN** `uzi-skill-analysis` DAG MUST be resolved from DB-backed Entity storage
- **AND** runtime MUST NOT read top-level `config/dags/uzi-skill-analysis.yaml` as a fallback source
