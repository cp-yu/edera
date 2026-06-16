### Task 1: 核查 sandbox_max_bytes 孤儿字段与 os-sandbox 配置 schema

**Goal**: 查清 `SystemConfig.sandbox_max_bytes`（schema.py:36）真实意图，据此定义 `DagConfig.os_sandbox` 配置段，避免命名/语义撞车。

**Files**:
- Modify: `packages/core/src/edera_core/config/schema.py`
- Test: `packages/core/tests/test_os_sandbox_config.py`

**Requirements**:
- 核查 `sandbox_max_bytes` 字段是否有任何消费者（grep 全代码库）；若确为孤儿，记录其推断意图，决定保留/移除/重命名
- 在 `DagConfig` 新增 `os_sandbox` 段：`enabled: bool`、`network.allowedDomains: list[str]`、`filesystem.{allowWrite,denyRead,denyWrite: list[str]}`
- 新增运行时覆盖类型（`OsSandboxOverride`），允许显式启用/关闭/改规则，仅作用于当次 run
- 配置校验：Linux 上 `allowWrite`/`denyRead` 含 glob 时拒绝（srt Linux 不支持 glob）

#### Checks

- [ ] C1 核查 sandbox_max_bytes 消费者
  - Preserves: `openspec/specs/node-executor/spec.md` / Requirement "Node 执行隔离" / Scenario "并发 Node 隔离"
  - Command: `grep -rn "sandbox_max_bytes" packages/ && uv run pytest packages/core/tests/test_os_sandbox_config.py -k max_bytes`
  - Expect: 全代码库无消费者则记录孤儿判定；os_sandbox 配置与该字段无命名冲突
- [ ] C2 os_sandbox 配置解析与覆盖合并
  - Verifies: `specs/dag-run-os-sandbox/spec.md` / Requirement "运行时临时覆盖沙箱配置" / Scenario "显式关闭已声明的沙箱"
  - Command: `uv run pytest packages/core/tests/test_os_sandbox_config.py -k override`
  - Expect: 覆盖 enabled=false 时合并结果为关闭，且原 DAG 声明配置对象未被修改
- [ ] C3 Linux glob 拒绝校验
  - Verifies: `specs/dag-run-os-sandbox/spec.md` / Requirement "沙箱文件系统约束" / Scenario "写入未授权路径被拒"
  - Command: `uv run pytest packages/core/tests/test_os_sandbox_config.py -k glob_reject`
  - Expect: Linux 平台下含 glob 的路径配置在校验阶段被拒绝并给出明确错误

### Task 2: srt 探测包装器与 .srt-settings.json 生成

**Goal**: 实现 `srt` CLI 探测、回退判定，以及把 `DagConfig.os_sandbox` 渲染为 `srt` 识别的 `.srt-settings.json`（含强制 deny 路径）。

**Files**:
- Create: `packages/core/src/edera_core/sandbox/srt_wrapper.py`
- Create: `packages/core/src/edera_core/sandbox/settings.py`
- Test: `packages/core/tests/test_srt_settings.py`

**Requirements**:
- `detect_srt()` 经 `shutil.which("srt")` 探测，返回路径或 None
- `build_srt_command(base_cmd, settings_path)`：srt 存在时返回 `["srt","exec","--settings",settings_path,*base_cmd]`，否则返回原 `base_cmd`
- `render_settings(os_sandbox, run_dir)`：生成 `.srt-settings.json`，写入 network/filesystem 规则，并叠加强制 deny 路径（`~/.ssh`、`.gitconfig`、`.bashrc`、`.zshrc`、`.claude/`、`.git/hooks/` 等）
- 默认 deny-all 网络、默认全盘禁写的 secure-by-default 语义

#### Checks

- [ ] C4 srt 缺失回退原命令
  - Verifies: `specs/dag-run-os-sandbox/spec.md` / Requirement "srt 缺失时回退" / Scenario "srt 不存在时回退"
  - Command: `PATH= uv run pytest packages/core/tests/test_srt_settings.py -k fallback`
  - Expect: srt 不在 PATH 时 `build_srt_command` 返回原命令，`detect_srt` 返回 None
- [ ] C5 settings 含强制 deny 路径
  - Verifies: `specs/dag-run-os-sandbox/spec.md` / Requirement "沙箱文件系统约束" / Scenario "强制 deny 路径不可写"
  - Command: `uv run pytest packages/core/tests/test_srt_settings.py -k mandatory_deny`
  - Expect: 生成的 settings JSON 的 denyWrite 包含全部强制 deny 路径，即使 allowWrite 覆盖该区域
