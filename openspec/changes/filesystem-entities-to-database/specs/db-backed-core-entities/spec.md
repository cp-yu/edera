## MODIFIED Requirements

### Requirement: 核心配置型 Entity 使用 DB source of truth

系统 SHALL 将 `node`、`dag`、`trigger`、`resource` 作为核心配置型 Entity 存储在 SQLite 中。运行时读取、CLI 数据操作和 Web Console 展示 MUST 以 DB 为唯一 source of truth，MUST NOT 从 YAML/config 文件读取这些类型的运行时状态。此要求扩展到所有 entities 和 relations，包括普通 entities 和 entity relations。

#### Scenario: 运行时从 DB 读取核心 Entity

- **WHEN** `edera-server` 启动并构建 runtime snapshot
- **THEN** 系统 SHALL 从 DB 读取 `node`、`dag`、`trigger` 和 `resource`
- **AND** 系统 MUST NOT 从 YAML 配置文件读取这些 core Entity 类型作为 runtime source

#### Scenario: 运行时从 DB 读取普通 Entity

- **WHEN** `edera-server` 启动并构建 runtime snapshot
- **THEN** 系统 SHALL 从 DB 读取所有 entity types 的 entities（包括 stock, rss-source 等）
- **AND** 系统 MUST NOT 从 `config/entities.yaml` 读取普通 entities

#### Scenario: 运行时从 DB 读取 entity relations

- **WHEN** `edera-server` 启动并构建 runtime snapshot
- **THEN** 系统 SHALL 从 DB `entity_relations` 表读取所有 relations
- **AND** 系统 MUST NOT 从 `config/entity-relations.yaml` 读取 relations

#### Scenario: DB 写入后替换 committed snapshot

- **WHEN** 用户通过 CLI 或 Web Console 修改核心配置型 Entity
- **THEN** 系统 SHALL 基于 DB 状态构建新的 committed runtime snapshot
- **AND** 只有构建成功后才替换当前运行视图

## ADDED Requirements

### Requirement: 自动迁移 YAML 文件到数据库

系统 SHALL 在首次启动时检测 `config/entities.yaml` 和 `config/entity-relations.yaml` 文件，自动导入数据库并备份原文件。

#### Scenario: 检测并导入 entities.yaml

- **WHEN** 系统启动时检测到 `config/entities.yaml` 存在
- **THEN** 系统 SHALL 读取文件内容
- **THEN** 系统 SHALL 批量导入所有 entities 到数据库
- **THEN** 系统 SHALL 重命名文件为 `entities.yaml.migrated`

#### Scenario: 检测并导入 entity-relations.yaml

- **WHEN** 系统启动时检测到 `config/entity-relations.yaml` 存在
- **THEN** 系统 SHALL 读取文件内容
- **THEN** 系统 SHALL 批量导入所有 relations 到数据库
- **THEN** 系统 SHALL 重命名文件为 `entity-relations.yaml.migrated`

#### Scenario: 迁移失败回退

- **WHEN** 自动迁移过程中发生错误
- **THEN** 系统 SHALL 记录详细错误日志
- **THEN** 系统 SHALL 保留原 YAML 文件不改名
- **THEN** 系统 SHALL 继续启动（使用文件系统模式或空状态）

#### Scenario: 已迁移的文件跳过

- **WHEN** 系统启动时只检测到 `entities.yaml.migrated` 文件
- **THEN** 系统 SHALL 跳过迁移流程
- **THEN** 系统 SHALL 从数据库加载 entities
