## 1. Actions

- [x] A1 `EntityTypeConfig` 新增 `system_protected: bool = False` 字段
- [x] A2 `config/schemas/` 下 node.yaml, dag.yaml, trigger.yaml, run-metadata.yaml 添加 `system_protected: true`
- [x] A3 后端新增 `_resolve_entity_type_path` 函数，支持双目录查找
- [x] A4 `GET /api/config/entity-types/{name}` 使用新 resolver
- [x] A5 `PUT /api/config/entity-types/{name}` 添加 `system_protected` 检查，返回 403
- [x] A6 `DELETE /api/config/entity-types/{name}` 添加 `system_protected` 检查，返回 403
- [x] A7 前端 `EntityType` 类型定义新增 `system_protected` 字段
- [x] A8 前端类型卡片：protected 或 relation 时隐藏删除按钮，编辑改为查看
- [x] A9 前端查看弹窗：readonly textarea，无保存按钮

## 2. Checks

- [x] C1 验证 `system_protected` 字段加载
  - Covers: A1, A2
  - Command: `uv run pytest tests/unit/test_entity_types.py -v`
  - Expect: node/dag/trigger/run-metadata 的 `system_protected` 为 `True`，stock 为 `False`

- [x] C2 验证 GET 双目录解析
  - Covers: A3, A4
  - Command: `uv run pytest tests/ -k "entity_type_read" -v`
  - Expect: GET node 返回 200 + content；GET unknown 返回 404

- [x] C3 验证 PUT protected 类型被拒绝
  - Covers: A5
  - Command: `uv run pytest tests/ -k "entity_type_update_protected" -v`
  - Expect: PUT node 返回 403，message 包含 `system protected`

- [x] C4 验证 DELETE protected 类型被拒绝
  - Covers: A6
  - Command: `uv run pytest tests/ -k "entity_type_delete_protected" -v`
  - Expect: DELETE node 返回 403，message 包含 `system protected`

- [x] C5 验证前端保护展示
  - Covers: A7, A8, A9
  - Command: `cd frontend && npm run test:c5`
  - Evidence: `frontend/test-results/c5-entity-type-protection/cards.png`, `frontend/test-results/c5-entity-type-protection/readonly-dialog.png`
  - Expect: node/dag/trigger/run-metadata/relation 卡片仅显示"查看"按钮；点击后弹窗 textarea 为 readonly，无保存按钮；stock 等普通类型仍显示"编辑"和"删除"
