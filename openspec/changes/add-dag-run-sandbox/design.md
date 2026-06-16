## Context

Edera 当前以「Entity 为原语、DAG 为执行模型」在本机编排。执行路径有两条：

- **agent 节点**：`NodeExecutor._execute_agent`（`node/executor.py:292`）经 `asyncio.create_subprocess_exec(*cmd)`（:318）拉起独立 `pi_bin` 进程，主进程流式收 stdout 写 `stdout.log`（:327），证书由 `agent_certificate_issuer`（:316）同步签发注入 `EDERA_CLIENT_CERT/KEY/CA` 环境变量。
- **handler 节点**：`_execute_payload`（:270）经 `_load_handler` → `importlib.exec_module`（:525）**在主进程内**加载并执行 handler 协程。

`DagController._run`（`dag_controller.py:608`）是 in-process `DagRunner.run()` 的唯一宿主，独占全部 DB 写入（`session.commit` 在 638/642/698/777/839）。`run_now`/`start_run` 经 `await task` 在主进程内同步等待。sub-DAG 经 `DagRunner._execute_dag_node_config`（runner.py:75-76）同进程递归，不跨边界。

约束（用户明确）：
- DAG 不与 DAG 交互；sub-DAG 共享同一个沙箱，不需要 nested sandbox。
- 沙箱可选，粒度 per-DAG 声明 + 运行时临时覆盖。
- 隔离参考 `anthropic-experimental/sandbox-runtime`（`srt`）。
- `edera-server` 是 Python（uv workspace, py312），`srt` 是 Node/npm 包。
- DB 为 SQLite（aiosqlite + WAL）。

术语：bare `sandbox` 已被现有 4 个 spec 占用，表示 pi CLI agent 的 session 目录；新概念命名 `os-sandbox`。

## Goals / Non-Goals

**Goals:**
- 整个 DAG run（含 sub-DAG）可被关进 OS 级沙箱，agent 与 handler 子树均被隔离。
- 主进程保持唯一 DB 写者与 `ca.key` 持有者，私钥永不进沙箱。
- 可选、可探测回退：无 `srt` 时行为与现状完全一致。
- per-DAG 声明 + 运行时覆盖的配置模型。

**Non-Goals:**
- 不做 nested sandbox（sub-DAG 不单独隔离）。
- 不做 DAG 间级联触发的沙箱内 emit 回传（约束：沙箱内 emit 不联动外部 DAG）。
- 不自研 bubblewrap/seatbelt profile 生成器，复用 `srt`。
- 不支持非 x64/arm64 架构（`srt` 限制）。
- 不提供 macOS glob 之外的高级路径匹配。

## Decisions

### D1: 沙箱粒度 = DAG run 级（方案 B），非节点级

**选择**：整个 DAG run 拉起为 `edera-dag-run` 子进程并整体进沙箱。

**为何**：节点级（仅包 `_execute_agent`）无法隔离 handler 同进程代码——而 handler 是第三方/不可信代码的主要落点。run 级把 DagRunner 连同其 importlib 加载的 handler 一并隔离，隔离收益最大。

**替代（已拒绝）**：
- 节点级：改动最小但留 handler 同进程隔离缺口。
- handler 进程化：每个 handler spawn 一个 `srt` 子进程，达到接近 run 级隔离但避开 DAG 级 IPC；拒绝原因是失去「整个 run 一个沙箱」语义，且每节点一次 `srt`/bubblewrap 启动开销叠加。

### D2: 子进程经 stdout NDJSON 事件流回传，主进程代写 DB（DB 策略 A）

**选择**：子进程不连 DB，把 `node_done`/`edge_input`/`dag_lifecycle` 等事件作为 JSON 行打到 stdout；主进程边读边调 `recorder`/`edge_recorder` 落库。

**为何**：
- SQLite 单写者与「沙箱需要独立子进程」结构性冲突。跨进程写同一 DB 文件会偶发 `SQLITE_BUSY`，WSL2 下更脆弱，且 bind-mount DB 文件进沙箱会泄漏写权限、削弱隔离。
- 复用现有 stdout 流式收集管道（executor.py:327 已在流式读子进程 stdout），加几个 JSON 事件不算新造 IPC，是 child→parent 单向流。
- 主进程独占写，消除并发写。

