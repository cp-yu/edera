## ADDED Requirements

### Requirement: Entity list 命令
系统 SHALL 提供 `edera entity list` 命令列出所有 entities，支持通用列过滤。

#### Scenario: 列出所有 entities
- **WHEN** 用户执行 `edera entity list`
- **THEN** 系统 SHALL 显示所有 entities 的 ID、type、简要信息

#### Scenario: 按 type 过滤
- **WHEN** 用户执行 `edera entity list --type stock`
- **THEN** 系统 SHALL 只显示 type 为 stock 的 entities

#### Scenario: 通用列过滤
- **WHEN** 用户执行 `edera entity list --type relation --filter from_entity_id=stock:00700.HK`
- **THEN** 系统 SHALL 查询 entity_relations 表，WHERE from_entity_id='stock:00700.HK'
- **THEN** 系统 SHALL 返回满足条件的 relations

#### Scenario: 多列组合过滤
- **WHEN** 用户执行 `edera entity list --type relation --filter from_entity_id=stock:00700.HK --filter relation_type=uses-source`
- **THEN** 系统 SHALL 应用所有过滤条件（AND 逻辑）
- **THEN** 系统 SHALL 返回满足所有条件的 entities

### Requirement: Entity show 命令
系统 SHALL 提供 `edera entity show` 命令显示 entity 详情。

#### Scenario: 显示 entity 详情
- **WHEN** 用户执行 `edera entity show stock:00700.HK`
- **THEN** 系统 SHALL 显示该 entity 的完整 attributes（JSON 格式）

#### Scenario: Entity 不存在
- **WHEN** 用户执行 `edera entity show nonexistent`
- **THEN** 系统 SHALL 返回错误："Entity not found: nonexistent"

### Requirement: Entity create 命令
系统 SHALL 提供 `edera entity create` 命令创建 entity。

#### Scenario: 创建 entity
- **WHEN** 用户执行 `edera entity create --type stock --id stock-new --attributes '{"code":"AAPL","name":"Apple"}'`
- **THEN** 系统 SHALL 创建该 entity 并返回成功消息

#### Scenario: 缺少必填参数
- **WHEN** 用户执行 `edera entity create --type stock`（缺少 attributes）
- **THEN** 系统 SHALL 返回错误："Missing required parameter: --attributes"

### Requirement: Entity update 命令
系统 SHALL 提供 `edera entity update` 命令更新 entity。

#### Scenario: 更新 entity attributes
- **WHEN** 用户执行 `edera entity update stock:00700.HK --attributes '{"holding":{"quantity":200}}'`
- **THEN** 系统 SHALL 合并 attributes 并更新数据库
- **THEN** 系统 SHALL 返回更新后的 entity

### Requirement: Entity delete 命令
系统 SHALL 提供 `edera entity delete` 命令删除 entity。

#### Scenario: 删除 entity
- **WHEN** 用户执行 `edera entity delete stock:00700.HK`
- **THEN** 系统 SHALL 检查 relations 引用
- **THEN** 如无引用，系统 SHALL 删除 entity

#### Scenario: 强制删除
- **WHEN** 用户执行 `edera entity delete stock:00700.HK --force`
- **THEN** 系统 SHALL 删除相关 relations 和 entity

### Requirement: Entity import 命令
系统 SHALL 提供 `edera entity import` 命令从 YAML 导入。

#### Scenario: 导入 YAML 文件
- **WHEN** 用户执行 `edera entity import entities.yaml`
- **THEN** 系统 SHALL 读取文件并批量导入 entities
- **THEN** 系统 SHALL 显示导入统计："Imported 5 entities, 0 errors"

### Requirement: Entity export 命令
系统 SHALL 提供 `edera entity export` 命令导出为 YAML。

#### Scenario: 导出所有 entities
- **WHEN** 用户执行 `edera entity export -o entities.yaml`
- **THEN** 系统 SHALL 生成 YAML 文件包含所有 entities

#### Scenario: 按 type 导出
- **WHEN** 用户执行 `edera entity export --type stock -o stocks.yaml`
- **THEN** 系统 SHALL 只导出 stock 类型的 entities

### Requirement: Relation CLI 别名（语法糖）
系统 SHALL 提供 `edera relation` 别名命令，简化常见 relation 操作。

#### Scenario: relation list 别名
- **WHEN** 用户执行 `edera relation list --from stock:00700.HK --to rss-source:hn --type uses-source`
- **THEN** 系统 SHALL 转换为 `edera entity list --type relation --filter from_entity_id=stock:00700.HK --filter to_entity_id=rss-source:hn --filter relation_type=uses-source`
- **THEN** 系统 SHALL 执行查询并返回结果

#### Scenario: relation create 别名
- **WHEN** 用户执行 `edera relation create --from stock:00700.HK --to rss-source:hn --type uses-source`
- **THEN** 系统 SHALL 转换为 `edera entity create --type relation --attributes '{"from_entity_id":"stock:00700.HK","to_entity_id":"rss-source:hn","relation_type":"uses-source"}'`
- **THEN** 系统 SHALL 创建 relation

#### Scenario: relation delete 别名
- **WHEN** 用户执行 `edera relation delete <relation-id>`
- **THEN** 系统 SHALL 转换为 `edera entity delete <relation-id>`
- **THEN** 系统 SHALL 删除 relation

#### Scenario: relation import/export 别名
- **WHEN** 用户执行 `edera relation import entity-relations.yaml`
- **THEN** 系统 SHALL 调用 `import_entities_from_yaml()` 并过滤 type=relation
- **WHEN** 用户执行 `edera relation export -o entity-relations.yaml`
- **THEN** 系统 SHALL 调用 `export_entities_to_yaml(entity_type="relation")`
