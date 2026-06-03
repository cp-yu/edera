<!-- propose-routing: Existing decomposition and impact sweep found; input length=31; detail score=5/5 from prior first-change dependency plus repository evidence; multi-subsystem=true but already decomposed into second migration change; decision=proceed with generated artifacts for move-workflows-to-extensions. -->
## Why

当前仓库仍把 `default` 和 `uzi-skill-analysis` 两条示例/业务工作流放在顶层 `config/` 中，和 core runtime 的用户配置边界混在一起。第一个 change 已经建立 extension manifest entity import 机制，本 change 负责把现有工作流内容迁移成 extension-owned package，让 core 启动只消费 DB 中已导入的 Entity。

## What Changes

- 新增 `extensions/default-news-workflow/` package，声明并导入 `default` DAG、6 个默认节点、`default-default-cron` trigger，以及该 DAG 直接引用的 RSS/API source Entity。
- 修改 `extensions/uzi-skill/manifest.yaml`，在保留 `legacy-script-adapter` handler 的同时声明并导入 `uzi-skill-analysis` DAG、UZI 节点、`uzi-skill-analysis-default-cron` trigger 和 `v8_isolate` Resource Entity。
- 将迁移后的工作流 Entity YAML 放在各 extension package 内，由 manifest `imports.entities` 列表显式枚举。
- **BREAKING** `config/dags/default.yaml`、`config/dags/uzi-skill-analysis.yaml`、迁移节点文件、迁移 trigger 文件和 `v8_isolate` resource 不再作为 runtime 的规范来源。
- 保留 `config/entities.yaml` 中未被 DAG 直接拥有的 stock Entity 和 `config/entity-relations.yaml` 作为用户/本地 seed 数据，不纳入 extension ownership。
- 为迁移内容增加 fixture/加载验证，证明 extension import 后两个 DAG、trigger、node 和 resource 可从 DB-backed Entity 路径加载。

## Capabilities

### New Capabilities
- `default-news-workflow`: 默认新闻工作流 extension package，覆盖 `default` DAG、默认节点、默认 cron trigger 和 DAG 直接引用的信息源 seed Entity 的导入边界。

### Modified Capabilities
- `extension-manifest-system`: workflow extension package MUST 通过 manifest `imports.entities` 显式声明拥有的 Entity 文件，不能依赖目录扫描或顶层 `config/` 文件。
- `uzi-skill-dag-instance`: UZI-Skill DAG 实例从 `config/dags/uzi-skill-analysis.yaml` 迁移到 `extensions/uzi-skill/` 的 manifest imports，拓扑和运行语义保持不变。

## Impact

- Affected files: `extensions/default-news-workflow/manifest.yaml`, `extensions/default-news-workflow/entities/**`, `extensions/uzi-skill/manifest.yaml`, `extensions/uzi-skill/entities/**`, `config/dags/**`, `config/nodes/**`, `config/triggers/**`, `config/entities.yaml`.
- Affected tests: bootstrap/import tests, DAG graph loading tests, trigger loading tests, UZI topology tests, config boundary regression tests.
- Dependency: requires `extension-import-clean-runtime` so manifest imports are parsed, imported idempotently, and indexed by `extension_imports`.
- Data ownership: imported `skipped_existing` behavior from the first change prevents extension packages from overwriting user-edited DB Entity records.