**替代（已拒绝）**：
- 子进程直连同 DB：零 IPC 但 `SQLITE_BUSY` + WSL2 锁脆弱 + 写权限泄漏。
- run 独立输出 + 结束合并：隔离最干净但需设计合并语义，改动过大。

### D3: `srt` 作为外部 CLI 依赖，探测回退

**选择**：`shutil.which("srt")` 探测；存在则命令前缀 `["srt","exec","--settings",<path>]`，不存在则走原 in-process 路径，os-sandbox 视为未启用。

**为何**：与现有 `pi_bin` 外部 CLI 模式一致；不绑定 Node 运行时进 Edera 分发链；探测回退保证非沙箱环境零行为变化。

**替代（已拒绝）**：
- Python 直调 bubblewrap：去掉 Node 依赖但要自维护 profile/代理/seccomp，重复造轮。
- vendor srt 源码：含 TS + 编译的 seccomp 二进制，vendor 与升级成本高。

### D4: 证书由主进程预签注入，非运行时同步签发

**选择**：run 启动前主进程预签 agent 证书，写入 run 临时目录或经环境变量注入子进程；`ca.key` 留主进程。

**为何**：`ca.key` 进沙箱等于自废武功。预签把「签名能力」与「执行环境」彻底分离，子进程无需运行时回主进程要证书，避免双向 IPC。

### D5: 停止信号 = SIGTERM + stopfile 双通道

**选择**：主进程发 `SIGTERM` 给子进程；同时在 run 临时目录写 stopfile 作为兜底（bubblewrap 下信号传递偶有边界问题）。

**为何**：单向信号，无双向 IPC；与现有 `stop_event`（asyncio.Event，进程内原语，不能跨进程）语义对齐。

### D6: 术语 os-sandbox，保留 bare sandbox = session 目录

**选择**：新概念全部用 `os-sandbox`；GLOSSARY.md 新增条目；现有 bare `sandbox` 语义不变。

**为何**：sweeper 发现 4 个 spec 已用 bare `sandbox` 表示 session 目录（7 处），复用裸词造成持续性歧义。

### D7: 配置两段式 —— per-DagConfig 声明 + run 参数覆盖

**选择**：`DagConfig.os_sandbox`（enabled / network.allowedDomains / filesystem.{allowWrite,denyRead,denyWrite}）；`run_now`/`start_run` 增 `sandbox` override 参数（显式开/关/改规则）。

**为何**：与现有 `run_now` 已接收临时参数（`source_shared_inputs`/`node_inputs`/`append_nodes`）模式一致。

## Risks / Trade-offs

- [WSL2 `apparmor_restrict_unprivileged_usernamespaces` 阻断 bubblewrap] → 探测失败即回退 in-process；文档说明 `sysctl` 或 AppArmor profile 配置；tests 标记需 srt 环境。
- [`srt` 仍是 beta，API/格式会变，曾有网络逃逸 advisory（GHSA-9gqj-5w7c-vx47）] → 钉版本；网络默认 deny-all；不向用户承诺「绝对隔离」。
- [stdout 既是日志又是事件通道，格式错乱会丢 node 记录] → 严格 NDJSON；非 JSON 行归入 `stdout.log` 不解析；事件序号连续性检测。
- [`SystemConfig.sandbox_max_bytes`（schema.py:36）已声明但全代码库无消费者] → tasks 首项查清该字段语义，再定 os-sandbox 配置命名，避免撞车。
- [per-DAG 配置增长 DagConfig 复杂度] → 默认 disabled；仅声明的 DAG 生效。
- [Linux 不支持 glob 路径匹配] → 文档明确 Linux 仅字面路径；配置校验在 Linux 上拒绝 glob。

## Migration Plan

无历史数据迁移（开发阶段）。部署：`npm i -g @anthropic/sandbox-runtime` + Linux 安装 `bubblewrap`/`socat`/`ripgrep`。回滚：卸载 `srt` 或配置 `os_sandbox.enabled=false`，自动回退 in-process。

## Open Questions

- `SystemConfig.sandbox_max_bytes` 字段真实意图为何？（tasks 首项核查）
- stdout 事件协议是否需要版本号字段以支持未来演进？（建议纳入，design 确认）
