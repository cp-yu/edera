### Task 1: 创建 data-collection Sub DAG

**Goal**: 创建 `uzi-data-collection` Sub DAG Entity，封装数据采集阶段的 25 个节点（1 basic + 22 fetch + 2 autofill）和 1 个新增的 aggregate 节点。

**Files**:
- Create: `extensions/uzi-skill/entities/dags/uzi-data-collection.yaml`
- Create: `extensions/uzi-skill/entities/nodes/uzi-aggregate-collection-results.yaml`

**Requirements**:
- Sub DAG 包含 `0_basic` 作为唯一 source 节点
- 22 个 fetch 节点和 2 个 autofill 节点保持原 ID 和配置
- 所有 fetch 节点标记为 `optional: true`
- 3 个使用 v8_isolate 的节点（`7_industry`, `10_valuation`, `12_capital_flow`）配置 `resource: "v8_isolate"`
- 新增 `aggregate_results` 节点作为唯一 sink，fan-in from 所有 fetch 和 autofill 节点

#### Checks

- [x] C1 验证 Sub DAG 拓扑加载
  - Verifies: `specs/uzi-subdag-structure/spec.md` / Requirement "data-collection Sub DAG 结构" / Scenario "data-collection Sub DAG 节点拓扑"
  - Command: `cd /home/yunxin/Documents/Code/tools/Edera && python -c "from edera_core.config.loader import load_dag_config; from edera_core.dag.loader import load_graph; from edera_core.config.entities import EntityStore; store = EntityStore(); dag = store.resolve('uzi-data-collection'); nodes = {n.name: store.resolve(f'node:{n.name}') for inst in dag.attributes['nodes'] for n in [inst] if isinstance(inst, dict) and 'type' in inst}; graph = load_graph(dag, nodes); print(f'Nodes: {len(graph.nodes)}'); assert len(graph.nodes) == 26"`
  - Expect: 输出 "Nodes: 26"，包含 1 basic + 22 fetch + 2 autofill + 1 aggregate

- [x] C2 验证 fetch 节点 optional 语义
  - Verifies: `specs/uzi-subdag-structure/spec.md` / Requirement "data-collection Sub DAG 结构" / Scenario "data-collection 聚合输出"
  - Evidence: `extensions/uzi-skill/entities/dags/uzi-data-collection.yaml`
  - Expect: 所有 fetch 节点的 `optional` 字段为 `true`

- [x] C3 验证 resource 约束配置
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "Resource 约束声明" / Scenario "v8_isolate 节点串行"
  - Evidence: `extensions/uzi-skill/entities/dags/uzi-data-collection.yaml`
  - Expect: 节点 `7_industry`, `10_valuation`, `12_capital_flow` 的 `resource` 字段为 `"v8_isolate"`

### Task 2: 创建 scoring-synthesis Sub DAG

**Goal**: 创建 `uzi-scoring-synthesis` Sub DAG Entity，封装评分与综合阶段的 3 个串联节点。

**Files**:
- Create: `extensions/uzi-skill/entities/dags/uzi-scoring-synthesis.yaml`

**Requirements**:
- Sub DAG 包含 3 个线性串联节点：`score_dimensions` (source) → `generate_panel` → `generate_synthesis` (sink)
- 保持原节点配置和 ID 不变

#### Checks

- [x] C4 验证 Sub DAG 串行拓扑
  - Verifies: `specs/uzi-subdag-structure/spec.md` / Requirement "scoring-synthesis Sub DAG 结构" / Scenario "scoring-synthesis Sub DAG 节点拓扑"
  - Command: `cd /home/yunxin/Documents/Code/tools/Edera && python -c "from edera_core.config.loader import load_dag_config; from edera_core.dag.loader import load_graph; from edera_core.config.entities import EntityStore; store = EntityStore(); dag = store.resolve('uzi-scoring-synthesis'); nodes = {n.name: store.resolve(f'node:{n.name}') for inst in dag.attributes['nodes'] for n in [inst] if isinstance(inst, dict) and 'type' in inst}; graph = load_graph(dag, nodes); print(f'Nodes: {len(graph.nodes)}, Edges: {sum(len(e) for e in graph.edges.values())}'); assert len(graph.nodes) == 3 and sum(len(e) for e in graph.edges.values()) == 2"`
  - Expect: 输出 "Nodes: 3, Edges: 2"，确认线性拓扑

