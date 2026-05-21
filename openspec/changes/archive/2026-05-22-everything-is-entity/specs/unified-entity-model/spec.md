## ADDED Requirements

### Requirement: 统一 Entity 原语

系统 SHALL 将所有概念（Node、DAG、Trigger、Relation、Output）统一建模为 Entity。每个 Entity MUST 包含 `id`（UUID）、`type`（引用 EntityType）和 `attributes`（自由字典）。

#### Scenario: Node 作为 Entity

- **WHEN** 系统加载 `config/nodes/rss-fetcher.yaml` 文件
- **THEN** 系统将其解析为一个 `type: node` 的 Entity，`attributes` 包含 `handler`、`input_type`、`output_type` 等字段

#### Scenario: DAG 作为 Entity

- **WHEN** 系统加载 `config/dags/default.yaml` 文件
- **THEN** 系统将其解析为一个 `type: dag` 的 Entity，`attributes` 包含 `nodes`（引用列表）和 `edges`（连线定义）

#### Scenario: Trigger 作为 Entity

- **WHEN** 系统加载 `config/triggers/every-30min.yaml` 文件
- **THEN** 系统将其解析为一个 `type: trigger` 的 Entity，`attributes` 包含 `wait_for` 和 `target`

#### Scenario: Relation 作为 Entity

- **WHEN** 系统加载 `config/relations.yaml` 中的一条关系记录
- **THEN** 系统将其解析为一个 `type: relation` 的 Entity，`attributes` 包含 `from`、`to`、`relation_type`

#### Scenario: Node 输出作为 Entity

- **WHEN** 一个 Node 执行完成并产出结果
- **THEN** 系统将输出存储为一个输出型 Entity（如 `type: analysis`），包含 `cycle_id`、`node_id`、`payload` 等字段

### Requirement: EntityType schema 字段即能力声明

系统 SHALL 通过 EntityType schema 中特定字段的存在来声明 Entity 的能力，MUST NOT 引入独立的 capabilities 抽象层。

#### Scenario: 可执行能力声明

- **WHEN** 一个 EntityType schema 定义中包含 `handler` 字段
- **THEN** 系统识别该类型的 Entity 为可执行的（Node）

#### Scenario: DAG 能力声明

- **WHEN** 一个 EntityType schema 定义中包含 `edges` 和 `nodes` 字段
- **THEN** 系统识别该类型的 Entity 为 DAG

#### Scenario: Trigger 能力声明

- **WHEN** 一个 EntityType schema 定义中包含 `wait_for` 和 `target` 字段
- **THEN** 系统识别该类型的 Entity 为 Trigger

#### Scenario: 普通数据 Entity

- **WHEN** 一个 EntityType schema 定义中不包含 `handler`、`edges`、`wait_for` 等能力字段
- **THEN** 系统将该类型的 Entity 视为纯数据载体

### Requirement: Entity 统一 CRUD 接口

系统 SHALL 为所有 Entity 提供统一的 CRUD 接口，无论其 EntityType 是什么。

#### Scenario: 通过统一接口创建 Node Entity

- **WHEN** 用户通过 Entity Store 创建一个 `type: node` 的 Entity
- **THEN** 系统校验 attributes 符合 `node` EntityType schema，生成 UUID，持久化到 `config/nodes/` 目录

#### Scenario: 通过统一接口查询 Trigger Entity

- **WHEN** 用户通过 Entity Store 查询所有 `type: trigger` 的 Entity
- **THEN** 系统返回 `config/triggers/` 目录下所有 Trigger Entity 实例

#### Scenario: 通过统一接口删除 Relation Entity

- **WHEN** 用户通过 Entity Store 删除一个 `type: relation` 的 Entity
- **THEN** 系统从 `config/relations.yaml` 中移除该条记录
