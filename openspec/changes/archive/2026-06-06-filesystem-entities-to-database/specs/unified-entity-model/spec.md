## MODIFIED Requirements

### Requirement: 统一 Entity 原语

系统 SHALL 将所有概念（Node、DAG、Trigger、Relation、Output）统一建模为 Entity。每个 Entity MUST 包含 `id`（UUID）、`type`（引用 EntityType）和 `attributes`（自由字典）。所有 entities（核心和普通）SHALL 从数据库加载，不再从 YAML 文件加载。

#### Scenario: Node 作为 Entity

- **WHEN** 系统加载 DB-backed `node` Entity
- **THEN** 系统将其解析为一个 `type: node` 的 Entity，`attributes` 包含 `handler`、`input_type`、`output_type` 等字段

#### Scenario: DAG 作为 Entity

- **WHEN** 系统加载 DB-backed `dag` Entity
- **THEN** 系统将其解析为一个 `type: dag` 的 Entity，`attributes` 包含 `nodes`（引用列表）和 `edges`（连线定义）

#### Scenario: Trigger 作为 Entity

- **WHEN** 系统加载 DB-backed `trigger` Entity
- **THEN** 系统将其解析为一个 `type: trigger` 的 Entity，`attributes` 包含 `wait_for` 和 `target`

#### Scenario: Relation 作为 Entity

- **WHEN** 系统按需查询数据库中的 relation 记录
- **THEN** 系统将其解析为一个 `type: relation` 的 Entity，`attributes` 包含 `from`、`to`、`relation_type`
- **THEN** 系统不再从 `config/entity-relations.yaml` 加载 relations

#### Scenario: 普通业务 Entity 按需从数据库查询

- **WHEN** 系统查询普通 entities（如 stock, rss-source）
- **THEN** 系统 SHALL 从对应 entity type 的数据库表读取结果
- **THEN** 启动时 `EntityStore` MUST NOT 需要包含所有普通 entities
- **THEN** 系统不再从 `config/entities.yaml` 加载普通 entities

#### Scenario: Node 输出作为 Entity

- **WHEN** 一个 Node 执行完成并产出结果
- **THEN** 系统将输出存储为一个输出型 Entity（如 `type: analysis`），包含 `run_id`、`node_id`、`payload` 等字段

### Requirement: Entity 统一 CRUD 接口

系统 SHALL 为所有 Entity 提供统一的 CRUD 接口，无论其 EntityType 是什么。所有 Entity 操作 SHALL 直接操作数据库，不涉及文件系统。

#### Scenario: 通过统一接口创建 Node Entity

- **WHEN** 用户通过 Entity Store 创建一个 `type: node` 的 Entity
- **THEN** 系统校验 attributes 符合 `node` EntityType schema，生成 UUID，持久化到 DB-backed Entity Store

#### Scenario: 通过统一接口创建普通 Entity

- **WHEN** 用户通过 Entity Store 创建一个 `type: stock` 的 Entity
- **THEN** 系统校验 attributes 符合 `stock` EntityType schema
- **THEN** 系统 SHALL 保存到数据库对应表（`entity_stock`）
- **THEN** 系统不写入 `config/entities.yaml` 文件
