## Context

Workbench 已经使用 React、Zustand 和 `@xyflow/react`。当前 `selectedDagName` 在 `useAppStore` 中固定初始化为 `default`，`Palette` 只做 role/prefix 分组展示，`Canvas` 已经基于 `selectedNodeId` 给直接相连的 edge 添加高亮 class，但未弱化无关 edge，导致大图中选中反馈不够明显。

这个变更只处理 Web Console 前端交互。它不改变后端 API、DAG YAML、运行时调度、节点实例模型或 edge 数据模型。

## Goals / Non-Goals

**Goals:**

- 打开 Workbench 时恢复上次选中的 DAG。
- 让节点面板支持搜索和临时折叠，降低节点类型增多后的扫描成本。
- 点击 Canvas node 后，让相连 edge 和无关 edge 形成清晰视觉对比。
- 保持运行态 edge 颜色优先，避免手动选中态影响运行路径判断。
- 用 Playwright 覆盖用户可见行为。

**Non-Goals:**

- 不新增后端偏好 API 或统一 preferences 模型。
- 不把 Palette 折叠状态写入 `localStorage`。
- 不做 `/workbench?dag=...` 深链同步。
- 不改 QuickAddPanel 的 `Cmd/Ctrl+K` 添加节点流程。
- 不重做 Workbench 整体视觉系统。

## Decisions

### D1: DAG 选择使用 `localStorage` 本地恢复

`useAppStore` 初始化 `selectedDagName` 时读取 `localStorage['workbench:selectedDagName']`，`setSelectedDag(name)` 写入同一个 key，并保留清空 node/edge 选中态和重置 Inspector tab 的现有行为。

替代方案是新增后端偏好模型或 URL 状态。后端偏好会把局部浏览器体验升级成服务端协议，当前没有必要；URL 状态适合分享和深链，但本次需求只要求“上一次关闭后打开恢复”。

### D2: Palette 搜索由当前 DAG 数据辅助

`WorkbenchPage` 将当前 `dag.data` 传给 `Palette`。`Palette` 根据 node prototypes 和当前 DAG nodes 建立 type 到 aliases 的映射。搜索命中 node type name，或命中当前 DAG 中该 type 的实例 alias 时，都展示对应 prototype。

这个规则避免把实例 alias 渲染成新的 Palette item。Palette 仍然只拖拽 node type，保持 `application/reactflow` payload 写入 `node.name` 的现有契约。

### D3: Palette 折叠只保存在组件内

role 组和 prefix 组使用组件内 `useState` 记录折叠状态。搜索 query 非空时，匹配项 SHALL 自动展示，不被折叠状态隐藏。

替代方案是持久化折叠状态。用户已确认不需要持久化；临时状态足以解决当前阅读成本，也减少持久化 key 和清理逻辑。

### D4: Canvas 选中态只派生视觉，不改 edge 数据

`styledEdges` 在有 `selectedNodeId` 时派生视觉：

- source 或 target 等于 selected node 的 edge 保持高 opacity，增加 stroke width、shadow 或 class。
- 不相连 edge 降低 opacity。
- stroke 颜色沿用运行态或 source kind 计算结果，不被手动选中态替换。

这样不会污染 undo/redo snapshot、DAG save payload 或 runtime status。

## Risks / Trade-offs

- 保存的 DAG 已不存在 → 先沿用当前请求行为，不在本次引入 fallback 协议；测试只覆盖存在 DAG 的恢复路径。
- alias 命中的是实例但展示的是 type → 明确采用“alias 命中实例 type，则展示对应 prototype”的规则。
- 搜索和折叠交互冲突 → 搜索时自动展示匹配项，折叠状态只影响空搜索或非搜索浏览。
- 无关 edge 过淡 → 采用中等弱化，不把无关 edge 完全隐藏。
- 选中态干扰运行态 → 手动选中态只改宽度、透明度、阴影，不改 runtime stroke color。
