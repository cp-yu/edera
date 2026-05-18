## MODIFIED Requirements

### Requirement: Inspector entity selector

系统 SHALL 在 Inspector 中提供实体选择器，支持按类型分组、搜索过滤、优先显示关联实体。

#### Scenario: Display entity selector

- **WHEN** 用户在 Inspector 中选择节点
- **THEN** 系统 SHALL 显示实体选择器，类似 skills 的多选组件

#### Scenario: Group entities by type

- **WHEN** 实体选择器展开
- **THEN** 系统 SHALL 按 entity type 分组显示实体（如 "股票"、"信息源"）

#### Scenario: Prioritize related entities

- **WHEN** 节点配置了 source，且 `entity-relations.yaml` 中有关联关系
- **THEN** 系统 SHALL 在选择器顶部优先显示关联的实体

#### Scenario: Search entities

- **WHEN** 用户在实体选择器中输入搜索关键词
- **THEN** 系统 SHALL 过滤显示匹配的实体（匹配 display_template 渲染结果）

#### Scenario: Save selected entities

- **WHEN** 用户选择实体后点击保存
- **THEN** 系统 SHALL 将 `entities` 字段保存到节点的 `config` 中

### Requirement: Inspector permission overrides

系统 SHALL 在 Inspector 中提供权限覆盖配置器，支持按需添加字段权限提权。

#### Scenario: Display permission overrides section

- **WHEN** 用户在 Inspector 中选择节点
- **THEN** 系统 SHALL 显示"实体权限覆盖"区域，默认为空

#### Scenario: Add permission override

- **WHEN** 用户点击"添加权限覆盖"按钮
- **THEN** 系统 SHALL 显示字段选择器和权限选择器

#### Scenario: Select field to override

- **WHEN** 用户在字段选择器中选择 entity type 和字段（如 `stock.code`）
- **THEN** 系统 SHALL 显示该字段的默认权限和可选的提权选项

#### Scenario: Select permission level

- **WHEN** 用户选择权限级别（如从 `read-only` 提权到 `read-write`）
- **THEN** 系统 SHALL 验证是否为合法提权（不能降权）

#### Scenario: Save permission overrides

- **WHEN** 用户点击保存
- **THEN** 系统 SHALL 将 `entity_permissions` 字段保存到节点的 `config` 中

#### Scenario: Remove permission override

- **WHEN** 用户点击权限覆盖条目的删除按钮
- **THEN** 系统 SHALL 从配置中移除该字段的权限覆盖

### Requirement: Target filtering replaced by entity filtering

系统 SHALL 将底部工具栏的 target 过滤器替换为 entity 过滤器，支持按任意 entity type 过滤。

#### Scenario: Filter by entity

- **WHEN** 用户在底部工具栏选择特定 entity 进行过滤
- **THEN** 系统 SHALL 将不包含该 entity 的节点 opacity 降至 0.2，匹配节点保持 1.0

#### Scenario: Entity filter shows all types

- **WHEN** 用户打开 entity 过滤器
- **THEN** 系统 SHALL 显示所有 entity types 的实体（不仅限于 stock）

#### Scenario: Clear entity filter

- **WHEN** 用户清除所有 entity 过滤
- **THEN** 系统 SHALL 恢复所有节点为完全不透明
