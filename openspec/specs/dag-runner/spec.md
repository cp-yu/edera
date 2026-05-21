# dag-runner Specification

## Purpose
此规约记录变更 project-mvp 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: DAG 定义加载与校验

系统 SHALL 从 Entity Store 加载 DAG Entity（替代直接 YAML 文件加载），解析节点引用列表、连线关系（含条件表达式和 fan_in_mode）和 fan-out/fan-in 配置。加载时 MUST 校验图结构无环、所有引用的 Node Entity 存在、I/O 类型匹配、子 DAG 引用无循环嵌套。

#### Scenario: 从 Entity Store 加载 DAG

- **WHEN** DAG Runner 通过 Entity Store 加载一个 DAG Entity
- **THEN** 系统解析 `attributes.nodes`（Node Entity 引用列表）和 `attributes.edges`（含 condition、fan_in_mode 字段），返回可执行的 DAG 图结构

#### Scenario: 加载包含环的 DAG 定义

- **WHEN** DAG Runner 加载一个包含循环依赖的 DAG Entity
- **THEN** 系统拒绝加载并返回明确的错误信息，指出构成环的节点

#### Scenario: 校验子 DAG 循环嵌套

- **WHEN** DAG Entity A 的 nodes 引用了 DAG Entity B，B 又引用了 A
- **THEN** 系统在加载时检测到循环嵌套并拒绝加载

### Requirement: 拓扑排序与并发调度

系统 SHALL 对 DAG 进行拓扑排序，确定节点执行顺序。同一拓扑层级的节点 MUST 使用 asyncio.gather 并发执行。条件分支 MUST 在拓扑排序后、数据路由时求值。

#### Scenario: 并发执行同层节点

- **WHEN** DAG 中有 3 个采集节点处于同一拓扑层级
- **THEN** 系统同时启动这 3 个节点的执行，总耗时接近单个最慢节点的耗时

#### Scenario: 顺序执行跨层节点

- **WHEN** reader 节点依赖所有采集节点的输出
- **THEN** reader 节点在所有采集节点完成后才开始执行

#### Scenario: 条件分支在数据路由时求值

- **WHEN** 节点 A 完成执行，其出边包含条件表达式
- **THEN** 系统在路由数据到下游前调用 condition evaluator 求值，仅将数据路由到条件为 true 的边

### Requirement: 数据路由

系统 SHALL 将上游节点的输出自动路由到下游节点的输入。路由时 MUST 考虑 edge 条件表达式和 fan_in_mode。

#### Scenario: 正常数据路由

- **WHEN** 采集节点输出 Entity 列表，出边无条件
- **THEN** DAG Runner 将输出传递给下游节点

#### Scenario: 条件路由

- **WHEN** 节点输出 `{sentiment: "negative"}`，出边条件为 `"output.sentiment == 'negative'"`
- **THEN** 系统将数据路由到该边的目标节点

#### Scenario: fan_in stream 模式路由

- **WHEN** 下游节点的入边配置 `fan_in_mode: stream`
- **THEN** 上游每完成一个输出，立即传给下游执行一次，不等其他上游完成

#### Scenario: fan_in collect 模式路由

- **WHEN** 下游节点的入边配置 `fan_in_mode: collect`（默认）
- **THEN** 系统等待所有上游完成后，收集可用结果一次性传给下游

### Requirement: Fan-out/Fan-in

系统 SHALL 支持 fan-out（一个节点的输出拆分到多个并发节点）和 fan-in（多个节点的输出汇聚为一个列表）。Fan-in MUST 支持 collect 和 stream 两种模式。

#### Scenario: Fan-out 拆分到并发执行

- **WHEN** 上游节点输出 10 条 Entity，出边标记 `fan_out: true`
- **THEN** DAG Runner 将 10 条 Entity 拆分为 10 个独立的下游节点实例并发执行

#### Scenario: Fan-in collect 模式汇聚

- **WHEN** 10 个并发节点完成，其中 8 个成功、2 个失败，入边 `fan_in_mode: collect`
- **THEN** 系统等待全部完成后，汇聚 8 条成功结果传给下游，失败的 2 条记录到 run metadata

#### Scenario: Fan-in stream 模式逐个处理

- **WHEN** 10 个并发节点逐个完成，入边 `fan_in_mode: stream`
- **THEN** 每个节点完成时立即将其输出传给下游执行，不等其他节点

### Requirement: 单节点失败不阻塞管道

系统 SHALL 在单个节点执行失败时标记降级状态，MUST NOT 阻塞管道中其他节点的执行。optional 节点失败 MUST NOT 阻塞其下游。

#### Scenario: 单个采集节点失败

- **WHEN** rss-fetcher 节点执行失败，其余采集节点正常
- **THEN** rss-fetcher 标记为 failed，其余节点继续执行，下游节点收到的输入中包含降级元数据

#### Scenario: optional 节点失败不阻塞下游

- **WHEN** 一个标记为 `optional: true` 的节点执行失败
- **THEN** 其下游节点正常执行，跳过该节点的输出

#### Scenario: 全部采集节点失败

- **WHEN** 所有采集节点均执行失败
- **THEN** 系统中止当前周期执行，触发系统状态通知推送

### Requirement: LLM 节点 fallback 策略

系统 SHALL 支持 LLM 节点的 fallback 策略：切换模型或跳过。MUST NOT 复用缓存结果。

#### Scenario: 切换模型 fallback

- **WHEN** LLM 节点使用主模型执行超时，且配置 `fallback: switch_model`，`fallback_model: "gpt-4o-mini"`
- **THEN** 系统使用 fallback 模型重新执行该节点

#### Scenario: 跳过 fallback

- **WHEN** LLM 节点执行失败，且配置 `fallback: skip`
- **THEN** 系统跳过该节点，将其标记为 skipped，下游按 optional 节点逻辑处理

