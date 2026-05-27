## Context

`mtls-identity-isolation` 在 `grpc_client.py::_channel_credentials()` 实现了"env PEM 优先 → `~/.rig/` 文件 fallback"的加载逻辑。当时的考虑是：人类 CLI 默认体验（不设 env 自动读文件），agent 由 daemon 注入 env 不会触达 fallback。

QA 与威胁模型分析暴露这条路径有两个洞：

1. **bootstrap 端口被污染**：`rig client init` 调用 `RigGrpcClient(bootstrap_address(server), allow_insecure=True)`（`rig_cli.py:302`）。`allow_insecure` 只在 cert 缺失时绕过；但当用户 `~/.rig/` 已有旧 cert（典型场景：之前 init 过、想换 daemon），`_channel_credentials()` 静默成功返回 credentials，channel 被强制为 secure，连到 daemon 的 insecure bootstrap 端口（`+1` 端口）→ TLS handshake 失败。
2. **agent 提权 human**：daemon 给 agent 注入 `RIG_CLIENT_CERT` PEM（CN=`node:fetcher-1`）。agent 进程任意一行 `os.environ.pop("RIG_CLIENT_CERT")`（不论恶意还是 bug），`_load_pem` fallback 到 `~/.rig/client.crt`（同 OS user 可读，CN=`human:yunxin`），daemon 看到 human 身份直接放行所有 entity 操作。

两个问题同根：`grpc_client.py` 的"我可能要建 mTLS 连接"语义里，混进了"我知道 human CLI 该读哪个文件"的语义。把后者剥离出去就能同时解决两个问题。

## Goals / Non-Goals

**Goals:**
- `_channel_credentials()` 只看 env，不读文件
- bootstrap channel 路径与 mTLS channel 路径在代码层面互不干扰
- 人类 CLI 默认体验不变（运行 `rig entity list` 不需要手动设 env）
- agent 清 env 后失败 fail-loud（`RuntimeError` / 连接拒绝），不能静默拿到 human 身份
- `rig client init` 不论 `~/.rig/` 是否有旧 cert，都能成功 bootstrap

**Non-Goals:**
- 改变 daemon 端的 cert 签发或权限校验逻辑（daemon 视角不变）
- 解决同 OS user 下 agent **主动** 读 `~/.rig/client.crt` 文件这种攻击（属于已记录的威胁模型，需要 namespace/setuid 才能解，本次不做）
- 重构 `RigGrpcClient` 整体接口（仅新增一个参数，不动其他）

## Decisions

### D1: 文件读取上移到 CLI 入口

`_channel_credentials()` 删除 fallback 路径：

```python
def _channel_credentials():
    if os.environ.get("RIG_ENV") == "dev":
        return None
    cert = os.environ.get("RIG_CLIENT_CERT")
    key = os.environ.get("RIG_CLIENT_KEY")
    ca = os.environ.get("RIG_CA_CERT")
    if not (cert and key and ca):
        return None
    return grpc.ssl_channel_credentials(
        root_certificates=ca.encode(),
        private_key=key.encode(),
        certificate_chain=cert.encode(),
    )
```

人类 CLI 入口（`rig_cli.py` main dispatcher）显式读文件：

```python
def _inject_human_cert_env() -> None:
    home = Path.home() / ".rig"
    for env_name, filename in [
        ("RIG_CLIENT_CERT", "client.crt"),
        ("RIG_CLIENT_KEY", "client.key"),
        ("RIG_CA_CERT", "ca.crt"),
    ]:
        if env_name in os.environ:
            continue
        path = home / filename
        if path.exists():
            os.environ[env_name] = path.read_text(encoding="utf-8")
```

入口逻辑：除了 `client init`、`daemon` 之类不需要 mTLS 的子命令外，所有 human-facing 子命令在 dispatch 前调用 `_inject_human_cert_env()`。

替代方案 A：在 `_channel_credentials()` 加 `allow_file_fallback: bool` 开关。**否决**——参数会被默认值掩盖，bootstrap 写错容易再出 bug，agent 进程也能复用 `RigGrpcClient` 默认开 fallback。语义不应该靠参数控制，应该靠"谁负责读文件"的代码位置控制。

替代方案 B：保留 fallback 但加 marker 文件（`~/.rig/.this-is-human`）。**否决**——marker 同样可被同 UID 进程访问，没解决根本问题。

### D2: `force_insecure` 显式标志

