---
capabilities:
  - cap.entity-storage-tiers
---
# entity-storage-tiers Specification

## Purpose
定义 三层存储模型、存储层路由规则、输出型 Entity retention 策略、瞬态 Entity 生命周期。
## Requirements
### Requirement: 三层存储模型

系统 SHALL 支持 Entity 按生命周期分层存储：核心配置型 Entity 使用数据库 per-type tables，输出型 Entity 使用数据库输出表，瞬态型 Entity 使用内存。Entity Store MUST 对上层提供统一查询接口，屏蔽存储层差异。YAML 文件 MAY 作为 import/export/template 格式存在，但 MUST NOT 作为核心配置型 Entity 的运行时 source of truth。

#### Scenario: 核心配置型 Entity 存储在数据库 per-type table

- **WHEN** 用户创建一个 `type: node` 的 Entity
- **THEN** 系统将其持久化到 `entity_node` 表
- **AND** 系统 MUST NOT 将其作为运行时配置写入 YAML 配置目录

#### Scenario: 输出型 Entity 存储在数据库

- **WHEN** Node 执行产出一个 `type: analysis` 的 Entity
- **THEN** 系统将其存储到数据库 `node_outputs` 表，payload 为 JSON 格式

#### Scenario: 瞬态 Entity 存储在内存

- **WHEN** DAG run 开始时创建 run metadata Entity
- **THEN** 系统将其保存在内存中，run 结束后释放

#### Scenario: 统一查询跨存储层

- **WHEN** 用户查询 `entity:analysis:00700-2026-05-21`
- **THEN** Entity Store 自动路由到数据库层查询并返回结果，调用方无需感知存储层

### Requirement: 存储层路由规则

系统 SHALL 根据 EntityType 的配置决定 Entity 存储在哪一层。EntityType schema MUST 声明 `storage_tier` 字段。对于 `node`、`dag`、`trigger`、`resource`，`storage_tier: database` MUST 路由到对应固定 per-type table，而不是 `node_outputs`。

#### Scenario: EntityType 声明核心数据库存储

- **WHEN** EntityType `node` 的 schema 中 `storage_tier: database`
- **THEN** 所有 `type: node` 的 Entity 存储在 `entity_node` 表

#### Scenario: EntityType 声明输出数据库存储

- **WHEN** EntityType `analysis` 的 schema 中 `storage_tier: database`
- **THEN** 所有 `type: analysis` 的输出型 Entity 存储在 `node_outputs` 表

#### Scenario: EntityType 声明内存存储

- **WHEN** EntityType `run-metadata` 的 schema 中 `storage_tier: memory`
- **THEN** 所有 `type: run-metadata` 的 Entity 仅存在于内存

### Requirement: 输出型 Entity retention 策略

系统 SHALL 对数据库层的输出型 Entity 执行 retention 清理。清理策略 MUST 可通过 `system.toml` 配置。默认 `retention_hours` SHALL 为 720。系统 MUST 只在完整 DAG run 成功完成后触发输出型 Entity retention 清理；失败 run、取消 run、单节点运行和 partial retry MUST NOT 触发 retention 清理。

#### Scenario: 按保留数量清理

- **WHEN** `system.toml` 配置 `retention_count: 20`，且当前已有 25 次 run 的输出 Entity
- **THEN** 系统清理最早 5 次 run 产生的所有输出型 Entity

#### Scenario: 按保留时间清理

- **WHEN** `system.toml` 配置 `retention_hours: 720`，且存在超过 720 小时的输出 Entity
- **THEN** 系统清理这些过期的输出型 Entity

#### Scenario: 成功完整 DAG run 触发 retention

- **WHEN** 完整 DAG run 成功完成
- **THEN** 系统 SHALL 执行输出型 Entity retention 清理

#### Scenario: 失败或取消 DAG run 不触发 retention

- **WHEN** DAG run 以 `failed` 或 `cancelled` 状态结束
- **THEN** 系统 MUST NOT 执行输出型 Entity retention 清理

#### Scenario: 非完整 DAG run 不触发 retention

- **WHEN** 单节点运行或 partial retry 完成
- **THEN** 系统 MUST NOT 执行输出型 Entity retention 清理

### Requirement: 瞬态 Entity 生命周期

系统 SHALL 在 DAG run 结束时自动释放该 run 创建的所有瞬态 Entity。

#### Scenario: run 正常结束释放瞬态 Entity

- **WHEN** DAG run 正常完成
- **THEN** 系统释放该 run 的 run-metadata Entity 和事件状态 Entity

#### Scenario: run 异常终止释放瞬态 Entity

- **WHEN** DAG run 因异常终止
- **THEN** 系统仍然释放该 run 的所有瞬态 Entity，不产生内存泄漏
