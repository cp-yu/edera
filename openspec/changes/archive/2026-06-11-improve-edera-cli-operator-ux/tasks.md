### Task 1: 输出模式和错误结构

**Goal**: 为 CLI 增加统一 `--output` 渲染和结构化 stderr。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/unit/test_cli.py`

**Requirements**:
- 顶层 parser 支持 `--output json|yaml|table`，默认保持 JSON。
- YAML 和 table 输出由 CLI 统一处理，不分散到各命令 dispatcher。
- 运行时错误写入结构化 JSON stderr，保留非零退出码和 server detail。

#### Checks

- [x] C1 Verify CLI 输出模式
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI 输出模式" / Scenario "默认 JSON 输出", "YAML 输出", "表格输出", "不支持的输出模式"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: CLI 针对同一 fake `GrpcClient` 结果可输出 JSON、YAML 和 table，无效 `--output` 返回非零状态

- [x] C2 Verify CLI 错误输出
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI 错误输出" / Scenario "缺少 server 地址", "gRPC 错误"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: stderr 为包含 `error`、`type`、`detail` 的 JSON object，并保留错误详情

### Task 2: watch 和 tail 运行观察

**Goal**: 为运行状态与日志命令增加有界可测的 watch/tail 行为。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/unit/test_cli.py`

**Requirements**:
- `dag status`、`dag runtime-status`、`system scheduler-status`、`source health` 支持 `--watch`、`--interval`、`--watch-count`。
- `node logs` 和 `source logs` 支持 `--tail`、`--interval`、`--watch-count`。
- tail 模式在单次会话内对日志项去重，只输出新增项。

#### Checks

- [x] C3 Verify CLI watch 模式
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI watch 模式" / Scenario "观察 DAG 运行状态", "观察 runtime graph 状态", "观察 scheduler 状态", "观察 source health"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: watch 命令按 `--watch-count` 调用对应 fake `GrpcClient` 方法指定次数并输出每轮结果

- [x] C4 Verify CLI tail 模式
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI tail 模式" / Scenario "跟随节点执行日志", "跟随 source execution logs"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: tail 命令重复查询日志，并只输出本次会话未见过的日志项

### Task 3: 控制面分页展示

**Goal**: 为控制面列表命令补齐统一 `--limit` 和 `--offset` 展示参数。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/unit/test_cli.py`

**Requirements**:
- `query briefing list`、`query advice list`、`query node-outputs`、`source logs` 支持 `--offset`，已有 `--limit` 继续传给 `GrpcClient`。
- `dag list`、`handler list` 支持 `--limit` 和 `--offset`，分页只影响 CLI 输出展示。
- offset 对顶层 list 或单一 list 字段生效，不改变 server 查询范围。

#### Checks

- [x] C5 Verify 控制面分页展示
  - Verifies: `specs/edera-cli-control-plane/spec.md` / Requirement "控制面分页展示" / Scenario "briefing 列表分页展示", "advice 列表分页展示", "node outputs 分页展示", "source logs 分页展示", "DAG 定义列表分页展示", "handler 列表分页展示"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: CLI 将 `limit` 传给 fake `GrpcClient`，并按 `offset` 裁剪 stdout 展示结果

### Task 4: OpenSpec 验证

**Goal**: 验证 change 制品结构和 CLI 测试覆盖。

**Files**:
- Modify: `openspec/changes/improve-edera-cli-operator-ux/proposal.md`
- Modify: `openspec/changes/improve-edera-cli-operator-ux/design.md`
- Modify: `openspec/changes/improve-edera-cli-operator-ux/specs/edera-cli/spec.md`
- Modify: `openspec/changes/improve-edera-cli-operator-ux/specs/edera-cli-control-plane/spec.md`
- Modify: `openspec/changes/improve-edera-cli-operator-ux/opsx-delta.yaml`
- Modify: `openspec/changes/improve-edera-cli-operator-ux/tasks.md`

**Requirements**:
- OpenSpec change 结构通过 validate。
- CLI 单元测试通过。

#### Checks

- [x] C6 Verify OpenSpec change
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI 输出模式" / Scenario "默认 JSON 输出"
  - Command: `openspec validate "improve-edera-cli-operator-ux" --type change --json`
  - Expect: change 结构验证通过或仅保留已说明的 warning
