## MODIFIED Requirements

### Requirement: Latest briefing display
系统 SHALL 展示最近一次生成的简报内容、cycle_id、创建时间和元数据，并提供进入历史简报列表和简报详情的入口。结果浏览首页还 SHALL 展示当前周期 metadata bar，包含 cycle_id、created_at、数据时间窗口、失败源数量和免责声明。结果浏览首页 SHALL 消费 `/api/results` 返回的 `metadata_bar` 和 `briefings` 字段；当存在历史简报但 `briefing` 为空时，页面仍 SHALL 展示可进入历史简报的入口。结果浏览 API SHALL 从统一输出 Entity 的 `attributes` 读取简报字段，并返回包含字符串 `id`、`cycle_id`、`content`、`metadata` 和 `created_at` 的扁平 `Briefing` payload。

#### Scenario: View latest briefing
- **WHEN** 用户打开结果浏览首页
- **THEN** 系统 SHALL 显示最新 `Briefing` 的正文、cycle_id、created_at 和 metadata

#### Scenario: No briefing exists
- **WHEN** 数据库中没有任何 `Briefing`
- **THEN** 系统 SHALL 显示空状态，而不是返回错误页面

#### Scenario: View current metadata bar
- **WHEN** 用户打开结果浏览首页且 `/api/results` 返回 `metadata_bar`
- **THEN** 系统 SHALL 显示 cycle_id、created_at、数据时间窗口、失败源数量和“不构成投资建议”免责声明

#### Scenario: View briefing history from results summary
- **WHEN** `/api/results` 返回一个或多个 `briefings`
- **THEN** 结果浏览首页 SHALL 显示历史简报摘要或入口，并使用每条 `Briefing.id` 链接到简报详情

#### Scenario: Read briefing from output Entity
- **WHEN** 最新 briefing 以 `EntityConfig(id, type, attributes)` 形式从 `node_outputs` 返回
- **THEN** `/api/results` SHALL 从 `attributes.metadata` 读取 `failed_sources` 和 `data_window`，并 MUST NOT 访问旧模型字段 `metadata_`

### Requirement: Advice list display
系统 SHALL 展示交易建议列表，包含标的、方向、置信度、原因、低置信度标记和创建时间，并支持按 `stock_code`、`direction`、created_at 时间范围和 limit 过滤。结果浏览首页还 SHALL 将建议作为当前摘要列表展示，并在摘要层用文本和样式区分 `buy`、`sell`、`hold`、低置信度和采集降级状态。结果浏览首页 SHALL 使用 `/api/results.summary_items` 作为摘要列表来源；当 `summary_items` 为空但 `advices` 存在时，页面 SHALL 继续展示 `advices`。结果浏览 API SHALL 从统一输出 Entity 的 `attributes` 读取建议字段，并返回包含字符串 `id` 的扁平 `Advice` payload。

#### Scenario: View advice list
- **WHEN** 用户打开建议列表
- **THEN** 系统 SHALL 按 created_at 倒序展示 `Advice` 记录

#### Scenario: Filter advice list
- **WHEN** 用户请求带 `stock_code`、`direction` 或时间范围的建议列表
- **THEN** 系统 SHALL 仅返回匹配条件的 `Advice` 记录，并保持 created_at 倒序

#### Scenario: Scan current summary
- **WHEN** 用户打开结果浏览首页且存在建议
- **THEN** 系统 SHALL 显示每条建议的标的、方向、置信度、核心原因、创建时间、低置信度标记和详情链接

#### Scenario: Show semantic summary state
- **WHEN** 建议方向为 `buy`、`sell`、`hold` 或 `low_confidence=true`
- **THEN** 系统 SHALL 在摘要层展示对应文字标签和非纯颜色依赖的状态样式

#### Scenario: Use summary items from results API
- **WHEN** `/api/results` 返回非空 `summary_items`
- **THEN** 结果浏览首页 SHALL 使用 `summary_items` 渲染当前摘要，并保留进入 advice 详情的链接

#### Scenario: Read advice from output Entity
- **WHEN** advice 以 `EntityConfig(id, type, attributes)` 形式从 `node_outputs` 返回
- **THEN** `/api/results` 和 `/api/advices` SHALL 从 `attributes` 读取 advice 字段，并将输出 Entity 的字符串 `id` 用作详情链接标识

### Requirement: Failure source display
系统 SHALL 展示 `/api/results.failed_sources` 或简报 metadata 中记录的失败源信息。

#### Scenario: View failed sources
- **WHEN** `/api/results` 返回 `failed_sources`
- **THEN** 系统 SHALL 在结果页面展示失败源名称和失败原因

#### Scenario: Keep result page usable without failed sources
- **WHEN** `/api/results.failed_sources` 为空对象
- **THEN** 系统 SHALL 保持结果页面可用，并 MUST NOT 显示空白失败源区域

### Requirement: Result error state display
系统 SHALL 在本机 Web 结果浏览界面区分 API 错误态与真实空数据态。

#### Scenario: Show API failure
- **WHEN** `/api/results` 返回非 2xx 响应或请求失败
- **THEN** 结果页面 SHALL 显示加载失败信息，并 MUST NOT 显示“暂无数据”

#### Scenario: Show empty state only after successful empty response
- **WHEN** `/api/results` 成功返回且 `briefing=null`、`briefings=[]`、`advices=[]`、`events=[]`、`summary_items=[]`
- **THEN** 结果页面 SHALL 显示明确空状态，说明当前数据库没有可展示结果，并 MUST NOT 只显示页面标题
