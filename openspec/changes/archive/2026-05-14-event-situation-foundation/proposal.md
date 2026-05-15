## Why

当前系统已具备 RawItem、AnalysisResult、Advice、Briefing 和结果浏览能力，但 P2 的核心差异化能力仍缺少事件级基础：多源信息只能作为独立分析或建议证据展示，无法稳定回答“这些来源是不是同一事件、是否互相矛盾、事件处于什么阶段、当前热度多高”。这是从 MVP 走向 `_bmad-output/` 中跨源事件态势分析的下一块必要地基。

本变更先做确定性、本地证据驱动的事件基础，不引入热度拐点预测、弱信号高置信建议、Node Graph UI、实时行情或第三方服务，避免把 P2 后续能力一次性做成大泥球。

## What Changes

- 新增事件管理能力，基于归并后的分析结果创建和更新事件记录。
- 为事件记录定义最小生命周期状态：`discovered`、`verifying`、`monitoring`、`climax`、`fading`、`archived`。
- 基于本地证据数量、来源多样性、证据新近性和矛盾标记计算确定性 `heat_score`，不访问实时市场数据。
- 在信息分析链路增加跨源关键词/事件归并：按 `stock_code`、规范化关键词/标题/正文重叠和时间窗口识别同一事件。
- 将现有 `AnalysisResult.contradiction` 扩展为跨源矛盾检测结果的一部分，要求保留矛盾双方证据。
- 在结果浏览 API 和 WebUI 暴露事件组、矛盾标记、生命周期状态、热度分数和关联证据，使用文本、表格和 badge 展示。
- 增加事件记录数据模型契约，用于保存事件分组、状态、热度和证据链接。

## Capabilities

### New Capabilities
- `event-management`: 事件记录、事件更新、生命周期状态和本地确定性热度分数。

### Modified Capabilities
- `data-models`: 增加事件记录模型及其与 RawItem/AnalysisResult 的证据关联字段。
- `information-analysis`: 增加跨源关键词事件归并和跨源矛盾检测要求。
- `result-explorer`: 增加事件组、矛盾、生命周期、热度和证据链的 API/WebUI 展示要求。

## Impact

- **代码**: 预计新增事件分组/更新服务、事件记录 SQLModel 与 Alembic migration、repository 查询方法；扩展分析输出存储和结果浏览路由 payload。
- **API**: `/api/results`、建议详情相关 API 和可能新增的事件列表/详情 API 返回事件组、状态、热度、矛盾和证据字段。
- **WebUI**: `results.html` 和 `advice_detail.html` 增加事件表格、badge 和证据链接；不引入复杂图、图表或 Node Graph。
- **依赖**: 不新增第三方服务，不依赖实时外部市场数据。
- **数据迁移**: 新增事件记录表；现有 RawItem、AnalysisResult、Advice、Briefing 数据保持可读。
