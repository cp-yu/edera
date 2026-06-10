### Task 1: Node output payload export

**Goal**: 实现 `edera node output export`，让 agent 可将指定 run/node 的业务 output payload 写入文件。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/unit/test_cli.py`

**Requirements**:
- 在 `edera node output` 下支持 `export --run-id <run_id> --node <node_id> --out <path>`。
- 导出内容只来自业务 output，不包含 execution logs。
- 缺少 `--out` 时返回非零状态。
- stdout 返回导出路径和条目摘要。

#### Checks

- [x] C1 验证 node output export 写入 payload 文件
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Agent payload 显式导出 CLI" / Scenario "导出指定节点 payload"
  - Command: `uv run pytest tests/core/unit/test_cli.py -q`
  - Expect: 新增测试证明 `edera node output export --run-id run-1 --node reader --out payload.json` 写出业务 output payload。

- [x] C2 验证导出不包含 execution logs
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Agent payload 显式导出 CLI" / Scenario "导出不包含 execution logs"
  - Command: `uv run pytest tests/core/unit/test_cli.py -q`
  - Expect: 新增测试证明 export 路径不调用 `query_node_logs`，文件内容不包含日志 payload。

- [x] C3 验证缺少导出目标失败
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Agent payload 显式导出 CLI" / Scenario "缺少导出目标"
  - Command: `uv run pytest tests/core/unit/test_cli.py -q`
  - Expect: 新增测试证明缺少 `--out` 时 CLI 返回非零状态并提示参数错误。

### Task 2: Dag retry inputs and source repair command

**Goal**: 实现 `edera dag retry` 临时输入参数，并为 `SystemService.CreateRepairTask` 增加 CLI 入口。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/unit/test_cli.py`

**Requirements**:
- `edera dag retry` 支持 `--source-shared-inputs`、`--node-inputs`、`--append-nodes`。
- retry 参数 JSON 非法时返回非零状态。
- `edera system repair-source <source_name>` 调用 source repair task 创建能力。
- server 返回 FAILED_PRECONDITION 或 NOT_FOUND 时，CLI 保持非零状态和错误输出。

#### Checks

- [x] C4 验证 dag retry 传递临时输入
  - Verifies: `specs/multi-node-retry/spec.md` / Requirement "CLI retry 临时输入参数" / Scenario "retry 传递 sourceSharedInputs"
  - Command: `uv run pytest tests/core/unit/test_cli.py -q`
  - Expect: 新增测试证明 retry 请求收到 `source_shared_inputs`。

- [x] C5 验证 dag retry 传递 nodeInputs 和 appendNodes
  - Verifies: `specs/multi-node-retry/spec.md` / Requirement "CLI retry 临时输入参数" / Scenario "retry 传递 nodeInputs 和 appendNodes"
  - Command: `uv run pytest tests/core/unit/test_cli.py -q`
  - Expect: 新增测试证明 retry 请求收到 `node_inputs` 和 `append_nodes`。

- [x] C6 验证 dag retry 非法 JSON 失败
  - Verifies: `specs/multi-node-retry/spec.md` / Requirement "CLI retry 临时输入参数" / Scenario "retry 临时输入 JSON 非法"
  - Command: `uv run pytest tests/core/unit/test_cli.py -q`
  - Expect: 新增测试证明非法 JSON 返回非零状态。

- [x] C7 验证 source repair task CLI
  - Verifies: `specs/grpc-control-services/spec.md` / Requirement "source repair task CLI 入口" / Scenario "为 escalated source 创建 repair task"
  - Command: `uv run pytest tests/core/unit/test_cli.py -q`
  - Expect: 新增测试证明 `edera system repair-source rss-main` 调用 repair task client 方法并输出 task 摘要。

- [x] C8 验证 source repair task 错误传播
  - Verifies: `specs/grpc-control-services/spec.md` / Requirement "source repair task CLI 入口" / Scenario "source 未 escalated" / Scenario "source 不存在"
  - Command: `uv run pytest tests/core/unit/test_cli.py -q`
  - Expect: 新增测试证明 server 错误会导致 CLI 非零退出并输出错误详情。

### Task 3: Workflow extension export completeness

**Goal**: 收紧 `edera extension export` 的 workflow extension 打包行为，保证 providers 和 libraries 可重新导入。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/unit/test_cli_extension.py`

**Requirements**:
- 导出包为每个 provider 写入 `_providers/<provider>/manifest.yaml`。
- 导出包包含 provider handler 代码。
- libraries 从已安装 handler 根目录的 `_libs` 来源复制到 `_lib/`。
- 缺失 provider 或 library 代码时返回 warning，不阻断其余可导出内容。

#### Checks

- [x] C9 验证 provider manifest 被导出
  - Verifies: `specs/extension-cli-commands/spec.md` / Requirement "workflow extension export 完整性" / Scenario "provider manifest 被导出"
  - Command: `uv run pytest tests/core/unit/test_cli_extension.py -q`
  - Expect: 新增测试证明 tar.gz 中包含 `_providers/<provider>/manifest.yaml` 和 provider handler 代码。

- [x] C10 验证 library 从 _libs 导出
  - Verifies: `specs/extension-cli-commands/spec.md` / Requirement "workflow extension export 完整性" / Scenario "library 从 _libs 导出"
  - Command: `uv run pytest tests/core/unit/test_cli_extension.py -q`
  - Expect: 新增测试证明 tar.gz 中包含 `_lib/<library>/...`，来源为已安装 handler 根目录下 `_libs`。

- [x] C11 验证缺失 provider 或 library 输出 warning
  - Verifies: `specs/extension-cli-commands/spec.md` / Requirement "workflow extension export 完整性" / Scenario "缺失 provider 或 library 代码"
  - Command: `uv run pytest tests/core/unit/test_cli_extension.py -q`
  - Expect: 新增测试证明缺失代码不会阻断导出，其余文件存在且 stdout 包含 warning。
