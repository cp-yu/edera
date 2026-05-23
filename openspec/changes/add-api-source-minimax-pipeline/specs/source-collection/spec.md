## MODIFIED Requirements

### Requirement: 非标准源抓取（FR2）
系统 SHALL 支持通过自定义规则从非标准公开信息源抓取结构化信息，使用 httpx 发起请求。`web-source` 类型保留用于 HTML regex 抓取场景，JSON API 场景由 `api-source` 类型承担。

#### Scenario: 成功抓取非标准源
- **WHEN** fetch-web handler 执行，按配置的抓取规则（URL + 选择器/正则）提取内容
- **THEN** 系统提取结构化信息，创建 RawItem

#### Scenario: 页面结构变化导致提取失败
- **WHEN** 非标准源的页面结构与配置的抓取规则不匹配
- **THEN** 系统记录提取失败，标记该源为本周期采集失败

## ADDED Requirements

### Requirement: JSON API 源采集集成（FR5）
系统 SHALL 在 pipeline 中注册 `fetch-api` handler，使其与 `fetch-rss` 和 `fetch-web` 并列作为数据源节点的执行入口。

#### Scenario: pipeline 注册 fetch-api handler
- **WHEN** pipeline 构建 NodeExecutor 时
- **THEN** handlers 字典 SHALL 包含 `"fetch-api"` 键，值为 `make_fetch_handler(entity_store, "api", system)` 的返回值

#### Scenario: DAG 中 api-fetcher 节点执行
- **WHEN** DAG runner 执行到 `api-fetcher` 类型节点
- **THEN** 系统调用 `fetch-api` handler，传入节点配置的 api-source entity 列表，输出 `list[RawItem]`
