---
capabilities:
  - cap.web.trigger-workbench-inspector
---
# trigger-workbench-inspector Specification

## Purpose
定义 Inspector Triggers tab、trigger 表达式编辑器、闹钟式 cron 片段生成器、事件源片段生成器等能力。
## Requirements
### Requirement: Inspector Triggers tab

Web Console 的 Workbench Inspector SHALL 在 `Config | Runtime` 之外增加 `Triggers` tab。Tab 内容根据当前选中目标切换：

- 无选中（canvas 空白）→ 显示 DAG 级 trigger 列表（`target = dag:{name}`）
- 选中 node → 显示 node 级 trigger 列表（`target = node:{id}`）

#### Scenario: 无选中显示 DAG 级 trigger

- **WHEN** 用户进入 Workbench 选中 DAG `default` 但未选中任何 node
- **THEN** Inspector 显示 `Triggers` tab，列出所有 `target = "dag:default"` 的 trigger entity

#### Scenario: 选中 node 显示 node 级 trigger

- **WHEN** 用户在 Canvas 中点击某 node `<node-id>`
- **THEN** Inspector 切换到 node 视图，`Triggers` tab 列出所有 `target = "node:<node-id>"` 的 trigger entity

#### Scenario: 切换目标后 trigger 列表更新

- **WHEN** 用户从一个 node 切换选中到另一个 node
- **THEN** Triggers tab 列表立即刷新为新 node 的 trigger 列表

### Requirement: trigger 表达式编辑器

Triggers tab SHALL 提供文本输入框作为 `wait_for` 表达式的主编辑面。文本输入 MUST 支持手写表达式，并在保存前进行语法校验。

#### Scenario: 直接编辑表达式

- **WHEN** 用户在表达式输入框中输入 `cron:"0 9 * * *" AND event:market-open` 并保存
- **THEN** 系统校验语法通过后保存到 trigger entity

#### Scenario: 语法错误提示

- **WHEN** 用户输入 `cron:0 9 * * * AND event:x`（cron 无引号）并保存
- **THEN** 系统在输入框下方显示语法错误提示，不保存

### Requirement: 闹钟式 cron 片段生成器

Triggers tab SHALL 提供"插入定时" picker，以闹钟交互形式生成 `cron:"..."` token 并插入表达式输入框光标位置。Picker MUST 支持时间选择和重复规则（每天 / 工作日 / 周末 / 自定义周几 / 一次性）。

#### Scenario: 闹钟生成每日 cron

- **WHEN** 用户在 picker 中选择时间 09:00、重复规则 "每天"
- **THEN** picker 在表达式输入框光标位置插入 `cron:"0 9 * * *"`

#### Scenario: 闹钟生成工作日 cron

- **WHEN** 用户选择时间 09:00、重复规则 "工作日"
- **THEN** picker 插入 `cron:"0 9 * * 1-5"`

#### Scenario: 闹钟生成一次性 cron

- **WHEN** 用户选择时间 09:00、重复规则 "不重复"，日期 2026-05-30
- **THEN** picker 插入 `cron:"0 9 30 5 *"`，并在该 trigger fire 后系统自动设置 `enabled=false`

#### Scenario: 高级模式直写 cron

- **WHEN** 用户切换 picker 到 "高级" 模式输入 `*/15 * * * *`
- **THEN** picker 插入 `cron:"*/15 * * * *"`

### Requirement: 事件源片段生成器

Triggers tab SHALL 提供"插入事件" picker，从已知事件源（系统事件 + Node Type 声明的 emits）中选择并生成 `event:<name>` token 插入表达式输入框。Picker MUST 也支持手写自定义事件名。

#### Scenario: 从 Node Type emits 选择事件

- **WHEN** 用户打开事件 picker，选择 node type `sentiment-analyzer` 声明的 `event:negative-news`
- **THEN** picker 在表达式输入框插入 `event:negative-news`

#### Scenario: 选择系统事件

- **WHEN** 用户选择系统事件 `event:config-changed`
- **THEN** picker 插入 `event:config-changed`

#### Scenario: 手写自定义事件

- **WHEN** 用户在 picker 中输入未注册的 `event:my-custom-event`
- **THEN** picker 接受并插入该事件名

### Requirement: trigger CRUD 操作

Triggers tab SHALL 支持创建、编辑、删除、启用/禁用 trigger entity。

#### Scenario: 创建新 trigger

- **WHEN** 用户在 Triggers tab 点击"新建"按钮，填写表达式和 target，点击"保存"
- **THEN** 系统通过 `EntityService.Create` 创建一个 type=trigger 的 entity，自动设置 `target` 为当前视图对象（DAG 或 node）

#### Scenario: 启用/禁用 trigger

- **WHEN** 用户在 trigger 列表中切换某 trigger 的 `enabled` 开关
- **THEN** 系统更新该 trigger entity 的 `enabled` 字段

#### Scenario: 删除 trigger

- **WHEN** 用户点击某 trigger 的"删除"按钮并确认
- **THEN** 系统通过 `EntityService.Delete` 删除该 trigger entity
