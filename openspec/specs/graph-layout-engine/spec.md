---
capabilities:
  - cap.web.graph-layout-engine
---
# graph-layout-engine Specification

## Purpose

定义 Workbench 图布局与视口能力，覆盖 ELK 自动布局、全图视口拟合、缩放边界和执行路径高亮。

## Requirements

### Requirement: ELK-based auto layout
系统 SHALL 使用 ELK layered 算法替代 dagre 进行自动布局，优化扇入/扇出拓扑的分层排列。

#### Scenario: Trigger auto layout
- **WHEN** 用户点击自动布局按钮
- **THEN** 系统 SHALL 使用 ELK layered 算法（方向 DOWN）计算所有节点位置并更新画布

#### Scenario: Port constraints
- **WHEN** ELK 计算布局
- **THEN** 系统 SHALL 配置端口约束，使 input 位于左侧、output 位于右侧

#### Scenario: Layer spacing
- **WHEN** ELK 计算布局
- **THEN** 系统 SHALL 设置足够的层间距和节点间距，避免节点重叠

### Requirement: Whole-graph viewport fit
系统 SHALL 在图加载后和自动布局后自动拟合全图视口。

#### Scenario: Fit graph on load
- **WHEN** 画布首次完成节点和连线加载
- **THEN** 系统 SHALL 自动调整视口，使用户默认能够看到整张图

#### Scenario: Fit graph after layout
- **WHEN** 自动布局完成
- **THEN** 系统 SHALL 再次调整视口，使布局结果完整落入当前视图

### Requirement: Deep zoom-out support
系统 SHALL 允许用户继续缩小视口以查看全局拓扑。

#### Scenario: Zoom out below default limit
- **WHEN** 用户持续缩小画布
- **THEN** 系统 SHALL 允许缩放到远低于 React Flow 默认下界的比例

### Requirement: Execution path highlighting
系统 SHALL 在 DAG 运行时高亮当前活跃执行路径。

#### Scenario: Active path edge highlight
- **WHEN** DAG 正在运行且某节点状态为 `running`
- **THEN** 系统 SHALL 将入口到该节点的活跃 edge 加粗并显示为蓝色

#### Scenario: Succeeded path edge highlight
- **WHEN** 某节点状态为 `succeeded`
- **THEN** 系统 SHALL 将对应上游执行路径 edge 显示为绿色

#### Scenario: Failed path edge highlight
- **WHEN** 某节点状态为 `failed`
- **THEN** 系统 SHALL 将对应上游执行路径 edge 显示为红色
