## ADDED Requirements

### Requirement: Trigger Entity 定义

系统 SHALL 支持通过 Trigger Entity 定义触发规则。Trigger Entity MUST 包含 `wait_for`（事件组条件）和 `target`（触发目标）字段。

#### Scenario: 定义时间触发器

- **WHEN** 用户创建 Trigger Entity，`wait_for: {mode: OR, events: ["schedule:09:00"]}`，`target: "dag:morning-analysis"`
- **THEN** 系统在每天 09:00 触发 `dag:morning-analysis` 的执行

#### Scenario: 定义事件触发器

- **WHEN** 用户创建 Trigger Entity，`wait_for: {mode: OR, events: ["event:config-changed"]}`，`target: "dag:config-validation"`
- **THEN** 系统在 config/ 文件变更时触发 `dag:config-validation` 的执行

#### Scenario: 定义叠加触发器

- **WHEN** 用户创建 Trigger Entity，`wait_for: {mode: AND, events: ["schedule:09:00", "event:market-open"]}`，`target: "dag:morning-analysis"`
- **THEN** 系统在 09:00 且 market-open 事件都满足时才触发执行

### Requirement: 事件组机制

系统 SHALL 实现 FreeRTOS 风格的事件组机制，支持 AND（全部满足）和 OR（任一满足）组合等待。

#### Scenario: AND 模式等待

- **WHEN** Trigger 配置 `mode: AND`，等待 `schedule:09:00` 和 `event:market-open` 两个事件
- **THEN** 系统仅在两个事件都置位后才触发目标执行

#### Scenario: OR 模式等待

- **WHEN** Trigger 配置 `mode: OR`，等待 `event:price-drop` 和 `event:volume-spike` 两个事件
- **THEN** 系统在任一事件置位后即触发目标执行

#### Scenario: 事件消费后清除

- **WHEN** 事件被 Trigger 消费触发执行后
- **THEN** 系统清除该事件的置位状态，下次需要重新触发

### Requirement: 事件源注册

系统 SHALL 支持多种事件源。任何可观测的状态变化 MUST 可以作为事件源。

#### Scenario: Entity 变更事件

- **WHEN** 一个 Entity 的 attributes 被修改
- **THEN** 系统产生 `event:entity-changed:{entity_ref}` 事件

#### Scenario: 配置文件变更事件

- **WHEN** `config/` 目录下的文件被修改
- **THEN** 系统产生 `event:config-changed` 事件

#### Scenario: 时间调度事件

- **WHEN** 系统时钟到达 Trigger 中声明的 schedule 时间
- **THEN** 系统产生对应的 `schedule:{time}` 事件

#### Scenario: Node 输出条件事件

- **WHEN** Node 执行输出满足预定义条件（如 `output.sentiment == 'negative'`）
- **THEN** 系统产生对应的自定义事件

### Requirement: 触发目标

系统 SHALL 支持触发任何可执行 Entity。触发目标 MUST 通过 Entity 引用指定。

#### Scenario: 触发 DAG 执行

- **WHEN** Trigger 的 `target` 指向一个 DAG Entity
- **THEN** Trigger Executor 启动该 DAG 的一次完整执行

#### Scenario: 触发单 Node 执行

- **WHEN** Trigger 的 `target` 指向一个 Node Entity
- **THEN** Trigger Executor 直接执行该 Node（不经过 DAG 调度）

#### Scenario: 用户手动触发

- **WHEN** 用户通过 Web Console 或 API 手动触发一个 Trigger
- **THEN** 系统立即执行该 Trigger 的目标，无需等待事件条件满足

### Requirement: 事件记录可观测

系统 SHALL 将事件的发生和消费记录到 run metadata Entity 中，确保可观测性。

#### Scenario: 事件触发记录

- **WHEN** 一个事件被产生并触发了 Trigger
- **THEN** 系统在 run metadata Entity 中记录事件名称、产生时间、消费时间和触发的目标
