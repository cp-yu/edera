## MODIFIED Requirements

### Requirement: Dynamic handle generation
系统 SHALL 根据节点 role 和连接关系动态生成 Handle：source 节点仅生成输出 Handle，sink 节点仅生成输入 Handle，processor 节点两侧均生成。

#### Scenario: Source node handle generation
- **WHEN** 画布渲染 `role: source` 的节点
- **THEN** 系统 SHALL 仅在右侧生成输出 Handle，左侧不生成任何 Handle

#### Scenario: Sink node handle generation
- **WHEN** 画布渲染 `role: sink` 的节点
- **THEN** 系统 SHALL 仅在左侧生成输入 Handle，右侧不生成任何 Handle

#### Scenario: Processor handle count follows connectivity
- **WHEN** processor 节点存在 N 条入边或出边
- **THEN** 系统 SHALL 在对应侧生成不少于 N 个 Handle，并保持均匀分布

## ADDED Requirements

### Requirement: Connection validation visual feedback
系统 SHALL 在拖拽连线过程中通过 Handle 颜色变化提供类型兼容性的实时视觉反馈。

#### Scenario: Compatible target — green highlight
- **WHEN** 用户拖拽连线经过一个类型兼容的目标 Handle
- **THEN** 系统 SHALL 将该 Handle 高亮为绿色

#### Scenario: Incompatible target — red highlight
- **WHEN** 用户拖拽连线经过一个类型不兼容的目标 Handle（Function 节点）
- **THEN** 系统 SHALL 将该 Handle 高亮为红色

#### Scenario: Warning connection line style
- **WHEN** 一条已建立的连线存在类型不匹配警告（LLM 节点目标）
- **THEN** 系统 SHALL 将该连线渲染为黄色虚线样式
