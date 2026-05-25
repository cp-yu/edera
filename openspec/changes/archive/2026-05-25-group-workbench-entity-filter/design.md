## Context

`EntityFilter` 当前直接读取当前 DAG 的 `entities`，并在底部工具栏右侧为每个 entity 渲染一个按钮。这个实现对少量 item 可用，但 item 增多后会横向撑开底栏。

## Goals / Non-Goals

**Goals:**
- 底栏只保留一个固定宽度入口和选择摘要。
- 展开后按 `entity.type` 分组展示全部 entity，并支持多选。
- 继续使用现有 `entityFilter` store 状态，保持画布 opacity 过滤逻辑不变。

**Non-Goals:**
- 不修改 DAG 选择器。
- 不新增后端字段或 API。
- 不重构 Workbench 布局。

## Decisions

- 使用组件内部 `open` state 控制一个绝对定位面板，而不是引入弹窗依赖。理由：项目当前没有通用 popover 组件，新增依赖不值当。
- 按 `entity.type` 分组，组内按 `display` 排序。理由：数据已提供 type，足以解决多 item 扫描问题。
- 底栏按钮显示 `全部实体`、单个 entity display 或 `已选 N 项`。理由：摘要稳定，不随 item 数量撑开。
- 面板中的每个 item 继续使用 `entityColor(entity.ref)` 作为色彩提示。理由：保留现有视觉语义。

## Risks / Trade-offs

- [Risk] 绝对定位面板可能被父容器裁剪 → Mitigation: 底栏父级未设置 overflow hidden，面板向上展开并设置 z-index。
- [Risk] 没有 click outside 关闭会留下展开面板 → Mitigation: 提供显式触发按钮和选择后保持面板，满足多选；Escape 关闭由后续需要再补。
