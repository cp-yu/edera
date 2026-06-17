## Context

`DagRunner.run` 当前以 `initial_payload`（第 3 个位置参数）作为 DAG 运行入口负载。经探索确认，该参数承载三件事：

1. **顶层入口默认**（`dag_controller.py:673,770`）：`payload if payload is not None else {"entities": _source_entity_refs(config)}` —— 无 spec 记录。
2. **源节点二级兜底**（`runner.py:921`）：`default_entity ?? initial_payload` —— spec 仅记录到 `default_entity` 层。
3. **子 DAG payload 直通**（`runner.py:786`）：`node_input.payload` 作为子 DAG `initial_payload`，使子 DAG 源节点在无 InputMapping 时透传父 payload —— 有 spec 契约（`uzi-subdag-structure`、`sub-dag-execution`）但属历史重构遗留。

同时对外三边界（proto、Web body、CLI flags）各自维护一条独立 payload 通路，与既有的 `source_shared_inputs` / `node_inputs` / `append_nodes` 三元组并存，输入模型割裂。

探索还发现一个**寄生耦合**：`payload` 同时被 `_run_entity_refs` 用于决定 `preload_for_dag` 的实体预加载范围。本次连带清理此耦合。

## Goals / Non-Goals

**Goals:**
- 消除 `initial_payload` 概念，DAG 输入（顶层与子 DAG 一致）统一为 `source_shared_inputs` + `node_inputs` + `append_nodes` 三元组。
- 删除 proto / Web / CLI 三条旧 payload 通路，统一到三元组。
- 源节点优先级定为 `source_shared_inputs > default_entity > None`。
- 实体预加载范围改为完全由节点配置推导，不再由运行时 payload 声明。

**Non-Goals:**
- 不改动 `preload_for_dag` 的缓存机制与关系连带预加载逻辑本身。
- 不扩展 InputMapping entity 引用进入预加载范围（保持运行时 `entity_store.resolve` 现查）。
- 不引入过渡兼容层（开发阶段，终点删除）。

## Decisions

### Decision 1: `initial_payload` 整体删除，不保留别名

**选择**：删除 `DagRunner.run` 的 `initial_payload` 形参与全部透传。

**理由**：保留别名会延续"两个概念并存"的割裂；开发阶段无历史负担，终点删除最干净。

**替代方案（拒绝）**：仅做 runner 内部清理（`_input_payload` 收窄），保留对外 `initial_payload` 参数。拒绝 —— 治标不治本，对外三边界仍割裂。

### Decision 2: 源节点优先级 `source_shared_inputs > default_entity > None`

**选择**：删除 `?? initial_payload` 兜底；无显式输入时源节点收 `None`。

**理由**：`source_shared_inputs`（显式注入）与 `default_entity`（实例声明）已覆盖所有"源节点需要数据"的场景；`initial_payload` 这层兜底是冗余保险。无输入即 `None` 是最诚实的语义。

**影响**：顶层不再自动注入 `{"entities": _source_entity_refs(config)}`；用户需显式经 `source_shared_inputs` 提供入口数据，或源节点声明 `default_entity`。

### Decision 3: 子 DAG payload 直通消除

**选择**：子 DAG 递归调用（`runner.py:782-789`）不再传 `node_input.payload` 作 `initial_payload`；子源节点仅经 InputMapping `shared` 映射或自身 `default_entity` 取值。

**理由**：直通是历史遗留。统一后子 DAG 与顶层输入语义完全一致，模型更纯。

**替代方案（拒绝）**：默认 InputMapping = 透传 payload，使其落入 `source_shared_inputs`。拒绝 —— 用"隐式默认 mapping"掩盖直通语义，仍是不显式耦合。

### Decision 4: 预加载范围由节点配置推导（删除 payload 分支）

**选择**：`_run_entity_refs` 删除 `payload is None` / `payload={"entities":[...]}` 两个分支（`dag_controller.py:1178-1183`），预加载 refs 仅来自 `instance.resource` / `config["entities"]` / `config["source"]`。

**理由**：删 `payload` 参数后，`_run_entity_refs` 失去数据来源；节点配置已能静态表达"本次运行引用哪些实体"，无需运行时声明。预加载范围匹配实际使用，语义更准确。

**影响**：未被节点引用的 source 实体不再预加载（当前 `payload=None` 会预加载所有 rss/web/api-source）。

### Decision 5: 对外三边界终点删除，无兼容层

**选择**：proto 字段、Web body 字段、CLI flags 全部删除并统一到三元组，不保留废弃过渡。

**理由**：开发阶段，调用方可同步修改；过渡兼容层会增加复杂度且最终仍需清理。

## Risks / Trade-offs

- **预加载范围收窄**：未被节点引用的 source 实体不再预加载，节点查这些实体会走数据库而非内存缓存。→ 可观察变化，spec 记录；若有节点依赖"隐式预加载所有 source"，需声明 `default_entity` 或 `config.entities`。
- **子 DAG `missing_path` 行为变化**：`test_subdag_input_mapping.py::...missing_path` 当前断言子源节点直通父 payload，删除后收 `None`。→ 真实行为变化，更新断言（用户已确认接受）。
- **Web/CLI breaking change**：前端与脚本调用方需同步。→ 开发阶段可接受；`dag-workbench-ui` 等同步更新。
- **trigger payload 语义收窄**：trigger 产出数据明确为"源节点输入"（`source_shared_inputs`），不再兼具预加载声明职责。→ 需逐个 trigger 类型核实产出语义。
- **proto 重新生成**：删字段需重新生成 `edera_pb2.py` 与 stubs。→ 走现有工具链，注意 stubs 引用更新。

## Migration Plan

无在线迁移（开发阶段）。实施顺序建议：

1. runner 核心（`run` 签名、`_get_node_input`、`_input_payload` 收窄、透传清理、子 DAG 递归）。
2. controller（签名、`_run_entity_refs` 分支删除）。
3. proto 删字段 + 重新生成 → server/grpc_client 跟随。
4. Web routes + CLI flags。
5. trigger 回调签名。
6. 测试签名与断言更新。
7. specs 更新。

## Open Questions

- trigger 各类型（cron/event）产出的 payload 语义，需在实施时逐个核实其归属 `source_shared_inputs` 是否正确，避免 trigger 原本依赖的预加载声明丢失。
