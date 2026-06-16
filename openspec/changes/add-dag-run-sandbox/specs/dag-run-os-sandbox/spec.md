---
capabilities:
  - cap.core.dag-run-os-sandbox
---

# dag-run-os-sandbox Delta

## ADDED Requirements

### Requirement: OS 级沙箱可选启用

系统 SHALL 支持对单个 DAG run 启用 OS 级进程隔离（os-sandbox）：开启时，整个 DAG run（含其全部 sub-DAG）MUST 在由 `srt`（Linux `bubblewrap` / macOS `sandbox-exec`）拉起的沙箱子进程内执行。os-sandbox 默认关闭；未声明的 DAG run 行为与无沙箱时完全一致。

#### Scenario: 声明 os-sandbox 的 DAG run 进沙箱

- **WHEN** DAG 配置声明 `os_sandbox.enabled = true` 且运行环境存在 `srt`
- **THEN** 该 DAG 的 run MUST 以 `srt exec` 拉起的子进程执行，子进程及其全部后代进程受沙箱策略约束

#### Scenario: 未声明 os-sandbox 的 DAG run 不受影响

- **WHEN** DAG 未声明 os-sandbox 或声明 `enabled = false`
- **THEN** 该 DAG 的 run MUST 在主进程内执行，文件系统与网络访问不受沙箱约束

### Requirement: 运行时临时覆盖沙箱配置

系统 SHALL 允许在触发 run 时临时覆盖该 DAG 声明的 os-sandbox 配置：可显式启用、显式关闭，或调整网络/文件系统规则。覆盖 MUST 仅作用于当次 run，不持久化回 DAG 声明配置。

#### Scenario: 显式关闭已声明的沙箱

- **WHEN** DAG 声明 `os_sandbox.enabled = true`，触发 run 时传入覆盖 `enabled = false`
- **THEN** 当次 run MUST 在主进程内执行（无沙箱），且 DAG 声明配置保持不变

### Requirement: 沙箱文件系统约束

os-sandbox 启用时，沙箱内进程的文件系统访问 MUST 满足：默认全盘禁止写入，仅显式 `allowWrite` 列出的路径可写；`denyWrite` 优先于 `allowWrite`。读取默认允许，`denyRead` 禁止的区域可由 `allowRead` 重新放行。强制 deny 路径（含 `~/.ssh`、`.gitconfig`、`.bashrc`、`.claude/`、`.git/hooks/`）即使落在 `allowWrite` 内也 MUST 禁止写入。

#### Scenario: 写入未授权路径被拒

- **WHEN** 沙箱内进程尝试写入不在 `allowWrite` 中的路径
- **THEN** 写操作 MUST 失败（返回 `EPERM` 或等价错误）

#### Scenario: 强制 deny 路径不可写

- **WHEN** 沙箱内进程尝试写入 `~/.ssh` 或 `.git/hooks/`，即使该路径在 `allowWrite` 内
- **THEN** 写操作 MUST 失败

#### Scenario: 读取敏感目录被拒

- **WHEN** 配置 `denyRead: ["~/.ssh"]` 且未在 `allowRead` 重新放行
- **THEN** 沙箱内进程读取 `~/.ssh` MUST 失败

### Requirement: 沙箱网络约束

os-sandbox 启用时，沙箱内进程的网络访问 MUST 默认全部拒绝；仅显式 `allowedDomains` 列出的域名可访问。空 `allowedDomains` 意味着无任何网络访问。网络流量 MUST 经宿主机代理按白名单过滤。

#### Scenario: 未授权域名访问被拒

- **WHEN** 沙箱内进程尝试访问不在 `allowedDomains` 中的域名
- **THEN** 连接 MUST 被拒绝

#### Scenario: 空白名单等于无网络

- **WHEN** os-sandbox 启用且 `allowedDomains` 为空
- **THEN** 沙箱内进程 MUST 无法发起任何出站网络连接

### Requirement: 沙箱 run 的事件流回传

os-sandbox 启用时，沙箱子进程 MUST NOT 直接连接数据库；node-run 结果、edge 输入与 DAG 生命周期事件 MUST 经 stdout NDJSON 事件流回传主进程，由主进程作为唯一数据库写入者落库。非 JSON 行 MUST 归入运行日志而不被解析为事件。

#### Scenario: 节点完成事件落库

- **WHEN** 沙箱内某节点执行完成
- **THEN** 子进程 MUST 经 stdout 输出一条 node 完成事件，主进程读取后 MUST 将其写入数据库，等价于非沙箱 run 的记录结果

#### Scenario: 非 JSON 日志行不破坏事件流

- **WHEN** 子进程 stdout 含有非 JSON 格式的日志行
- **THEN** 这些行 MUST 被归入运行日志文件，MUST NOT 导致事件解析中断或节点记录丢失

### Requirement: 主进程独占证书签发

os-sandbox 启用时，agent 节点所需的客户端证书 MUST 由主进程在 run 启动前预签发并注入沙箱子进程；证书签发根（`ca.key`）MUST NOT 进入沙箱。

#### Scenario: 私钥不进沙箱

- **WHEN** os-sandbox run 启动
- **THEN** `ca.key` MUST 仅存在于主进程可访问的路径，沙箱子进程 MUST 无法读取 `ca.key`

### Requirement: srt 缺失时回退

os-sandbox 启用但运行环境不存在 `srt` CLI 时，系统 MUST 回退到无沙箱的主进程内执行路径，MUST NOT 导致 run 失败；该回退 MUST 被记录。

#### Scenario: srt 不存在时回退

- **WHEN** DAG 声明 `os_sandbox.enabled = true` 但 `srt` 不在 PATH
- **THEN** run MUST 在主进程内执行（无沙箱），且该回退 MUST 被记录到运行元数据
