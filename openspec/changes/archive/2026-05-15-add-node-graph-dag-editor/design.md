## Context

现有 Web 控制台是 FastAPI + Jinja2 + 静态 CSS/JS，没有 Node 前端构建链。当前 `add-web-dag-visual-editor` 已经提供结构化表格和 SVG 预览，但它仍是配置表单，不是用户要求的 ComfyUI 风格 Node Graph。后端已有关键边界：`DagConfig`、`NodeConfig`、`RuntimeConfigEditor.save()`、`load_graph()`、`PipelineRun`/`NodeRun` 和 `/api/pipeline/status`。

新设计必须一次性覆盖多个阶段，但每个阶段有独立检查点。最终目标是让 `/config` 中的 DAG 编辑主入口进入节点画布，而不是继续把表格作为主体验。

## Goals / Non-Goals

**Goals:**
- 提供 ComfyUI 风格的节点画布：palette、拖拽节点、端口连线、可视化数据流、缩放/平移、选中节点。
- 在节点上展示 `input_type`、`output_type`、`type`、运行状态和最近错误。
- 在右侧 Inspector 编辑节点配置字段：`skills[]`、`model`、`source_names`、`timeout_seconds`、`parameters`。
- 保存 DAG 时继续写回现有 DAG 执行语义，并由后端统一校验。
- 保存 Node 配置时继续写回 `config/nodes/*.yaml`，并由后端统一校验现有 DAG。
- 为节点坐标和画布状态引入隔离 UI 元数据，避免执行引擎依赖前端布局。
- 保留 raw YAML 和当前结构化表格作为兜底/调试入口，直到 Node Graph 验收完成。

**Non-Goals:**
- 不复刻完整 ComfyUI 功能集，不做多工作流管理、节点代码热加载、插件市场或复杂参数组件库。
- 不在前端复制完整 DAG 业务校验；前端只做交互层提示，保存结果以后端校验为准。
- 不引入 React/Vite 构建链作为第一选择。
- 不改变 DAG Runner 的执行调度语义。
- 第一版不要求真正流式节点日志；运行状态可以先用轮询快照。

## Decisions

1. **使用一个无构建链 Node Graph 引擎，优先 LiteGraph.js**
   - 理由：用户明确要求 ComfyUI 风格，LiteGraph.js 与该交互模型贴近，并且可以作为静态资源引入，不破坏现有 Jinja 架构。
   - 替代方案：React Flow。它的开发体验好，但需要 React/Vite/npm 构建链，会把当前本机控制台变成混合 SPA，超出第一版边界。
   - 替代方案：继续自研 Canvas/SVG。端口命中、拖拽、缩放、选择、连线、序列化会快速膨胀，风险高于引入小型图引擎。

2. **新增 Graph ViewModel API，而不是让前端直接读写 YAML**
   - 后端提供图编辑 JSON：节点原型、DAG 节点实例、边、fan flags、节点配置摘要、UI 坐标、运行状态。
   - 保存时后端把 ViewModel 映射回 `DagConfig`/`NodeConfig` 并调用现有 editor 校验。
   - 这样可以避免前端承担 YAML 格式、注释和 schema 漂移问题。

3. **UI 元数据与执行语义隔离**
   - 第一推荐：在 DAG YAML 中增加 `ui` 字段，并让 `DagConfig` 明确允许/忽略该字段，执行图只读取 `name`、`nodes`、`edges`。
   - 如果实现发现 `DagConfig` 允许额外字段会破坏配置严格性，则使用旁路文件 `config/dags/<name>.ui.yaml`。
   - 不允许让 DAG Runner 依赖坐标或前端布局状态。

4. **运行状态先用快照轮询，后续再升级 SSE**
   - 现有 `/api/pipeline/status` 已可提供运行和最近记录，第一阶段可轮询并映射到节点。
   - 如果状态刷新延迟影响体验，再新增 `/api/pipeline/status/stream` SSE；不在第一阶段强制 WebSocket。

5. **侧边栏配置按字段白名单保存**
   - Inspector 第一版只覆盖 schema 已有字段：`skills[]`、`model`、`source_names`、`timeout_seconds`、`parameters`。
   - `parameters` 作为 JSON-like mapping 编辑；凭据相关字段继续由 `NodeConfig` 校验拒绝。
   - 修改 Node 配置后必须校验所有现有 DAG，保持当前 `RuntimeConfigEditor` 语义。

## Risks / Trade-offs

- [Risk] 引入图引擎增加静态资源和交互测试复杂度 → Mitigation: 仅引入本地静态资源，添加 smoke test 和 Playwright/DOM 级检查，避免前端构建链。
- [Risk] LiteGraph 内部 JSON 与项目 DAG YAML 双向转换丢失字段 → Mitigation: 以项目 Graph ViewModel 为中间层，写 adapter 单元测试覆盖 load-save round trip。
- [Risk] UI 坐标污染执行配置 → Mitigation: `ui` 字段或旁路文件隔离，DAG Runner 只消费执行字段。
- [Risk] 右侧 Inspector 同时编辑 NodeConfig 和 DagConfig，保存边界混乱 → Mitigation: UI 区分 “保存 DAG” 与 “保存节点配置”，后端分别调用 `editor.save("dag", ...)` 和 `editor.save("node", ...)`。
- [Risk] 实时状态可能与当前编辑草稿不一致 → Mitigation: 运行状态只叠加到已保存节点名；草稿新增节点显示为未运行，不影响保存。

## Migration Plan

1. 保留当前表格 DAG 编辑入口作为 fallback。
2. 新增 Node Graph 页面/API，只读渲染默认 DAG。
3. 开启图上编辑和保存；通过测试确认保存后现有管道仍可运行。
4. 添加 Inspector 节点配置编辑。
5. 添加运行状态叠加。
6. Node Graph 验收后，将 `/config` 中 DAG 编辑主入口指向 Node Graph，表格/YAML 退为高级入口。

## Open Questions

- UI 元数据最终采用 `ui` 字段还是旁路 `*.ui.yaml`，需要在实现前做一次小 spike 验证与 `DagConfig` 严格性兼容。
- 是否需要引入 Playwright 作为 dev dependency 做画布交互验证；如果不引入，至少需要 API 和 DOM smoke test 覆盖。