- [x] C5 验证 source/sink 角色
  - Verifies: `specs/uzi-subdag-structure/spec.md` / Requirement "scoring-synthesis Sub DAG 结构" / Scenario "scoring-synthesis 串行执行"
  - Evidence: `extensions/uzi-skill/entities/dags/uzi-scoring-synthesis.yaml`
  - Expect: `score_dimensions` 无上游边，`generate_synthesis` 无下游边

### Task 3: 创建 rendering Sub DAG

**Goal**: 创建 `uzi-rendering` Sub DAG Entity，封装报告渲染阶段的 21 个独立 render 节点。

**Files**:
- Create: `extensions/uzi-skill/entities/dags/uzi-rendering.yaml`

**Requirements**:
- Sub DAG 包含 21 个独立 render 节点（无内部依赖）
- 所有 render 节点标记为 `optional: true`
- 每个节点既是 source 也是 sink（多 source 多 sink 模式）

#### Checks

- [x] C6 验证 rendering 节点数量和 optional
  - Verifies: `specs/uzi-subdag-structure/spec.md` / Requirement "rendering Sub DAG 结构" / Scenario "rendering Sub DAG 节点拓扑"
  - Command: `cd /home/yunxin/Documents/Code/tools/Edera && python -c "from edera_core.config.entities import EntityStore; store = EntityStore(); dag = store.resolve('uzi-rendering'); nodes = dag.attributes['nodes']; print(f'Nodes: {len(nodes)}'); assert len(nodes) == 21 and all(n.get('optional') == True for n in nodes)"`
  - Expect: 输出 "Nodes: 21"，所有节点 optional 为 true

- [x] C7 验证无内部边依赖
  - Verifies: `specs/uzi-subdag-structure/spec.md` / Requirement "rendering Sub DAG 结构" / Scenario "rendering 并行执行"
  - Evidence: `extensions/uzi-skill/entities/dags/uzi-rendering.yaml`
  - Expect: `edges` 数组为空或不存在

### Task 4: 重构主 DAG 为 Sub DAG 引用

**Goal**: 修改 `uzi-skill-analysis` 主 DAG，将 51 个中间节点替换为 3 个 Sub DAG 引用节点（type: dag），节点总数从 53 降至 5。

**Files**:
- Modify: `extensions/uzi-skill/entities/dags/uzi-skill-analysis.yaml`

**Requirements**:
- 保留 `preflight` 和 `assemble_report` 节点
- 新增 3 个 Sub DAG 引用节点：`data_collection` (type: dag, dag_ref: uzi-data-collection), `scoring_synthesis` (type: dag, dag_ref: uzi-scoring-synthesis), `rendering` (type: dag, dag_ref: uzi-rendering)
- 配置边：preflight → data_collection → scoring_synthesis → rendering → assemble_report，且 preflight → assemble_report 直接边保持
- 删除原有 51 个中间节点和对应的边

#### Checks

- [x] C8 验证主 DAG 节点数量
  - Verifies: `specs/uzi-subdag-structure/spec.md` / Requirement "主 DAG 重构为 Sub DAG 引用" / Scenario "主 DAG 节点结构"
  - Command: `cd /home/yunxin/Documents/Code/tools/Edera && python -c "from edera_core.config.entities import EntityStore; store = EntityStore(); dag = store.resolve('uzi-skill-analysis'); nodes = dag.attributes['nodes']; print(f'Nodes: {len(nodes)}'); assert len(nodes) == 5"`
  - Expect: 输出 "Nodes: 5"

- [x] C9 验证 Sub DAG 引用节点类型
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "DAG 拓扑声明" / Scenario "主 DAG 配置可加载"
  - Evidence: `extensions/uzi-skill/entities/dags/uzi-skill-analysis.yaml`
  - Expect: 3 个节点 (`data_collection`, `scoring_synthesis`, `rendering`) 的 `type` 字段为 `"dag"`，且 `dag_ref` 字段分别为对应的 Sub DAG 名称

