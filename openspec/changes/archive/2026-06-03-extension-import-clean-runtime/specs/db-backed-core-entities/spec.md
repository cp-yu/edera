## ADDED Requirements

### Requirement: Core runtime does not generate configuration entities
系统 MUST NOT 在 runtime snapshot、runtime config materialization 或 startup 流程中根据已有 DAG 自动生成 `node`、`dag`、`trigger` 或 `resource` 实例。核心配置型 Entity 的运行时来源 SHALL 是 DB 中已经存在的 Entity。

#### Scenario: Materialization does not create default cron trigger
- **WHEN** DB 中存在一个 DAG Entity 且不存在对应 Trigger Entity
- **THEN** `materialize_runtime_app_config()` MUST NOT 创建 `<dag>-default-cron` Trigger Entity

#### Scenario: Snapshot install does not create default cron trigger
- **WHEN** `DagController.install_snapshot()` 构建 runtime snapshot
- **THEN** 系统 MUST NOT 创建任何新的 Trigger Entity

