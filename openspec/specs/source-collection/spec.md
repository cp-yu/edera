---
capabilities:
  - cap.advisory.trade-advisory
---
# source-collection Specification

## Purpose
此规约记录变更 project-mvp 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: RSS 订阅拉取（FR1）
系统 SHALL 通过 RSS 订阅自动拉取财经新闻流，使用 feedparser 解析 RSS/Atom 格式。

#### Scenario: 成功拉取 RSS 源
- **WHEN** fetch-rss Skill 执行，目标 RSS 源可访问
- **THEN** 系统解析 RSS 条目，为每条创建 RawItem，包含 title、content、url、published_at

#### Scenario: RSS 源不可访问
- **WHEN** fetch-rss Skill 执行，目标 RSS 源返回 HTTP 错误或超时
- **THEN** 系统记录失败信息，标记该源为本周期采集失败，不阻塞其他源

### Requirement: 非标准源抓取（FR2）
系统 SHALL 支持通过自定义规则从非标准公开信息源抓取结构化信息，使用 httpx 发起请求。

#### Scenario: 成功抓取非标准源
- **WHEN** fetch-web Skill 执行，按配置的抓取规则（URL + 选择器/正则）提取内容
- **THEN** 系统提取结构化信息，创建 RawItem

#### Scenario: 页面结构变化导致提取失败
- **WHEN** 非标准源的页面结构与配置的抓取规则不匹配
- **THEN** 系统记录提取失败，标记该源为本周期采集失败

### Requirement: 定时触发（FR3）
系统 SHALL 使用 APScheduler 按 30min 周期定时触发采集任务。

#### Scenario: 周期性采集触发
- **WHEN** APScheduler 到达 30min 周期
- **THEN** 系统触发 DAG Runner 执行默认管道

### Requirement: URL 去重（FR4）
系统 SHALL 基于 URL 对采集到的信息进行去重，同一 URL 在系统中仅保留一条 RawItem。

#### Scenario: 重复 URL 去重
- **WHEN** 采集到的条目 URL 已存在于数据库
- **THEN** 系统跳过该条目，不重复处理

#### Scenario: 不同源的相同 URL
- **WHEN** 两个不同信息源采集到相同 URL 的条目
- **THEN** 系统仅保留首次采集的记录