- [x] C10 验证主 DAG 数据流边
  - Verifies: `specs/uzi-subdag-structure/spec.md` / Requirement "主 DAG 重构为 Sub DAG 引用" / Scenario "主 DAG 数据流"
  - Evidence: `extensions/uzi-skill/entities/dags/uzi-skill-analysis.yaml`
  - Expect: `edges` 包含 preflight → data_collection, data_collection → scoring_synthesis, scoring_synthesis → rendering, rendering → assemble_report, preflight → assemble_report 五条边

### Task 5: 更新 extension manifest imports

**Goal**: 更新 `extensions/uzi-skill/manifest.yaml` 的 `imports.entities`，添加 3 个 Sub DAG Entity 和 aggregate 节点的导入声明。

**Files**:
- Modify: `extensions/uzi-skill/manifest.yaml`

**Requirements**:
- 在 `imports.entities` 添加 3 个 Sub DAG YAML 路径
- 在 `imports.entities` 添加 aggregate 节点 YAML 路径
- 保持原有所有节点、trigger、resource 的导入声明不变

#### Checks

- [x] C11 验证 manifest imports 包含 Sub DAG
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "UZI-Skill workflow extension imports" / Scenario "Manifest imports 主 DAG 和 Sub DAG"
  - Evidence: `extensions/uzi-skill/manifest.yaml`
  - Expect: `imports.entities` 包含 `entities/dags/uzi-data-collection.yaml`, `entities/dags/uzi-scoring-synthesis.yaml`, `entities/dags/uzi-rendering.yaml` 和 `entities/nodes/uzi-aggregate-collection-results.yaml`

### Task 6: 端到端集成测试

**Goal**: 验证重构后的主 DAG 和 Sub DAG 能够正常执行，运行时行为与原扁平化结构一致。

**Files**:
- Test: `tests/integration/test_uzi_skill_subdag.py`

**Requirements**:
- 主 DAG 能够成功加载并通过拓扑验证
- Sub DAG 嵌套深度验证通过（2 层，在 max_dag_depth=3 限制内）
- 手动触发主 DAG 运行，所有 Sub DAG 正常执行
- aggregate 节点正确聚合所有 fetch 和 autofill 输出
- 最终 assemble_report 输出与原结构一致

#### Checks

- [x] C12 验证 Sub DAG 嵌套深度
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "DAG 拓扑声明" / Scenario "Sub DAG 嵌套深度验证"
  - Command: `cd /home/yunxin/Documents/Code/tools/Edera && python -c "from edera_core.dag.loader import validate_sub_dag_nesting; from edera_core.config.entities import EntityStore; store = EntityStore(); dags = {d.id.split(':')[1]: d for d in store.query('dag')}; validate_sub_dag_nesting(dags, 3); print('Validation passed')"`
  - Expect: 输出 "Validation passed"，无异常抛出

- [x] C13 验证主 DAG 可执行
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "DAG 拓扑声明" / Scenario "主 DAG 配置可加载"
  - Command: `cd /home/yunxin/Documents/Code/tools/Edera && edera dag run uzi-skill-analysis --input '{"ticker": "300470.SZ"}' --dry-run`
  - Expect: dry-run 成功，输出执行计划包含 5 个主 DAG 节点和 3 个 Sub DAG 嵌套执行

- [x] C14 验证 aggregate 节点输出格式
  - Verifies: `specs/uzi-subdag-structure/spec.md` / Requirement "aggregate-collection-results 节点" / Scenario "aggregate 节点输出格式"
  - Command: `cd /home/yunxin/Documents/Code/tools/Edera && python -c "from edera_core.config.entities import EntityStore; store = EntityStore(); node = store.resolve('node:uzi-aggregate-collection-results'); print(f'Node type: {node.attributes.get(\"type\")}'); assert node.attributes.get('type') in ['function', 'agent']"`
  - Expect: 输出 aggregate 节点类型为 function 或 agent

## Remediation

- [x] [code_fix] data-collection 数据流按 spec 改为 `0_basic` 直接 fan-out 到 `autofill_mx` 和 `autofill_playwright`。
- [x] [code_fix] rendering 多 sink 输出改为仅包含成功 sink payload，并覆盖 optional renderer 失败场景。
