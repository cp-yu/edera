### Task 1: runner 核心消除 initial_payload

**Goal**: 删除 `DagRunner.run` 的 `initial_payload` 形参与全部透传，源节点优先级定为 `source_shared_inputs > default_entity > None`，子 DAG 递归不再透传父 payload。

**Files**:
- Modify: `packages/core/src/edera_core/dag/runner.py`
- Test: `tests/core/integration/test_node_input_resolution.py`
- Test: `tests/core/integration/test_dag_runner.py`
- Test: `tests/core/integration/test_subdag_input_mapping.py`
- Test: `packages/core/tests/test_dag_runner.py`

**Requirements**:
- `run()` 签名删除 `initial_payload` 位置参数；输入仅经 `source_shared_inputs` / `node_inputs` / `append_nodes`。
- `_get_node_input` 源节点分支改为 `source_shared_inputs > default_entity > None`（删除 `?? initial_payload`）。
- `_input_payload` 收窄：去掉死的 `initial_payload` 参数并重命名为 `_collect_upstream_payloads`；删除 `_start_node` / `_start_ready_nodes` / `_run_node` 中 13 处 `initial_payload` 透传。
- 子 DAG 递归调用（`_execute_sub_dag` 内 `runner.run(...)`）不再传 `node_input.payload` 作 `initial_payload`。
- 全局重命名排除 `extensions/uzi-skill/adapter.py` 的无关 `_input_payload`。

#### Checks

- [x] C1 验证源节点优先级
  - Verifies: `specs/runtime-temporary-input/spec.md` / Requirement "节点输入三步解析逻辑" / Scenario "Source 节点无临时输入且无默认配置"
  - Command: `pytest tests/core/integration/test_node_input_resolution.py -k source`
  - Expect: source 节点无 sourceSharedInputs 且无 default_entity 时输入为 None/空

- [x] C2 验证子 DAG 不再直通父 payload
  - Verifies: `specs/sub-dag-execution/spec.md` / Requirement "Source/Sink 接口映射" / Scenario "上游输出映射到子 DAG source"
  - Command: `pytest tests/core/integration/test_subdag_input_mapping.py::test_input_mapping_entity_node_string_mapping_missing_path_skips_node_input`
  - Expect: 子 source 节点未声明 mapping/default_entity 时输入为 None（断言已从直通父 payload 改为 None）

- [x] C3 验证 runner 内无 initial_payload 残留
  - Verifies: `specs/dag-input-parameters/spec.md` / Requirement "运行时参数传递" / Scenario "无入口 payload 参数"
  - Command: `grep -n "initial_payload" packages/core/src/edera_core/dag/runner.py`
  - Expect: 无匹配（adapter.py 的无关 _input_payload 不在 runner.py）

### Task 2: controller 删除 payload 参数与预加载分支

**Goal**: 控制面 `start_run` / `retry_node` / `run_now` 等删除 `payload` 参数；`_run_entity_refs` 删除 payload 分支，预加载范围完全由节点配置推导。

**Files**:
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Test: `packages/core/tests/test_web_routes.py`
- Test: `packages/core/tests/test_grpc_control_services.py`

**Requirements**:
- 删除 `start_run` / `retry_node` / `run_now` / `run_node_trigger` 等签名中的 `payload` 参数。
- 删除两处 `payload if payload is not None else {"entities": _source_entity_refs(config)}`（run 与 single-node 路径）。
- `_run_entity_refs` 删除 `payload is None` / `payload={"entities":[...]}` 两个分支，预加载 refs 仅来自 `instance.resource` / `config["entities"]` / `config["source"]`。
- 若 `_source_entity_refs` 无其他调用方则删除。

#### Checks

- [x] C4 验证 controller 无 payload 参数
  - Verifies: `specs/dag-input-parameters/spec.md` / Requirement "运行时参数传递" / Scenario "无入口 payload 参数"
  - Command: `grep -n "payload" packages/core/src/edera_core/dag_controller.py`
  - Expect: 仅剩预加载内部逻辑或无 payload 参数透传（无 `payload if payload`、无 `{"entities": _source_entity_refs(config)}`）

- [x] C5 验证预加载由节点配置推导
  - Preserves: `openspec/specs/runtime-input-context/spec.md` / Requirement "Source recovery runtime facts"
  - Command: `pytest packages/core/tests/test_grpc_control_services.py -k preload`
  - Expect: 未被节点引用的 source 实体不再预加载；被节点 resource/config.entities/config.source 引用的实体仍预加载

### Task 3: proto 删字段并重新生成

**Goal**: 删除 `DagRunRequest.inputs_json` 与 `DagRetryRequest.payload_json`，统一到三元组字段，重新生成绑定。

**Files**:
- Modify: `proto/edera.proto`
- Modify: `packages/core/src/edera_core/proto/edera_pb2.py`
- Modify: `packages/core/src/edera_core/proto/*_pb2_grpc.py`

**Requirements**:
- `DagRunRequest` 删除 `inputs_json`；`DagRetryRequest` 删除 `payload_json`。
- 保留 `source_shared_inputs_json` / `node_inputs_json` / `append_nodes_json`。
- 重新生成 `edera_pb2.py` 与 gRPC stubs。

#### Checks

