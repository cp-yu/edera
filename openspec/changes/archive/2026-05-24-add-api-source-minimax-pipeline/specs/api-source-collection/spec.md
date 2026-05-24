## ADDED Requirements

### Requirement: JSON API 源拉取（FR1）
系统 SHALL 支持通过 `api-source` entity type 定义 JSON API 类型信息源，使用 httpx 发起 GET 请求并解析 JSON 响应。

#### Scenario: 成功拉取 API 源
- **WHEN** fetch-api handler 执行，目标 API 源可访问且返回 `{"code": 200, "data": [...]}`
- **THEN** 系统遍历 `data` 数组，为每条记录创建 RawItem，包含 title、content、url、published_at

#### Scenario: API 源返回错误码
- **WHEN** fetch-api handler 执行，目标 API 返回 HTTP 错误或 JSON 中 `code` 非 200
- **THEN** 系统记录失败信息，标记该源为本周期采集失败，不阻塞其他源

#### Scenario: API 源不可访问
- **WHEN** fetch-api handler 执行，目标 API 源网络超时或连接失败
- **THEN** 系统触发 source recovery 机制，按配置的重试次数尝试恢复

### Requirement: 内容字段自动探测（FR2）
系统 SHALL 使用优先级探测链从 JSON 响应条目中提取内容字段，无需 entity 额外配置。

#### Scenario: extra.content 字段存在
- **WHEN** API 响应条目包含 `extra.content` 字段
- **THEN** 系统使用 `extra.content` 作为 RawItem 的 content

#### Scenario: 仅 extra.desc 字段存在
- **WHEN** API 响应条目不含 `extra.content` 但包含 `extra.desc`
- **THEN** 系统使用 `extra.desc` 作为 RawItem 的 content

#### Scenario: 仅 extra.brief 字段存在
- **WHEN** API 响应条目不含 `extra.content` 和 `extra.desc` 但包含 `extra.brief`
- **THEN** 系统使用 `extra.brief` 作为 RawItem 的 content

#### Scenario: 所有 extra 内容字段缺失
- **WHEN** API 响应条目的 extra 中无 content/desc/brief 字段
- **THEN** 系统 fallback 使用 `title` 作为 RawItem 的 content

### Requirement: 时间戳解析（FR3）
系统 SHALL 从 JSON 响应条目中提取发布时间，支持毫秒级 Unix 时间戳。

#### Scenario: pubDate 字段存在
- **WHEN** API 响应条目包含 `pubDate` 字段（毫秒时间戳）
- **THEN** 系统将其除以 1000 转换为 UTC datetime 作为 published_at

#### Scenario: 仅 extra.date 字段存在
- **WHEN** API 响应条目不含 `pubDate` 但 `extra.date` 存在
- **THEN** 系统使用 `extra.date`（毫秒时间戳）转换为 published_at

#### Scenario: 无时间戳字段
- **WHEN** API 响应条目无 `pubDate` 且无 `extra.date`
- **THEN** 系统使用当前 UTC 时间作为 published_at

### Requirement: Entity 驱动的参数化（FR4）
系统 SHALL 通过 `api-source` entity 的 `base_url` 和 `params` 属性实现 handler 的可复用配置。

#### Scenario: 不同 platform 使用同一 handler
- **WHEN** DAG 中 api-fetcher 节点配置了多个 api-source entity（各自 params.platform 不同）
- **THEN** handler 逐个拉取每个 entity 对应的 API 端点，合并结果为统一的 RawItem 列表

#### Scenario: entity 缺少必要属性
- **WHEN** api-source entity 缺少 `base_url` 属性
- **THEN** 系统跳过该源并记录配置错误日志
