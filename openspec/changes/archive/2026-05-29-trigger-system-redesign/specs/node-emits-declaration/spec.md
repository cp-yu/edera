## ADDED Requirements

### Requirement: Node Type emits 字段

Node Type schema SHALL 包含可选 `emits` 字段，声明该类型 node 在执行完毕后可能产出的事件及其条件。`emits` MUST 为对象数组，每项包含 `event`（事件名）和 `condition`（基于 output 的布尔表达式）。

#### Scenario: 声明事件产出

- **WHEN** node type `sentiment-analyzer` 声明 `emits: [{event: "event:negative-news", condition: "output.sentiment == 'negative'"}]`
- **THEN** 该 node type 注册到事件词汇表，UI 中的事件 picker 可枚举此事件

#### Scenario: 多事件声明

- **WHEN** node type 声明多个 emits 项
- **THEN** 系统在 node 执行完毕后逐个评估每项 condition

### Requirement: DAG Runner 评估 emits 条件

DAG Runner SHALL 在 node 完成后遍历该 node 的 `emits` 列表，对每项 condition 求值；满足条件的项 MUST 调用 `emit()` 注入对应事件。

#### Scenario: 条件满足触发 emit

- **WHEN** node 执行输出 `{sentiment: "negative"}`，对应 emits 项 condition 为 `output.sentiment == 'negative'`
- **THEN** DAG Runner 调用 `emit("event:negative-news", payload={sentiment: "negative"})`

#### Scenario: 条件不满足跳过

- **WHEN** node 执行输出 `{sentiment: "positive"}`
- **THEN** condition 求值为 false，不 emit

#### Scenario: condition 求值异常容错

- **WHEN** condition 表达式引用了 output 中不存在的字段
- **THEN** DAG Runner 视为 false，不 emit，记录警告日志，不影响 DAG 继续执行

### Requirement: Node Instance 覆盖 emits

Node Instance（DAG 中的 node 实例）SHALL 支持在 instance 级 config 中声明 `emits` 字段，覆盖 Node Type 默认声明。

#### Scenario: instance 覆盖 type emits

- **WHEN** node instance config 中包含 `emits: [{event: "event:custom", condition: "output.score > 0.9"}]`
- **THEN** DAG Runner 使用 instance 级 emits 而非 type 级声明

#### Scenario: instance 不声明则继承 type

- **WHEN** node instance config 中无 `emits` 字段
- **THEN** DAG Runner 使用 Node Type 上的 emits 声明
