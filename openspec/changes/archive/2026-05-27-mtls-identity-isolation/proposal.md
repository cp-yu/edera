## Why

当前设计中 daemon 数据（CA 私钥、server cert、agent cert、session 存储）与客户端数据（user cert）共用 `~/.rig/` 目录，同机部署时无法满足"CA key 仅 daemon 可读"的安全承诺。同时 agent cert 落盘后，同 OS user 下的其他 agent 可直接读取，且 daemon 迁移数据目录时需要考虑 agent 是否仍在引用旧路径。

## What Changes

- **BREAKING** `RIG_CLIENT_CERT` / `RIG_CLIENT_KEY` / `RIG_CA_CERT` 环境变量语义从文件路径改为 PEM 文本内容
- daemon 签发 agent cert 后不落盘，直接将 PEM 内容注入 subprocess 环境变量
- daemon 数据目录（CA、server cert、sessions）与客户端数据目录（`~/.rig/`）分离，通过 `RIG_DAEMON_DATA_DIR` 配置
- daemon 首次启动时自动生成自签 CA（无需手动 init）
- agent stop/resume 时每次重新签发 cert，不缓存旧证书
- `grpc_client.py` 加载逻辑：env 有值 → 当 PEM 内容用；env 无值 → fallback 读 `~/.rig/` 文件

## Capabilities

### New Capabilities
- `daemon-data-directory`: daemon 数据目录管理，覆盖目录结构定义、`RIG_DAEMON_DATA_DIR` 配置、CA 自动生成和与客户端目录的隔离边界

### Modified Capabilities
- `rig-daemon-grpc`: agent 短期证书签发从落盘改为内存持有 + env PEM 注入；新增 daemon data dir 配置要求
- `agent-executor`: 环境变量注入语义从证书路径改为 PEM 内容；resume 时重新签发
- `rig-cli`: 环境变量覆盖语义从路径改为 PEM 内容；fallback 逻辑调整

## Impact

- `packages/core/src/stockimformation_core/grpc_client.py`: `_channel_credentials()` 重写，支持 PEM 内容优先 + 文件 fallback
- `packages/core/src/stockimformation_core/node/executor.py`: `_agent_cert_env()` 改为注入 PEM 内容而非路径
- `packages/core/src/stockimformation_core/daemon.py`（待创建）: cert 签发逻辑改为返回 PEM bytes 而非写文件；CA 自动生成；data dir 管理
- `packages/core/src/stockimformation_core/rig_cli.py`: `client init` 保存路径不变，但 env var 语义文档更新
- 设计文档 D9（安全模型）需同步更新
