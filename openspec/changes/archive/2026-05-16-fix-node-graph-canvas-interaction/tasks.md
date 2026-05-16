## 1. Actions

- [x] A1 移除 `styles.css` 中 `.ng-canvas-wrap canvas { width: 100% }` 规则，保留 `display: block`
- [x] A2 移除 `node_graph_editor.html` 中 `<canvas>` 的 `width="1200" height="700"` 属性
- [x] A3 在 `node_graph_editor.js` 的 `init()` 中，创建 `LGraphCanvas` 前先读取容器尺寸设置 `canvas.width`/`canvas.height`
- [x] A4 在 `node_graph_editor.js` 中添加 `ResizeObserver` 监听 `.ng-canvas-wrap`，尺寸变化时调用 `canvasRenderer.resize()`
- [x] A5 将 `node_graph_editor.js` 中 canvas 的 `mousedown` Inspector 选中逻辑替换为 `canvasRenderer.onNodeSelected` 和节点取消选中回调

## 2. Checks

- [ ] C1 验证 CSS 不再包含 canvas 宽度拉伸
  - Covers: A1
  - Command: `grep -c "width: 100%" src/stockimformation/web/static/styles.css | grep -v "max-width"` 在 `.ng-canvas-wrap canvas` 块内
  - Expect: `.ng-canvas-wrap canvas` 规则中不包含 `width: 100%`

- [ ] C2 验证 canvas HTML 无固定尺寸属性
  - Covers: A2
  - Command: `grep 'width=\|height=' src/stockimformation/web/templates/node_graph_editor.html | grep -i canvas`
  - Expect: canvas 标签不含 `width` 或 `height` 属性

- [ ] C3 验证 canvas 分辨率由 JS 动态设置
  - Covers: A3
  - Evidence: `node_graph_editor.js` 中 `init()` 函数在创建 `LGraphCanvas` 前包含容器尺寸读取和 `canvas.width`/`canvas.height` 赋值
  - Expect: `canvas.width = wrap.offsetWidth` 或等效逻辑先于 `new LiteGraph.LGraphCanvas` 执行

- [ ] C4 验证 `ResizeObserver` 存在且调用 `resize()`
  - Covers: A4
  - Command: `grep -c "ResizeObserver" src/stockimformation/web/static/node_graph_editor.js`
  - Expect: 至少 1 处 `ResizeObserver` 实例化，回调中调用 `canvasRenderer.resize()`

- [ ] C5 验证 Inspector 选中使用 `onNodeSelected` 回调
  - Covers: A5
  - Command: `grep "onNodeSelected\|onNodeDeselected" src/stockimformation/web/static/node_graph_editor.js`
  - Expect: 包含 `onNodeSelected` 和取消选中的回调设置，不再有 canvas `mousedown` 事件中的 `selected_nodes` 读取

- [ ] C6 页面加载与交互回归
  - Covers: A1, A2, A3, A4, A5
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && python -m pytest tests/ -x -q --tb=short 2>&1 | tail -20`
  - Expect: 现有测试全部通过，无回归
