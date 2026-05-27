## Context

`core-architecture-overhaul` 引入了 mTLS 安全模型（D9）：daemon 持有自签 CA，给客户端和 agent 节点签发证书，从证书 CN 提取身份做权限判断。当前实现把 CA 私钥、server cert、agent cert 和客户端 cert 都堆在 `~/.rig/` 下，agent cert 通过文件路径经环境变量传给 subprocess。

存在两类问题：

1. **目录共用违反 D9 安全承诺**：D9 声称 "CA key 仅 daemon 进程可读"，但同机部署（客户端和 daemon 在同一台机器、同一 OS user）下，`~/.rig/` 是用户家目录，daemon 的 CA 私钥落在用户能读的位置，承诺无法兑现。
2. **agent cert 落盘扩大攻击面**：daemon 给每个 agent 签发短期 cert 后写文件，subprocess 通过 `RIG_CLIENT_CERT` 环境变量拿到路径再读文件。同 OS user 下其他 agent 进程能直接读这些文件；daemon 数据迁移时需要清理旧路径；cert 在文件系统上的生命周期与进程生命周期不一致。

服务端典型场景：DAG 运行中多个 agent node 并发执行，每个 node 需要不同身份（不同 entity_permissions）。客户端典型场景：人类或外部 agent 通过 `rig` CLI 做全局控制，使用单一长期身份。这两类场景在身份并发数、cert 生命周期、存储位置上都不同。

项目处于开发阶段，可做 breaking change。

## Goals / Non-Goals

**Goals:**
- daemon 数据目录与客户端目录物理分离，CA 私钥落在 daemon 专属位置
- agent cert 不落盘：daemon 内存签发 → PEM 文本注入 env → subprocess 直接交给 gRPC SSL credentials
- 三个证书相关 env var（`RIG_CLIENT_CERT` / `RIG_CLIENT_KEY` / `RIG_CA_CERT`）统一改为 PEM 内容语义
- `grpc_client.py` 加载优先级：env 有值 → 当 PEM 文本用；env 无值 → fallback 读 `~/.rig/` 文件（人类 CLI 默认路径）
- daemon 首次启动自动生成 CA，零人工初始化

**Non-Goals:**
- 同 OS user 下 agent 之间的强隔离（namespace / setuid 路线，本次不做）
- 客户端多身份并存（profile 切换机制，本次不做；需要时人类侧 fallback 到环境变量足够）
- 外部 PKI 集成（带入企业 CA），仅保留扩展接口
- pi CLI 内部如何使用注入的 cert（pi 本身就是 `rig` CLI，复用同一份 `grpc_client.py` 逻辑）

## Decisions

### D1: 证书 env var 语义统一为 PEM 文本

`RIG_CLIENT_CERT` / `RIG_CLIENT_KEY` / `RIG_CA_CERT` 的值从"文件路径"改为"PEM 文本内容"。废弃路径语义，无向后兼容。

加载逻辑（位于 `grpc_client.py::_channel_credentials()`）：
```python
def _load_pem(env_name: str, fallback_path: Path) -> bytes:
    val = os.environ.get(env_name)
    if val:
        return val.encode()           # PEM 本身是 ASCII，直接 encode
    if fallback_path.exists():
        return fallback_path.read_bytes()
    return None
```

替代方案 A：新增 `_PEM` 后缀变量，与路径变量并存。**否决**：开发阶段无兼容包袱，并存增加心智负担。

替代方案 B：值前缀协议（`pem:<...>` / `file:<...>`）。**否决**：人类手动设置 env 时啰嗦，且 PEM 内容本身有 `-----BEGIN` 标识，自动检测也可行但隐式行为更糟。

替代方案 C：base64 编码 PEM。**否决**：PEM 已是 ASCII safe，base64 多此一举。

### D2: daemon 内存签发，PEM 注入 env

executor `_agent_cert_env()` 改为：
```python
def _agent_cert_env(cert: AgentCert) -> dict[str, str]:
    return {
        "RIG_CLIENT_CERT": cert.cert_pem,    # str (PEM text)
        "RIG_CLIENT_KEY":  cert.key_pem,     # str (PEM text)
        "RIG_CA_CERT":     cert.ca_pem,      # str (PEM text)
    }
```

`AgentCert` 不再带 `cert_path` / `key_path` 字段，daemon 签发函数返回 PEM bytes/str，不写文件系统。subprocess 启动后 env var 通过 `subprocess.Popen(env=...)` 注入，进程退出后 PEM 内容随 env 一起释放。

替代方案：fd 继承 + `/dev/fd/N`。**否决**：Windows 不支持，且需要 pi/rig CLI 知道从哪个 fd 读，gRPC SSL credentials API 接受 bytes，无需 fd 这层抽象。

替代方案：tmpfs + unlink。**否决**：仍有短暂落盘窗口，macOS 无 `/dev/shm`。

### D3: 部署目录分离

