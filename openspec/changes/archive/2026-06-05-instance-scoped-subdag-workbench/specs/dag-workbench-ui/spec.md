## ADDED Requirements

### Requirement: DAG palette entries
Workbench 左侧节点面板 SHALL 展示可作为 sub-DAG 节点拖入的 DAG 候选。DAG 候选 MUST 与普通 Node type 候选可区分，并 MUST NOT 将当前正在编辑的根 DAG 作为可直接拖入候选。

#### Scenario: DAG appears in palette
- **WHEN** 用户进入 `/workbench` 且系统存在 DAG `common-subdag`
- **THEN** 左侧节点面板 SHALL 显示 `common-subdag` 作为可拖入的 DAG 候选
- **AND** 该候选 SHALL 与普通 function/agent/wait 节点候选分组区分

#### Scenario: Drag DAG into canvas
- **WHEN** 用户将 DAG 候选 `common-subdag` 拖入 DAG `dagA` 的 Canvas
- **THEN** 系统 SHALL 创建一个新的节点实例
- **AND** 该实例 SHALL 使用稳定 `id`
- **AND** 该实例 SHALL 保存 `type: "dag"` 与 `dag_ref: "common-subdag"`

#### Scenario: Current DAG excluded
- **WHEN** 用户正在编辑 DAG `dagA`
- **THEN** 左侧节点面板 MUST NOT 将 `dagA` 作为可拖入 DAG 候选展示

### Requirement: Instance-scoped sub-DAG navigation
Workbench SHALL 支持从父 DAG 中的 sub-DAG 节点进入目标 DAG 的结构视图，同时保留父节点实例上下文。该导航 MUST 不覆盖根 DAG 选择器中持久化的 `selectedDagName`。

#### Scenario: Enter sub-DAG view
- **WHEN** 用户从 DAG `dagA` 的节点实例 `nodeX` 进入 `common-subdag`
- **THEN** Workbench SHALL 渲染 `common-subdag` 的 Canvas
- **AND** Workbench SHALL 保存导航上下文 `parentDagName=dagA`、`parentNodeId=nodeX`、`childDagName=common-subdag`

#### Scenario: Breadcrumb returns to parent
- **WHEN** 用户位于 `dagA.nodeX -> common-subdag` 的 sub-DAG 视图
- **THEN** Workbench SHALL 提供返回父 DAG `dagA` 的导航
- **AND** 返回后 SHALL 恢复父 DAG Canvas

#### Scenario: Root selection preserved
- **WHEN** 用户从 DAG `dagA` 进入 sub-DAG `common-subdag`
- **THEN** 浏览器本地保存的最后选中 DAG SHALL 仍为 `dagA`
