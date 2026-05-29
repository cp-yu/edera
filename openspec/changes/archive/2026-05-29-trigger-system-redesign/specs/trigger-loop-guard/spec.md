## ADDED Requirements

### Requirement: emit 深度计数

系统 SHALL 为每次 emit 调用维护深度计数器，初始为 0；trigger fire 引发的下游 emit 深度递增。

#### Scenario: 浅层 emit 通过

- **WHEN** 外部调用 `emit("event:a", depth=0)`，trigger A fire 后调度 DAG，DAG 内 node emit `event:b`（depth=1），trigger B fire 调度 DAG，DAG 内 node emit `event:c`（depth=2）
- **THEN** 三次 emit 全部成功

#### Scenario: 超过深度阈值拒绝

- **WHEN** emit 深度达到 `system.max_trigger_depth`（默认 3）后再次链式 emit
- **THEN** 系统拒绝该 emit 调用，记录告警日志，不置位 bit

### Requirement: 深度阈值可配

系统 SHALL 通过 `system.toml` 中的 `max_trigger_depth` 字段配置深度阈值，默认值为 3。

#### Scenario: 调整阈值

- **WHEN** 用户在 `system.toml` 设置 `max_trigger_depth = 5`
- **THEN** 系统在加载配置后，允许 emit 链式深度最大为 5

#### Scenario: 阈值非法值拒绝加载

- **WHEN** `max_trigger_depth` 配置为负数或非整数
- **THEN** 系统启动时报错并拒绝加载
