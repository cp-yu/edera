## Why

`mtls-identity-isolation` 已 apply，但 `_channel_credentials()` 仍保留 `~/.rig/` 文件 fallback。这条隐式 fallback 路径在两个场景下出问题：

1. **bootstrap 端口被 secure channel 污染**：`rig client init` 调用 `RigGrpcClient(bootstrap_address, allow_insecure=True)`，但若用户 `~/.rig/` 已有旧 cert，`_channel_credentials()` 默默加载文件 → 走 secure channel 连 insecure bootstrap 端口 → TLS handshake 失败。QA 已复现。
2. **agent 清 env 提权 human 身份**：agent subprocess 收到 daemon 注入的 `RIG_CLIENT_CERT` PEM。若 agent 进程 `del os.environ["RIG_CLIENT_CERT"]` 再发起 gRPC 调用，`_channel_credentials()` fallback 读 `~/.rig/client.crt`（同 OS user 下可读），daemon 收到 CN=`human:*`，按 human 身份放行，绕过 entity_permissions。

两个问题同根：`grpc_client.py` 不应该自己读文件。文件读取属于"我是 human CLI 入口"的语义，不属于"我是 gRPC 连接层"。

## What Changes

- **BREAKING** `_channel_credentials()` 移除 `~/.rig/` 文件 fallback；env PEM 缺失即返回 `None`（mTLS 不可用）
- **BREAKING** `RigGrpcClient` 新增 `force_insecure: bool = False` 参数；为 True 时跳过 cert 加载，强制 insecure channel
- 文件读取下沉到 `rig_cli.py` CLI 入口：human 命令启动时显式读 `~/.rig/{client.crt, client.key, ca.crt}` 注入 `os.environ`，再交给 `RigGrpcClient`
- `rig client init` 调用 `RigGrpcClient(bootstrap_address, force_insecure=True)`，与 fallback 路径完全解耦
- agent subprocess 由 daemon 注入 env，永远不触达文件读取代码路径；agent 删 env 后 `RigGrpcClient` 直接抛 `FileNotFoundError`，连接失败 fail-loud

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `rig-cli`: gRPC client 层只看 env；文件 fallback 从 `_channel_credentials()` 上移到 CLI 入口；引入 `force_insecure` 显式标志支持 bootstrap； agent 清 env 后 fail-loud（这一变化由 grpc_client 行为收敛带来，不再单独修改 agent-executor / rig-daemon-grpc spec）

## Impact

- `packages/core/src/stockimformation_core/grpc_client.py`: `_channel_credentials()` 删除文件 fallback；`RigGrpcClient.__init__` 新增 `force_insecure`；删除 `_load_pem` 中文件分支或保留为内部辅助
- `packages/core/src/stockimformation_core/rig_cli.py`: CLI 入口（main 或 dispatch 处）新增 `_inject_human_cert_env()` — 读 `~/.rig/` 文件写入 `os.environ`；`client init` 命令显式 `force_insecure=True`
- `packages/core/src/stockimformation_core/daemon.py`: agent subprocess 启动路径不变（env 注入已就位），无需改动
- 测试：新增 agent-clear-env 提权回归测试、bootstrap-with-existing-cert 回归测试
