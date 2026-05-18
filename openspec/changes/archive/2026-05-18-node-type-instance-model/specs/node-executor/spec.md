## ADDED Requirements

### Requirement: Node execution by instance ID
系统 SHALL 按 DAG 拓扑顺序调度节点实例执行，使用实例 UUID 作为调度和状态上报的索引键。

#### Scenario: Schedule by instance ID
- **WHEN** DAG 执行引擎启动一个运行周期
- **THEN** 系统 SHALL 按拓扑顺序遍历节点实例（通过 UUID 标识），而非节点类型名

#### Scenario: Runtime status indexed by instance ID
- **WHEN** 节点实例执行完成并上报状态
- **THEN** 系统 SHALL 以实例 UUID 为键存储运行状态（running/succeeded/failed）

#### Scenario: Multiple instances of same type execute independently
- **WHEN** DAG 中存在同一类型的多个实例
- **THEN** 系统 SHALL 独立调度和执行每个实例，各自维护独立的运行状态

### Requirement: Dynamic handler loading
系统 SHALL 通过 `importlib` 从 `handlers/` 目录动态加载 Function 节点的 handler。

#### Scenario: Load handler by name
- **WHEN** 系统执行一个 Function 节点实例且其类型定义 `handler: fetch-rss`
- **THEN** 系统 SHALL 动态加载 `handlers/fetch-rss.py` 并调用其 `run(input_data, parameters, context)` 函数

#### Scenario: Handler not found
- **WHEN** handler 文件不存在于 `handlers/` 目录
- **THEN** 系统 SHALL 将该节点实例标记为 `failed` 并记录错误信息

#### Scenario: Handler runtime error
- **WHEN** handler 执行过程中抛出异常
- **THEN** 系统 SHALL 捕获异常，将节点实例标记为 `failed`，记录错误堆栈

### Requirement: Instance config resolution
系统 SHALL 在执行节点实例时合并类型定义和实例级配置，实例配置优先。

#### Scenario: Merge type and instance config
- **WHEN** 系统准备执行一个节点实例
- **THEN** 系统 SHALL 以类型定义为基础，用实例 `config` 中的字段覆盖对应运行时参数（source_names、parameters、model、skills）

#### Scenario: Structural fields from type only
- **WHEN** 系统解析节点实例的执行配置
- **THEN** 系统 SHALL 始终从类型定义获取 `input_type`、`output_type`、`role`、`handler`、`system_prompt_file`，忽略实例级对这些字段的任何覆盖
