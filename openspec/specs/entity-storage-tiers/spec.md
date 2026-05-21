# entity-storage-tiers Specification

## Purpose
此规约记录变更 everything-is-entity 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 三层存储模型

系统 SHALL 支持 Entity 按生命周期分三层存储：文件系统（配置型）、数据库（输出型）、内存（瞬态型）。Entity Store MUST 对上层提供统一查询接口，屏蔽存储层差异。

#### Scenario: 配置型 Entity 存储在文件系统

- **WHEN** 用户创建一个 `type: stock` 的 Entity
- **THEN** 系统将其持久化为 `config/entities/` 目录下的 YAML 文件

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

系统 SHALL 根据 EntityType 的配置决定 Entity 存储在哪一层。EntityType schema MUST 声明 `storage_tier` 字段。

#### Scenario: EntityType 声明文件系统存储

- **WHEN** EntityType `node` 的 schema 中 `storage_tier: filesystem`
- **THEN** 所有 `type: node` 的 Entity 存储在 `config/nodes/` 目录

#### Scenario: EntityType 声明数据库存储

- **WHEN** EntityType `analysis` 的 schema 中 `storage_tier: database`
- **THEN** 所有 `type: analysis` 的 Entity 存储在数据库

#### Scenario: EntityType 声明内存存储

- **WHEN** EntityType `run-metadata` 的 schema 中 `storage_tier: memory`
- **THEN** 所有 `type: run-metadata` 的 Entity 仅存在于内存

### Requirement: 输出型 Entity retention 策略

系统 SHALL 对数据库层的输出型 Entity 执行 retention 清理。清理策略 MUST 可通过 `system.toml` 配置。

#### Scenario: 按保留数量清理

- **WHEN** `system.toml` 配置 `retention_count: 20`，且当前已有 25 次 run 的输出 Entity
- **THEN** 系统清理最早 5 次 run 产生的所有输出型 Entity

#### Scenario: 按保留时间清理

- **WHEN** `system.toml` 配置 `retention_hours: 24`，且存在超过 24 小时的输出 Entity
- **THEN** 系统清理这些过期的输出型 Entity

### Requirement: 瞬态 Entity 生命周期

系统 SHALL 在 DAG run 结束时自动释放该 run 创建的所有瞬态 Entity。

#### Scenario: run 正常结束释放瞬态 Entity

- **WHEN** DAG run 正常完成
- **THEN** 系统释放该 run 的 run-metadata Entity 和事件状态 Entity

#### Scenario: run 异常终止释放瞬态 Entity

- **WHEN** DAG run 因异常终止
- **THEN** 系统仍然释放该 run 的所有瞬态 Entity，不产生内存泄漏

