### Task 1: DAG、node type 和 handler 控制面命令

**Goal**: 在现有 argparse CLI 中接入 DAG 定义、node type 和 handler 管理命令。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/unit/test_cli.py`

**Requirements**:
- 扩展 `edera dag` 的定义层命令，不改变 `run/status/stop/retry/edit` 运行控制语义。
- 新增 `edera node-type` 命令组，映射 DB-backed node type 定义管理。
- 新增 `edera handler` 命令组，映射 handler 列表、读取和保存。

#### Checks

- [x] C1 Verify DAG 定义命令
  - Verifies: `specs/edera-cli-control-plane/spec.md` / Requirement "DAG 定义命令" / Scenario "列出 DAG 定义", "读取 DAG 定义", "创建空 DAG", "保存 DAG 定义文件", "导出 DAG 定义文件", "导入 DAG 定义文件", "查询 runtime graph 状态"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: DAG 定义命令通过 fake `GrpcClient` 调用正确方法并处理文件读写

- [x] C2 Verify node type 命令
  - Verifies: `specs/edera-cli-control-plane/spec.md` / Requirement "Node type 命令" / Scenario "列出 node types", "读取 node type", "创建 node type", "保存 node type", "删除 node type"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: `edera node-type` 子命令通过 fake `GrpcClient` 调用 GraphService 封装方法

- [x] C3 Verify handler 命令
  - Verifies: `specs/edera-cli-control-plane/spec.md` / Requirement "Handler 命令" / Scenario "列出 handlers", "读取 handler", "保存 handler"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: `edera handler` 子命令通过 fake `GrpcClient` 调用 handler 读写方法，`handler-validate` 离线入口保持可用

### Task 2: Config 控制面命令

**Goal**: 新增 `edera config` 命令组，覆盖 system config、通用 config 和 entity type config 的脚本化读写。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/unit/test_cli.py`

**Requirements**:
- `edera config list` 返回 server 可编辑 config 列表。
- `edera config system show/save` 读写 system config 文本。
- `edera config read/save` 读写指定 kind/name 的通用 config。
- `edera config entity-type` 覆盖 entity type config 的 list/show/create/save/delete。

#### Checks

- [x] C4 Verify config system 和通用 config 命令
  - Verifies: `specs/edera-cli-control-plane/spec.md` / Requirement "Config 命令" / Scenario "列出可编辑 config", "读取 system config", "保存 system config", "读取通用 config", "保存通用 config"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: config system 和通用 config 命令读取文件内容并调用对应 `GrpcClient` 方法

- [x] C5 Verify config entity-type 命令
  - Verifies: `specs/edera-cli-control-plane/spec.md` / Requirement "Config 命令" / Scenario "列出 entity type config", "读取 entity type config", "创建 entity type config", "保存 entity type config", "删除 entity type config"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: `edera config entity-type` 命令调用对应 ConfigService 封装方法并传递 `cascade`

### Task 3: Query 和 source 控制面命令

**Goal**: 新增 `edera query` 和 `edera source` 命令组，暴露 QueryService 读模型和 source 运维入口。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/unit/test_cli.py`

**Requirements**:
- `edera query` 覆盖 briefing、advice、results summary、node outputs、node history 和 child run 查询。
- `edera source` 覆盖 source health、source logs 和 source repair task。
- 所有命令继续输出 JSON，不引入 phase 3 的表格或 YAML 输出模式。

#### Checks

- [x] C6 Verify query 命令
  - Verifies: `specs/edera-cli-control-plane/spec.md` / Requirement "Query 命令" / Scenario "查询最新 briefing", "列出 briefings", "查询 briefing 详情", "列出 advices", "查询 advice 详情", "查询 results summary", "查询 node outputs", "查询 node history", "查询 child run"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: `edera query` 子命令把过滤参数传递给对应 QueryService `GrpcClient` 方法

- [x] C7 Verify source 命令
  - Verifies: `specs/edera-cli-control-plane/spec.md` / Requirement "Source 命令" / Scenario "查询 source health", "查询 source logs", "创建 source repair task"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: `edera source` 子命令调用 source health/logs 查询和 source repair task 创建方法

### Task 4: CLI 入口和变更验证

**Goal**: 更新 CLI 顶层入口列表，并验证 OpenSpec change 制品和 CLI 单元测试。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/unit/test_cli.py`
- Modify: `openspec/changes/expand-edera-cli-control-plane/specs/edera-cli/spec.md`
- Modify: `openspec/changes/expand-edera-cli-control-plane/specs/edera-cli-control-plane/spec.md`
- Modify: `openspec/changes/expand-edera-cli-control-plane/tasks.md`

**Requirements**:
- `edera --help` 展示新增顶层命令组。
- OpenSpec delta specs、OPSX delta 和 tasks 结构通过验证。

#### Checks

- [x] C8 Verify CLI binary 入口
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI binary 入口" / Scenario "CLI 可执行"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: `edera --help` 覆盖新增命令组，现有 console script 行为不回退

- [x] C9 Verify OpenSpec change
  - Verifies: `specs/edera-cli-control-plane/spec.md` / Requirement "DAG 定义命令" / Scenario "列出 DAG 定义"
  - Command: `openspec validate "expand-edera-cli-control-plane" --type change --json`
  - Expect: change 结构验证通过或仅保留已说明的 warning
