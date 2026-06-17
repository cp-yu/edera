---
capabilities:
  - cap.core.uzi-skill-dag-instance
---
# uzi-skill-dag-instance Specification

## Purpose
定义 UZI-Skill 分析管道 DAG 实例拓扑、并发波次、optional 节点、资源约束和 extension imports 边界。
## Requirements
### Requirement: DAG 拓扑声明

系统 SHALL 在 `extensions/uzi-skill/` package 的 manifest imports 中声明 UZI-Skill 分析管道 Entity。主 DAG `uzi-skill-analysis` MUST 包含 5 个节点：`preflight`、3 个 Sub DAG 引用节点（`data_collection`, `scoring_synthesis`, `rendering`）和 `assemble_report`。

3 个 Sub DAG Entity（`uzi-data-collection`, `uzi-scoring-synthesis`, `uzi-rendering`）SHALL 分别封装数据采集、评分综合、渲染阶段的内部节点拓扑。

每个 DAG 实例 SHALL 使用对应业务语义的 `uzi-*` node type，并设置非空 `alias` 作为 WebConsole 展示标签。相近业务 node type MAY 复用同一个 handler，但 MUST NOT 将所有实例的 `type` 直接声明为通用 handler 名称。

#### Scenario: 主 DAG 配置可加载

- **WHEN** 系统启动、执行 `extensions/uzi-skill/manifest.yaml` imports 并从 DB-backed Entity 加载 `uzi-skill-analysis`
- **THEN** DagGraph MUST 包含 5 个节点：`preflight`, `data_collection` (type: dag), `scoring_synthesis` (type: dag), `rendering` (type: dag), `assemble_report`，无加载错误

#### Scenario: Sub DAG 配置可加载

- **WHEN** 系统加载 3 个 Sub DAG Entity（`uzi-data-collection`, `uzi-scoring-synthesis`, `uzi-rendering`）
- **THEN** 每个 Sub DAG 的 DagGraph MUST 包含所有声明的内部节点和边，无加载错误

#### Scenario: 拓扑验证通过

- **WHEN** 对加载的主 DAG 和所有 Sub DAG 执行 `topological_layers()` 验证
- **THEN** MUST 无环检测通过，所有节点可达

#### Scenario: Sub DAG 嵌套深度验证

- **WHEN** 对 `uzi-skill-analysis` 执行 `validate_sub_dag_nesting` 验证
- **THEN** MUST 通过嵌套深度检查（主 DAG + 1 层 Sub DAG = 2 层，在 max_dag_depth=3 限制内）

#### Scenario: WebConsole 展示主 DAG 简化结构

- **WHEN** WebConsole 加载 `uzi-skill-analysis` DAG
- **THEN** 画布 MUST 展示 5 个节点，3 个 Sub DAG 引用节点的 type 为 `dag`

### Requirement: Wave 并行拓扑

`uzi-data-collection` Sub DAG SHALL 声明 Wave 2 的 18 个 fetcher 节点仅 depends_on `0_basic`，使其在 `0_basic` 完成后全部并发启动。Wave 3 的 4 个 fetcher MUST 声明 depends_on `0_basic`（required 边）。

#### Scenario: Wave 2 并发启动

- **WHEN** `uzi-data-collection` Sub DAG 内 `0_basic` 节点完成
- **THEN** 18 个 Wave 2 fetcher MUST 同时变为 ready 状态

#### Scenario: Wave 3 等待 0_basic

- **WHEN** `uzi-data-collection` Sub DAG 内 `0_basic` 节点未完成
- **THEN** Wave 3 的 `3_macro`、`7_industry`、`9_futures`、`13_policy` MUST NOT 启动

### Requirement: Fetcher 节点 optional 声明

`uzi-data-collection` Sub DAG 内所有 22 个 fetcher 节点 SHALL 声明 `optional: true`，确保单个 fetcher 失败不阻塞后续阶段。

#### Scenario: fetcher 失败不阻塞 aggregate

- **WHEN** `uzi-data-collection` Sub DAG 内 `1_financials` fetcher 执行失败
- **THEN** `aggregate_results` 节点 MUST 仍然被触发，其输出中该 fetcher 对应字段为 null

### Requirement: Resource 约束声明

`uzi-data-collection` Sub DAG 内使用 mini_racer 的 3 个 fetcher 节点（`7_industry`、`12_capital_flow`、`10_valuation`）SHALL 配置 `resource: "v8_isolate"`，引用 permits=1 的 Resource Entity。

#### Scenario: v8_isolate 节点串行

- **WHEN** `uzi-data-collection` Sub DAG 内 `7_industry` 和 `10_valuation` 同时 ready
- **THEN** 同一时刻 MUST 最多只有 1 个在执行

### Requirement: Score 链串行依赖

`uzi-scoring-synthesis` Sub DAG SHALL 包含 3 个线性串联节点：`score_dimensions` (source) SHALL 接收 `uzi-data-collection` 的聚合输出，`generate_panel` SHALL depends_on `score_dimensions`，`generate_synthesis` (sink) SHALL depends_on `generate_panel`。

#### Scenario: score 接收聚合数据

- **WHEN** `uzi-scoring-synthesis` Sub DAG 启动
- **THEN** `score_dimensions` MUST 接收上游 `uzi-data-collection` 的聚合输出，包含所有 fetcher 和 autofill 结果字段

#### Scenario: panel 等待 score

