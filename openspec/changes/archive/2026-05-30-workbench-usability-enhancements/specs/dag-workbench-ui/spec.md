## MODIFIED Requirements

### Requirement: Node palette with drag-to-add
系统 SHALL 在左侧面板按 role 分组展示可用节点类型（Sources / Processors / Sinks），并在每个 role 分组内按节点名称前缀做二级分组。系统 SHALL 支持拖拽到画布创建节点实例。画布 SHALL 允许同一节点类型被多次拖入，每次创建独立实例。

#### Scenario: Grouped display by role and prefix
- **WHEN** 用户打开 Palette 面板
- **THEN** 系统 SHALL 将节点类型按 `role` 分为 Sources、Processors、Sinks
- **AND** 系统 SHALL 在每个 `role` 组内按节点名称前缀显示二级分组

#### Scenario: Drag to create instance
- **WHEN** 用户将节点类型从 Palette 拖入画布
- **THEN** 系统 SHALL 创建一个新的节点实例（生成 UUID），而非引用类型本身

#### Scenario: Multiple instances of same type
- **WHEN** 用户将同一节点类型拖入画布多次
- **THEN** 系统 SHALL 为每次拖入创建独立实例（不同 UUID），不做去重限制

#### Scenario: Search matches type name and instance alias
- **WHEN** 用户在 Palette 搜索框输入关键词
- **THEN** 系统 SHALL 同时匹配节点类型名称和当前 DAG 中已有实例的别名

### Requirement: Node inspector with editable/readonly fields
系统 SHALL 在右侧 Inspector 面板根据节点类型展示差异化的编辑字段。Config tab 中的实例保存动作 SHALL 固定显示在 Inspector 可视域底部。

#### Scenario: Fetcher node inspector
- **WHEN** 用户选中类型为 `fetcher` 的节点
- **THEN** 系统 SHALL 展示 source_names、timeout_seconds、parameters 编辑字段

#### Scenario: LLM node inspector
- **WHEN** 用户选中类型为 `llm` 的节点
- **THEN** 系统 SHALL 展示 model、timeout_seconds、skills、parameters 编辑字段

#### Scenario: Aggregator node inspector
- **WHEN** 用户选中类型为 `aggregator` 的节点
- **THEN** 系统 SHALL 展示 timeout_seconds、parameters 编辑字段

#### Scenario: Common readonly fields
- **WHEN** Inspector 展示任意类型节点
- **THEN** 系统 SHALL 以只读方式展示 name、type、input_type、output_type 字段

#### Scenario: Config save remains visible
- **WHEN** 用户在 Inspector Config tab 中滚动长表单
- **THEN** 系统 SHALL 保持“保存实例”动作固定显示在 Inspector 可视域底部

#### Scenario: Non-config tabs do not show instance save footer
- **WHEN** 用户切换到 Runtime 或 Triggers tab
- **THEN** 系统 SHALL NOT 显示 Config tab 的“保存实例”固定 footer
