### Task 1: Safe output retention policy

**Goal**: 让 output retention 只在完整 DAG 成功后触发，并将默认保留时间统一为 720 小时。

**Files**:
- Modify: `config/system.toml`
- Modify: `packages/core/src/edera_core/config/schema.py`
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Test: `tests/core/integration/test_per_dag.py`

**Requirements**:
- `retention_hours` 默认值改为 720。
- 当前项目 `config/system.toml` 使用 `retention_hours = 720`。
- 完整 DAG 成功完成后触发 retention cleanup。
- `failed` / `cancelled` run 不触发 retention cleanup。
- 单节点运行和 partial retry 不触发 retention cleanup。

#### Checks

- [x] C1 Verify successful full DAG run triggers retention
  - Verifies: `specs/entity-storage-tiers/spec.md` / Requirement "输出型 Entity retention 策略" / Scenario "成功完整 DAG run 触发 retention"
  - Command: `uv run pytest tests/core/integration/test_per_dag.py`
  - Expect: 覆盖完整 DAG 成功完成后执行 retention cleanup 的测试通过

- [x] C2 Verify failed or cancelled DAG run skips retention
  - Verifies: `specs/entity-storage-tiers/spec.md` / Requirement "输出型 Entity retention 策略" / Scenario "失败或取消 DAG run 不触发 retention"
  - Command: `uv run pytest tests/core/integration/test_per_dag.py`
  - Expect: 覆盖 `failed` / `cancelled` run 不执行 retention cleanup 的测试通过