`RigGrpcClient.__init__` 新增 `force_insecure: bool = False`：

```python
def __init__(self, address=None, data_dir=None,
             allow_insecure=False, force_insecure=False):
    ...
    if force_insecure:
        self._channel = grpc.aio.insecure_channel(self.address)
    else:
        credentials = _channel_credentials()
        if credentials is None and not (allow_insecure or os.environ.get("RIG_ENV") == "dev"):
            raise FileNotFoundError("gRPC client certificate is required")
        self._channel = (grpc.aio.secure_channel(self.address, credentials)
                         if credentials is not None
                         else grpc.aio.insecure_channel(self.address))
```

`rig client init` 调用方式：

```python
client = RigGrpcClient(bootstrap_address(server), force_insecure=True)
```

`force_insecure` 与 `allow_insecure` 的区别：
- `allow_insecure=True`：cert 缺失时**允许**降级为 insecure，cert 存在时仍走 secure
- `force_insecure=True`：忽略 cert，**强制** insecure

bootstrap 必须用 `force_insecure`，因为它的目标端口本就是明文。

替代方案：复用 `allow_insecure=True` + 显式清空 env。**否决**——清 env 会污染父进程状态（`rig` CLI 是单进程），且 `_channel_credentials()` 仍需要"忽略 env"开关才能生效，最终等价于 `force_insecure`，不如直接命名清晰。

### D3: agent fail-loud 而非 fail-silent

agent subprocess 启动时 daemon 已注入 env，正常路径走 secure channel。如果 agent 进程清掉 env 重新发起 gRPC 调用：

```
RigGrpcClient.__init__()
    → _channel_credentials() 返回 None（env 缺失，无 fallback）
    → allow_insecure=False, RIG_ENV != dev
    → raise FileNotFoundError("gRPC client certificate is required")
```

这是预期行为：agent 不能在没有合法身份的情况下静默连接 daemon。错误信息明确指向 cert 缺失，不暴露"也许该去读文件"的提示。

### D4: 不限制人类 CLI 的"显式无 cert" 用法

人类用户可能想在没有 init 过的机器上跑 dev 模式（`RIG_ENV=dev`），或显式 `rig --insecure entity list` 连开发 daemon。这两个路径仍然走原 `allow_insecure` / dev mode 逻辑，不被 D1 影响——`_inject_human_cert_env()` 只是在 env 不存在时尝试读文件，文件不存在则啥都不做，下游 `_channel_credentials()` 返回 None，再由 `allow_insecure` / dev mode 接管。

## Risks / Trade-offs

- **同 OS user agent 主动读文件仍能提权**：本次方案只堵"清 env 触发 fallback"这条静默路径。agent 主动 `Path.home() / ".rig/client.crt"` 读文件 + 自己塞 env 的攻击仍然有效。**Mitigation**：威胁模型已在 mtls-identity-isolation design.md Risks 记录，本次不扩大承诺。

- **CLI 入口需识别哪些子命令需要注入 cert**：`client init`、`daemon` 不需要；其他子命令需要。**Mitigation**：在每个子命令的执行函数内调用，而不是在全局 main 入口（避免 `client init` 误触发）。或者反过来：默认全局注入，`client init` / `daemon` 显式跳过。后者更难漏，采用后者。

- **现有 `_load_pem` helper 失去作用**：D1 删除后 `_load_pem` 只剩 env 分支，等同 `os.environ.get`。可保留作为命名清晰的 helper，也可删除直接用 `os.environ.get`。倾向直接删除，减少抽象。

- **测试覆盖**：需要新增两个回归测试：
  - bootstrap 在 `~/.rig/` 已有 cert 时仍能 insecure 连接
  - agent 清 env 后 `RigGrpcClient` 抛 `FileNotFoundError` 而非走 fallback

## Migration Plan

按以下顺序提交：

1. **`grpc_client.py`** 删除 `_load_pem` 文件 fallback 分支；新增 `force_insecure` 参数；保留 `allow_insecure` 语义不变
2. **`rig_cli.py`** 新增 `_inject_human_cert_env()`；在 main dispatcher 默认调用，`client init` / `daemon` 子命令内显式跳过
3. **`rig client init` 调用** 改为 `RigGrpcClient(..., force_insecure=True)`
4. **回归测试** 新增两条
5. 手动 QA 复现：QA 报告中"`~/.rig/` 已有 cert 时 init 失败"场景应通过

回滚：每步独立 commit，单步回滚。
