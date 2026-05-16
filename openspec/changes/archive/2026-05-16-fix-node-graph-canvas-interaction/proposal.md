## Why

Node Graph DAG 编辑器的画布交互完全失效——节点无法拖动、点击选中偏移、连线无法建立。根因是 HTML canvas 内部分辨率与 CSS 显示尺寸不一致，导致 LiteGraph.js 的鼠标坐标计算全面偏移。同时 Inspector 节点选中机制依赖原始 mousedown 事件而非 LiteGraph 的官方回调，存在时序隐患。

## What Changes

- 修复 canvas 坐标系：去除 CSS `width: 100%` 对 canvas 的拉伸，改用 JavaScript 动态设置 canvas 分辨率匹配容器实际像素尺寸
- 响应式 canvas 尺寸：通过 `ResizeObserver` 监听容器尺寸变化，调用 LiteGraph 的 `resize()` 保持分辨率同步
- Inspector 选中机制：将 mousedown 事件监听替换为 LiteGraph 的 `onNodeSelected` / `onNodeDeselected` 回调

## Capabilities

### New Capabilities

（无新增能力）

### Modified Capabilities

- `node-graph-dag-editor`: Interactive graph editing 和 Node Inspector configuration 的前端交互行为需要修正——画布坐标系对齐、节点选中回调机制

## Impact

- `src/stockimformation/web/static/node_graph_editor.js` — canvas 初始化逻辑、Inspector 选中绑定
- `src/stockimformation/web/static/styles.css` — `.ng-canvas-wrap canvas` 样式
- `src/stockimformation/web/templates/node_graph_editor.html` — canvas 元素属性
