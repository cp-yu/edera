## Context

结果浏览后端已经通过 `latest_briefing()`、`list_briefings()`、`list_advices()` 读取 `node_outputs` 中的统一输出 Entity。当前 Web routes 仍把返回值当作旧 `Briefing`/`Advice` 模型实例，直接访问 `metadata_`、`cycle_id`、`created_at` 等属性，导致 `/api/results` 在有 briefing 输出时 500。

前端 `ResultsPage` 没有查询错误态分支，React Query 抛出的 500 会落到 `data` 为空路径，显示“暂无数据”。这掩盖了后端合同错误。

## Goals / Non-Goals

**Goals:**

- 让结果浏览 API 明确接受 `EntityConfig` 输入，并输出扁平、稳定、前端可直接消费的 result payload。
- 统一结果深链标识为输出 Entity 的字符串 `id`。
- 删除结果浏览链路对旧 `metadata_` 字段和数据库行号的依赖。
- 让结果页区分加载失败与真实空态。

**Non-Goals:**

- 不恢复旧多表模型。
- 不引入向后兼容别名。
- 不改变 DAG 执行、节点输出存储或 source collection 行为。
- 不实现新的价格对比、事件归并或数据迁移能力。

## Decisions

### 1. 在 Web 层做 payload 归一化

结果浏览 API 使用小型 helper 将 `EntityConfig.attributes` 转为 `Briefing`、`Advice` payload。这样 repository 保持统一 Entity 查询职责，不承担某个页面的展示合同。

Alternative considered: 在 `EntityConfig` 上补 `metadata_` 属性。拒绝原因：这是伪装旧模型，会继续扩大概念混乱。

### 2. 深链使用 Entity 字符串 id

`/api/briefings/{id}` 和 `/api/advices/{id}` SHALL 按输出 Entity 的 `id` 查询。前端路由参数保持字符串，不再 `Number(id)`。

Alternative considered: 暴露数据库 row id 作为详情 id。拒绝原因：row id 只是存储细节，统一 Entity 模型已经有稳定 id。

### 3. Briefing payload 使用 `metadata`

Web API SHALL 返回 `metadata`，不返回 `metadata_`。旧字段来自 Pydantic alias workaround，不应成为前端合同。

Alternative considered: 同时返回 `metadata` 和 `metadata_`。拒绝原因：开发阶段无需兼容，双字段会留下永久歧义。

### 4. 前端显式处理错误态

`ResultsPage` SHALL 在 `isError` 时展示加载失败消息。只有 API 成功返回且列表/briefing 均为空时才显示真实空态。

Alternative considered: 继续用统一“暂无数据”。拒绝原因：会把系统错误伪装成业务空态，调试成本高。

## Risks / Trade-offs

- [Risk] 现有手工打开的数字详情 URL 会失效 → Mitigation: 开发阶段接受 breaking change，前端生成的新链接统一使用字符串 id。
- [Risk] 后端 helper 漏掉某些 Advice 字段 → Mitigation: 用 API 测试覆盖 `/api/results` 和详情响应关键字段。
- [Risk] `metadata` 为空或类型异常导致 metadata bar 再次崩溃 → Mitigation: helper 对非 dict metadata 使用 `{}`。
- [Risk] repository 仍只有 row id 查询函数 → Mitigation: 增加按 `entity_id` 查询的窄函数，不改变通用查询路径。