- **WHEN** `uzi-scoring-synthesis` Sub DAG 内 `score_dimensions` 未完成
- **THEN** `generate_panel` MUST NOT 启动

### Requirement: Renderer 并行 + assemble 汇聚

`uzi-rendering` Sub DAG SHALL 包含 21 个独立 renderer 节点（全部 optional），无内部依赖。主 DAG 的 `assemble_report` SHALL depends_on `rendering` Sub DAG 节点和 `preflight` 节点（fan_in_mode: barrier）。

#### Scenario: renderer 并发

- **WHEN** `uzi-rendering` Sub DAG 接收上游 `uzi-scoring-synthesis` 的输出
- **THEN** 21 个 renderer MUST 同时启动

#### Scenario: assemble 等待 rendering Sub DAG

- **WHEN** 主 DAG 的 `assemble_report` 节点等待上游
- **THEN** MUST 等待 `rendering` Sub DAG 整体完成和 `preflight` 节点完成

### Requirement: ticker 通过 initial_payload 传入

主 DAG 运行时 SHALL 通过 `sourceSharedInputs: {"ticker": "<code>"}` 接收股票代码。preflight 节点从 `sourceSharedInputs` 提取 ticker，并通过主 DAG 边将 preflight 输出传递给 `data_collection` Sub DAG。

#### Scenario: 手动触发传入 ticker

- **WHEN** 用户调用 `POST /api/dags/uzi-skill-analysis/run` 并传入 `{"sourceSharedInputs": {"ticker": "300470.SZ"}}`
- **THEN** 主 DAG source 节点的 `sourceSharedInputs` MUST 为 `{"ticker": "300470.SZ"}`

#### Scenario: ticker 经 preflight 输出传递到 Sub DAG

- **WHEN** `data_collection` Sub DAG 节点启动
- **THEN** preflight 的输出（包含 ticker 信息）SHALL 经 `input_mapping` 映射到该 Sub DAG 的 `sourceSharedInputs`

### Requirement: UZI-Skill workflow extension imports

`extensions/uzi-skill/manifest.yaml` SHALL import UZI-Skill workflow-owned Entity files：主 DAG `uzi-skill-analysis`、3 个 Sub DAG Entity（`uzi-data-collection`, `uzi-scoring-synthesis`, `uzi-rendering`）、所有 `uzi-*` node 定义、`aggregate-collection-results` node 定义、`uzi-skill-analysis-default-cron` Trigger Entity 和 `v8_isolate` Resource Entity。Manifest MUST 声明对应的 handler entry。Manifest MUST 使用 glob patterns 替代手动列举 59 个 entity imports。

#### Scenario: Manifest 使用 glob pattern 导入所有 entities

- **WHEN** 读取 `extensions/uzi-skill/manifest.yaml`
- **THEN** manifest MUST 包含 `imports.entities: ["entities/**/*.yaml"]`
- **AND** glob pattern MUST 展开为 4 个 DAG files + 67 个 node files + 2 个 resource files

#### Scenario: Imported UZI trigger targets DAG

- **WHEN** 导入 trigger entity `uzi-skill-analysis-default-cron`
- **THEN** 该 trigger MUST 保持 `wait_for = cron:"*/30 * * * *"`、`target = dag:uzi-skill-analysis` 和 `enabled = true`

#### Scenario: UZI-Skill handler 注册

- **WHEN** 读取 manifest 的 `handlers` 字段
- **THEN** manifest MUST 声明对应的 handler entry
- **AND** handler entry MUST 指向 `adapter.py`
- **AND** 安装后 handler 代码 MUST 复制到对应 `handlers_dir/` 子目录

### Requirement: UZI-Skill trigger is imported

UZI-Skill workflow package SHALL import `uzi-skill-analysis-default-cron`。Trigger MUST 保持 `wait_for = cron:"*/30 * * * *"`、`target = dag:uzi-skill-analysis` 和 `enabled = true`。

#### Scenario: Imported UZI trigger targets DAG

- **WHEN** extension imports 已执行
- **THEN** Trigger registry SHALL 包含 `uzi-skill-analysis-default-cron`
- **AND** trigger target MUST 为 `dag:uzi-skill-analysis`

#### Scenario: UZI cron expression preserved

- **WHEN** Trigger Entity `uzi-skill-analysis-default-cron` 从 DB 加载
- **THEN** `wait_for` MUST 等于 `cron:"*/30 * * * *"`
- **AND** `enabled` MUST 为 true

### Requirement: Top-level UZI workflow config is no longer authoritative

UZI workflow 的 DAG、Sub DAG、node、trigger 和 resource instances SHALL 由 extension manifest imports 写入 DB-backed Entity Store，并以 DB records 作为唯一 runtime-authoritative source。

#### Scenario: Manifest import is UZI workflow source

- **WHEN** repository workflow ownership 被检查
- **THEN** `extensions/uzi-skill/manifest.yaml` MUST 作为导入 `uzi-skill-analysis` 主 DAG 和 3 个 Sub DAG Entity 的 manifest source
- **AND** runtime MUST NOT 将 workflow YAML 文件视为 authoritative runtime sources

#### Scenario: Runtime loads imported UZI workflow

- **WHEN** runtime materialization 在 extension imports 后构建 DAG registry
- **THEN** `uzi-skill-analysis` 主 DAG 和 3 个 Sub DAG MUST 从 DB-backed Entity storage 解析
- **AND** runtime MUST NOT 读取 workflow YAML 文件作为 fallback runtime sources

