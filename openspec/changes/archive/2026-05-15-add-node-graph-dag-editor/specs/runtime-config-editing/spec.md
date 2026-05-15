## ADDED Requirements

### Requirement: Node Graph as primary DAG editor
系统 SHALL 将 Node Graph 作为 DAG 可视化编辑的主要 Web 入口，同时保留 YAML 兜底编辑。

#### Scenario: Navigate to primary DAG graph editor
- **WHEN** 用户从配置页进入 DAG 编辑
- **THEN** 系统 SHALL 优先打开 Node Graph DAG 编辑界面，而不是仅展示表格编辑器

#### Scenario: Continue raw DAG editing
- **WHEN** 用户选择高级或兜底编辑
- **THEN** 系统 SHALL 继续提供现有 DAG YAML 编辑能力

### Requirement: Node Graph save uses runtime config semantics
系统 MUST 使用运行时配置编辑的校验、原子写入和运行中配置快照语义保存 Node Graph 产生的 DAG 和 Node 配置。

#### Scenario: Graph DAG save uses existing validation
- **WHEN** Node Graph 保存 DAG
- **THEN** 系统 MUST 通过 `RuntimeConfigEditor.save("dag", ...)` 和 `load_graph()` 校验后写入

#### Scenario: Inspector node save uses existing validation
- **WHEN** Inspector 保存 Node 配置
- **THEN** 系统 MUST 通过 `RuntimeConfigEditor.save("node", ...)` 校验后写入

#### Scenario: Active run keeps previous graph config
- **WHEN** 用户在管道运行中通过 Node Graph 保存 DAG 或 Node 配置
- **THEN** 系统 SHALL 让当前运行继续使用启动时配置，并让新配置只影响后续运行
