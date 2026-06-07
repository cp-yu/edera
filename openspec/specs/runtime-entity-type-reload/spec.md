---
capabilities:
  - cap.core.runtime-entity-type-reload
---
# runtime-entity-type-reload Specification

## Purpose
定义 EntityType 运行时配置在 DB-backed source of truth 下的生效方式，以及新 DAG run 使用最新配置、运行中 DAG run 继续使用既有快照的隔离语义。
## Requirements
### Requirement: EntityType 运行时配置不依赖 reload API
系统 SHALL 以 DB-backed EntityType metadata 作为新 DAG run 的运行时 source of truth。EntityType 写入成功后 SHALL emit `event:config-changed`，MUST NOT mutate `AppConfig.entity_types` 或 rebuild `RuntimeControlSnapshot`；正在运行的 DAG MUST 继续使用启动时冻结的 `DagExecutionSnapshot`。

#### Scenario: EntityType 写入不重建控制面
- **WHEN** EntityType metadata 被保存到 DB
- **THEN** 系统 SHALL emit `event:config-changed`
- **AND** 系统 MUST NOT mutate `AppConfig.entity_types`
- **AND** 系统 MUST NOT rebuild `RuntimeControlSnapshot`

#### Scenario: 新 DAG run 使用 DB 中的新 EntityType
- **WHEN** EntityType metadata 已在 DB 中更新
- **WHEN** 后续 DAG run 启动
- **THEN** `DagExecutionSnapshot` SHALL 从 DB-backed EntityType metadata 复制新配置

#### Scenario: 运行中 DAG 不受 EntityType 变更影响
- **WHEN** DAG run 已启动并持有 `DagExecutionSnapshot`
- **WHEN** EntityType metadata 在 DB 中被修改
- **THEN** 该 DAG run MUST 继续使用快照中的旧 EntityType 配置

