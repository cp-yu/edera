## MODIFIED Requirements

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
