## Why

Workbench Canvas 目前沿用 fetcher / processor / aggregator 的视觉词汇，无法稳定区分同一 role 下的 function 与 agent 节点。后端已经提供 `type` 与 `role` 两个轴，前端应按这两个轴分离视觉语义与连接拓扑。

## What Changes

- 将 Canvas 节点视觉分类从 legacy role-like kind 迁移为 `function`、`agent`、`dag`、`wait` 的 type-driven visual kind。
- `node.type` 决定节点图标、颜色、卡片样式、尺寸和边颜色；`node.role` 继续只决定 Handle 拓扑与 Palette role 分组。
- 保留现有 agent intervention 按钮，不改变后端 schema、BFF payload 或 Palette 分组行为。
- **BREAKING**: 前端不保留 fetcher / processor / aggregator 视觉兼容层。

## Capabilities

### New Capabilities

### Modified Capabilities
- `node-visual-system`: Canvas 节点视觉分类改为由 `node.type` 驱动，并明确 `node.role` 只驱动 Handle 拓扑。

## Impact

- Affected code: `apps/web-console/src/features/workbench/lib/graph.ts`, `apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx`, `apps/web-console/src/features/workbench/components/Canvas.tsx`。
- Tests: 更新或新增 `getNodeKind` 断言，覆盖 function 与 agent 在 source / processor / sink role 下的视觉差异，并验证 Handle 规则仍由 role 驱动。
- Not affected: `Palette.tsx`, `packages/core/src/edera_core/models/schema.py`, `packages/core/src/edera_core/service_common.py`。
