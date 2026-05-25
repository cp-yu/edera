## MODIFIED Requirements

### Requirement: Latest briefing display
系统 SHALL 展示最近一次生成的简报内容、cycle_id、创建时间和元数据，并提供进入历史简报列表和简报详情的入口。结果浏览首页还 SHALL 展示当前周期 metadata bar，包含 cycle_id、created_at、数据时间窗口、失败源数量和免责声明。结果浏览 API SHALL 从统一输出 Entity 的 `attributes` 读取简报字段，并返回包含字符串 `id`、`cycle_id`、`content`、`metadata` 和 `created_at` 的扁平 `Briefing` payload。

#### Scenario: View latest briefing
- **WHEN** 用户打开结果浏览首页
- **THEN** 系统 SHALL 显示最新 `Briefing` 的正文、cycle_id、created_at 和 metadata

#### Scenario: No briefing exists
- **WHEN** 数据库中没有任何 `Briefing`
- **THEN** 系统 SHALL 显示空状态，而不是返回错误页面

#### Scenario: View current metadata bar
- **WHEN** 用户打开结果浏览首页且存在最新 `Briefing`
- **THEN** 系统 SHALL 显示 cycle_id、created_at、数据时间窗口、失败源数量和“不构成投资建议”免责声明

#### Scenario: Read briefing from output Entity
- **WHEN** 最新 briefing 以 `EntityConfig(id, type, attributes)` 形式从 `node_outputs` 返回
- **THEN** `/api/results` SHALL 从 `attributes.metadata` 读取 `failed_sources` 和 `data_window`，并 MUST NOT 访问旧模型字段 `metadata_`

### Requirement: Advice list display
系统 SHALL 展示交易建议列表，包含标的、方向、置信度、原因、低置信度标记和创建时间，并支持按 `stock_code`、`direction`、created_at 时间范围和 limit 过滤。结果浏览首页还 SHALL 将建议作为当前摘要列表展示，并在摘要层用文本和样式区分 `buy`、`sell`、`hold`、低置信度和采集降级状态。结果浏览 API SHALL 从统一输出 Entity 的 `attributes` 读取建议字段，并返回包含字符串 `id` 的扁平 `Advice` payload。

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

#### Scenario: Read advice from output Entity
- **WHEN** advice 以 `EntityConfig(id, type, attributes)` 形式从 `node_outputs` 返回
- **THEN** `/api/results` 和 `/api/advices` SHALL 从 `attributes` 读取 advice 字段，并将输出 Entity 的字符串 `id` 用作详情链接标识

### Requirement: Result deep links
系统 SHALL 提供稳定的本机 HTML 和 API 深链，允许用户直达单条简报或单条建议证据链。结果深链 SHALL 使用统一输出 Entity 的字符串 `id`，不依赖数据库行号。

#### Scenario: Open briefing deep link
- **WHEN** 用户访问 `/results/briefings/{id}` 或 `/api/briefings/{id}`
- **THEN** 系统 SHALL 返回对应 `Briefing`；不存在时 API MUST 返回统一 JSON error，HTML SHALL 返回不崩溃的未找到页面

#### Scenario: Open advice deep link
- **WHEN** 用户访问 `/results/advices/{id}` 或 `/api/advices/{id}`
- **THEN** 系统 SHALL 返回对应 `Advice`、相关 `AnalysisResult` 和 `RawItem`；不存在时 API MUST 返回统一 JSON error，HTML SHALL 返回不崩溃的未找到页面

#### Scenario: Use Entity id for deep links
- **WHEN** 结果列表生成简报或建议详情链接
- **THEN** 前端 SHALL 使用 API payload 中的字符串 `id` 作为路由参数，后端 SHALL 按输出 Entity id 查询对应记录

## ADDED Requirements

### Requirement: Result error state display
系统 SHALL 在本机 Web 结果浏览界面区分 API 错误态与真实空数据态。

#### Scenario: Show API failure
- **WHEN** `/api/results` 返回非 2xx 响应或请求失败
- **THEN** 结果页面 SHALL 显示加载失败信息，并 MUST NOT 显示“暂无数据”

#### Scenario: Show empty state only after successful empty response
- **WHEN** `/api/results` 成功返回且没有 briefing、advice 或 event 数据
- **THEN** 结果页面 SHALL 显示空状态
