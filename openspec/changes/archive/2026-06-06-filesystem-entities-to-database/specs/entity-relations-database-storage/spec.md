## MODIFIED Requirements

### Requirement: Entity relations 存储到数据库
系统 SHALL 将所有 entity relations 存储到 `entity_relations` 表中。

#### Scenario: 创建 relation
- **WHEN** 用户调用 `create_relation(from="stock:00700.HK", to="rss-source:hn-rss", type="uses-source")`
- **THEN** 系统 SHALL 验证 from 和 to entity 存在
- **THEN** 系统 SHALL 生成唯一 ID
- **THEN** 系统 SHALL 插入到 `entity_relations` 表

#### Scenario: Relation 唯一性约束
- **WHEN** 创建已存在的 relation（相同 from, to, type）
- **THEN** 系统 SHALL 返回已存在的 relation，不创建重复记录

#### Scenario: 删除 relation
- **WHEN** 用户调用 `delete_relation(id="relation-id")`
- **THEN** 系统 SHALL 从 `entity_relations` 表删除该 relation

### Requirement: 查询 entity relations
系统 SHALL 提供灵活的 relation 查询接口。

#### Scenario: 按 from entity 查询
- **WHEN** 用户调用 `list_relations(from_entity_id="stock:00700.HK")`
- **THEN** 系统 SHALL 返回所有 from 字段为该 entity 的 relations

#### Scenario: 按 to entity 查询
- **WHEN** 用户调用 `list_relations(to_entity_id="rss-source:hn-rss")`
- **THEN** 系统 SHALL 返回所有 to 字段为该 entity 的 relations

#### Scenario: 按 relation type 查询
- **WHEN** 用户调用 `list_relations(relation_type="uses-source")`
- **THEN** 系统 SHALL 返回所有指定 type 的 relations

#### Scenario: 组合查询
- **WHEN** 用户调用 `list_relations(from_entity_id="stock:00700.HK", relation_type="uses-source")`
- **THEN** 系统 SHALL 返回满足所有条件的 relations

### Requirement: Relations 批量导入导出
系统 SHALL 支持 relations 的批量导入和导出。

#### Scenario: 从 YAML 导入 relations
- **WHEN** 用户调用 `import_relations("entity-relations.yaml")`
- **THEN** 系统 SHALL 解析 YAML 文件
- **THEN** 系统 SHALL 验证所有引用的 entities 存在
- **THEN** 系统 SHALL 批量创建 relations

#### Scenario: 导入时引用的 entity 不存在
- **WHEN** 导入的 relation 引用不存在的 entity
- **THEN** 系统 SHALL 记录警告日志
- **THEN** 系统 SHALL 跳过该 relation，继续导入其他 relations

#### Scenario: 导出 relations 到 YAML
- **WHEN** 用户调用 `export_relations(output="entity-relations.yaml")`
- **THEN** 系统 SHALL 查询所有 relations
- **THEN** 系统 SHALL 生成与原格式兼容的 YAML 文件

### Requirement: 删除 entity 时检查 relations
系统 SHALL 在删除 entity 前检查是否有 relations 引用该 entity。

#### Scenario: Entity 被 relations 引用时拒绝删除
- **WHEN** 用户尝试删除 entity `stock:00700.HK`
- **WHEN** 存在 relation 引用该 entity（作为 from 或 to）
- **THEN** 系统 SHALL 拒绝删除并返回错误："Entity is referenced by relations"
- **THEN** 系统 SHALL 列出引用该 entity 的 relation IDs

#### Scenario: 强制删除 entity 及其 relations
- **WHEN** 用户调用 `delete_entity(id="stock:00700.HK", force=True)`
- **THEN** 系统 SHALL 先删除所有引用该 entity 的 relations
- **THEN** 系统 SHALL 删除该 entity
