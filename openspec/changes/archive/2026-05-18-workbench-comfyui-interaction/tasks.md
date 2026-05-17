## 1. Actions

- [x] A1 安装 `elkjs` 依赖，移除 `@dagrejs/dagre`
- [x] A2 重构 `CustomNode.tsx`：按节点类型差异化渲染（fetcher 蓝色/llm 紫色/aggregator 绿色），动态生成 Handle（左 input 右 output），添加运行状态 badge（左上角圆点）
- [x] A3 实现位置自动持久化：`onNodeDragStop` 写 localStorage 草稿，debounce 500ms 调用 `PUT /api/graph/dag/{name}` 保存；加载时优先使用 localStorage 草稿
- [x] A4 连线美化：将 edge 类型改为 `bezier`，根据 source 节点类型着色，保留 `MarkerType.ArrowClosed` 箭头
- [x] A5 实现右键上下文菜单组件：edge 菜单（反转方向、删除）、node 菜单（删除节点、断开所有连线）
- [x] A6 实现 ELK 自动布局：替换 dagre 逻辑，使用 ELK layered 算法（方向 DOWN），配置端口约束和层间距
- [x] A7 实现按 target 自动分组可视化：计算分组边界，渲染半透明背景色块
- [x] A8 实现 Cmd+K 搜索快速添加节点面板：模糊匹配节点原型，选中后在画布视口中心创建节点
- [x] A9 实现执行路径高亮：运行时根据节点状态对 edge 加粗变色（running 蓝/succeeded 绿/failed 红）
- [x] A10 实现 Undo/Redo：维护 `{nodes, edges}` snapshot 栈（上限 50），Ctrl+Z 撤销，Ctrl+Shift+Z 重做
- [x] A11 启用 `snapToGrid`（20px）并实现对齐辅助线（拖拽时显示与相邻节点的水平/垂直对齐参考线）

## 2. Checks

- [x] C1 验证依赖变更
  - Covers: A1
  - Command: `cd frontend && cat package.json | grep -E "elkjs|dagre"`
  - Expect: `elkjs` 存在于 dependencies，`@dagrejs/dagre` 已移除

- [x] C2 验证节点类型差异化渲染和动态 Handle
  - Covers: A2
  - Command: `cd frontend && npx tsc --noEmit`
  - Expect: 编译通过，`CustomNode.tsx` 包含按 type 分支的样式逻辑和动态 Handle 生成

- [x] C3 验证运行状态 badge 渲染
  - Covers: A2
  - Evidence: `CustomNode.tsx` 中 badge 渲染逻辑
  - Expect: 根据 `status` 字段渲染对应颜色圆点（succeeded 绿/running 蓝+pulse/pending 灰/failed 红），无状态时不渲染

- [x] C4 验证位置自动持久化
  - Covers: A3
  - Evidence: `Canvas.tsx` 中 `onNodeDragStop` 处理逻辑
  - Expect: 拖拽停止后写 localStorage，debounce 500ms 后调用 save API；加载时检查 localStorage 草稿

- [x] C5 验证连线贝塞尔渲染和着色
  - Covers: A4
  - Evidence: `Canvas.tsx` 中 edge 配置
  - Expect: edge 使用 `bezier` 类型，根据 source 节点类型设置 `style.stroke` 颜色

- [x] C6 验证右键菜单功能
  - Covers: A5
  - Command: `cd frontend && npx tsc --noEmit`
  - Expect: 编译通过，存在 `onNodeContextMenu`/`onEdgeContextMenu` 处理器，反转方向操作交换 source/target

- [x] C7 验证 ELK 自动布局
  - Covers: A6
  - Command: `cd frontend && npx tsc --noEmit`
  - Expect: 编译通过，布局函数调用 `elkjs` 的 `ELK().layout()` 方法，配置 `elk.algorithm: layered`、`elk.direction: DOWN`

- [x] C8 验证 target 分组可视化
  - Covers: A7
  - Evidence: 分组渲染组件代码
  - Expect: 按节点关联的 target 计算分组，为每组渲染半透明背景色块

- [x] C9 验证搜索添加节点面板
  - Covers: A8
  - Command: `cd frontend && npx tsc --noEmit`
  - Expect: 编译通过，Cmd+K 快捷键绑定存在，搜索面板组件实现模糊匹配和节点创建

- [x] C10 验证执行路径高亮
  - Covers: A9
  - Evidence: `Canvas.tsx` 中 edge 样式计算逻辑
  - Expect: 运行时根据 `runtimeStatus` 中节点状态对上游 edge 应用加粗和颜色变更

- [x] C11 验证 Undo/Redo
  - Covers: A10
  - Command: `cd frontend && npx tsc --noEmit`
  - Expect: 编译通过，存在 snapshot 栈管理逻辑，Ctrl+Z/Ctrl+Shift+Z 键绑定，栈深度上限 50

- [x] C12 验证 snap-to-grid 和对齐辅助线
  - Covers: A11
  - Evidence: `Canvas.tsx` 中 `snapToGrid` 配置和辅助线组件
  - Expect: `ReactFlow` 组件配置 `snapToGrid` + `snapGrid={[20, 20]}`，拖拽时渲染对齐辅助线
