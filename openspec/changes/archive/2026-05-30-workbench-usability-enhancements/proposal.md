<!--
propose-routing:
  input_length: 18
  detail_score: 5/5
  multi_subsystem: false
  decision: Design Summary found; use confirmed exploration design as primary input.
-->
## Why

DAG Workbench 目前在大图场景下更强调节点类型而不是实例语义，导致用户难以直接确认业务节点身份；长 Inspector 表单也会把保存动作挤出可视域。节点面板和手动选中反馈同样缺少足够的扫描效率。

## What Changes

- Canvas 节点标题改为优先显示实例 `alias`，并保留 `type_name` 作为副信息。
- Inspector 的 Config tab 将“保存实例”动作固定在右侧面板可视域底部。
- Palette 保留 `role` 一级分组，并在每个 role 下按节点名称前缀做二级分组。
- 点击 Canvas 上的节点时，高亮该节点及一跳入边/出边，不改变运行态路径高亮语义。

## Capabilities

### New Capabilities

### Modified Capabilities
- `dag-workbench-ui`: 修改 Palette 分组和 Inspector 保存动作可见性要求。
- `node-visual-system`: 修改 Canvas 节点标题展示要求，优先显示实例 alias。
- `canvas-interaction-enhancement`: 增加手动选中节点时的一跳连线高亮交互。

## Impact

- Affected code:
  - `apps/web-console/src/features/workbench/components/Palette.tsx`
  - `apps/web-console/src/features/workbench/components/Inspector.tsx`
  - `apps/web-console/src/features/workbench/components/Canvas.tsx`
  - `apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx`
  - `apps/web-console/src/features/workbench/lib/graph.ts` if shared display/grouping helpers are needed
- APIs: no backend API changes.
- Data model: no DAG YAML schema changes; edge identity remains UUID based.
- Dependencies: no new dependencies.
