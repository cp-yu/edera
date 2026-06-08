---
capabilities:
  - cap.core.default-news-workflow
---
# default-news-workflow Specification

## Purpose
定义 Default news workflow extension package、Default DAG topology is preserved、Default workflow seed sources are extension-owned、Default workflow trigger is imported等能力。
## Requirements
### Requirement: Default news workflow extension package

系统 SHALL 提供 `extensions/default-news-workflow/manifest.yaml` 作为默认新闻工作流 package。该 manifest MUST 声明 `type: workflow_extension`、package name、version、内部 handler provider dependencies，并通过 `imports.entities`、`imports.providers`、`imports.libraries` 显式列出本 package 拥有的 DAG、node、trigger、source seed Entity、内部 providers 和共享库。所有路径 MUST 支持 glob patterns。

#### Scenario: Manifest 声明 workflow extension 类型

- **WHEN** 读取 `extensions/default-news-workflow/manifest.yaml`
- **THEN** manifest MUST 包含 `type: workflow_extension`
- **AND** manifest MUST 包含 `name: default-news-workflow` 和 `version` 字段

#### Scenario: Manifest 使用 glob patterns 声明 entities

- **WHEN** 读取 manifest 的 `imports.entities`
- **THEN** manifest MUST 使用 `entities/**/*.yaml` 替代手动列举
- **AND** 实际导入时 glob pattern MUST 展开为所有 DAG、node、trigger、source 文件

#### Scenario: Manifest 声明内部 providers

- **WHEN** 读取 manifest 的 `imports.providers`
- **THEN** manifest MUST 包含 `["_providers/rss-fetcher", "_providers/api-fetcher", "_providers/reader", "_providers/advisor", "_providers/briefing-generator", "_providers/notifier", "_providers/web-scraper"]`
- **AND** 安装时 MUST 递归读取每个 provider 的 manifest

#### Scenario: Manifest 声明共享库

- **WHEN** 读取 manifest 的 `imports.libraries`
- **THEN** manifest MUST 包含 `["_lib/http_fetch"]`
- **AND** 安装时 MUST 复制 `_lib/http_fetch/` 到 `handlers_dir/_libs/default-news-workflow.http_fetch/`

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

- **WHEN** 安装 `default-news-workflow`
- **THEN** 系统 SHALL 导入 6 个 source seed entities（从 `entities/sources/*.yaml`）
- **AND** 这些 sources MUST 包含 `hn-rss`, `cls-telegraph`, `jqka`, `solidot`, `ithome`, `github`

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
default workflow 的 DAG、node、trigger 和 resource instances SHALL 由 extension manifest imports 写入 DB-backed Entity Store，并以 DB records 作为唯一 runtime-authoritative source.

#### Scenario: Manifest import is default workflow source
- **WHEN** repository workflow ownership is inspected
- **THEN** `extensions/default-news-workflow/manifest.yaml` MUST be the manifest source for importing the `default` DAG Entity
- **AND** runtime MUST NOT treat workflow YAML files as authoritative runtime sources

#### Scenario: Runtime loads imported default workflow
- **WHEN** runtime materialization builds the DAG registry after extension imports
- **THEN** `default` DAG MUST be resolved from DB-backed Entity storage
- **AND** runtime MUST NOT read workflow YAML files as fallback runtime sources
