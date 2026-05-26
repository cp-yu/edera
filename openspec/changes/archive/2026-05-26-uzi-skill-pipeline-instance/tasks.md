## 1. Actions

- [x] A1 创建 `extensions/uzi-skill/manifest.yaml`，声明 extension 元数据和 `legacy-script-adapter` handler
- [x] A2 实现 LegacyScriptAdapter（`extensions/uzi-skill/adapter.py`）：HandlerContext → importlib 调用 → NodeOutput 包装
- [x] A3 实现 args_map 参数提取逻辑：支持从 params 和 input payload 中按路径提取值
- [x] A4 实现 sys.path/cwd 环境隔离：调用前设置、调用后恢复
- [x] A5 创建 `config/dags/uzi-skill-analysis.yaml`：声明完整 DAG 拓扑（~50 节点 + 边）
- [x] A6 在 `config/entities.yaml` 中新增 `v8_isolate` Resource Entity（permits=1）
- [x] A7 集成测试：用 mock fetcher 验证完整 DAG 拓扑可运行

## 2. Checks

- [x] C1 Extension manifest 可加载
  - Covers: A1
  - Command: `python -c "from stockimformation_core.bootstrap import scan_extensions; exts = scan_extensions(); assert any(e.name == 'uzi-skill' for e in exts)"`
  - Expect: uzi-skill extension 被发现并注册

- [x] C2 LegacyScriptAdapter 正常调用脚本
  - Covers: A2
  - Command: `pytest tests/extensions/test_legacy_script_adapter.py::test_basic_call`
  - Expect: adapter 成功 import mock 模块并调用 main()，返回 NodeOutput.ok=True

- [x] C3 脚本异常被 catch
  - Covers: A2
  - Command: `pytest tests/extensions/test_legacy_script_adapter.py::test_exception_handling`
  - Expect: 脚本抛 ValueError 后 adapter 返回 NodeOutput.ok=True，payload 含 error 信息

- [x] C4 args_map 从 params 提取
  - Covers: A3
  - Command: `pytest tests/extensions/test_legacy_script_adapter.py::test_args_from_params`
  - Expect: `params.ticker` 正确传入脚本函数第一个参数

- [x] C5 args_map 从 fan-in input 提取
  - Covers: A3
  - Command: `pytest tests/extensions/test_legacy_script_adapter.py::test_args_from_input`
  - Expect: `input.0_basic.data.industry` 正确提取并传入

- [x] C6 sys.path 隔离
  - Covers: A4
  - Command: `pytest tests/extensions/test_legacy_script_adapter.py::test_path_isolation`
  - Expect: 调用前后 sys.path 和 cwd 一致

- [x] C7 DAG YAML 加载无错误
  - Covers: A5
  - Command: `python -c "from stockimformation_core.dag.loader import load_graph; from stockimformation_core.config.loader import load_config; c = load_config(); g = load_graph(c.dags['uzi-skill-analysis'], c.nodes); print(f'{len(g.nodes)} nodes')"`
  - Expect: 输出节点数 ≥ 45，无异常

- [x] C8 Resource Entity 可 resolve
  - Covers: A6
  - Command: `python -c "from stockimformation_core.config.entities import EntityStore; es = EntityStore(); r = es.resolve('v8_isolate'); assert r.attributes['permits'] == 1"`
  - Expect: v8_isolate Entity resolve 成功，permits=1

- [x] C9 完整 DAG 拓扑可运行（mock fetcher）
  - Covers: A7, A5, A2
  - Command: `pytest tests/extensions/test_uzi_skill_dag.py::test_full_dag_mock -v`
  - Expect: DAG 运行完成，assemble_report 节点输出非空，无 DagError

## Remediation

- [x] [code_fix] Preserve `None` for routed optional fetcher failures in score fan-in input.
- [x] [artifact_fix] Clarify UZI DAG instances must use business `uzi-*` node types rather than `legacy-script-adapter` as the instance type.
- [x] [code_fix] Add concrete UZI node type configs, wire DAG instances to them, and set non-empty aliases for WebConsole display.
