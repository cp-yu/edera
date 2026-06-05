## ADDED Requirements

### Requirement: 普通 entities 存储到数据库
系统 SHALL 将所有普通 entities（非核心 entities）存储到数据库的动态表中，按 entity type 分表。

#### Scenario: 创建 entity 时自动创建表
- **WHEN** 创建第一个 `type: stock` 的 entity
- **THEN** 系统 SHALL 检查表 `entity_stock` 是否存在
- **THEN** 如果不存在，系统 SHALL 根据 `entity_types` 表中的 schema 创建表

#### Scenario: 保存 entity 到对应表
- **WHEN** 保存 entity `id: stock-00700-hk, type: stock`
- **THEN** 系统 SHALL 将 entity 插入或更新到 `entity_stock` 表
- **THEN** 系统 SHALL 序列化 attributes 为 JSON 存储

#### Scenario: 从数据库加载所有 entities
- **WHEN** 系统启动时加载 entities
- **THEN** 系统 SHALL 查询所有 entity type 表
- **THEN** 系统 SHALL 将所有 entities 加载到 `EntityStore` 内存中

### Requirement: Entity CRUD 操作
系统 SHALL 提供 entity 的创建、读取、更新、删除操作。

#### Scenario: 创建 entity
- **WHEN** 用户调用 `create_entity(type="stock", id="stock-new", attributes={...})`
- **THEN** 系统 SHALL 验证 entity type 存在
- **THEN** 系统 SHALL 验证 attributes 符合 schema
- **THEN** 系统 SHALL 保存到对应表并返回 entity

#### Scenario: 更新 entity
- **WHEN** 用户调用 `update_entity(id="stock-00700-hk", attributes={...})`
- **THEN** 系统 SHALL 验证 entity 存在
- **THEN** 系统 SHALL 合并 attributes（保留未修改字段）
- **THEN** 系统 SHALL 更新数据库

#### Scenario: 删除 entity
- **WHEN** 用户调用 `delete_entity(id="stock-00700-hk")`
- **THEN** 系统 SHALL 从数据库删除该 entity
- **THEN** 系统 SHALL 检查是否有 relations 引用该 entity，如有则拒绝删除

### Requirement: 从文件导入 entities
系统 SHALL 支持从 YAML 文件批量导入 entities。

#### Scenario: 导入 YAML 文件
- **WHEN** 用户调用 `import_entities("entities.yaml")`
- **THEN** 系统 SHALL 解析 YAML 文件
- **THEN** 系统 SHALL 逐个创建或更新 entities
- **THEN** 系统 SHALL 返回导入成功和失败的统计

#### Scenario: 导入时 ID 冲突
- **WHEN** 导入的 entity ID 已存在
- **THEN** 系统 SHALL 更新现有 entity（覆盖模式）
- **THEN** 系统 SHALL 记录更新日志

### Requirement: 导出 entities 到文件
系统 SHALL 支持将 entities 导出为 YAML 文件。

#### Scenario: 导出所有 entities
- **WHEN** 用户调用 `export_entities(output="entities.yaml")`
- **THEN** 系统 SHALL 查询所有 entities
- **THEN** 系统 SHALL 生成 YAML 格式文件

#### Scenario: 按 type 过滤导出
- **WHEN** 用户调用 `export_entities(type="stock", output="stocks.yaml")`
- **THEN** 系统 SHALL 只导出指定 type 的 entities
