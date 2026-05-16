## Context

Node Graph DAG 编辑器基于 LiteGraph.js，以静态 JS 方式嵌入 Jinja2 模板（无构建链）。当前 canvas 的 HTML 属性设置了固定分辨率 `1200×700`，但 CSS `width: 100%` 将其拉伸到容器宽度，造成内部分辨率与显示尺寸不一致。LiteGraph 的 `adjustMouseEvent` 使用 `getBoundingClientRect()` 获取的是 CSS 显示尺寸坐标，而节点渲染使用的是 `canvas.width`/`canvas.height` 内部分辨率——两者不匹配导致所有鼠标命中检测偏移。

Inspector 节点选中通过 canvas 上的 `mousedown` 事件读取 `selected_nodes`，虽然 LiteGraph 用 capture phase 先执行使得当前可工作，但这是脆弱的隐式依赖。

## Goals / Non-Goals

**Goals:**
- 修复画布拖动、节点选中、连线建立等全部交互
- 让 canvas 分辨率动态匹配容器实际像素尺寸
- 用 LiteGraph 官方回调替代自定义 mousedown 时序依赖

**Non-Goals:**
- 不变更 LiteGraph.js 库代码
- 不改动后端 Graph ViewModel API 和序列化逻辑
- 不重构 Inspector 表单渲染或 palette 逻辑

## Decisions

### D1: 去除 CSS canvas 拉伸，改用 JS 动态设置分辨率

**选择**: 移除 `.ng-canvas-wrap canvas { width: 100% }`，在 `init()` 中通过容器的 `offsetWidth`/`offsetHeight` 设置 `canvas.width`/`canvas.height`，并用 `ResizeObserver` 响应尺寸变化。

**备选 A — 启用 `autoresize` 选项**: LiteGraph 在 `processMouseMove` 中调用 `resize()`，但仅在鼠标移动时触发，初始加载和窗口 resize 时不生效。

**备选 B — 保持 CSS `width:100%` 并补偿坐标**: 需要修改 LiteGraph 库内部代码，违反 Non-Goals。

**理由**: `ResizeObserver` 覆盖所有尺寸变化场景（初始化、窗口调整、面板折叠），且不需要修改 LiteGraph 源码。LiteGraph 的 `resize()` 方法（`litegraph.js:10353`）已原生支持 `parentNode` 尺寸读取。

### D2: 用 `onNodeSelected` 回调替代 mousedown 监听

**选择**: 设置 `canvasRenderer.onNodeSelected = renderInspector` 和 `canvasRenderer.onNodeDeselected = function() { renderInspector(null) }`。

**理由**: `onNodeSelected`（`litegraph.js:7485`）在 `processNodeSelected` → `selectNode` 完成后触发，时序确定。消除对事件冒泡顺序的隐式依赖。

### D3: 移除 canvas HTML 固定尺寸属性

**选择**: 去掉 `<canvas width="1200" height="700">`，canvas 初始尺寸完全由 JS 在 `init()` 中根据容器设置。

**理由**: 固定值在容器尺寸不同的场景下必然导致坐标不匹配。

## Risks / Trade-offs

- **[Risk] `ResizeObserver` 在极老浏览器不可用** → 项目为个人本机工具，目标浏览器为现代 Chrome/Firefox，无兼容性风险
- **[Risk] 初始化时容器尺寸为 0（CSS 未渲染完成）** → `ResizeObserver` 会在布局稳定后触发回调，覆盖此场景
- **[Trade-off] canvas 不再有 HTML 默认尺寸** → 在 JS 执行前 canvas 为 300×150（浏览器默认），视觉上有短暂空白，但 `init()` 立即执行，用户无感知
