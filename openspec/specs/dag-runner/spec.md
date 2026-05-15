# dag-runner Specification

## Purpose
此规约记录变更 project-mvp 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: DAG 定义加载与校验
系统 SHALL 从 YAML 文件加载 DAG 定义，解析节点列表、连线关系和 fan-out/fan-in 配置。加载时 MUST 校验图结构无环、所有引用的 Node 配置存在、I/O 类型匹配。

#### Scenario: 加载合法 DAG 定义
- **WHEN** DAG Runner 加载一个合法的 YAML DAG 定义文件
- **THEN** 系统解析出完整的节点列表和连线关系，返回可执行的 DAG 图结构

#### Scenario: 加载包含环的 DAG 定义
- **WHEN** DAG Runner 加载一个包含循环依赖的 YAML DAG 定义
- **THEN** 系统拒绝加载并返回明确的错误信息，指出构成环的节点

### Requirement: 拓扑排序与并发调度
系统 SHALL 对 DAG 进行拓扑排序，确定节点执行顺序。同一拓扑层级的节点 MUST 使用 asyncio.gather 并发执行。

#### Scenario: 并发执行同层节点
- **WHEN** DAG 中有 3 个采集节点（rss-fetcher、web-scraper-a、web-scraper-b）处于同一拓扑层级
- **THEN** 系统同时启动这 3 个节点的执行，总耗时接近单个最慢节点的耗时

#### Scenario: 顺序执行跨层节点
- **WHEN** reader 节点依赖所有采集节点的输出
- **THEN** reader 节点在所有采集节点完成后才开始执行

### Requirement: 数据路由
系统 SHALL 将上游节点的输出自动路由到下游节点的输入，MUST 在路由时进行 Pydantic 类型校验。

#### Scenario: 正常数据路由
- **WHEN** 采集节点输出 RawItem 列表
- **THEN** DAG Runner 将该列表作为 reader 节点的输入传递，类型校验通过

#### Scenario: 类型不匹配
- **WHEN** 节点输出的数据类型与下游节点期望的输入类型不匹配
- **THEN** 系统记录类型错误并标记该数据路径为失败

### Requirement: Fan-out/Fan-in
系统 SHALL 支持 fan-out（一个节点的输出拆分到多个并发节点）和 fan-in（多个节点的输出汇聚为一个列表）。Fan-in MUST 使用 Collector 汇聚。

#### Scenario: Fan-in 后将采集结果 fan-out 到并发分析
- **WHEN** 上游采集节点的结果经 Collector 汇聚为 10 条 RawItem
- **THEN** DAG Runner 将这 10 条 RawItem 拆分为 10 个独立的 reader 节点实例并发执行

#### Scenario: Fan-in 汇聚分析结果
- **WHEN** 10 个 reader 节点并发完成，其中 8 个成功、2 个失败
- **THEN** Collector 汇聚 8 条成功的 AnalysisResult，失败的 2 条记录降级状态

### Requirement: 单节点失败不阻塞管道
系统 SHALL 在单个节点执行失败时标记降级状态，MUST NOT 阻塞管道中其他节点的执行。

#### Scenario: 单个采集节点失败
- **WHEN** rss-fetcher 节点执行失败，其余采集节点正常
- **THEN** rss-fetcher 标记为 failed，其余节点继续执行，下游节点收到的输入中包含降级元数据

#### Scenario: 全部采集节点失败
- **WHEN** 所有采集节点均执行失败
- **THEN** 系统中止当前周期执行，触发系统状态通知推送

