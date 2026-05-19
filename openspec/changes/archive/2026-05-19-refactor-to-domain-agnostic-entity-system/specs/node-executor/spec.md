## ADDED Requirements

### Requirement: Entity context injection

Node executor SHALL 在节点执行时注入实体上下文，提供 `context.get_entity()`, `context.save_entity()`, `context.create_entity()` 接口。

#### Scenario: Get entity by reference

- **WHEN** 节点调用 `context.get_entity("stock:00700.HK")`
- **THEN** executor 解析引用（UUID 或业务 ID），返回对应的实体对象

#### Scenario: Get entity not found

- **WHEN** 节点调用 `context.get_entity()` 引用不存在的实体
- **THEN** executor 抛出异常 "Entity not found: <reference>"

#### Scenario: Save entity with permission check

- **WHEN** 节点修改实体后调用 `context.save_entity(entity)`
- **THEN** executor 检查字段权限，保存允许修改的字段，记录警告日志并忽略受保护字段

#### Scenario: Create new entity

- **WHEN** 节点调用 `context.create_entity(type="stock", attributes={...})`
- **THEN** executor 生成 UUID，验证 attributes，保存到 `entities.yaml`

### Requirement: Field permission enforcement

Node executor SHALL 在节点访问实体字段时检查权限，违反权限时发出警告并阻止操作。

#### Scenario: Read protected field

- **WHEN** 节点尝试读取权限为 `none` 或 `write-only` 的字段
- **THEN** executor 记录警告 "Permission denied: <entity_type>.<field> is not readable"，返回 None

#### Scenario: Write protected field

- **WHEN** 节点尝试修改权限为 `none` 或 `read-only` 的字段
- **THEN** executor 记录警告 "Permission denied: <entity_type>.<field> is not writable"，不保存修改

#### Scenario: Permission check uses instance overrides

- **WHEN** 节点实例配置了 `entity_permissions: {stock: {code: read-write}}`
- **THEN** executor 使用实例权限（`read-write`）而非默认权限（`read-only`）

### Requirement: Entity auto-discovery

Node executor SHALL 在节点配置只指定 source 而未指定 entities 时，自动从 `entity-relations.yaml` 发现关联实体。

#### Scenario: Auto-discover entities from source

- **WHEN** 节点配置 `config: {source: "rss-source:sample-rss"}`，未指定 `entities`
- **THEN** executor 查找 `entity-relations.yaml` 中包含该 source 的关系，返回关联的其他实体

#### Scenario: Explicit entities override auto-discovery

- **WHEN** 节点配置 `config: {source: "rss-source:sample-rss", entities: ["stock:600519.SH"]}`
- **THEN** executor 使用显式配置的 `entities`，忽略自动发现

#### Scenario: Empty entities disable auto-discovery

- **WHEN** 节点配置 `config: {source: "rss-source:sample-rss", entities: []}`
- **THEN** executor 不提供任何实体上下文
