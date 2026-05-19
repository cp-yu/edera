## ADDED Requirements

### Requirement: Read entities config via dedicated endpoint

系统 SHALL 提供 `GET /api/config/entities` 端点，返回 entities 配置文件的原始 YAML 文本内容。

#### Scenario: Read entities config successfully

- **WHEN** 前端请求 `GET /api/config/entities`
- **THEN** 系统 SHALL 返回 `{ "content": "<yaml text>" }` 格式的响应

#### Scenario: Entities config file missing

- **WHEN** `config/entities.yaml` 文件不存在
- **THEN** 系统 MUST 返回 404 错误，包含 `not_found` 错误类型

### Requirement: Read entity-relations config via dedicated endpoint

系统 SHALL 提供 `GET /api/config/entity-relations` 端点，返回 entity-relations 配置文件的原始 YAML 文本内容。

#### Scenario: Read entity-relations config successfully

- **WHEN** 前端请求 `GET /api/config/entity-relations`
- **THEN** 系统 SHALL 返回 `{ "content": "<yaml text>" }` 格式的响应

#### Scenario: Entity-relations config file missing

- **WHEN** `config/entity-relations.yaml` 文件不存在
- **THEN** 系统 MUST 返回 404 错误，包含 `not_found` 错误类型

### Requirement: Save entities config

系统 SHALL 支持通过 `POST /api/config/entities` 保存 entities 配置，并验证实体类型和 schema。

#### Scenario: Save valid entities config

- **WHEN** 用户提交符合 entities schema 的配置
- **THEN** 系统 SHALL 原子写入 `config/entities.yaml`，并返回保存成功状态

#### Scenario: Reject invalid entity type

- **WHEN** 用户提交的实体 `type` 在 `schemas/entity-types/` 中不存在
- **THEN** 系统 MUST 拒绝保存并返回校验错误 "Unknown entity type: <type>"

#### Scenario: Reject invalid entity attributes

- **WHEN** 用户提交的实体 `attributes` 不符合对应类型的 schema
- **THEN** 系统 MUST 拒绝保存并返回校验错误

### Requirement: Save entity-relations config

系统 SHALL 支持通过 `POST /api/config/entity-relations` 保存 entity-relations 配置，并验证引用的实体存在。

#### Scenario: Save valid entity-relations config

- **WHEN** 用户提交符合 entity-relations schema 的配置
- **THEN** 系统 SHALL 原子写入 `config/entity-relations.yaml`，并返回保存成功状态

#### Scenario: Reject relation with non-existent entity

- **WHEN** 用户提交的关系引用不存在的实体
- **THEN** 系统 MUST 拒绝保存并返回校验错误 "Entity not found: <entity_ref>"

## REMOVED Requirements

### Requirement: Structured portfolio management entry

**Reason**: Portfolio 概念被废弃，替换为通用的 entities 管理

**Migration**: 实体管理将通过新的实体管理页面或通用配置编辑入口完成

### Requirement: Structured portfolio save

**Reason**: Portfolio 概念被废弃，替换为通用的 entities 系统

**Migration**: 使用 `POST /api/config/entities` 保存实体配置

### Requirement: Portfolio save semantics

**Reason**: Portfolio 概念被废弃，替换为通用的 entities 系统

**Migration**: Entities 配置保存复用相同的原子写入和配置快照语义

### Requirement: Read portfolio config via dedicated endpoint

**Reason**: Portfolio 概念被废弃，替换为通用的 entities 系统

**Migration**: 使用 `GET /api/config/entities` 读取实体配置
