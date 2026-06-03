## ADDED Requirements

### Requirement: Default news workflow extension package
系统 SHALL 提供 `extensions/default-news-workflow/manifest.yaml` 作为默认新闻工作流 package。该 manifest MUST 声明 package name、version、handler provider dependencies，并通过 `imports.entities` 显式列出本 package 拥有的 DAG、node、trigger 和 source seed Entity 文件。

#### Scenario: Manifest declares workflow imports
- **WHEN** bootstrap 扫描 `extensions/default-news-workflow/manifest.yaml`
- **THEN** manifest SHALL 包含 `imports.entities` 条目覆盖 `default` DAG、6 个默认节点、`default-default-cron` trigger 和默认 DAG 直接引用的 RSS/API source Entity
- **AND** manifest MUST NOT 依赖目录扫描隐式导入 Entity

#### Scenario: Dependencies are declared
- **WHEN** bootstrap 校验 `default-news-workflow` manifest
- **THEN** manifest MUST 声明对 `rss-fetcher`、`api-fetcher`、`reader`、`advisor`、`briefing-generator` 和 `notifier` provider extensions 的依赖

### Requirement: Default DAG topology is preserved
导入后的 `default` DAG Entity SHALL 保留现有新闻工作流拓扑：`rss-fetcher` 和 `api-fetcher` 并行进入 `reader`，再依次执行 `advisor`、`briefing-generator` 和 `notifier`。节点 alias、node type、config、edge optional 语义和 UI layout SHALL 与迁移前等价。

#### Scenario: Imported default DAG loads
- **WHEN** extension imports 已执行且 runtime 从 DB-backed Entity 加载 `default` DAG
- **THEN** DagGraph MUST 包含 6 个节点和 5 条边
- **AND** 节点 type MUST 依次覆盖 `rss-fetcher`、`api-fetcher`、`reader`、`advisor`、`briefing-generator` 和 `notifier`

#### Scenario: Source node configs are preserved
- **WHEN** runtime 加载导入后的 `default` DAG
- **THEN** `rss-fetcher` 节点 MUST 继续引用 `rss-source:hn-rss`
- **AND** `api-fetcher` 节点 MUST 继续引用 `api-source:cls-telegraph`、`api-source:jqka`、`api-source:solidot`、`api-source:ithome` 和 `api-source:github`

### Requirement: Default workflow seed sources are extension-owned
`default-news-workflow` SHALL import `default` DAG 直接引用的 source seed Entity。该 package MUST own `rss-source:hn-rss` and the five `api-source` Entity records used by the default DAG. Stock Entity 和 entity relation seed MUST remain outside this workflow package.

#### Scenario: Source seeds imported with workflow
- **WHEN** `default-news-workflow` imports are applied to an empty DB
- **THEN** Entity Store SHALL contain `rss-source:hn-rss`
- **AND** Entity Store SHALL contain `api-source:cls-telegraph`、`api-source:jqka`、`api-source:solidot`、`api-source:ithome` 和 `api-source:github`

#### Scenario: Stock seeds remain outside package
- **WHEN** reviewing `extensions/default-news-workflow/manifest.yaml`
- **THEN** `imports.entities` MUST NOT include stock Entity files
- **AND** MUST NOT include `entity-relations` seed files

### Requirement: Default workflow trigger is imported
`default-news-workflow` SHALL import the `default-default-cron` Trigger Entity. The trigger MUST keep `wait_for = cron:"*/30 * * * *"`, `target = dag:default`, and `enabled = true`.

#### Scenario: Imported trigger targets default DAG
- **WHEN** extension imports 已执行
- **THEN** Trigger registry SHALL include `default-default-cron`
- **AND** the trigger target MUST be `dag:default`

#### Scenario: Cron expression preserved
- **WHEN** Trigger Entity `default-default-cron` is loaded from DB
- **THEN** `wait_for` MUST equal `cron:"*/30 * * * *"`
- **AND** `enabled` MUST be true

### Requirement: Top-level default workflow config is no longer authoritative
迁移完成后，`config/dags/default.yaml`、default workflow 的 6 个 `config/nodes/*.yaml` 文件和 `config/triggers/default-default-cron.yaml` MUST NOT remain as runtime-authoritative sources for the default workflow. Runtime SHALL load these migrated entities from DB records created or skipped by extension imports.

#### Scenario: No top-level default DAG source
- **WHEN** repository configuration is inspected after migration
- **THEN** `config/dags/default.yaml` MUST be absent or ignored by runtime loading
- **AND** `extensions/default-news-workflow/manifest.yaml` MUST be the manifest source for importing the `default` DAG Entity

#### Scenario: Runtime loads imported default workflow
- **WHEN** runtime materialization builds the DAG registry after extension imports
- **THEN** `default` DAG MUST be resolved from DB-backed Entity storage
- **AND** runtime MUST NOT read top-level `config/dags/default.yaml` as a fallback source
