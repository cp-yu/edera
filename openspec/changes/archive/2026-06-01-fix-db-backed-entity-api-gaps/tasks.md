## 测试覆盖

本变更引入 6 个测试文件（4 新建 + 2 扩展），共 22 个新增测试覆盖所有修复点。

### Bug A: API 响应格式 (`routes.py`)

**文件**: `tests/core/integration/test_entity_api_format.py`（新建）

- [x] A1 `test_entities_list_returns_wrapped_format` — GET `/api/entities` 返回 `{"entities": [...]}`
- [x] A2 `test_entities_list_with_type_filter` — type 参数透传
- [x] A3 `test_entity_relations_returns_wrapped_format` — 返回 `{"relations": [...]}`，每条含 `id`, `entities`, `type`
- [x] A4 `test_entity_relation_types_returns_wrapped_format` — 返回 `{"types": [...]}`，去重排序

### Bug B: `_entity_payload` 缺少 display 字段 (`server.py`)

**文件**: `tests/core/unit/test_entity_payload.py`（新建）

- [x] B1 `test_entity_payload_includes_display` — display 按 `display_template` 渲染
- [x] B2 `test_entity_payload_includes_ref` — ref 格式为 `{type}:{business_id}`
- [x] B3 `test_display_fallback_on_missing_template_key` — template 属性缺失时 fallback
- [x] B4 `test_display_fallback_when_no_matching_entity_type` — 无匹配 entity_type 时 fallback

### Bug C: `_relation_filters` 空 dict falsy (`server.py`)

**文件**: `tests/core/unit/test_relation_query.py`（新建）

- [x] C1 `test_type_relation_returns_non_none` — `["type=relation"]` 返回非 None
- [x] C2 `test_type_relation_returns_empty_dict` — 返回空 dict
- [x] C3 `test_non_relation_type_returns_none` — `["type=stock"]` 返回 None
- [x] C4 `test_extracts_relation_type` — 提取 `relation_type` filter
- [x] C5 `test_extracts_from_to` — 提取 from/to filter
- [x] C6 `test_combined_filters` — 组合 filter
- [x] C7 `test_returns_all_with_empty_filters` — 空 filter dict 返回全部关系
- [x] C8 `test_filters_by_type` — 按 type 过滤
- [x] C9 `test_result_has_relation_structure` — 返回 struc含 `relation_type`, `entities`

### Bug D: Handler 注册表查找 (`graph_service.py`)

**文件**: `packages/core/tests/test_graph_service.py`（扩展）

- [x] D1 `test_list_handlers_returns_registry_entries` — 返回注册表 handler 列表
- [x] D2 `test_get_handler_reads_from_registry_path` — 从注册表 path 读代码
- [x] D3 `test_get_handler_not_found_not_in_registry` — 注册表无记录时 404
- [x] D4 `test_save_handler_writes_to_registry_path` — 写入注册表 path

**文件**: `tests/core/integration/test_graph_api.py`（扩展）

- [x] D5 `test_graph_handler_list_route` — GET `/api/graph/handlers` 返回 `{"handlers": [...]}`

### Bug E: 前端 handlers tab (`NodesPage.tsx`)

**文件**: `apps/web-console/tests/nodes-handlers-tab.spec.ts`（新建）

- [ ] E1 `handlers tab renders from list API` — 渲染 3 张 handler 卡
- [ ] E2 `handlers tab shows handler code` — textarea 含 handler 代码
- [ ] E3 `handlers tab uses registry not node handler field` — 只显示 registry 列表条目

### 测试执行

```bash
# 后端 (22/22)
pytest tests/core/unit/test_relation_query.py tests/core/unit/test_entity_payload.py \
       tests/core/integration/test_entity_api_format.py tests/core/integration/test_graph_api.py \
       packages/core/tests/test_graph_service.py -v

# 前端 (需 Playwright)
cd apps/web-console && npx playwright test tests/nodes-handlers-tab.spec.ts
```