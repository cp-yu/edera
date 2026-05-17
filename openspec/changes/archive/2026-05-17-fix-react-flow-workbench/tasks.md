## 1. Actions

- [x] A1 修复 `Canvas.tsx` 的 `useEffect` 依赖：移除 `selectedNodeId`，仅在 `dag` 数据变化时重建节点；运行状态通过独立更新路径注入节点 data 而不重建位置
- [x] A2 为 Edge 添加 `markerEnd: { type: MarkerType.ArrowClosed }` 箭头标记
- [x] A3 在 `Canvas.tsx` 添加 `onConnect` 回调创建新 edge（含 sourceHandle/targetHandle），添加 `onEdgesDelete` 回调和 `deleteKeyCode="Delete"` 支持删除
- [x] A4 在 `Canvas.tsx` 添加 `onDragOver` 和 `onDrop` 处理器，使用 `screenToFlowPosition` 转换坐标，调用 `useCreateNode` 将 Palette 拖拽的节点添加到 DAG
- [x] A5 重构 `CustomNode.tsx`：四边各放一个 source Handle + 一个 target Handle（共 8 个），使用 `id` 区分（`top-target`、`top-source`、`right-target`、`right-source` 等），默认 `opacity: 0`，节点 hover 时 `opacity: 1`
- [x] A6 安装 `@dagrejs/dagre`，在 `Canvas.tsx` 或 `BottomToolbar.tsx` 添加自动布局按钮，使用 dagre TB 方向计算节点位置并更新画布
- [x] A7 重构 `Inspector.tsx`：根据 `node.type` 条件渲染差异化字段（fetcher: source_names/timeout/parameters；llm: model/timeout/skills/parameters；aggregator: timeout/parameters；通用只读: name/type/input_type/output_type）
- [x] A8 扩展 `api/types.ts` 中 Edge 类型，添加 `sourceHandle?: string` 和 `targetHandle?: string`；`useSaveDag` 保存时将 handle 信息写入 `ui.edges` 元数据

## 2. Checks

- [x] C1 验证节点位置不因选中/取消选中而重置
  - Covers: A1
  - Command: `cd frontend && npx tsc --noEmit`
  - Evidence: 在浏览器中拖拽节点到新位置，点击画布空白区域，观察节点是否保持位置
  - Expect: 节点保持在拖拽后的位置，不回归初始坐标

- [x] C2 验证连接线显示箭头
  - Covers: A2
  - Evidence: 在浏览器中查看 workbench 画布中的 edge 渲染
  - Expect: 每条连接线的 target 端显示闭合箭头标记

- [x] C3 验证连线增删功能
  - Covers: A3
  - Command: `cd frontend && npx tsc --noEmit`
  - Evidence: 在浏览器中从一个节点的 source Handle 拖拽到另一个节点的 target Handle；选中一条 edge 后按 Delete 键
  - Expect: 拖拽创建新连线成功；Delete 键删除选中连线成功

- [x] C4 验证 Palette 拖拽新增节点
  - Covers: A4
  - Command: `cd frontend && npx tsc --noEmit`
  - Evidence: 在浏览器中从 Palette 拖拽节点到画布任意位置释放
  - Expect: 节点出现在鼠标释放位置，已加入 DAG 拓扑

- [x] C5 验证四边 Handle 显示行为
  - Covers: A5
  - Command: `cd frontend && npx tsc --noEmit`
  - Evidence: 在浏览器中 hover 节点观察 Handle 显示/隐藏
  - Expect: 未 hover 时 Handle 不可见；hover 时四边各显示 source 和 target Handle

- [x] C6 验证自动布局功能
  - Covers: A6
  - Command: `cd frontend && npm ls @dagrejs/dagre`
  - Evidence: 在浏览器中点击自动布局按钮
  - Expect: dagre 依赖已安装；点击后节点按 TB 层级重新排布

- [x] C7 验证 Inspector 按类型分字段
  - Covers: A7
  - Command: `cd frontend && npx tsc --noEmit`
  - Evidence: 在浏览器中分别选中 fetcher、llm、aggregator 类型节点
  - Expect: 不同类型节点显示对应的编辑字段集合

- [x] C8 验证 Edge 类型扩展和 handle 持久化
  - Covers: A8
  - Command: `cd frontend && npx tsc --noEmit`
  - Evidence: 检查 `api/types.ts` 中 Edge 类型定义
  - Expect: Edge 类型包含 `sourceHandle` 和 `targetHandle` 可选字段；TypeScript 编译无错误
