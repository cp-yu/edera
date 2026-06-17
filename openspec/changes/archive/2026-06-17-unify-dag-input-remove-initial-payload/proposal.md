<!--
路由决策记录：
- 输入来源：explore 生成的 Design Summary（unify-dag-input-remove-initial-payload），存在
- 决策：proceed，使用 Design Summary 作为主输入
- 多子系统判定：否（聚焦 DAG 输入模型单一子系统；实体预加载作为连带修改，不构成独立子系统）
-->

## Why

`DagRunner.run` 的 `initial_payload` 是历史遗留参数，其"源节点输入兜底"职责已被 `source_shared_inputs` / `default_entity` 覆盖，退化为冗余兜底层与子 DAG payload 直通通道。同时对外三个边界（proto `inputs_json`/`payload_json`、Web body 解包、CLI flags）各自维护一条独立的 payload 通路，与统一的输入三元组（`source_shared_inputs` + `node_inputs` + `append_nodes`）并存，造成输入模型割裂。开发阶段无历史负担，需重构干净。

## What Changes

- **BREAKING** 删除 `DagRunner.run` 的 `initial_payload` 位置参数；源节点输入统一为 `source_shared_inputs` + `node_inputs` + `append_nodes` 三元组。
- **BREAKING** 源节点输入解析优先级从 `source_shared_inputs > default_entity > initial_payload` 改为 `source_shared_inputs > default_entity > None`；无显式输入时源节点收 `None`。
- **BREAKING** 删除子 DAG payload 直通：子 DAG 源节点不再透传父节点 payload，仅经 InputMapping 的 `shared` 映射或自身 `default_entity` 取值。
- **BREAKING** 删除 proto `DagRunRequest.inputs_json` 与 `DagRetryRequest.payload_json` 字段；统一到 `source_shared_inputs_json` / `node_inputs_json` / `append_nodes_json`。
- **BREAKING** 删除 Web `/api/dags/{name}/run` 与 `/api/dags/{name}/retry` 的 `body["inputs"]` / `body["payload"]` / 裸 body 解包；统一到 `sourceSharedInputs` / `nodeInputs` / `appendNodes`。
- **BREAKING** 删除 CLI `_dag_run_payload` 及 `--input` / `--inputs` / `--payload` 三个 flag；统一到 `--source-shared-inputs` / `--node-inputs` / `--append-nodes`。
- **BREAKING** 删除 controller `start_run` / `retry_node` 等签名的 `payload` 参数；trigger 产出数据改注入 `source_shared_inputs`。
- 连带修改：实体预加载范围 `_run_entity_refs` 删除 payload 分支，改为完全由节点配置推导（`instance.resource` / `config["entities"]` / `config["source"]`）；未被节点引用的 source 实体不再预加载。

## Capabilities

### New Capabilities

（无新增能力；本次为既有 DAG 输入模型的统一与清理。）

### Modified Capabilities

- `dag-input-parameters`：删除旧 payload/inputs 输入通路，记录 `source_shared_inputs` / `node_inputs` / `append_nodes` 为唯一运行时输入契约。
- `runtime-temporary-input`：节点输入三步解析逻辑改为 `source_shared_inputs > default_entity > None`，删除 `initial_payload` 兜底层；记录无显式输入时源节点为 `None` 的可观察行为。
- `sub-dag-execution`：Source/Sink 接口映射删除"父输入作为 initial_payload 传递"语义，改为经 InputMapping 映射到达子源节点。
- `uzi-subdag-structure`：Sub DAG 结构中 ticker/父数据到达子源节点的契约改用 `source_shared_inputs` 表达。
- `uzi-skill-dag-instance`：`ticker 通过 initial_payload 传入` 改为通过 `sourceSharedInputs` 传入。

注：`dag-run-control` 的 retry/resume Requirement 不记录 payload 参数（payload 仅是实现细节），故无需 delta spec；retry 路径的临时输入行为由 `runtime-temporary-input` 覆盖。

## Impact

- **核心代码**：`packages/core/src/edera_core/dag/runner.py`（`run` 签名、`_get_node_input`、`_input_payload` 收窄、13 处透传、子 DAG 递归调用点）；`dag_controller.py`（控制面签名、`_run_entity_refs` 预加载分支）；`node/executor.py`（核实无孤儿引用）。
- **对外边界**：`proto/edera.proto`（删字段、重新生成 `edera_pb2.py`）；`server.py`（Run/Retry handler）；`grpc_client.py`（`dag_run`/`dag_retry`）；`web/routes.py`（两个端点）；`cli.py`（flag 与 `_dag_run_payload`）；`trigger.py`（run_dag 回调签名）。
- **测试**：`test_node_input_resolution.py`、`test_subdag_input_mapping.py`、`test_dag_runner.py`、`test_per_dag.py`、`test_web_routes.py`、`test_grpc_control_services.py` 等调用签名与断言更新；`test_subdag_input_mapping.py::...missing_path` 断言从"直通父 payload"改为 `None`（真实行为变化）。
- **实体预加载行为变化**：未被节点引用的 source 实体不再预加载，语义更准确但是可观察变化。
- **符号注意**：`extensions/uzi-skill/adapter.py` 的 `_input_payload` 是无关的 handler 侧辅助函数，全局重命名须排除。
