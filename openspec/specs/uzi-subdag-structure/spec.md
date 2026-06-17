---
capabilities:
  - cap.core.uzi-subdag-structure
---
# uzi-subdag-structure Specification

## Purpose
此规约记录变更 uzi-skill-subdag-refactor 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: data-collection Sub DAG 结构

系统 SHALL 提供 `uzi-data-collection` Sub DAG，作为数据采集阶段的封装子图。该 Sub DAG MUST 包含 1 个 source 节点（`0_basic`）、22 个并行数据采集节点（全部 optional）、2 个 autofill 节点和 1 个聚合 sink 节点。

#### Scenario: data-collection Sub DAG 节点拓扑

- **WHEN** 加载 `uzi-data-collection` Sub DAG 配置
- **THEN** 包含以下节点：
  - 1 个 source：`0_basic`（基础信息采集）
  - 22 个 fetch 节点：`1_financials`, `2_news`, `3_macro`, `4_market`, `5_shareholder`, `6_technical`, `7_industry`, `8_sentiment`, `9_futures`, `10_valuation`, `11_moneyflow`, `12_capital_flow`, `13_policy`, `14_events`, `15_competitors`, `16_risk`, `17_estimates`, `18_insider`, `19_dividend`, `20_liquidity`, `21_regulatory`, `22_ownership`（全部标记为 optional）
  - 2 个 autofill 节点：`autofill_mx`, `autofill_playwright`
  - 1 个 sink：`aggregate_results`（聚合所有采集结果）

#### Scenario: data-collection 数据流

- **WHEN** `0_basic` 节点完成
- **THEN** 其输出 fan-out 到所有 22 个 fetch 节点和 2 个 autofill 节点，所有节点并行执行

#### Scenario: data-collection 聚合输出

- **WHEN** 所有 fetch 和 autofill 节点执行完成（optional 节点失败不阻塞）
- **THEN** `aggregate_results` 节点 SHALL 聚合所有成功节点的输出为单一字典，字段名对应节点 ID，缺失的 optional 节点输出字段为 null

### Requirement: scoring-synthesis Sub DAG 结构

系统 SHALL 提供 `uzi-scoring-synthesis` Sub DAG，作为评分与综合阶段的封装子图。该 Sub DAG MUST 包含 3 个线性串联节点：`score_dimensions` (source) → `generate_panel` → `generate_synthesis` (sink)。

#### Scenario: scoring-synthesis Sub DAG 节点拓扑

- **WHEN** 加载 `uzi-scoring-synthesis` Sub DAG 配置
- **THEN** 包含以下线性拓扑：
  - source：`score_dimensions`（维度评分）
  - 中间节点：`generate_panel`（生成面板）
  - sink：`generate_synthesis`（综合结论）

#### Scenario: scoring-synthesis 输入契约

- **WHEN** `uzi-scoring-synthesis` Sub DAG 接收上游输入
- **THEN** 输入 payload MUST 包含所有数据采集阶段的字段（`basic`, `financials`, ..., `autofill_mx`, `autofill_playwright`）

#### Scenario: scoring-synthesis 串行执行

- **WHEN** `score_dimensions` 节点完成
- **THEN** 其输出传递给 `generate_panel`，`generate_panel` 完成后输出传递给 `generate_synthesis`

### Requirement: rendering Sub DAG 结构

系统 SHALL 提供 `uzi-rendering` Sub DAG，作为报告渲染阶段的封装子图。该 Sub DAG MUST 包含 21 个独立的 render 节点（全部 optional，无内部依赖），每个节点既是 source 也是 sink。

#### Scenario: rendering Sub DAG 节点拓扑

- **WHEN** 加载 `uzi-rendering` Sub DAG 配置
- **THEN** 包含 21 个独立 render 节点：`render_01_summary`, `render_02_financials`, `render_03_macro`, `render_04_market`, `render_05_news`, `render_06_shareholder`, `render_07_technical`, `render_08_industry`, `render_09_sentiment`, `render_10_futures`, `render_11_valuation`, `render_12_moneyflow`, `render_13_capital_flow`, `render_14_policy`, `render_15_events`, `render_16_competitors`, `render_17_risk`, `render_18_estimates`, `render_19_insider`, `render_20_dividend`, `render_21_liquidity`（全部标记为 optional）

#### Scenario: rendering 并行执行

- **WHEN** `uzi-rendering` Sub DAG 接收上游输入
- **THEN** 所有 21 个 render 节点 SHALL 并行执行，每个节点独立接收相同的输入 payload

#### Scenario: rendering 多 sink 输出

- **WHEN** 所有 render 节点执行完成
- **THEN** Sub DAG 输出 SHALL 为所有成功节点输出组成的数组，optional 节点失败不影响整体输出

### Requirement: aggregate-collection-results 节点

系统 SHALL 提供 `aggregate-collection-results` 节点，作为 `uzi-data-collection` Sub DAG 的 sink 节点。该节点 MUST 聚合所有上游数据采集节点的输出为单一字典。

#### Scenario: aggregate 节点输入

- **WHEN** `aggregate-collection-results` 节点接收输入
- **THEN** 输入 SHALL 为 fan-in from 所有 fetch 和 autofill 节点的输出

#### Scenario: aggregate 节点输出格式

- **WHEN** `aggregate-collection-results` 节点执行完成
- **THEN** 输出 SHALL 为字典，字段名为上游节点 ID，字段值为对应节点的输出 payload，optional 节点失败时对应字段为 null

#### Scenario: aggregate 节点处理 optional 失败

- **WHEN** 部分 optional 节点失败
- **THEN** `aggregate-collection-results` 节点 SHALL 继续执行，将失败节点对应字段设为 null，不阻塞整体流程

### Requirement: 主 DAG 重构为 Sub DAG 引用

系统 SHALL 将 `uzi-skill-analysis` 主 DAG 重构为包含 3 个 Sub DAG 引用节点（type: dag）的简化结构。主 DAG MUST 保留 `preflight` 和 `assemble_report` 节点，节点总数从 53 降至 5。

#### Scenario: 主 DAG 节点结构

- **WHEN** 加载重构后的 `uzi-skill-analysis` DAG 配置
- **THEN** 包含以下 5 个节点：
  - `preflight`（原有 source 节点）
  - `data_collection`（type: dag, dag_ref: uzi-data-collection）
  - `scoring_synthesis`（type: dag, dag_ref: uzi-scoring-synthesis）
  - `rendering`（type: dag, dag_ref: uzi-rendering）
  - `assemble_report`（原有 sink 节点）

#### Scenario: 主 DAG 数据流

- **WHEN** 主 DAG 执行
- **THEN** 数据流 SHALL 为：`preflight` → `data_collection` → `scoring_synthesis` → `rendering` → `assemble_report`，且 `preflight` 到 `assemble_report` 存在直接边（保持原有逻辑）

#### Scenario: Sub DAG 节点输入映射

- **WHEN** Sub DAG 引用节点接收上游输出
- **THEN** 上游输出 SHALL 经 `input_mapping` 映射到子 DAG 的 `sourceSharedInputs`，由子 DAG source 节点接收

#### Scenario: Sub DAG 节点输出映射

- **WHEN** Sub DAG 执行完成
- **THEN** Sub DAG 的 sink 节点输出 SHALL 作为 Sub DAG 引用节点的输出传递给下游节点

