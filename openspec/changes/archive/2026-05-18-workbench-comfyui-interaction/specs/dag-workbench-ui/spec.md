## MODIFIED Requirements

### Requirement: Node position persistence
系统 SHALL 在用户拖拽节点后自动持久化位置，采用 localStorage 草稿 + debounce 写后端的混合策略。

#### Scenario: Auto-save on drag stop
- **WHEN** 用户拖拽节点并释放
- **THEN** 系统 SHALL 立即将当前所有节点位置写入 localStorage 作为草稿

#### Scenario: Debounce save to backend
- **WHEN** 节点拖拽停止后 500ms 内无新的拖拽操作
- **THEN** 系统 SHALL 调用 `PUT /api/graph/dag/{name}` 将完整 UI + 拓扑持久化到后端

#### Scenario: Restore from localStorage on load
- **WHEN** 画布加载 DAG 且 localStorage 中存在该 DAG 的草稿位置
- **THEN** 系统 SHALL 优先使用 localStorage 中的位置数据（比后端更新）

#### Scenario: Clear localStorage after backend save
- **WHEN** 后端保存成功
- **THEN** 系统 SHALL 清除该 DAG 在 localStorage 中的草稿数据

### Requirement: Custom node rendering with target colors
系统 SHALL 使用自定义 React Flow 节点组件，按节点类型动态生成 Handle（左 input 右 output），默认隐藏未连接的 Handle，hover 时全部显示。

#### Scenario: Dynamic handles by type
- **WHEN** 画布渲染节点
- **THEN** 系统 SHALL 根据节点类型和已有连接数动态生成 Handle，input 在左侧、output 在右侧

#### Scenario: Handles hidden by default
- **WHEN** 节点未被 hover
- **THEN** 系统 SHALL 隐藏未连接的 Handle（opacity: 0），已连接的 Handle 保持可见

#### Scenario: All handles visible on hover
- **WHEN** 用户将鼠标悬停在节点上
- **THEN** 系统 SHALL 显示该节点所有 Handle

#### Scenario: Single target node color
- **WHEN** 节点仅关联一个 target
- **THEN** 系统 SHALL 使用该 target 的预定义颜色作为节点左边框色

#### Scenario: Multi-target node color
- **WHEN** 节点关联多个 target
- **THEN** 系统 SHALL 使用各 target 颜色的 RGB 均值作为节点左边框色

### Requirement: Auto-layout tool
系统 SHALL 提供自动布局工具按钮，使用 ELK layered 算法计算分层布局。

#### Scenario: Trigger auto-layout
- **WHEN** 用户点击自动布局按钮
- **THEN** 系统 SHALL 使用 ELK layered 算法重新计算所有节点位置并更新画布

#### Scenario: Layout direction
- **WHEN** 自动布局执行
- **THEN** 系统 SHALL 默认使用 DOWN 方向排布，input 节点在上、output 节点在下
