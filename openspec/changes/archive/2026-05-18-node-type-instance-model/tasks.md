## 1. Actions

- [x] A1 重构 `config/nodes/*.yaml` 格式：新增 `role` 字段，Function 节点 `skills` 重命名为 `handler`，LLM 节点新增 `system_prompt_file`
- [x] A2 创建 `prompts/` 目录，为现有 LLM 节点类型（reader、advisor、briefing-generator）创建 system prompt 文件
- [x] A3 创建 `config/skills/` 目录，将现有 LLM skills（summarize、classify-sentiment）提取为独立 skill 定义 YAML
- [x] A4 创建 `skill_handlers/` 目录结构（handler 文件由 pi 侧管理，此处仅建立约定目录）
- [x] A5 创建 `handlers/` 目录，将现有 function 节点的执行入口迁移为独立 handler 文件（fetch-rss.py、notify-ntfy.py 等）
- [x] A6 手动改写 `config/dags/default.yaml` 为新格式（instance 对象列表 + UUID id + type 引用 + config）
- [x] A7 后端：重构节点类型加载逻辑，支持新 YAML 格式（区分 LLM/Function，解析 role、handler、system_prompt_file）
- [x] A8 后端：重构 DAG 解析逻辑，支持 instance 对象列表格式，按 instance UUID 索引
- [x] A9 后端：实现 handler 动态加载（`importlib` 从 `handlers/` 加载，调用 `run(input_data, parameters, context)` 签名）
- [x] A10 后端：运行状态上报改为 instance UUID 索引
- [x] A11 后端：新增节点类型 CRUD API（`GET/POST/PUT/DELETE /api/graph/node-types`）
- [x] A12 后端：新增 Skill CRUD API（`GET/POST/PUT/DELETE /api/graph/skills`）
- [x] A13 后端：新增 handler 代码读写 API（`GET/PUT /api/graph/handlers/{name}`）
- [x] A14 前端：重构 TypeScript 类型定义，分离 `NodeType` 和 `NodeInstance` 接口
- [x] A15 前端：重构 `graph.ts` 中 `getHandleSpecs` 逻辑，按 role 驱动 handle 渲染（source 无输入、sink 无输出）
- [x] A16 前端：实现 `isValidConnection` 连线校验（role 约束 + 类型匹配分层策略）
- [x] A17 前端：Canvas 去掉去重限制，支持同类型多实例拖入
- [x] A18 前端：重构 QuickAddPanel 按 role 分组展示，搜索支持类型名和实例别名匹配
- [x] A19 前端：重构 Inspector 支持节点实例配置（LLM: alias/skills/model/parameters，Function: alias/source_names/parameters）
- [x] A20 前端：Inspector 支持选中边时展示 fan_in/fan_out 配置
- [x] A21 前端：连线视觉反馈（拖拽时 handle 变绿/红，类型警告连线黄色虚线）
- [x] A22 前端：创建节点管理页面 `/nodes`（三 tab：LLM 节点 / Function 节点 / Skills）
- [x] A23 前端：LLM 节点类型 tab — 列表 + 创建/编辑表单（name、role、system prompt 编辑器、默认 skills、I/O 类型、model）
- [x] A24 前端：Function 节点类型 tab — 列表 + 创建/编辑表单（name、role、handler 代码编辑器、I/O 类型、parameters schema）
- [x] A25 前端：Skills tab — 列表 + 创建/编辑表单（name、description、handler 代码编辑器、parameters_schema）
- [x] A26 前端：路由新增 `/nodes`，SideNav 新增导航入口
- [x] A27 前端：运行状态轮询适配 instance UUID 索引

## 2. Checks

- [x] C1 节点类型 YAML 格式校验
  - Covers: A1, A2
  - Command: `python -c "from stockimformation.config import load_node_configs; from pathlib import Path; nodes = load_node_configs(Path('config/nodes')); [print(f'{n.name}: role={n.role}, type={n.type}') for n in nodes.values()]"`
  - Expect: 所有节点类型加载成功，每个节点有 role 字段，LLM 节点有 system_prompt_file，Function 节点有 handler

- [x] C2 Skill 定义文件加载
  - Covers: A3, A4
  - Command: `ls config/skills/*.yaml && python -c "import yaml; from pathlib import Path; [print(yaml.safe_load(f.read_text())['name']) for f in Path('config/skills').glob('*.yaml')]"`
  - Expect: skill YAML 文件存在且可解析，包含 name、description、handler、parameters_schema 字段

- [x] C3 Handler 目录结构和动态加载
  - Covers: A5, A9
  - Command: `ls handlers/*.py && python -c "import importlib.util; spec = importlib.util.spec_from_file_location('fetch_rss', 'handlers/fetch-rss.py'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); assert hasattr(mod, 'run')"`
  - Expect: handler 文件存在且包含 `run` 函数

