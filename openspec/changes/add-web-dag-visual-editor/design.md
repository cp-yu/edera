## Context

现有 `/config` 页面已经能列出并编辑 `system`、`portfolio`、`node`、`dag`、`skill` 配置。DAG 保存路径由 `RuntimeConfigEditor.save("dag", name, content)` 统一处理，并通过 `DagConfig` 与 `load_graph()` 校验缺失节点、未知边、I/O 类型不匹配和环。当前缺口是 DAG 编辑体验：用户必须手写 YAML 才能维护节点和边。

前端现状是 FastAPI + Jinja2 + `styles.css`，没有 Node 构建链。设计必须保持精准改动，不引入新的前端框架或图编辑库。

## Goals / Non-Goals

**Goals:**
- 在 `kind=dag` 的配置页内提供结构化 DAG 编辑表单和 SVG 预览。
- 支持勾选启用节点、添加/删除边、编辑 `from`、`to`、`fan_in`、`fan_out`。
- 结构化保存写回现有 DAG YAML，并复用现有后端校验和原子保存。
- 保留原 YAML textarea 和 `/config` 保存路径。

**Non-Goals:**
- 不做拖拽连线或画布坐标持久化。
- 不引入 React、Vite、Cytoscape、React Flow 等新依赖。
- 不在前端复制环检测或 I/O 类型校验。
- 不改变 DAG Runner 执行语义。

## Decisions

1. **在 `/config` 页面内渐进增强，而不是新增独立应用**
   - 理由：DAG 是运行时配置的一种，现有页面已经承载保存语义和错误展示。把结构化编辑嵌入当前页面，改动边界最小。
   - 替代方案：新增 `/dag` 页面。它会重复配置文件选择、错误展示和保存流程，第一版没有必要。

2. **结构化表单提交到新增 `POST /config/dag`，最终仍调用 `RuntimeConfigEditor.save()`**
   - 理由：表单适合无构建前端，后端可以用现有 YAML 序列化与校验链路保证单一真相。
   - 替代方案：前端直接生成 YAML 后走 `/config`。这会让浏览器承担 YAML 序列化，增加注释丢失和格式差异风险。

3. **前端 JS 只做 DOM 操作和 SVG 预览**
   - 理由：添加/删除边和预览属于交互层；DAG 合法性属于后端配置校验层。
   - 替代方案：前端实现完整 DAG 校验。会产生双重规则，后续 schema 变化时容易漂移。

4. **节点列表使用 checkbox，边使用表格**
   - 理由：当前 DAG 数据量小，表格比拖拽图编辑更可控、更易测试、更符合现有 UI 风格。
   - 替代方案：全画布拖拽连线。第一版复杂度过高，且可访问性和移动端体验更差。

## Risks / Trade-offs

- [Risk] 结构化保存会重排 YAML 格式并丢失原有注释 → Mitigation: 保留 YAML 原文编辑入口；第一版不承诺注释保持。
- [Risk] 预览布局不能表达复杂 DAG 的所有细节 → Mitigation: 预览仅作为辅助，表格和后端校验是权威。
- [Risk] 无 JS 时无法使用添加/删除边增强 → Mitigation: YAML textarea 继续可用，满足兜底编辑。
- [Risk] 用户禁用所有节点或提交空边导致非法/无意义配置 → Mitigation: 后端结构化 payload 构造后仍走 `RuntimeConfigEditor.save()`，由 schema/DAG 校验拒绝非法配置。
