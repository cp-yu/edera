## Context

Workbench 页面使用 `@xyflow/react` 渲染 DAG 拓扑。当前实现存在以下架构问题：

1. `Canvas.tsx` 的 `useEffect` 将 `selectedNodeId` 列为依赖，导致每次选中/取消选中都从服务端数据重建节点位置，覆盖用户拖拽结果
2. 缺少 `onDrop`/`onDragOver` 处理器，Palette 的 drag 事件无法被画布接收
3. Edge 创建时未设置 `markerEnd`，无箭头
4. `CustomNode` 仅有 Top/Bottom 两个 Handle，连线方向受限
5. 无 `onConnect`/`onEdgesDelete` 回调，连线无法增删
6. Inspector 对所有节点类型渲染相同字段

## Goals / Non-Goals

**Goals:**
- 使 React Flow 画布具备完整的交互式 DAG 编辑能力（拖拽新增、连线增删、位置持久化）
- 提供 dagre 自动布局工具
- 四边 Handle 方案，hover 时显示
- Inspector 按 `node.type` 渲染差异化编辑字段

**Non-Goals:**
- 不改动后端 API 接口签名（handle 信息存储在现有 `ui` 元数据字段中）
- 不实现 undo/redo
- 不实现多选批量操作
- 不处理 Issue 8-11（运行按钮、信息源健康度、fetcher 创建、设置页面）

## Decisions

### D1: 节点位置状态管理

**选择**：将 `useEffect` 的依赖从 `[dag, runtimeStatus, isRunning, selectedNodeId]` 缩减为 `[dag]`（仅在 DAG 数据变化时重建）。运行状态通过独立的节点数据更新（不重建位置）。

**替代方案**：引入独立的 position store → 过度设计，React Flow 的 `useNodesState` 已经管理位置。

### D2: Handle 信息持久化

**选择**：Edge 的 `sourceHandle`/`targetHandle` 存储在 DAG 的 `ui.edges` 元数据中（与 `ui.nodes` 位置信息同级），不修改后端核心 edge 模型 `{from, to}`。

**理由**：Handle 选择是纯 UI 布局信息，不影响数据流语义。后端只关心 from/to 拓扑关系。

### D3: 四边 Handle 方案

**选择**：每个节点 8 个 Handle（上下左右各一个 source + 一个 target），默认 `opacity: 0`，节点 hover 时 `opacity: 1`。使用 `id` 区分：`top-target`、`top-source`、`right-target`、`right-source` 等。

**替代方案**：4 Handle + `connectionMode="loose"` → React Flow loose 模式行为不够可控，且无法精确记录连线锚点。

### D4: 自动布局

**选择**：使用 `@dagrejs/dagre` 计算层级布局。提供工具栏按钮触发，不自动执行。布局方向默认 TB（top-bottom），可切换 LR。

**替代方案**：ELK → 包体积大（~200KB），dagre 足够满足 DAG 场景（~30KB）。

### D5: 连线增删

**选择**：
- 新增：`onConnect` 回调 → 更新本地 edges state + 标记 dirty
- 删除：`onEdgesDelete` 回调 + `deleteKeyCode="Delete"` → 选中 edge 后按 Delete 删除
- 保存：统一通过 `useSaveDag` 将 nodes/edges/ui 写回后端

### D6: Inspector 按类型分字段

**选择**：根据 `node.type` 条件渲染不同字段组。类型映射：
- `fetcher`: source_names、timeout_seconds、parameters
- `llm`: model、timeout_seconds、skills、parameters
- `aggregator`: timeout_seconds、parameters
- 通用: name（只读）、type（只读）、input_type（只读）、output_type（只读）

## Risks / Trade-offs

- [8 Handle 视觉噪音] → hover 显示 + 小尺寸 Handle 缓解
- [dagre 布局覆盖用户手动排布] → 仅按钮触发，不自动执行；执行前可考虑加确认
- [ui 元数据与核心拓扑分离] → 如果 ui 数据丢失，连线仍然存在（退化为默认 Handle 位置），不影响功能
