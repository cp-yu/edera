## Context

Workbench Canvas 已从后端接收节点 `type` 与 `role`。当前前端 `NodeKind` 仍混用 fetcher / processor / aggregator 视觉词汇，导致 `agent` 与 `function` 在同一 role 下无法形成稳定视觉差异。

## Goals / Non-Goals

**Goals:**
- 建立两轴模型：`node.type` 决定视觉家族，`node.role` 决定 Handle 拓扑与 Palette 分组。
- 让 `function` 与 `agent` 在 source / processor / sink role 下都能视觉区分。
- 保留现有 agent intervention 按钮与 Canvas helper 消费边界。

**Non-Goals:**
- 不修改后端 `schema.py`、`service_common.py` 或 API payload。
- 不改 `Palette.tsx` 的 role 分组。
- 不新增 fetcher / processor / aggregator 兼容层。

## Decisions

- 使用 `function | agent | dag | wait | unknown` 作为 `NodeKind`。理由：它直接对应后端 `node.type`，避免 role 与视觉语义继续耦合。备选的 legacy kind 映射会继续隐藏 agent/function 差异。
- `getNodeKind` 只从 `node.type` 推导视觉 kind。理由：role 已由 `getHandleSpecs` 消费，继续参与视觉会让同一 agent 因 role 不同而失去统一家族外观。
- `CustomNode.tsx` 只根据 visual kind 选择图标、颜色和卡片样式。agent intervention 按钮继续由 `node.type === 'agent'` 控制，因为这是功能入口，不是视觉分类。
- `Canvas.tsx` 继续只消费 `getNodeSize` 与 `getNodeEdgeColor`。理由：Canvas 应依赖图形 helper，不直接分支 agent/function，减少重复条件。

## Risks / Trade-offs

- legacy visual vocabulary 直接移除 → 通过 `getNodeKind` 测试覆盖 function/agent 跨 role 的映射，避免静默回退。
- role 不再影响视觉 → 通过 `getHandleSpecs` 测试证明 source / processor / sink Handle 规则保持不变。
- Canvas helper 边界被绕过 → 通过代码检查确认 `Canvas.tsx` 未直接对 agent/function 分支。