- [x] C6 验证 proto 字段删除
  - Verifies: `specs/dag-input-parameters/spec.md` / Requirement "运行时参数传递" / Scenario "无入口 payload 参数"
  - Command: `grep -n "inputs_json\|payload_json" proto/edera.proto`
  - Expect: 仅剩 `source_shared_inputs_json` / `node_inputs_json` / `append_nodes_json`，无 `inputs_json`/`payload_json`

- [x] C7 验证生成的绑定与 proto 一致
  - Verifies: `specs/dag-input-parameters/spec.md` / Requirement "运行时参数传递" / Scenario "HTTP API 传递临时输入"
  - Command: `python -c "from edera_core.proto import edera_pb2; assert not hasattr(edera_pb2.DagRunRequest(), 'inputs_json')"`
  - Expect: 断言通过（字段不存在）

### Task 4: gRPC handler 与 client 跟随

**Goal**: `server.py` 的 Run/Retry handler 与 `grpc_client.py` 的 `dag_run`/`dag_retry` 删除 payload 解析与参数。

**Files**:
- Modify: `packages/core/src/edera_core/server.py`
- Modify: `packages/core/src/edera_core/grpc_client.py`
- Test: `packages/core/tests/test_grpc_control_services.py`

**Requirements**:
- `_DagService.Run` / `_DagService.Retry` 删除 `inputs_json` / `payload_json` 解析与对应 `payload` 传参。
- `grpc_client.dag_run` / `grpc_client.dag_retry` 删除 `payload` 参数，仅传三元组字段。

#### Checks

- [x] C8 验证 server handler 无 payload 解析
  - Verifies: `specs/dag-input-parameters/spec.md` / Requirement "运行时参数传递" / Scenario "HTTP API 传递临时输入"
  - Command: `grep -n "inputs_json\|payload_json\|payload," packages/core/src/edera_core/server.py`
  - Expect: 无 `inputs_json`/`payload_json` 解析，无 payload 位置传参

- [x] C9 验证 client 无 payload 参数
  - Verifies: `specs/dag-input-parameters/spec.md` / Requirement "运行时参数传递" / Scenario "CLI 传递 sourceSharedInputs"
  - Command: `grep -n "def dag_run\|def dag_retry\|payload" packages/core/src/edera_core/grpc_client.py`
  - Expect: `dag_run`/`dag_retry` 签名无 payload 参数

### Task 5: Web routes 与 CLI flags 统一到三元组

**Goal**: Web 端点删除 body payload 解包，CLI 删除 `_dag_run_payload` 与三个 flag，统一到三元组。

**Files**:
- Modify: `packages/core/src/edera_core/web/routes.py`
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/integration/test_per_dag.py`

**Requirements**:
- `api_dag_run` 删除 `body["inputs"]` / `body["payload"]` / 裸 body 解包，仅认 `sourceSharedInputs` / `nodeInputs` / `appendNodes`。
- `api_dag_retry` 删除 `body["payload"]`。
- CLI 删除 `_dag_run_payload` 及 `--input` / `--inputs` / `--payload` 三个 flag；输入仅经 `--source-shared-inputs` / `--node-inputs` / `--append-nodes`。

#### Checks

- [x] C10 验证 Web body 仅认三元组
  - Verifies: `specs/runtime-temporary-input/spec.md` / Requirement "DAG run API 临时输入参数" / Scenario "运行 DAG 时指定 sourceSharedInputs"
  - Command: `pytest tests/core/integration/test_per_dag.py -k "dag_run_api or run_with_temp"`
  - Expect: body 解包断言改为三元组字段，裸 body/inputs/payload 不再被接受为 payload

- [x] C11 验证 CLI flags 删除
  - Verifies: `specs/dag-input-parameters/spec.md` / Requirement "运行时参数传递" / Scenario "CLI 传递 sourceSharedInputs"
  - Command: `grep -n "_dag_run_payload\|--input\b\|--inputs\|--payload" packages/core/src/edera_core/cli.py`
  - Expect: 无 `_dag_run_payload`、无 `--input`/`--inputs`/`--payload` flag 定义

### Task 6: trigger 回调签名与全量测试回归

**Goal**: trigger `run_dag` 回调的 payload 改注入 `source_shared_inputs`；全量回归确认无孤儿引用与行为符合 spec。

**Files**:
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `packages/core/src/edera_core/trigger.py`
- Test: `tests/core/integration/test_per_dag.py`
- Test: `tests/core/integration/test_node_input_resolution.py`

**Requirements**:
- `run_dag=lambda name, payload, source` 的 payload 改注入 `source_shared_inputs`（trigger 产出数据 = 源节点输入）。
- 核实 cron/event 各 trigger 类型产出语义归属 `source_shared_inputs` 正确，不丢失原有预加载声明依赖。

#### Checks

- [x] C12 验证 trigger 注入 source_shared_inputs
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "ticker 通过 initial_payload 传入" / Scenario "ticker 经 preflight 输出传递到 Sub DAG"
  - Command: `pytest tests/core/integration/test_per_dag.py -k trigger`
  - Expect: trigger 触发的运行中 ticker 经 sourceSharedInputs 到达 source 节点

- [x] C13 全量回归
  - Preserves: `openspec/specs/runtime-temporary-input/spec.md` / Requirement "浅合并语义" / Scenario "Dict 浅合并"
  - Command: `pytest tests/core/integration packages/core/tests`
  - Expect: 全部通过；无 initial_payload/payload 相关孤儿引用