```
客户端家目录 ~/.rig/
  ├── client.crt + client.key     # 人类身份长期 cert
  ├── ca.crt                      # 校验 daemon server cert
  └── config.json                 # daemon_addr 等

daemon 数据目录 (RIG_DAEMON_DATA_DIR)
  默认 = /var/lib/rig/  (生产)
       = ~/.local/share/rig/  (开发，无 root 权限时)
  ├── ca.crt + ca.key             # 自签 CA，daemon 进程私有
  ├── server.crt + server.key     # daemon mTLS server cert
  ├── sessions/{dag}/{instance}/{cycle}/  # agent session 存储
  └── daemon.json                 # listen addr 等
```

daemon 启动时按以下顺序确定 data dir：
1. `--data-dir` 命令行参数
2. `RIG_DAEMON_DATA_DIR` 环境变量
3. 默认路径（先尝试 `/var/lib/rig/`，无写权限则用 `~/.local/share/rig/`）

agent session 路径从 `~/.rig/sessions/...` 改为 `${data_dir}/sessions/...`。

### D4: CA 自动生成

daemon 启动时检查 `${data_dir}/ca.key` 是否存在：
- 不存在 → 生成自签 CA（RSA 2048 或 EC P-256），写入 `ca.crt` + `ca.key`，权限 `0600`
- 存在 → 加载现有 CA

server cert 同样按需生成：基于 CA 签发，CN=`rig-daemon`，SAN 包含 `localhost` 和 listen address。

替代方案：显式 `rig daemon init` 命令。**否决**：开发阶段追求零摩擦。如果未来需要带入外部 CA，加 `--ca-cert` / `--ca-key` 参数即可。

### D5: stop/resume 每次重新签发

agent stop 后 cert 随进程消亡。resume 时 daemon 调用相同的签发逻辑生成新 cert（CN 仍为 `node:{instance_id}`，TTL 重置）。daemon 不缓存 cert。

替代方案：daemon 缓存原 cert 复用。**否决**：cert 可能在 resume 时已过期；每次签发逻辑单一更简单；开销可忽略（CA 签发 ~毫秒级）。

### D6: CLI fallback 默认路径不变

`grpc_client.py` 在 env var 无值时 fallback 读 `~/.rig/client.crt` / `client.key` / `ca.crt`。人类用户体验完全不变（`rig client init` 写文件，`rig` 命令读文件）。

agent subprocess 由 daemon 启动时 env var 全部填充，永远走 env 分支，不会触达 fallback 路径——这意味着 daemon data dir 下的 sessions 子目录是 daemon 唯一会生成的磁盘 cert 相关数据，agent 进程对磁盘 cert 零依赖。

## Risks / Trade-offs

- **同 UID `/proc/<pid>/environ` 可读**：同 OS user 下 agent A 进程能读 agent B 的 `/proc/environ`，看到完整 PEM key。**Mitigation**：威胁模型显式定义 — 信任边界在 daemon 进程内，agent 之间不做 OS 级隔离；短期 cert + TTL 对齐 timeout 把窗口压到最小；如未来需硬隔离，走 namespace / setuid 路线，不在 env 层面打补丁。

- **`/proc/<pid>/environ` 是内核快照**：subprocess 启动后 `del os.environ["RIG_CLIENT_CERT"]` 无法清除快照，缓解措施无效。接受，记录到威胁模型。

- **`prctl(PR_SET_DUMPABLE, 0)` 过度防御**：能阻止同 UID 读 `/proc/environ`，但同时阻止调试和 core dump，开发阶段不适用。

- **env var 长度限制**：Linux 单条 env 默认 128 KB（`MAX_ARG_STRLEN`），CA + cert + key 三件套 ~6 KB，远低于限制。

- **Windows / macOS 兼容**：`os.environ` + `subprocess.Popen(env=...)` 跨平台 OK；daemon data dir 默认路径需要分平台处理（Linux `/var/lib/rig/` 或 `~/.local/share/rig/`，macOS `~/Library/Application Support/rig/`，Windows `%PROGRAMDATA%\rig\`）。

- **breaking change 范围**：现有 dev 环境若已落 cert 在 `~/.rig/`，人类 CLI 仍能工作（fallback 读文件）；但任何手动设置 `RIG_CLIENT_CERT=/path/to/cert.crt` 的脚本都会失败。开发阶段可接受，需在 PR 描述里点名。

## Migration Plan

按以下顺序提交，每步都可独立工作：

1. **grpc_client.py** 改造 `_channel_credentials()` 支持 PEM env + 文件 fallback；测试 fallback 路径（无 env）和 PEM 路径（设 env）。
2. **daemon 数据目录** 引入 `RIG_DAEMON_DATA_DIR` 配置和默认路径解析；CA 自动生成逻辑；server cert 按需生成。
3. **executor `_agent_cert_env()`** 改为注入 PEM 内容；daemon 签发函数返回 `AgentCert` dataclass（带 `cert_pem` / `key_pem` / `ca_pem` 字段）。
4. **session 路径** 从 `~/.rig/sessions/` 迁移到 `${data_dir}/sessions/`。

回滚策略：每步独立 commit，单步回滚不影响其他改动。开发阶段无生产数据，全量回滚即 `git revert`。