- [ ] C6 默认 deny-all 网络
  - Verifies: `specs/dag-run-os-sandbox/spec.md` / Requirement "沙箱网络约束" / Scenario "空白名单等于无网络"
  - Command: `uv run pytest packages/core/tests/test_srt_settings.py -k deny_all_network`
  - Expect: allowedDomains 为空时生成的 settings 表示无网络访问

### Task 3: edera-dag-run 子进程 CLI 入口与 stdout 事件协议

**Goal**: 实现独立可执行的 `edera-dag-run` 入口，在沙箱内加载 config、跑指定 run_id 的 DagRunner，把 node-run/edge/lifecycle 事件以 NDJSON 打到 stdout。

**Files**:
- Create: `packages/core/src/edera_core/sandbox/dag_run_cli.py`
- Create: `packages/core/src/edera_core/sandbox/event_protocol.py`
- Modify: `packages/core/src/edera_core/dag/runner.py`（recorder 回调改为输出 NDJSON 事件）
- Test: `packages/core/tests/test_dag_run_cli.py`

**Requirements**:
- `edera-dag-run --run-id R` 入口：加载 config、构造 DagRunner、执行指定 run，不连接数据库
- 事件协议：`{"type":"node_done"|"edge_input"|"dag_lifecycle", ...}` NDJSON 行，含 `run_id`/`node`/`ok`/`payload`/`metadata` 等字段
- DagRunner 的 `recorder`/`edge_recorder`/`dag_lifecycle` 在子进程模式下输出事件而非写 DB
- 非 JSON 日志行原样写到 stdout 但不被事件解析器消费（归入运行日志）

#### Checks

- [ ] C7 节点完成事件输出
  - Verifies: `specs/dag-run-os-sandbox/spec.md` / Requirement "沙箱 run 的事件流回传" / Scenario "节点完成事件落库"
  - Command: `uv run pytest packages/core/tests/test_dag_run_cli.py -k node_done_event`
  - Expect: 子进程模式下每节点完成输出一条合法 node_done NDJSON 事件，字段齐全
- [ ] C8 非 JSON 日志不破坏事件流
  - Verifies: `specs/dag-run-os-sandbox/spec.md` / Requirement "沙箱 run 的事件流回传" / Scenario "非 JSON 日志行不破坏事件流"
  - Command: `uv run pytest packages/core/tests/test_dag_run_cli.py -k non_json_log`
  - Expect: handler 输出的非 JSON stdout 行被归入日志，事件解析器不中断、不丢节点记录
- [ ] C9 子进程不连数据库
  - Verifies: `specs/dag-run-os-sandbox/spec.md` / Requirement "沙箱 run 的事件流回传" / Scenario "节点完成事件落库"
  - Command: `grep -n "create_engine\|session.commit\|factory()" packages/core/src/edera_core/sandbox/dag_run_cli.py`
  - Expect: dag_run_cli.py 内无直接 DB 写入调用

### Task 4: 主进程事件流→DB 桥接与证书预签

**Goal**: 改造 `DagController._run`，os-sandbox 启用时改为 spawn `edera-dag-run` 子进程，主进程流式读 stdout 事件代写 DB；证书预签注入。

**Files**:
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `packages/core/src/edera_core/node/executor.py`（证书预签流程）
- Create: `packages/core/src/edera_core/sandbox/run_bridge.py`
- Test: `packages/core/tests/test_os_sandbox_run_bridge.py`

**Requirements**:
- `_run` 分支：os-sandbox 启用且 srt 存在 → spawn `srt exec edera-dag-run`；否则走原 in-process 路径
- `run_bridge`：解析 stdout NDJSON 事件，调用现有 `recorder`/`edge_recorder`/`dag_lifecycle` 落库（主进程独占 DB 写）
- run 启动前主进程预签 agent 证书，写入 run 临时目录，经环境变量注入子进程；`ca.key` 不传入子进程
- 回退路径行为与现状一致（回归保护）

#### Checks

- [ ] C10 事件代写 DB 等价非沙箱记录
  - Verifies: `specs/dag-run-os-sandbox/spec.md` / Requirement "沙箱 run 的事件流回传" / Scenario "节点完成事件落库"
  - Command: `uv run pytest packages/core/tests/test_os_sandbox_run_bridge.py -k event_to_db`
  - Expect: 桥接器把 node_done 事件写入 NodeRun/NodeOutput，记录结果与非沙箱 run 一致
