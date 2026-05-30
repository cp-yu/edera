## Context

Workbench 已经使用 React Flow、Zustand 和实例化 DAG 模型。当前 `CustomNode` 在 Canvas 中突出显示 `type_name`，而 `alias` 虽然已是实例的人类可读标签，但没有成为 Canvas 标题。`Inspector` 把保存按钮放在滚动内容末尾，长配置时需要滚动到底才能保存。`Palette` 只按 `role` 分组，在大量 `uzi-*` 节点存在时扫描成本高。`Canvas` 已经维护 `selectedNodeId`，但 edge 没有基于手动选择态派生视觉反馈。

## Goals / Non-Goals

**Goals:**
- 让 Canvas 节点标题直接呈现实例语义：`alias || type_name`。
- 保持真实类型信息可见，避免 alias 重名时无法确认节点类型。
- 让 Inspector Config 保存动作始终停留在右侧面板可视域底部。
- 保留 Palette 的 `role` 语义，并增加名称前缀二级分组。
- 点击节点时高亮一跳入边/出边，辅助确认局部拓扑。

**Non-Goals:**
- 不修改后端 API、DAG YAML schema 或 edge 引用规则。
- 不新增显式 `category` / `group` 元数据字段。
- 不把手动选中高亮扩展为全上下游路径高亮。
- 不重做 Workbench 整体视觉系统。

## Decisions

1. Canvas 标题使用 `alias || type_name`，`type_name` 保留为副信息。
   - Rationale: `alias` 是实例级人类可读标签，最适合在 DAG 上确认节点；`type_name` 仍用于辨认真实节点类型。
   - Alternative: 只显示 alias。Rejected because alias may duplicate and hides type context.

2. Palette 使用 `role` 一级分组、名称前缀二级分组。
   - Rationale: 保留 Sources / Processors / Sinks 的执行语义，同时把 `uzi-fetch-*`、`uzi-render-*` 等批量节点收拢。
   - Alternative: 纯前缀分组。Rejected because it loses role semantics.
   - Alternative: 新增显式 category 字段。Rejected because current need is presentational and does not justify schema/API expansion.

3. 选中节点只高亮直接相连 edge。
   - Rationale: 手动选择态用于确认局部拓扑；全路径高亮已属于运行态执行路径语义。
   - Alternative: 高亮全部上下游。Rejected because it conflicts visually with runtime path highlighting.

4. Inspector sticky save 只作用于 Config tab。
   - Rationale: Runtime 和 Triggers tab 没有实例保存动作，强行固定 footer 会浪费空间并混淆语义。

## Risks / Trade-offs

- alias 重名 → 保留 `type_name` 副信息，必要时实现时可用 tooltip 展示完整类型。
- 手动选中态覆盖运行态颜色 → 选中态只叠加 stroke width、opacity 或 shadow，不替换 runtime edge color。
- 前缀分组是启发式 → 分组只影响展示，不写入配置，也不成为领域模型。
- sticky save 压缩表单空间 → 使用右侧 panel 内部 flex 布局，让内容区滚动、footer 固定。
