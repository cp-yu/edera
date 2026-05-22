## MODIFIED Requirements

### Requirement: Inspector permission overrides

系统 SHALL 在 Inspector 中提供权限覆盖配置器，仅展示当前节点已选 entities 对应的 entity type 的权限字段，支持按需添加字段权限提权。

#### Scenario: Filter by selected entities

- **WHEN** 节点已选择 entities（如 `["stock:AAPL", "web-source:reuters"]`）
- **THEN** 系统 SHALL 仅展示 `stock` 和 `web-source` 两个 entity type 的权限字段

#### Scenario: No entities selected

- **WHEN** 节点未选择任何 entity
- **THEN** 系统 SHALL 不展示权限配置器，或展示空状态提示

#### Scenario: Entity deselection cleans permissions

- **WHEN** 用户取消选择某个 entity，导致其 type 不再被任何已选 entity 引用
- **THEN** 系统 SHALL 自动清除该 type 的 permission overrides

#### Scenario: Add permission override

- **WHEN** 用户点击"添加权限覆盖"按钮
- **THEN** 系统 SHALL 显示字段选择器和权限选择器

#### Scenario: Select field to override

- **WHEN** 用户在字段选择器中选择 entity type 和字段
- **THEN** 系统 SHALL 显示该字段的默认权限和可选的提权选项

#### Scenario: Select permission level

- **WHEN** 用户选择权限级别
- **THEN** 系统 SHALL 验证是否为合法提权（不能降权）

#### Scenario: Save permission overrides

- **WHEN** 用户点击保存
- **THEN** 系统 SHALL 将 `entity_permissions` 字段保存到节点的 `config` 中

#### Scenario: Remove permission override

- **WHEN** 用户点击权限覆盖条目的删除按钮
- **THEN** 系统 SHALL 从配置中移除该字段的权限覆盖
