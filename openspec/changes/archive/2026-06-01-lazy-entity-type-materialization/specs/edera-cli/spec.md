## ADDED Requirements

### Requirement: Entity materialization maintenance commands

`edera entity-type` SHALL 提供普通 EntityType 字段物化维护命令，用于 plan、apply 和 inspect materialized fields。命令 MUST 通过 gRPC 调用 server，MUST NOT 直接修改数据库 schema。

#### Scenario: Plan field materialization
- **WHEN** 用户执行 `edera entity-type materialize plan stock --field code`
- **THEN** CLI SHALL 返回将要创建的列、索引和回填数量摘要

#### Scenario: Apply field materialization
- **WHEN** 用户执行 `edera entity-type materialize apply stock --field code`
- **THEN** server SHALL 物化该字段并更新 EntityType metadata

#### Scenario: Inspect materialized fields
- **WHEN** 用户执行 `edera entity-type materialize inspect stock`
- **THEN** CLI SHALL 展示 `stock` 的 materialized fields 和 deprecated fields
