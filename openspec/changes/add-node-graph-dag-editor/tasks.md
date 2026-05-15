## 1. Actions

- [ ] A1 建立 Node Graph 编辑器 OpenSpec 文档，明确一个 change 内的多阶段范围、非目标、API 和验收边界。
- [ ] A2 设计并实现 Graph ViewModel 后端层，提供节点原型、DAG 图状态、UI 布局元数据和运行状态映射，不让前端直接解析 YAML。
- [ ] A3 引入无构建链节点图引擎静态资源，优先 LiteGraph.js，并新增 Node Graph 页面骨架：palette、canvas、Inspector、fallback 链接。
- [ ] A4 实现 Phase 1 只读图展示：加载现有 DAG，显示节点、输入/输出端口、连线、fan flags 和类型标签。
- [ ] A5 实现 Phase 2 图上编辑与保存：添加节点、拖拽定位、端口连线、删除节点/边、保存 DAG，并保持后端校验和原子写入。
- [ ] A6 实现 Phase 3 Inspector 节点配置：展示并保存 `skills[]`、`model`、`source_names`、`timeout_seconds`、`parameters`。
- [ ] A7 实现 Phase 4 运行状态叠加：将当前或最近 NodeRun 状态、错误和 cycle_id 映射到画布节点。
- [ ] A8 调整配置页入口，使 Node Graph 成为 DAG 编辑主入口，保留表格/YAML 兜底入口。
- [ ] A9 增加测试覆盖：Graph ViewModel round trip、DAG/Node 保存拒绝路径、页面加载、静态资源、运行状态映射和 fallback 可用性。

## 2. Checks

- [ ] C1 验证 OpenSpec change 可用于实施
  - Covers: A1
  - Command: `openspec validate add-node-graph-dag-editor --strict`
  - Expect: validation passes

- [ ] C2 验证 Graph ViewModel 与配置 round trip
  - Covers: A2, A5, A9
  - Command: `pytest tests/unit/test_config_editor.py tests/integration/test_web_api.py`
  - Expect: DAG graph state load-save round trip preserves nodes, edges, fan flags, and UI metadata; invalid graph saves do not modify files

- [ ] C3 验证 Node Graph 页面和静态资源
  - Covers: A3, A4, A8, A9
  - Command: `pytest tests/integration/test_web_api.py`
  - Expect: DAG editor entry opens Node Graph page with palette, canvas, Inspector, graph script, and fallback links

- [ ] C4 验证图上编辑保存和 Inspector 保存
  - Covers: A5, A6, A9
  - Command: `pytest tests/integration/test_web_api.py`
  - Expect: graph DAG save writes valid `config/dags/*.yaml`; Inspector node save writes valid `config/nodes/*.yaml`; invalid DAG/Node payloads are rejected without writing

- [ ] C5 验证运行状态叠加数据
  - Covers: A7, A9
  - Command: `pytest tests/integration/test_web_api.py`
  - Expect: graph runtime status response maps saved node names to status, error, and cycle_id; unsaved draft nodes remain `unknown`

- [ ] C6 验证静态质量门禁
  - Covers: A2, A3, A4, A5, A6, A7, A8, A9
  - Command: `ruff check . && mypy src/stockimformation`
  - Expect: no lint or type errors
