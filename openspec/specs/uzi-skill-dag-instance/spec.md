# uzi-skill-dag-instance Specification

## Purpose
此规约记录变更 uzi-skill-pipeline-instance 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: DAG 拓扑声明

系统 SHALL 在 `config/dags/uzi-skill-analysis.yaml` 中声明完整的 UZI-Skill 分析管道拓扑，包含 preflight、22 fetcher、scoring 链、21 renderer 和 assemble 节点。

每个 DAG 实例 SHALL 使用对应业务语义的 `uzi-*` node type，并设置非空 `alias` 作为 WebConsole 展示标签。相近业务 node type MAY 复用同一个 handler，但 MUST NOT 将所有实例的 `type` 直接声明为通用 handler 名称。

#### Scenario: DAG 配置可加载
- **WHEN** 系统启动并加载 `config/dags/uzi-skill-analysis.yaml`
- **THEN** DagGraph MUST 包含所有声明的节点和边，无加载错误

#### Scenario: 拓扑验证通过
- **WHEN** 对加载的 DagGraph 执行 `topological_layers()` 验证
- **THEN** MUST 无环检测通过，所有节点可达

#### Scenario: WebConsole 展示业务节点
- **WHEN** WebConsole 加载 `uzi-skill-analysis` DAG
- **THEN** 每个实例 MUST 返回具体 `uzi-*` type_name 和非空 alias，而不是全部显示为 `legacy-script-adapter`

### Requirement: Wave 并行拓扑

DAG SHALL 声明 Wave 2 的 18 个 fetcher 节点仅 depends_on `0_basic`，使其在 `0_basic` 完成后全部并发启动。Wave 3 的 4 个 fetcher MUST 声明 depends_on `0_basic`（required 边）。

#### Scenario: Wave 2 并发启动
- **WHEN** `0_basic` 节点完成
- **THEN** 18 个 Wave 2 fetcher MUST 同时变为 ready 状态

#### Scenario: Wave 3 等待 0_basic
- **WHEN** `0_basic` 节点未完成
- **THEN** Wave 3 的 `3_macro`、`7_industry`、`9_futures`、`13_policy` MUST NOT 启动

### Requirement: Fetcher 节点 optional 声明

所有 22 个 fetcher 节点 SHALL 声明 `optional: true`，确保单个 fetcher 失败不阻塞 scoring 阶段。

#### Scenario: fetcher 失败不阻塞 score
- **WHEN** `1_financials` fetcher 执行失败
- **THEN** `score_dimensions` 节点 MUST 仍然被触发，其 input 中该 fetcher 的 payload 为 None

### Requirement: Resource 约束声明

声明使用 mini_racer 的 3 个 fetcher 节点（`7_industry`、`12_capital_flow`、`10_valuation`）SHALL 配置 `resource: "v8_isolate"`，引用 permits=1 的 Resource Entity。

#### Scenario: v8_isolate 节点串行
- **WHEN** `7_industry` 和 `10_valuation` 同时 ready
- **THEN** 同一时刻 MUST 最多只有 1 个在执行

### Requirement: Score 链串行依赖

`score_dimensions` SHALL depends_on 所有 22 个 fetcher（fan_in_mode: barrier）。`generate_panel` SHALL depends_on `score_dimensions`。`generate_synthesis` SHALL depends_on `generate_panel`。

#### Scenario: score 等待所有 fetcher
- **WHEN** 22 个 fetcher 中有 1 个仍在执行
- **THEN** `score_dimensions` MUST NOT 启动

#### Scenario: panel 等待 score
- **WHEN** `score_dimensions` 未完成
- **THEN** `generate_panel` MUST NOT 启动

### Requirement: Renderer 并行 + assemble 汇聚

21 个 renderer 节点 SHALL depends_on `generate_synthesis`，并发执行。`assemble_report` SHALL depends_on 所有 21 个 renderer（fan_in_mode: barrier）。renderer 节点 SHALL 声明 `optional: true`。

#### Scenario: renderer 并发
- **WHEN** `generate_synthesis` 完成
- **THEN** 21 个 renderer MUST 同时变为 ready

#### Scenario: assemble 等待所有 renderer
- **WHEN** 所有 renderer 完成（含 optional 失败的）
- **THEN** `assemble_report` MUST 被触发

### Requirement: ticker 通过 initial_payload 传入

DAG 运行时 SHALL 通过 `initial_payload: {"ticker": "<code>"}` 接收股票代码。preflight 节点从 payload 提取 ticker。

#### Scenario: 手动触发传入 ticker
- **WHEN** 用户调用 `POST /api/pipeline/dag/uzi-skill-analysis/run` 并传入 `{"ticker": "300470.SZ"}`
- **THEN** DAG 的 initial_payload MUST 为 `{"ticker": "300470.SZ"}`