- [x] C4 DAG YAML 新格式解析
  - Covers: A6, A8
  - Command: `python -c "from stockimformation.config import load_dag_config; from pathlib import Path; dag = load_dag_config(Path('config/dags/default.yaml')); [print(f'{n.id}: type={n.type}, alias={n.alias}') for n in dag.nodes]"`
  - Expect: DAG 加载成功，节点有 UUID id 和 type 引用，边使用 instance UUID

- [x] C5 后端运行状态按 instance ID 索引
  - Covers: A10
  - Command: `uv run pytest tests/integration/test_web_api.py -k runtime_status -v`
  - Expect: 返回的状态字典以 UUID 为键（非 type name）

- [x] C6 节点类型 CRUD API
  - Covers: A11
  - Command: `curl -s http://localhost:8000/api/graph/node-types | python -c "import sys,json; data=json.load(sys.stdin); assert len(data['types'])>=6; print(f'OK: {len(data[\"types\"])} types')"`
  - Expect: 返回所有节点类型，包含 role、type 等新字段

- [x] C7 Skill CRUD API
  - Covers: A12
  - Command: `curl -s http://localhost:8000/api/graph/skills | python -c "import sys,json; data=json.load(sys.stdin); assert len(data['skills'])>=2; print(f'OK: {len(data[\"skills\"])} skills')"`
  - Expect: 返回所有已注册 skill

- [x] C8 Handler 代码读写 API
  - Covers: A13
  - Command: `curl -s http://localhost:8000/api/graph/handlers/fetch-rss | python -c "import sys,json; data=json.load(sys.stdin); assert 'code' in data; print('OK: code field present')"`
  - Expect: 返回 handler 源代码

- [x] C9 前端构建通过
  - Covers: A14, A15, A16, A17, A18, A19, A20, A21, A22, A23, A24, A25, A26, A27
  - Command: `cd frontend && npm run build`
  - Expect: TypeScript 编译无错误，构建成功

- [x] C10 Handle 按 role 渲染验证
  - Covers: A15
  - Command: `cd frontend && npm run verify`
  - Expect: source 节点仅有输出 handle，sink 节点仅有输入 handle，processor 节点两侧均有

- [x] C11 多实例拖入验证
  - Covers: A17
  - Command: `cd frontend && npm run verify`
  - Expect: 画布上出现两个独立节点实例，各自有不同 UUID

- [x] C12 连线校验验证
  - Covers: A16, A21
  - Command: `cd frontend && npm run verify`
  - Expect: source 节点无法接收入边；function 节点类型不匹配时硬阻止（红色）；LLM 节点类型不匹配时允许但显示黄色警告线

- [x] C13 Inspector 节点实例配置验证
  - Covers: A19, A20
  - Command: `cd frontend && npm run verify`
  - Expect: LLM 实例展示 alias/skills/model/parameters 可编辑字段；选中边展示 fan_in/fan_out 开关

- [x] C14 节点管理页面验证
  - Covers: A22, A23, A24, A25, A26
  - Command: `cd frontend && npm run verify`
  - Expect: 页面正常渲染，LLM tab 可创建/编辑类型，Function tab 展示代码编辑器，Skills tab 可管理 skill

- [x] C15 QuickAddPanel 分组和搜索验证
  - Covers: A18
  - Command: `cd frontend && npm run verify`
  - Expect: 节点按 Sources/Processors/Sinks 分组展示，搜索可匹配类型名和实例别名

- [x] C16 运行状态轮询适配验证
  - Covers: A27
  - Command: `cd frontend && npm run verify`
  - Expect: 各节点实例独立显示运行状态（running/succeeded/failed badge）

## Remediation

- [x] [code_fix] Instance config resolution: merge instance `source_names` and `model` overrides into execution inputs before invoking handlers/pi, and cover distinct same-type instances.
- [x] [code_fix] System prompt file binding: validate/read `system_prompt_file` during node loading and reject missing prompt files.
- [x] [code_fix] Node type API: create/update prompt or handler files and reject node type deletion while DAG instances reference the type.
- [x] [code_fix] Skill registry API: create/update/delete `skill_handlers/*.py` with skill YAML and resolve handlers separately from function handlers.
- [x] [code_fix] Node management page: add required create/delete/code-editing flows for LLM nodes, Function nodes, and Skills.
- [x] [code_fix] Type compatibility rules: make frontend/backend `Any` and `list[X]` matching follow the spec consistently.
- [x] [code_fix] Real-time drag feedback: add drag-state-driven handle validity styling and automated browser coverage.
