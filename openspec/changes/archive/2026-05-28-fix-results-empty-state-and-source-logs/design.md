## Context

当前 `/api/results` 可以成功返回结构完整但内容为空的对象，例如 `briefing:null`、`briefings:[]`、`advices:[]`、`events:[]`、`summary_items:[]`。`ResultsPage.tsx` 只在 `!data` 时显示空态，因此有效空对象会渲染成只剩标题的页面。

后端结果 API 已返回 `metadata_bar`、`briefings`、`summary_items`、`failed_sources`、`event_details`，但结果首页只消费 `briefing`、`advices`、`events`。信息源页则相反：后端日志 payload 返回 `status`，前端类型和页面读取 `node_status`，状态列为空。`source_execution_logs()` 在未指定 `source_name` 时还会从 `NodeRun` 拉取普通节点记录，导致 UUID 节点实例混入信息源日志。

## Goals / Non-Goals

**Goals:**
- `/results` 对成功空对象显示明确占位，说明当前数据库没有可展示结果。
- `/results` 展示 `metadata_bar`、历史简报入口、摘要建议和失败源。
- 信息源日志 API 与前端统一使用 `status` 字段。
- 信息源日志默认只包含已配置信息源或 source recovery 记录。
- 信息源日志时间列不会因为 `started_at=null` 变成空白。

**Non-Goals:**
- 不迁移 `data/stockimformation.db` 到当前 `data/edera.db`。
- 不修改 `config/system.toml` 的 `database_url`。
- 不在本 change 修复 runtime 写入 `started_at` 的根因；runtime redesign 由独立 change 处理。
- 不重做结果页整体视觉系统或引入新的 UI 组件库。

## Decisions

1. 空态以“成功响应但无可展示结果”为判定，不以 `data` 是否存在为判定。
   - 理由：后端返回有效对象时页面仍然应给用户结论，不能让用户通过空白推断系统状态。
   - 取舍：空态不代表数据库为空，只代表当前 API 响应没有可展示的 briefing/advice/event/summary 数据。

2. 结果页消费已有字段，不扩大 API。
   - 理由：`/api/results` 已返回 `metadata_bar`、`briefings`、`summary_items`、`failed_sources`，修复应优先解决前端未消费问题。
   - 取舍：`event_details` 暂不作为首页核心展示字段，保留给详情或后续证据视图，避免本 change 扩大范围。

3. 信息源日志契约使用 `status`。
   - 理由：后端现有 payload 已返回 `status`，且项目其他运行状态类型也使用 `status`；让前端改为匹配后端比增加重复字段更干净。
   - 取舍：删除前端 `node_status` 假设；如果兼容旧数据，只能在解析层做临时兜底，但最终契约是 `status`。

4. 日志过滤依赖已配置信息源集合。
   - 理由：只有 portfolio/config 中声明的信息源才应出现在信息源日志视图；普通 DAG 节点属于运行历史，不属于信息源健康页。
   - 取舍：repository 查询需要获得或推导 source 名称集合；如果保持 repository 签名不传集合，则 web route 必须在调用前后过滤。

5. 时间显示采用前端容错，不在本 change 回填历史记录。
   - 理由：`started_at=null` 是历史写入链路问题，但用户当前需要页面可读。显示层用 `started_at ?? ended_at` 能解决空列。
   - 取舍：这不修复数据语义，只修复可见性；根因由 runtime 表和 source recovery redesign 处理。

## Risks / Trade-offs

- [Risk] 只显示“当前数据库没有可展示结果”可能被误读为所有历史库都无数据。→ Mitigation：文案限定为“当前数据库/当前配置”，不承诺其他数据库。
- [Risk] 过滤日志时 source recovery 记录和 NodeRun 记录的来源字段不同。→ Mitigation：统一以 `source_name` 作为过滤键，缺失或不在配置集合内的记录不进入信息源页。
- [Risk] 结果页展示更多字段可能增加布局拥挤。→ Mitigation：只做紧凑 summary/section，不引入大面积重设计。
