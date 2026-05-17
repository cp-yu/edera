## Why

当前 ReactFlow 画布交互质量远低于 ComfyUI/UE Blueprint 级别：连线不美观、连接点固定死板、缺少布局辅助、30+ 节点时可用性差、节点拖拽位置不持久化。用户搭建一次 DAG 后主要是运行观察，但搭建阶段的体验和运行观察阶段的状态反馈都不达标。

## What Changes

- 节点拖拽后自动持久化位置（debounce → 调用已有 save API）
- 动态 Handle 生成（按节点类型/端口语义，左 input 右 output）
- 贝塞尔曲线连线美化（曲率、颜色、粗细优化）
- 节点外观按类型差异化（不同 type 不同样式/图标/尺寸）
- 右键上下文菜单（反转 edge 方向、删除节点/边）
- 节点运行状态轻量 badge（完成/运行中/等待/失败）
- 替换 dagre → ELK 布局算法（分层正交，适合扇入/扇出拓扑）
- 节点按 target 自动分组可视化（背景色块区分）
- 搜索快速添加节点（Cmd+K 弹窗）
- 执行路径高亮（运行时活跃路径连线加粗/变色）
- Undo/Redo 操作历史
- 对齐辅助线 + snap to grid

## Capabilities

### New Capabilities

- `canvas-interaction-enhancement`: 画布交互增强，覆盖连线美化、右键菜单、对齐辅助线、snap-to-grid、undo/redo
- `node-visual-system`: 节点视觉系统，覆盖类型差异化外观、动态 Handle、运行状态 badge、分组可视化
- `graph-layout-engine`: 图布局引擎，覆盖 ELK 自动布局、执行路径高亮、搜索快速添加节点

### Modified Capabilities

- `dag-workbench-ui`: 节点位置自动持久化行为变更（从手动保存变为拖拽后自动保存）

## Impact

- 前端 `frontend/src/features/workbench/` 目录下的 Canvas、CustomNode、Palette 组件重构
- 新增依赖：`elkjs`（替代 `@dagrejs/dagre`）
- 纯前端变更，后端 API 零改动（复用已有 `PUT /api/graph/dag/{name}` 接口）
- `ui.nodes` / `ui.edges` 数据结构不变，仅前端写入时机变更
