## Context

当前系统支持两种信息源类型：`rss-source`（feedparser 解析 XML）和 `web-source`（regex 匹配 HTML）。示例源指向 `example.com` 无法运行。目标信息源 `news.yltfspace.com` 是 JSON API，现有 handler 无法处理。

现有采集架构：
- `EntityStore` 管理所有 source entity
- `make_fetch_handler(entity_store, source_type, system)` 返回通用 handler
- handler 从 `node_input.payload["source_names"]` 获取源列表，逐个拉取
- 拉取结果统一为 `list[RawItem]`

## Goals / Non-Goals

**Goals:**
- 新增 `api-source` entity type 和 `fetch-api` handler，支持 JSON API 类型源
- handler 通过 entity 属性配置实现可复用（不同 platform 只需不同 entity 实例）
- 内容字段自动探测，零配置适配 yltfspace 各 platform 的响应差异
- 替换示例源为真实可用源，使管道可端到端运行
- 新增 Minimax stock entity 并关联信息源

**Non-Goals:**
- 东方财富实时行情 API 集成（后续独立变更）
- LLM 内容过滤（AI/科技相关筛选由 reader 节点的 skill 处理，不在采集层）
- 修改 reader/advisor 节点逻辑

## Decisions

### D1: 新增 `api-source` entity type 而非扩展 `web-source`

**选择**: 独立的 `api-source` type + `fetch-api` handler

**备选**: 在 `web-source` 上加 `response_type: json` 字段复用 `fetch-web` handler

**理由**: `web-source` 的语义是 HTML 抓取 + regex 提取，JSON API 的解析逻辑完全不同（遍历数组、字段映射）。混在一起会让 handler 内部分支过多，违反单一职责。独立 type 也让 UI 上的 entity 管理更清晰。

### D2: 内容字段优先级探测链（方案 A）

**选择**: handler 内置探测链，按优先级尝试提取内容字段：
```
extra.content → extra.desc → extra.brief → title
```

**备选**: entity 上声明 `content_path` 字段（方案 B）

**理由**: yltfspace 所有 platform 的响应结构差异仅在 `extra` 子字段命名上。探测链覆盖已知的所有变体，无需每个 entity 额外配置。如果未来出现无法覆盖的格式，再按需加 `content_path` 覆盖字段。

### D3: `api-source` entity schema 设计

```yaml
schema:
  properties:
    name: {type: string}
    base_url: {type: string}       # e.g. https://news.yltfspace.com/api/news
    params: {type: object}         # e.g. {platform: "cls_telegraph"}
```

`params` 作为 query string 参数传递给 `httpx.get(base_url, params=params)`。这使得同一个 handler 可以服务任何带 query 参数的 JSON API。

### D4: 复用 `make_fetch_handler` 模式

**选择**: 在 `collection.py` 中新增 `fetch_api_source()` 函数，并通过现有的 `make_fetch_handler(entity_store, "api", system)` 模式注册

**理由**: 与 `fetch_rss_source` / `fetch_web_source` 保持一致的架构模式，`_source_map` 和 recovery 逻辑可直接复用。

### D5: 时间戳解析策略

yltfspace 返回毫秒时间戳（`pubDate` 或 `extra.date`），探测链：
```
item["pubDate"] → item["extra"]["date"] → datetime.now(utc)
```

均为 Unix 毫秒，除以 1000 转 `datetime`。

## Risks / Trade-offs

- [yltfspace API 无文档保证] → 接口可能变更。Mitigation: 已有 source recovery 机制会捕获解析失败并上报
- [探测链可能遗漏新格式] → Mitigation: 探测失败时 fallback 到 `title`，保证不丢数据；日志记录 warning
- [移除 sample-rss/sample-web 影响测试] → Mitigation: 测试 fixture 中保留独立的 mock source，不依赖 config/ 下的真实源
