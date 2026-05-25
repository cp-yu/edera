## ADDED Requirements

### Requirement: Grouped entity filter selector
系统 SHALL 在 Workbench 底部工具栏提供紧凑的 entity 分组多选过滤器，避免所有 item 横向铺开。

#### Scenario: Show compact entity filter summary
- **WHEN** 当前 DAG 存在多个 entity
- **THEN** 系统 SHALL 在底部工具栏显示一个固定入口和当前选择摘要，而不是直接横向显示全部 entity item

#### Scenario: Group entity filter items
- **WHEN** 用户展开底部 entity 过滤器
- **THEN** 系统 SHALL 按 `entity.type` 分组显示可选 entity item

#### Scenario: Toggle grouped entity filter item
- **WHEN** 用户在分组面板中选择或取消选择 entity item
- **THEN** 系统 SHALL 更新现有 `entityFilter` 多选状态，并保持画布按已选 entity 过滤

#### Scenario: Clear grouped entity filter
- **WHEN** 用户点击清除入口
- **THEN** 系统 SHALL 清空 `entityFilter` 并恢复显示全部节点
