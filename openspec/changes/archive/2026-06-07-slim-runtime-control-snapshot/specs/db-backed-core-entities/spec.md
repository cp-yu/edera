## MODIFIED Requirements

### Requirement: 核心配置型 Entity 使用 DB source of truth

系统 SHALL 将 `node`、`dag`、`trigger`、`resource` 作为核心配置型 Entity 存储在 SQLite 中。运行时读取、CLI 数据操作和 Web Console 展示 MUST 以 DB 为唯一 source of truth，MUST NOT 从 YAML/config 文件读取这些类型的运行时状态。此要求扩展到所有 entities、relations、EntityTypes 和 Skills。DAG/Node/EntityType/Skill runtime reads MUST NOT require these objects to be loaded into `RuntimeControlSnapshot`.

#### Scenario: 运行时从 DB 读取核心 Entity

- **WHEN** `edera-server` 启动并构建 `RuntimeControlSnapshot`
- **THEN** 系统 SHALL 从 DB 读取 trigger entity 构建全局 TriggerExecutor
- **AND** 系统 MUST NOT 从 YAML 配置文件读取 core Entity 类型作为 runtime source
- **AND** 系统 MUST NOT load all DAG/Node configs solely to build `RuntimeControlSnapshot`

#### Scenario: 运行时从 DB 读取普通 Entity

- **WHEN** 运行时、CLI 或 Web Console 查询普通 entities（包括 stock, rss-source 等）
- **THEN** 系统 SHALL 从对应 entity type 的数据库表读取结果
- **AND** 系统 MUST NOT 从 `config/entities.yaml` 读取普通 entities
- **AND** 系统 MUST NOT 要求普通 entities 已加载到启动时 runtime snapshot

#### Scenario: 运行时从 DB 读取 entity relations

- **WHEN** 运行时、CLI 或 Web Console 查询 entity relations
- **THEN** 系统 SHALL 从 DB `entity_relations` 表读取 relations
- **AND** 系统 MUST NOT 从 `config/entity-relations.yaml` 读取 relations
- **AND** 系统 MUST NOT 要求 relations 已加载到启动时 runtime snapshot

#### Scenario: DB 写入后不替换控制面 snapshot

- **WHEN** 用户通过 CLI 或 Web Console 修改 DAG、Node、EntityType 或 Skill
- **THEN** 系统 SHALL 将变更写入 DB source of truth
- **AND** 系统 SHALL emit `event:config-changed`
- **AND** 系统 MUST NOT rebuild `RuntimeControlSnapshot`

#### Scenario: Trigger 写入后替换控制面 snapshot

- **WHEN** 用户通过 CLI 或 Web Console 修改 Trigger Entity
- **THEN** 系统 SHALL 基于 DB 状态构建新的 committed `RuntimeControlSnapshot`
- **AND** 只有构建成功后才替换当前控制面视图

## ADDED Requirements

### Requirement: Indexed core entity reads
系统 SHALL 提供按 identity 读取核心 DAG 和 Node Entity 的 DB-backed repository API。DAG execution closure 构建 MUST use indexed reads or bounded reachable traversal, MUST NOT list all core entities as the normal run-start path.

#### Scenario: 按名称读取 DAG
- **WHEN** DagController 构建 root DAG "analysis" 的 execution closure
- **THEN** system SHALL query DB for DAG "analysis" directly or through bounded indexed lookup
- **AND** system MUST NOT require loading all DAG entities

#### Scenario: 按名称读取 Node type
- **WHEN** execution closure references node type "fetch-news"
- **THEN** system SHALL query DB for node type "fetch-news" directly or through bounded indexed lookup
- **AND** system MUST NOT require loading all Node entities
