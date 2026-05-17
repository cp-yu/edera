## Why

Workbench 页面的 React Flow 画布存在多项交互缺陷：节点无法拖拽新增、连线无箭头、节点位置无法持久化、缺少自动布局、Handle 位置固定、连线无法增删、Inspector 不区分节点类型。这些问题导致 DAG 编辑器基本不可用。

## What Changes

- 修复 Canvas 缺失的 `onDrop`/`onDragOver`，使 Palette 拖拽新增节点生效
- Edge 添加 `markerEnd` 箭头标记
- 修复 `useEffect` 依赖导致节点位置在每次选中/取消选中时重置的问题
- 集成 dagre 自动布局工具按钮
- CustomNode 改为四边 Handle（上下左右各一对 source/target），默认隐藏、hover 显示
- 添加 `onConnect` 新增连线、支持选中 edge 后 Delete 键删除
- Inspector 根据 `node.type` 渲染不同编辑字段

## Capabilities

### New Capabilities

### Modified Capabilities
- `dag-workbench-ui`: 补全画布拖拽新增、连线箭头、位置持久化、自动布局、四边 Handle、连线增删、Inspector 按类型分字段
- `node-graph-dag-editor`: 补全交互式图编辑中缺失的 drop/connect/delete 实现，Handle 位置从固定上下改为四边

## Impact

- `frontend/src/features/workbench/components/Canvas.tsx` — 主要改动文件
- `frontend/src/features/workbench/components/nodes/CustomNode.tsx` — Handle 重构
- `frontend/src/features/workbench/components/Inspector.tsx` — 按类型分字段
- `frontend/src/api/types.ts` — Edge 类型扩展 `sourceHandle`/`targetHandle`
- 新增依赖：`dagre`（自动布局）
- 后端 DAG edge 模型需扩展 handle 字段（或前端仅在 `ui` 元数据中存储）