- [ ] C11 回退路径行为不变
  - Preserves: `openspec/specs/dag-run-control/spec.md` / Requirement "Soft stop" / Scenario "Soft stop 不中断当前节点"
  - Command: `uv run pytest packages/core/tests/test_dag_runner.py packages/core/tests/test_node_executor.py`
  - Expect: 现有 DAG run 与 executor 测试全绿，回退路径无行为变化
- [ ] C12 私钥不进子进程环境
  - Verifies: `specs/dag-run-os-sandbox/spec.md` / Requirement "主进程独占证书签发" / Scenario "私钥不进沙箱"
  - Command: `uv run pytest packages/core/tests/test_os_sandbox_run_bridge.py -k cert_no_key_leak`
  - Expect: 传给子进程的环境变量与挂载包含证书 PEM 但不包含 `ca.key` 路径或内容

### Task 5: 沙箱 run 的 stop 信号通道

**Goal**: os-sandbox run 的 soft/hard stop 经子进程信号通道实现，语义等价主进程 `asyncio.Event`/`task.cancel()`。

**Files**:
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `packages/core/src/edera_core/sandbox/dag_run_cli.py`
- Test: `packages/core/tests/test_os_sandbox_stop.py`

**Requirements**:
- soft stop：主进程经子进程停止通道（SIGTERM 或 stopfile）通知停止调度新节点，子进程等待当前节点完成后退出
- hard stop：主进程终止子进程及其全部后代进程树
- run 标记为 `cancelled`，与非沙箱 stop 结果一致

#### Checks

- [ ] C13 沙箱 soft stop 等待当前节点
  - Verifies: `specs/dag-run-control/spec.md` / Requirement "Soft stop" / Scenario "沙箱 run 的 soft stop"
  - Command: `uv run pytest packages/core/tests/test_os_sandbox_stop.py -k soft`
  - Expect: soft stop 后当前执行节点完成，无新节点启动，子进程随后退出，run 标记 cancelled
- [ ] C14 沙箱 hard stop 终止进程树
  - Verifies: `specs/dag-run-control/spec.md` / Requirement "Hard stop" / Scenario "沙箱 run 的 hard stop"
  - Command: `uv run pytest packages/core/tests/test_os_sandbox_stop.py -k hard`
  - Expect: hard stop 后子进程及其后代进程全部终止，run 标记 cancelled

### Task 6: 隔离有效性集成测试与 WSL2 回退

**Goal**: 端到端验证 os-sandbox 的文件系统/网络隔离有效性，以及 srt 环境缺失/受限时的回退。

**Files**:
- Test: `packages/core/tests/test_os_sandbox_integration.py`
- Modify: `README.md`（部署说明：安装 srt、bubblewrap、socat、ripgrep）

**Requirements**:
- 需 srt 环境的集成测试：handler 试图读 `~/.ssh` 被拒；写 `allowWrite` 之外被拒；访问非 allowlist 域名被拒
- sub-DAG 在同一沙箱内执行（无 nested sandbox）
- WSL2 `apparmor_restrict_unprivileged_usernamespaces` 受限场景：探测失败即回退并记录到运行元数据

#### Checks

- [ ] C15 文件系统隔离有效性
  - Verifies: `specs/dag-run-os-sandbox/spec.md` / Requirement "沙箱文件系统约束" / Scenario "写入未授权路径被拒"
  - Command: `uv run pytest packages/core/tests/test_os_sandbox_integration.py -k fs_isolation`
  - Expect: handler 读 `~/.ssh` 与写未授权路径均失败（EPERM 或等价）
- [ ] C16 网络隔离有效性
  - Verifies: `specs/dag-run-os-sandbox/spec.md` / Requirement "沙箱网络约束" / Scenario "未授权域名访问被拒"
  - Command: `uv run pytest packages/core/tests/test_os_sandbox_integration.py -k net_isolation`
  - Expect: 访问非 allowlist 域名的连接被拒绝
- [ ] C17 sub-DAG 共享沙箱无嵌套
  - Verifies: `specs/dag-run-os-sandbox/spec.md` / Requirement "OS 级沙箱可选启用" / Scenario "声明 os-sandbox 的 DAG run 进沙箱"
  - Command: `uv run pytest packages/core/tests/test_os_sandbox_integration.py -k subdag_shared`
  - Expect: sub-DAG 节点在同一沙箱进程内执行，无第二层 srt/bubblewrap 嵌套
