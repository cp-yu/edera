## MODIFIED Requirements

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

### Requirement: Default workflow seed sources are extension-owned

`default-news-workflow` SHALL import `default` DAG 直接引用的 source seed Entity。该 package MUST own `rss-source:hn-rss` and the five `api-source` Entity records used by the default DAG. Stock Entity 和 entity relation seed MUST remain outside this workflow package.

#### Scenario: Source seeds imported with workflow

- **WHEN** 安装 `default-news-workflow`
- **THEN** 系统 SHALL 导入 6 个 source seed entities（从 `entities/sources/*.yaml`）
- **AND** 这些 sources MUST 包含 `hn-rss`, `cls-telegraph`, `jqka`, `solidot`, `ithome`, `github`
