## 1. Actions

- [x] A1 新增 `schemas/entity-types/api-source.yaml`，定义 api-source entity type schema（name, base_url, params）
- [x] A2 在 `src/stockimformation/services/collection.py` 中实现 `fetch_api_source()` 函数，含内容字段探测链和时间戳解析
- [x] A3 在 `make_fetch_handler` 中支持 `source_type="api"`，使其调用 `fetch_api_source`
- [x] A4 新增 `config/nodes/api-fetcher.yaml` 节点配置
- [x] A5 新增 `handlers/fetch-api.py` handler 入口文件
- [x] A6 在 `src/stockimformation/pipeline.py` 的 `_build_executor` 中注册 `"fetch-api"` handler
- [x] A7 更新 `config/entities.yaml`：替换 sample-rss 为 HN RSS，移除 sample-web 和 minimax-docs 系列，新增 api-source 实例（cls-telegraph, jqka, solidot, ithome, github）和 stock-hk0100 entity
- [x] A8 更新 `config/entity-relations.yaml`：移除旧 sample/minimax-docs 关系，新增 stock-hk0100 与各源的 uses-source 关系
- [x] A9 更新 `config/dags/default.yaml`：加入 api-fetcher 节点，更新 rss-fetcher 的 entities 引用
- [x] A10 更新 `config/nodes/rss-fetcher.yaml` 的 source_names 为 hn-rss

## 2. Checks

- [x] C1 验证 api-source entity type schema 可被 EntityStore 加载
  - Covers: A1
  - Command: `python -c "from stockimformation.config.loader import load_app_config; from pathlib import Path; c=load_app_config(Path('config')); print([e for e in c.entities.entities if e.type=='api-source'])"`
  - Expect: 输出包含 api-source 类型的 entity 列表

- [x] C2 验证 fetch_api_source 对 yltfspace cls_telegraph 的实际拉取
  - Covers: A2, A3
  - Command: `python -c "import asyncio; from stockimformation.config.loader import load_app_config; from stockimformation.services.collection import fetch_api_source; from pathlib import Path; c=load_app_config(Path('config')); store=c.portfolio; src=[e for e in store.entities.entities if e.type=='api-source'][0]; items=asyncio.run(fetch_api_source(src, [])); print(f'{len(items)} items, first: {items[0].title[:50]}')"`
  - Expect: 输出条目数量 > 0，且 title 非空

- [x] C3 验证内容字段探测链 fallback 逻辑
  - Covers: A2
  - Command: `python -m pytest tests/ -k "api_source" -v`
  - Expect: 探测链各分支的单元测试通过

- [x] C4 验证 pipeline handler 注册
  - Covers: A5, A6
  - Command: `python -c "from stockimformation.config.loader import load_app_config; from stockimformation.pipeline import _build_executor; from pathlib import Path; c=load_app_config(Path('config')); ex=_build_executor(c, config_dir=Path('config')); print('fetch-api' in ex._handlers)"`
  - Expect: 输出 True

- [x] C5 验证 DAG 端到端运行（rss-fetcher + api-fetcher → reader）
  - Covers: A4, A7, A8, A9, A10
  - Command: `python -m stockimformation.cli run --once --dag default 2>&1 | tail -20`
  - Expect: 管道运行完成无 source fetch 错误，输出包含 RawItem 数据

- [x] C6 验证现有测试不因配置变更而失败
  - Covers: A7, A8, A9, A10
  - Command: `python -m pytest tests/unit/test_config_collection_notification.py -v`
  - Expect: 所有测试通过（可能需要更新 fixture 中的源名称引用）
