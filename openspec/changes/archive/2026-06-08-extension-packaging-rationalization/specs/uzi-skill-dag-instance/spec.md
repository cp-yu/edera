## MODIFIED Requirements

### Requirement: UZI-Skill workflow extension imports

`extensions/uzi-skill/manifest.yaml` SHALL import UZI-Skill workflow-owned Entity files：主 DAG `uzi-skill-analysis`、3 个 Sub DAG Entity（`uzi-data-collection`, `uzi-scoring-synthesis`, `uzi-rendering`）、所有 `uzi-*` node 定义、`aggregate-collection-results` node 定义、`uzi-skill-analysis-default-cron` Trigger Entity 和 `v8_isolate` Resource Entity。Manifest MUST 保留 `legacy-script-adapter` handler 注册。Manifest MUST 使用 glob patterns 替代手动列举 59 个 entity imports。

#### Scenario: Manifest 使用 glob pattern 导入所有 entities

- **WHEN** 读取 `extensions/uzi-skill/manifest.yaml`
- **THEN** manifest MUST 包含 `imports.entities: ["entities/**/*.yaml"]`
- **AND** glob pattern MUST 展开为 4 个 DAG files + 67 个 node files + 2 个 resource files

#### Scenario: Imported UZI trigger targets DAG

- **WHEN** 导入 trigger entity `uzi-skill-analysis-default-cron`
- **THEN** 该 trigger MUST 保持 `wait_for = cron:"*/30 * * * *"`、`target = dag:uzi-skill-analysis` 和 `enabled = true`

#### Scenario: UZI-Skill handler 注册保持不变

- **WHEN** 读取 manifest 的 `handlers` 字段
- **THEN** manifest MUST 保留 `legacy-script-adapter` handler 声明
- **AND** handler entry MUST 为 `adapter.py`
- **AND** 安装后 handler 代码 MUST 复制到 `handlers_dir/uzi-skill.legacy-script-adapter/`
