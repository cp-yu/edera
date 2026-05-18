## 1. Actions

- [x] A1 `NodeConfig` 新增 `parameters_schema: dict[str, Any]` 字段（`schema.py`），默认 `{}`，与 `SkillConfig` 统一模式
- [x] A2 后端新增 `_build_inspector_schema(node: NodeConfig, skills: dict, portfolio: PortfolioConfig)` 函数（`routes.py`），根据 `node.type` 自动生成顶层字段 schema + 合并 `parameters_schema` + 预填充动态 enum
- [x] A3 `_node_payload()` 和 DAG 实例响应中注入 `inspector_schema` 字段，调用 A2 生成的函数
- [x] A4 后端 DAG 保存端点增加 schema 字段拆分逻辑：`param.*` 前缀字段写入 `config.parameters`，顶层字段（`model`/`skills`/`source_names`/`timeout_seconds`）保留在 `config` 顶层
- [x] A5 前端 `types.ts` 中 `NodeType` / `NodeInstance` 接口新增 `inspector_schema` 字段
- [x] A6 前端新建 `SchemaForm.tsx` 组件，根据 JSON Schema properties 渲染对应控件：`string` → 文本输入、`string+enum` → 下拉、`integer/number` → 数字输入、`boolean` → 开关、`array+items.enum` → 多选标签、未知类型 → raw JSON textarea
- [x] A7 重写 `Inspector.tsx`：删除硬编码条件字段（`model`/`skills`/`source_names` 文本输入和 `parameters` textarea），保留顶部 `alias` + 只读元信息，其余全部由 `SchemaForm` 渲染。实现三级值回退（instance config > 类型默认 > schema default）和差异保存

## 2. Checks

- [x] C1 验证 `NodeConfig` 接受 `parameters_schema` 字段
  - Covers: A1
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && python -c "from stockimformation.config.schema import NodeConfig; n = NodeConfig(name='test', type='function', handler='x', input_type='Any', output_type='Any', parameters_schema={'type': 'object', 'properties': {'k': {'type': 'string'}}}); assert n.parameters_schema['properties']['k']['type'] == 'string'; print('OK')"`
  - Expect: 输出 `OK`，无 ValidationError

- [x] C2 验证不合法 `parameters_schema` 被拒绝
  - Covers: A1
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && python -c "from stockimformation.config.schema import NodeConfig; NodeConfig(name='test', type='function', handler='x', input_type='Any', output_type='Any', parameters_schema='not-a-dict')" 2>&1 || true`
  - Expect: 抛出 ValidationError

- [x] C3 验证 `GET /api/graph/node-types` 返回 `inspector_schema` 且包含动态 enum
  - Covers: A2, A3
  - Command: `curl -s http://127.0.0.1:8000/api/graph/node-types | python -m json.tool`
  - Expect: 每个节点类型包含 `inspector_schema` 字段；LLM 类型的 `model` 字段有 `enum` 列表；`skills` 字段的 `items` 有 `enum` 列表

- [x] C4 验证 DAG 实例响应包含 `inspector_schema`
  - Covers: A3
  - Command: `curl -s http://127.0.0.1:8000/api/graph/dag/default | python -m json.tool`
  - Expect: 每个节点实例包含 `inspector_schema` 字段

- [x] C5 验证保存时 schema 字段正确拆分
  - Covers: A4
  - Evidence: 通过 Inspector 修改 LLM 实例的 `model` 并保存后，检查 `config/dags/default.yaml` 中对应实例的 `config.model` 字段
  - Expect: `config.model` 为新值，`config.parameters` 中不出现 `model` 字段

- [x] C6 验证前端 `SchemaForm` 渲染正确控件
  - Covers: A5, A6
  - Evidence: 浏览器中选中 LLM 节点实例，检查 Inspector 面板
  - Expect: `model` 显示为下拉选择（含可选值列表），`skills` 显示为多选标签（含已注册 skills），`timeout_seconds` 显示为数字输入

- [x] C7 验证 Inspector 三级值回退和差异保存
  - Covers: A7
  - Evidence: 浏览器中选中节点实例，清空 `model` 字段保存，再次选中
  - Expect: `model` 字段显示为空（placeholder 显示类型默认值），DAG YAML 中该实例 `config` 不含 `model` key

- [x] C8 验证未知 schema 类型回退 textarea
  - Covers: A6
  - Evidence: 手动在节点 YAML 中添加 `parameters_schema` 含 `type: object` 嵌套字段，刷新页面选中该节点
  - Expect: 该字段渲染为 raw JSON textarea
