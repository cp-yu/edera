## ADDED Requirements

### Requirement: Node instance loop configuration in Inspector

系统 SHALL 在用户选中画布上的节点实例时，在 Inspector Config tab 提供「循环」折叠区块，编辑实例顶层字段 `loop`（mode/count/until）与 `resource`。区块默认在实例无 `loop` 配置时收起。保存 SHALL 将两字段写入节点实例顶层（与 `optional` 同层），MUST NOT 写入 `config`。

#### Scenario: 循环区块渲染

- **WHEN** 用户选中节点实例并展开「循环」区块
- **THEN** Inspector SHALL 展示 mode 下拉（无/parallel/serial）、count 数字输入、until 文本输入、resource 下拉

#### Scenario: resource 下拉选项来源

- **WHEN** 「循环」区块渲染 resource 下拉
- **THEN** 选项 SHALL 来自 DAG state 返回的 entities 中 `type` 为 `resource` 者，并包含「无」选项

#### Scenario: 保存写入顶层字段

- **WHEN** 用户配置 mode=parallel、count=3 并保存实例
- **THEN** PUT 的节点 record SHALL 包含顶层 `loop: {mode: "parallel", count: 3}`，`config` 中 MUST NOT 出现 loop

#### Scenario: 清除循环配置

- **WHEN** 用户将 mode 改回「无」并保存
- **THEN** 节点 record 的 `loop` 字段 SHALL 被移除或置 null，持久化后实例不再循环

### Requirement: Canvas loop badge

系统 SHALL 在画布节点卡片上展示循环徽标：并行模式显示 `∥ ×N`，串行模式显示 `⟳ ×N`，配置了 `until` 时附加条件标记。无 `loop` 配置的节点 MUST NOT 显示徽标。

#### Scenario: 并行徽标

- **WHEN** 节点实例配置 `loop: {mode: parallel, count: 3}`
- **THEN** 节点卡片 SHALL 显示 `∥ ×3` 徽标

#### Scenario: 串行带条件徽标

- **WHEN** 节点实例配置 `loop: {mode: serial, count: 5, until: "..."}`
- **THEN** 节点卡片 SHALL 显示 `⟳ ×5` 徽标及条件标记

#### Scenario: 无循环无徽标

- **WHEN** 节点实例未配置 `loop`
- **THEN** 节点卡片 MUST NOT 显示循环徽标
