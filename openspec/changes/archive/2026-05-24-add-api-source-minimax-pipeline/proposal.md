## Why

当前 `config/entities.yaml` 中的示例源（`sample-rss`、`sample-web`）指向 `example.com`，无法实际获取数据，导致管道运行失败。需要替换为真实可用的信息源，并新增 JSON API 类型源的支持，以覆盖 Minimax (HK0100) 的股市分析场景。

## What Changes

- 新增 `api-source` entity type，支持 JSON API 类型的信息源（如 news.yltfspace.com）
- 新增 `fetch-api` handler，通过 entity 配置实现可复用的 JSON API 数据拉取，内置优先级探测链自动提取内容字段
- 新增 `api-fetcher` node 类型，作为 DAG 中独立的数据源节点
- 替换 `sample-rss` 为 Hacker News RSS (`https://news.ycombinator.com/rss`)
- 移除 `sample-web` 及所有 minimax-docs/tonghuashun 相关的 web-source（不再需要 regex 抓取）
- 新增 Minimax stock entity (`stock-hk0100`, code: `00100.HK`)
- 新增多个 `api-source` entity 实例，覆盖 yltfspace 的科技和财经 platform
- 更新 `entity-relations.yaml`，将新源关联到 Minimax stock entity
- 更新 `config/dags/default.yaml`，加入 `api-fetcher` 节点

## Capabilities

### New Capabilities
- `api-source-collection`: 覆盖 JSON API 类型信息源的定义、拉取、内容字段自动探测和 RawItem 转换

### Modified Capabilities
- `source-collection`: 新增 FR5 — JSON API 源拉取需求，扩展现有采集能力

## Impact

- 新增文件：`schemas/entity-types/api-source.yaml`、`config/nodes/api-fetcher.yaml`、`handlers/fetch-api.py`
- 修改文件：`config/entities.yaml`、`config/entity-relations.yaml`、`config/dags/default.yaml`、`config/nodes/rss-fetcher.yaml`、`src/stockimformation/services/collection.py`、`src/stockimformation/pipeline.py`
- 新增依赖：无（httpx 已存在）
- 测试影响：需更新引用 `sample-rss`/`sample-web` 的单元测试和集成测试
