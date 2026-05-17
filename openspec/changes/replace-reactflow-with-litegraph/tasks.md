## 1. Actions

- [ ] A1 从 ComfyUI Frontend monorepo 拷贝 `src/lib/litegraph/` 到 `frontend/src/lib/litegraph/`，确认 TypeScript 编译通过
- [ ] A2 移除 `@xyflow/react` 和 `@dagrejs/dagre` 依赖，清理 `package.json`
- [ ] A3 创建 `DynamicNode` 基类，支持通过构造参数配置 title、color、input/output slots
- [ ] A4 创建 `frontend/src/features/workbench/lib/nodeRegistry.ts`，从 `useNodePrototypes` API 数据动态注册 LiteGraph 节点类型
- [ ] A5 创建 `frontend/src/features/workbench/lib/adapter.ts`，实现 `toGraph(dag)` 和 `toDag(lgraph)` 双向转换
- [ ] A6 重写 `Canvas.tsx`：挂载 `<canvas>` 元素，创建 `LGraph` + `LGraphCanvas` 实例，通过 React ref 管理生命周期
- [ ] A7 实现事件桥接：`onNodeSelected` / `onNodeDeselected` / `onConnectionChange` → zustand store
- [ ] A8 实现 Palette 拖拽到 canvas：监听 canvas `dragover` + `drop` 事件，坐标转换后调用 `LGraph.add()`
- [ ] A9 实现手动保存按钮：点击时调用 adapter `toDag()` → API 写回后端；添加未保存状态指示
- [ ] A10 实现 localStorage 草稿：定时序列化 LGraph 状态，加载时检测并提示恢复
- [ ] A11 实现运行时状态覆盖：轮询 runtime status → 修改 LGraphNode `bgcolor`/`color` 属性展示状态
- [ ] A12 CSS 换皮：覆盖 litegraph 默认样式（深色背景、节点色、字体、圆角），匹配 Tailwind 主题
- [ ] A13 移除 `CustomNode.tsx`、旧 `Canvas.tsx` 中 ReactFlow 相关代码和 `@xyflow/react` 导入
- [ ] A14 保留自动布局功能：集成 dagre 或 litegraph 内置布局算法，绑定到工具栏按钮

## 2. Checks

- [ ] C1 验证 litegraph vendor 编译通过
  - Covers: A1
  - Command: `cd frontend && npx tsc --noEmit`
  - Expect: 无 TypeScript 编译错误

- [ ] C2 验证旧依赖移除干净
  - Covers: A2, A13
  - Command: `cd frontend && grep -r "@xyflow\|@dagrejs" src/ --include="*.ts" --include="*.tsx" | grep -v node_modules`
  - Expect: 无匹配结果

- [ ] C3 验证动态节点注册
  - Covers: A3, A4
  - Evidence: 浏览器打开 `/workbench`，DevTools console 无 LiteGraph 注册错误
  - Expect: 所有后端返回的节点原型在 canvas 中可见

- [ ] C4 验证 DAG 加载渲染
  - Covers: A5, A6
  - Evidence: 浏览器打开 `/workbench`，选择已有 DAG
  - Expect: 画布渲染出所有节点和连线，位置与后端 `ui.nodes` 一致

- [ ] C5 验证节点选中桥接 Inspector
  - Covers: A7
  - Evidence: 浏览器点击画布中节点
  - Expect: Inspector 面板显示对应节点配置字段

- [ ] C6 验证 Palette 拖拽添加节点
  - Covers: A8
  - Evidence: 浏览器从 Palette 拖拽节点到画布
  - Expect: 节点出现在鼠标释放位置，LGraph 中新增对应节点

- [ ] C7 验证手动保存写回后端
  - Covers: A9
  - Evidence: 浏览器编辑 DAG 后点击保存，检查后端 yaml 文件
  - Expect: yaml 文件包含新增/修改的节点和边，`ui.nodes` 包含位置元数据

- [ ] C8 验证草稿持久化和恢复
  - Covers: A10
  - Evidence: 浏览器编辑 DAG 后等待 60s，刷新页面
  - Expect: 系统提示恢复草稿，确认后画布恢复到编辑状态

- [ ] C9 验证运行时状态覆盖
  - Covers: A11
  - Evidence: 浏览器触发 DAG 运行，观察画布节点
  - Expect: 运行中节点显示蓝色，成功显示绿色，失败显示红色

- [ ] C10 验证 CSS 主题一致性
  - Covers: A12
  - Evidence: 浏览器截图对比
  - Expect: 画布深色背景、节点圆角、字体与 Tailwind 主题一致，无默认 litegraph 灰色样式残留

- [ ] C11 验证自动布局功能
  - Covers: A14
  - Evidence: 浏览器点击自动布局按钮
  - Expect: 节点重新排列为 TB 方向层级布局
