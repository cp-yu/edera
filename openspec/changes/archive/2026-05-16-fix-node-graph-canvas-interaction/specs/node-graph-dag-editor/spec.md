## MODIFIED Requirements

### Requirement: Interactive graph editing
系统 SHALL 支持用户在画布上通过节点和端口交互编辑 DAG 数据流。画布 SHALL 动态匹配容器实际像素尺寸，确保鼠标坐标与节点渲染坐标一致。

#### Scenario: Add node from palette
- **WHEN** 用户从 palette 添加一个 Node 到画布
- **THEN** 系统 SHALL 在 DAG 草稿中加入该 Node，并在画布上显示其输入/输出端口

#### Scenario: Connect node ports
- **WHEN** 用户从上游输出端口连接到下游输入端口
- **THEN** 系统 SHALL 在 DAG 草稿中创建对应边，并在画布上显示数据流连线

#### Scenario: Delete graph edge
- **WHEN** 用户删除画布上的连线
- **THEN** 系统 SHALL 从 DAG 草稿中移除对应边

#### Scenario: Drag node on canvas
- **WHEN** 用户在画布上拖动节点
- **THEN** 节点 SHALL 跟随鼠标移动，拖动位置与鼠标位置一致（无坐标偏移）

#### Scenario: Canvas resize follows container
- **WHEN** 浏览器窗口尺寸变化或容器布局改变
- **THEN** 画布分辨率 SHALL 自动匹配容器实际像素尺寸，交互坐标保持准确

### Requirement: Node Inspector configuration
系统 SHALL 在 Node Graph Inspector 中展示并编辑选中节点的可配置字段。节点选中 SHALL 通过 LiteGraph 的节点选中回调触发，确保选中状态与画布渲染同步。

#### Scenario: Inspect node configuration
- **WHEN** 用户选中画布中的节点
- **THEN** 系统 SHALL 在 Inspector 展示该节点的 `skills[]`、`model`、`source_names`、`timeout_seconds` 和 `parameters`

#### Scenario: Deselect node clears Inspector
- **WHEN** 用户点击画布空白区域取消选中
- **THEN** Inspector SHALL 清空节点配置显示

#### Scenario: Save node configuration
- **WHEN** 用户在 Inspector 中保存合法节点配置
- **THEN** 系统 SHALL 写回对应 `config/nodes/*.yaml`，并让新配置仅影响后续运行

#### Scenario: Reject invalid node configuration
- **WHEN** 用户在 Inspector 中保存非法节点配置
- **THEN** 系统 MUST 拒绝保存、返回可读错误并保持原 Node 文件内容不变
