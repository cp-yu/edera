## Why

当前 ReactFlow 画布需要从零拼装所有交互（连线路由、端口吸附、框选、undo 等），开发成本高且交互质量远低于 ComfyUI 级别。需要一个开箱即用、交互完整的 node editor 替代当前方案。

## What Changes

- 移除 `@xyflow/react` 和 `@dagrejs/dagre` 依赖
- 从 ComfyUI Frontend monorepo (`src/lib/litegraph`) vendor 进 TypeScript 版 litegraph 作为画布引擎
- Canvas 区域由 LiteGraph `<canvas>` 渲染替代 ReactFlow 组件
- 新增双向 adapter 层：后端 DAG 格式 ↔ LGraph 内部格式
- 新增事件桥接层：LiteGraph canvas 事件 → zustand store（节点选中、连线变更等）
- 保留现有 React Palette 和 Inspector 组件，仅替换中间画布
- 保存策略变更：手动保存写后端 + localStorage 自动草稿（60s，可配置）
- CSS 换皮：深色主题 + 现代字体 + 圆角，匹配现有设计系统
- 节点外观：统一 DynamicNode class + 动态 ports + 按类型颜色区分，保留扩展空间

## Capabilities

### New Capabilities

- `litegraph-canvas-engine`: LiteGraph 画布引擎集成，覆盖 canvas 挂载、节点渲染、连线交互、缩放平移、框选等核心交互
- `dag-litegraph-adapter`: DAG 数据与 LGraph 格式的双向转换层，覆盖加载、保存、草稿持久化

### Modified Capabilities

- `dag-workbench-ui`: 三栏布局中间画布从 ReactFlow 替换为 LiteGraph canvas；Palette 拖拽目标从 ReactFlow drop 改为 LGraph.add；保存策略从操作即保存改为手动保存+草稿
- `node-graph-dag-editor`: 图编辑交互实现从 ReactFlow hooks 改为 LiteGraph 回调；节点渲染从 React 组件改为 canvas 绘制；事件桥接方式变更

## Impact

- **前端依赖**：移除 `@xyflow/react`、`@dagrejs/dagre`；新增 vendor 目录 `src/lib/litegraph/`
- **组件变更**：`Canvas.tsx` 重写；`CustomNode.tsx` 移除；新增 adapter 和 bridge 模块
- **保留不变**：`Palette.tsx`、`Inspector.tsx`、`BottomToolbar.tsx`、zustand store 接口、后端 API
- **运行时**：新增 canvas 2D 渲染上下文，无额外外部依赖（无 jQuery/D3）
