<!--
路由决策记录：
- 输入来源：explore 生成的 Design Summary（add-dag-run-sandbox），存在
- 决策：proceed，使用 Design Summary 作为主输入
- 多子系统判定：否（聚焦 DAG run 执行边界单一子系统）
-->

## Why

DAG run 当前在 `edera-server` 主进程内以 `asyncio.Task` 执行，agent 节点虽以子进程拉起、但 handler 节点以 `importlib` 在主进程同进程加载执行。这意味着第三方/不可信 handler 与 agent 可访问主进程的全部文件系统与网络（含 `ca.key`、`~/.ssh`、DB 文件）。需要一个**可选的、per-DAG 的 OS 级隔离层**，在不引入容器的前提下把整个 DAG run（含其 sub-DAG）关进沙箱。

## What Changes

- 引入 `os-sandbox`（术语限定词，区别于已被占用的 bare `sandbox`=session 目录）：基于 Anthropic `srt` CLI（Linux `bubblewrap` / macOS `sandbox-exec`）的进程级文件系统与网络隔离。
- 把开启 os-sandbox 的 DAG run 从「主进程内 Task」升级为「`srt exec edera-dag-run` 拉起的沙箱子进程」；sub-DAG 在同一沙箱内同进程递归执行，不引入 nested sandbox。
- 主进程 `edera-server` 保持**唯一 DB 写者**与 `ca.key` 持有者；沙箱子进程不连 DB、不持私钥。
- 子进程通过 **stdout NDJSON 事件流**把 node-run 结果回传主进程落库（复用现有 stdout 流式收集管道）。
- `srt` 为**外部 CLI 依赖**，探测不到时回退到现有 in-process 执行路径，行为零变化。
- per-DAG 声明式配置（`DagConfig.os_sandbox` 段）+ 运行时临时覆盖（`run_now`/`start_run` 的 `sandbox` 参数）。
- 安全语义：默认无网络（allow-only `allowedDomains`）、默认全盘禁写（显式 `allowWrite`）、强制 deny 路径（`~/.ssh`、`.gitconfig`、`.claude/` 等）。

## Capabilities

### New Capabilities
- `dag-run-os-sandbox`: 可选的 per-DAG OS 级进程隔离，把整个 DAG run（含 sub-DAG）包进 `srt` 沙箱，强制文件系统读写与网络域名白名单约束；主进程独占 DB 写与证书签发，子进程经 stdout NDJSON 事件流回传 node-run 结果。

### Modified Capabilities
- `dag-run-control`: run 入口语义变化——开启 os-sandbox 时，run 以子进程执行并由主进程经事件流代写 DB；停止语义增加子进程信号通道。
- `node-executor`: agent 节点在沙箱内执行时不再二次包 `srt`，复用沙箱边界；证书由主进程预签注入而非运行时同步签发。

## Impact

- **新增代码**：`edera-dag-run` 子进程 CLI 入口；stdout 事件协议与解析；`os-sandbox` 配置 schema 与 `.srt-settings.json` 生成器；`srt` 探测/回退包装器；事件流→DB 桥接器。
- **修改代码**：`dag_controller.py` `_run`（in-process `await task` ↔ 子进程 + 事件流代写）；`node/executor.py` `_build_agent_command`/证书签发流程；`config/schema.py` `DagConfig`（新增 `os_sandbox` 段，并核查孤儿字段 `sandbox_max_bytes`）。
- **外部依赖**：`srt`（npm 包 `@anthropic/sandbox-runtime`），Linux 需 `bubblewrap`+`socat`+`ripgrep`。
- **平台约束**：WSL2 的 `kernel.apparmor_restrict_unprivileged_usernamespaces` 会阻断 bubblewrap，探测失败即回退。
- **术语**：GLOSSARY.md 新增 `os-sandbox` 条目；全文 bare `sandbox` 仍指 session 目录。
