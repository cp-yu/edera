<!--
Smart Routing:
- Design Summary found: true
- Input length: 16
- Detail score: 0/5 without conversation context; Design Summary supplies architecture, components, data flow, stack, tests, and risks.
- Multi-subsystem: false
- Decision: proceed using the explore Design Summary.
-->
## Why

Workbench 现在无法恢复用户上次查看的 DAG，节点面板在节点类型增多后扫描成本高，选中节点的一跳连线反馈也不够突出。这个变更补齐这些前端交互缺口，让 DAG 阅读和编辑保持轻量、可恢复、可扫描。

## What Changes

- Workbench DAG 选择器记住用户上次选中的 DAG，下次打开 `/workbench` 时优先恢复该 DAG。
- 节点面板增加搜索框，搜索同时匹配节点类型名称和当前 DAG 中同类型实例的 alias。
- 节点面板的 role 组和 prefix 组支持折叠；折叠状态只在当前页面会话内有效。
- Canvas 选中节点时，直接相连的入边/出边更明显，其他边降低透明度。
- 选中态只作为渲染派生状态，不写入 DAG 配置，不覆盖运行态 edge 颜色。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `dag-workbench-ui`: DAG 选择器增加上次 DAG 本地恢复；节点面板增加搜索和临时折叠行为。
- `canvas-interaction-enhancement`: 选中节点的一跳连线高亮同时弱化无关连线，保持运行态颜色优先。

## Impact

- 前端状态：`apps/web-console/src/store/useAppStore.ts`
- Workbench 页面数据流：`apps/web-console/src/features/workbench/WorkbenchPage.tsx`
- 节点面板：`apps/web-console/src/features/workbench/components/Palette.tsx`
- Canvas 连线视觉派生：`apps/web-console/src/features/workbench/components/Canvas.tsx`
- 前端行为测试：`apps/web-console/tests/`
- 不影响后端 API、DAG YAML、运行时调度、节点/边数据模型或新增依赖。
