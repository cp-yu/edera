## MODIFIED Requirements

### Requirement: 节点上下文实体访问

系统 SHALL 在节点执行时提供实体访问接口，支持读取和保存实体。Pipeline services SHALL 直接使用 `EntityStore` 获取实体数据，不再通过兼容层间接访问。

#### Scenario: 读取实体

- **WHEN** 节点调用 `context.get_entity("stock:00700.HK")`
- **THEN** 系统返回对应的实体对象，包含 `id`, `type`, `attributes`

#### Scenario: 保存实体

- **WHEN** 节点修改实体的 `attributes` 后调用 `context.save_entity(entity)`
- **THEN** 系统检查权限，保存允许修改的字段，忽略受保护字段

#### Scenario: 创建新实体

- **WHEN** 节点调用 `context.create_entity(type="stock", attributes={...})`
- **THEN** 系统生成 UUID，验证 attributes，保存到 `entities.yaml`

#### Scenario: Pipeline service 获取 source 实体

- **WHEN** collection service 需要获取信息源列表
- **THEN** 系统 SHALL 通过 `EntityStore` 按 type 过滤（`rss-source`、`web-source`）获取实体，直接从 `attributes` 读取 URL、regex 等字段

#### Scenario: Pipeline service 获取 stock 实体

- **WHEN** advisory/briefing service 需要获取股票列表
- **THEN** 系统 SHALL 通过 `EntityStore` 按 type 过滤（`stock`）获取实体，直接从 `attributes` 读取 code、name、holding 等字段

#### Scenario: Pipeline service 获取实体关系

- **WHEN** collection service 需要确定 stock 关联的 sources
- **THEN** 系统 SHALL 通过 `EntityStore` 查询 `entity-relations` 获取关联关系
