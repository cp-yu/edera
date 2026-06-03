---
capabilities:
  - cap.entity-type-protection
---
# entity-type-protection Specification

## Purpose
定义 system_protected 字段声明、前端保护展示、查看弹窗只读。
## Requirements
### Requirement: system_protected 字段声明

`EntityTypeConfig` SHALL 支持 `system_protected: bool` 字段（默认 `false`）。标记为 `true` 的 entity type 不可通过 Web Console API 被修改或删除。

#### Scenario: 加载 protected entity type

- **WHEN** 系统加载 `config/schemas/node.yaml`，其中包含 `system_protected: true`
- **THEN** 对应的 `EntityTypeConfig` 实例的 `system_protected` 属性 SHALL 为 `true`

#### Scenario: 加载普通 entity type

- **WHEN** 系统加载 `schemas/entity-types/stock.yaml`，其中不包含 `system_protected` 字段
- **THEN** 对应的 `EntityTypeConfig` 实例的 `system_protected` 属性 SHALL 为 `false`

### Requirement: 前端保护展示

前端 SHALL 对受保护的 entity type 隐藏删除按钮，并将编辑按钮替换为查看按钮。受保护判定条件为 `system_protected === true` 或类型名为 `relation`。

#### Scenario: protected 类型卡片

- **WHEN** 前端渲染 `system_protected: true` 的类型卡片
- **THEN** 卡片 SHALL 仅显示"查看"按钮，MUST NOT 显示"编辑"或"删除"按钮

#### Scenario: relation 类型卡片

- **WHEN** 前端渲染名为 `relation` 的类型卡片
- **THEN** 卡片 SHALL 仅显示"查看"按钮，MUST NOT 显示"编辑"或"删除"按钮

#### Scenario: 普通类型卡片

- **WHEN** 前端渲染 `system_protected: false` 且名称非 `relation` 的类型卡片
- **THEN** 卡片 SHALL 显示"编辑"和"删除"按钮

### Requirement: 查看弹窗只读

前端 SHALL 为受保护类型提供只读查看弹窗，展示 YAML 内容但不可编辑。

#### Scenario: 打开 protected 类型查看弹窗

- **WHEN** 用户点击 protected 类型的"查看"按钮
- **THEN** 弹窗 SHALL 显示 YAML 内容，textarea MUST 为 readonly，MUST NOT 显示保存按钮
