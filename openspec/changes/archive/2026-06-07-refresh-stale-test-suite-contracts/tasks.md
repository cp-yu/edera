### Task 1: Clean stale OpenSpec registry contracts

**Goal**: 清理直接冲突的 registry / snapshot / import 规约文本，使 specs 和当前架构一致。

**Files**:
- Modify: `openspec/specs/core-bootstrap/spec.md`
- Modify: `openspec/specs/node-executor/spec.md`
- Modify: `openspec/specs/edera-cli/spec.md`
- Modify: `openspec/specs/edera-server-grpc/spec.md`
- Test: `openspec/changes/refresh-stale-test-suite-contracts/specs/core-bootstrap/spec.md`

**Requirements**:
- `core-bootstrap` 不再描述构建 `HandlerRegistry` 或 `EntityTypeRegistry`。
- `node-executor` 不再描述通过 handler registry 执行 Node Entity。
- `edera-cli` 明确 `edera entity import --file` 走 `GrpcClient.entity_import`。
- `edera-server-grpc` 保留 bootstrap fallback 作为独立 server 契约。

#### Checks

- [x] C1 Verify OpenSpec registry cleanup
  - Verifies: `specs/core-bootstrap/spec.md` / Requirement "Handler Registry 构建" / Scenario "注册 handler metadata"
  - Command: `openspec validate refresh-stale-test-suite-contracts --type change --json`
  - Expect: change validation reports no blocking errors for modified delta specs

- [x] C2 Verify node executor spec cleanup
  - Verifies: `specs/node-executor/spec.md` / Requirement "Node 作为 Entity 执行" / Scenario "加载 Node Entity 并执行"
  - Evidence: `openspec/specs/node-executor/spec.md`
  - Expect: the archived target spec no longer requires Node Entity execution through handler registry after archive

### Task 2: Refresh core architecture unit tests

**Goal**: 更新 `test_core_architecture_overhaul.py` 中 stale runtime tests，使其使用当前 snapshot 和 service contracts。

**Files**:
- Modify: `tests/core/unit/test_core_architecture_overhaul.py`
- Test: `tests/core/unit/test_core_architecture_overhaul.py`
- Test: `packages/core/tests/test_node_executor.py`
- Test: `packages/core/tests/test_grpc_control_services.py`

**Requirements**:
- `NodeExecutor` tests build explicit `DagExecutionSnapshot` or use existing snapshot helper.
- `RuntimeControlSnapshot` tests stop expecting `.config`.
- `_NodeService` fakes implement `active_dag_for_node`, `dag_for_run_node`, `stop_current`, and `resume_node`.
- No compatibility shim is added to application code for old test call sites.

#### Checks

- [x] C3 Verify NodeExecutor snapshot tests
  - Verifies: `specs/node-executor/spec.md` / Requirement "Node 作为 Entity 执行" / Scenario "加载 Node Entity 并执行"
  - Command: `uv run pytest tests/core/unit/test_core_architecture_overhaul.py packages/core/tests/test_node_executor.py`
  - Expect: tests pass without constructing `NodeExecutor` through old `handlers=` or missing-`snapshot` paths

- [x] C4 Verify current node service contract tests
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "Bootstrap 端口硬绑 localhost" / Scenario "Bootstrap 状态文件"
  - Command: `uv run pytest tests/core/unit/test_core_architecture_overhaul.py packages/core/tests/test_grpc_control_services.py`
  - Expect: service-related tests pass with current controller fake methods

### Task 3: Refresh CLI entity tests

**Goal**: 将 CLI running-server entity tests 拆成纯 gRPC 路径验证和显式 import/seed 后实体可查验证。

**Files**:
- Modify: `tests/core/unit/test_cli.py`
- Test: `tests/core/unit/test_cli.py`

**Requirements**:
- Running-server query tests verify CLI gRPC behavior without relying on implicit `stock:TEST`.
- Explicit entity availability tests import or seed `stock:TEST` before asserting it is queryable.
- Entity import tests stub `entity_import`, not `entity_create`.
- Invalid YAML import remains rejected before opening gRPC client.

#### Checks

- [x] C5 Verify CLI entity import RPC path
  - Verifies: `specs/edera-cli/spec.md` / Requirement "Entity YAML 文件工作流" / Scenario "Import entity from YAML file"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: CLI import test proves `GrpcClient.entity_import` is called with the full Entity YAML document

- [x] C6 Verify explicit entity query path
  - Verifies: `specs/edera-cli/spec.md` / Requirement "Entity YAML 文件工作流" / Scenario "Imported entity is queryable"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: running-server tests distinguish pure gRPC query behavior from explicitly imported or seeded entity availability

### Task 4: Restore bootstrap fallback collection and verification

**Goal**: 重写 `test_bootstrap_fallback.py` 的 stale imports 和 fake controller，使 bootstrap fallback 测试重新参与回归。

**Files**:
- Modify: `tests/core/unit/test_bootstrap_fallback.py`
- Test: `tests/core/unit/test_bootstrap_fallback.py`
- Test: `tests/core/unit/test_web_bootstrap_discovery.py`
- Test: `packages/core/tests/test_bootstrap_with_existing_cert.py`

**Requirements**:
- Test file no longer imports removed `edera_core.registry` symbols.
- Fake controller matches current `Server` startup needs.
- Bootstrap fallback, status file, and port exhaustion behavior remain covered.
- BFF bootstrap discovery and existing-cert client init remain in final verification.

#### Checks

- [x] C7 Verify bootstrap fallback collection
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "Bootstrap 端口硬绑 localhost" / Scenario "Bootstrap 端口退避"
  - Command: `uv run pytest tests/core/unit/test_bootstrap_fallback.py`
  - Expect: file collects and bootstrap fallback tests pass without `edera_core.registry`

- [x] C8 Verify issue regression command
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "Bootstrap 端口硬绑 localhost" / Scenario "Bootstrap 状态文件"
  - Command: `uv run pytest tests/core/unit/test_core_architecture_overhaul.py tests/core/unit/test_web_bootstrap_discovery.py tests/core/unit/test_cli.py packages/core/tests/test_bootstrap_with_existing_cert.py tests/core/unit/test_bootstrap_fallback.py`
  - Expect: targeted regression command passes
