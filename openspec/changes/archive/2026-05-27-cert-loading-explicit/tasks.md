## 1. Actions

- [x] A1 删除 `_channel_credentials()` 中的 `~/.rig/` 文件 fallback；只读 env，缺失返回 None
- [x] A2 删除或简化 `_load_pem` helper（不再需要文件分支）
- [x] A3 `RigGrpcClient.__init__` 新增 `force_insecure: bool = False`，为 True 时跳过 cert 加载强制 insecure channel
- [x] A4 `rig_cli.py` 新增 `_inject_human_cert_env()`：读 `~/.rig/{client.crt, client.key, ca.crt}` 内容写入对应环境变量；env 已设置则跳过
- [x] A5 `rig_cli.py` main dispatcher 默认调用 `_inject_human_cert_env()`，`client init` / `daemon` 子命令显式跳过
- [x] A6 `rig client init` 改为 `RigGrpcClient(bootstrap_address(server), force_insecure=True)`
- [x] A7 新增回归测试：`~/.rig/` 已有 cert 时 `rig client init` 仍能 bootstrap 成功
- [x] A8 新增回归测试：agent 清空 `RIG_CLIENT_CERT` 后 `RigGrpcClient` 抛 `FileNotFoundError`，不读 `~/.rig/client.crt`

## 2. Checks

- [x] C1 验证 grpc_client 不再读文件
  - Covers: A1, A2
  - Command: `cd packages/core && uv run python -c "import os; os.environ.pop('RIG_CLIENT_CERT', None); os.environ.pop('RIG_CLIENT_KEY', None); os.environ.pop('RIG_CA_CERT', None); from stockimformation_core.grpc_client import _channel_credentials; assert _channel_credentials() is None"`
  - Expect: env 缺失时返回 None，不尝试读 `~/.rig/`

- [x] C2 验证 force_insecure 强制 insecure channel
  - Covers: A3
  - Command: `cd packages/core && uv run python -c "import asyncio; from stockimformation_core.grpc_client import RigGrpcClient; c = RigGrpcClient('127.0.0.1:1', force_insecure=True); asyncio.run(c.close()); print('ok')"`
  - Expect: 输出 ok，无 cert 加载错误

- [x] C3 验证 _inject_human_cert_env 注入正确
  - Covers: A4
  - Command: `cd packages/core && uv run python -c "import os, tempfile, pathlib; tmp=pathlib.Path(tempfile.mkdtemp()); rig=tmp/'.rig'; rig.mkdir(); (rig/'client.crt').write_text('CERT'); (rig/'client.key').write_text('KEY'); (rig/'ca.crt').write_text('CA'); os.environ['HOME']=str(tmp); os.environ.pop('RIG_CLIENT_CERT', None); from stockimformation_core.rig_cli import _inject_human_cert_env; _inject_human_cert_env(); assert os.environ['RIG_CLIENT_CERT']=='CERT'; assert os.environ['RIG_CLIENT_KEY']=='KEY'; assert os.environ['RIG_CA_CERT']=='CA'"`
  - Expect: 三个 env var 被注入对应 PEM 内容

- [x] C4 验证 env 已设置时 _inject 不覆盖
  - Covers: A4
  - Command: `cd packages/core && uv run python -c "import os; os.environ['RIG_CLIENT_CERT']='ORIGINAL'; from stockimformation_core.rig_cli import _inject_human_cert_env; _inject_human_cert_env(); assert os.environ['RIG_CLIENT_CERT']=='ORIGINAL'"`
  - Expect: 已存在的 env 值不被文件内容覆盖

- [x] C5 验证 client init / daemon 子命令跳过注入
  - Covers: A5
  - Evidence: `rig_cli.py` `client init` / `daemon` 子命令分支不调用 `_inject_human_cert_env`
  - Expect: grep 显示这两个分支无 `_inject_human_cert_env()` 调用，或主入口逻辑显式跳过

- [x] C6 验证 client init 走 insecure channel
  - Covers: A6
  - Evidence: `grep -n "force_insecure" packages/core/src/stockimformation_core/rig_cli.py`
  - Expect: `client init` 处的 `RigGrpcClient` 实例化包含 `force_insecure=True`

- [x] C7 bootstrap 在 ~/.rig/ 有旧 cert 时仍成功
  - Covers: A6, A7
  - Command: `cd packages/core && uv run pytest tests/test_bootstrap_with_existing_cert.py -v`
  - Expect: 测试通过；模拟 `~/.rig/` 已存在 cert 时 `rig client init` 不会因 TLS handshake 失败

- [x] C8 agent 清 env 后 fail-loud 而非提权
  - Covers: A1, A8
  - Command: `cd packages/core && uv run pytest tests/test_agent_clear_env_fails.py -v`
  - Expect: 测试通过；清空 `RIG_CLIENT_CERT` 后 `RigGrpcClient` 抛 `FileNotFoundError`，不读 `~/.rig/client.crt`，不连成 human 身份
