## ADDED Requirements

### Requirement: ELK-based auto layout
系统 SHALL 使用 ELK layered 算法替代 dagre 进行自动布局，优化扇入/扇出拓扑的分层排列。

#### Scenario: Trigger auto layout
- **WHEN** 用户点击自动布局按钮
- **THEN** 系统 SHALL 使用 ELK layered 算法（方向 DOWN）计算所有节点位置并更新画布

#### Scenario: Port constraints
- **WHEN** ELK 计算布局
- **THEN** 系统 SHALL 配置端口约束（input 左侧、output 右侧），使连线方向一致

#### Scenario: Layer spacing
- **WHEN** ELK 计算布局
- **THEN** 系统 SHALL 设置层间距 >= 80px、节点间距 >= 40px，避免节点重叠

### Requirement: Execution path highlighting
系统 SHALL 在 DAG 运行时高亮当前活跃的执行路径。

#### Scenario: Active path edge highlight
- **WHEN** DAG 正在运行且某节点状态为 `running`
- **THEN** 系统 SHALL 将从 DAG 入口到该节点的所有 edge 加粗并变色（蓝色）

#### Scenario: Completed path edge style
- **WHEN** 某节点状态为 `succeeded`
- **THEN** 系统 SHALL 将到达该节点的 edge 变为绿色

#### Scenario: Failed path edge style
- **WHEN** 某节点状态为 `failed`
- **THEN** 系统 SHALL 将到达该节点的最后一条 edge 变为红色

#### Scenario: No runtime clears highlight
- **WHEN** DAG 未在运行且无运行状态数据
- **THEN** 系统 SHALL 恢复所有 edge 为默认样式

### Requirement: Quick-add node search
系统 SHALL 提供快捷键触发的搜索面板，支持模糊匹配快速添加节点到画布。

#### Scenario: Open search panel
- **WHEN** 用户按下 Cmd+K（macOS）或 Ctrl+K（Linux/Windows）
- **THEN** 系统 SHALL 在画布中央显示搜索输入框

#### Scenario: Fuzzy match node prototypes
- **WHEN** 用户在搜索框中输入文本
- **THEN** 系统 SHALL 模糊匹配所有可用节点原型名称，实时显示匹配结果列表

#### Scenario: Add node from search
- **WHEN** 用户在搜索结果中选择一个节点原型并按 Enter
- **THEN** 系统 SHALL 在画布视口中心创建该节点实例并添加到 DAG

#### Scenario: Dismiss search
- **WHEN** 用户按下 Escape 或点击搜索面板外部
- **THEN** 系统 SHALL 关闭搜索面板，不执行任何操作
