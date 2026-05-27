## 1. Actions

- [x] A1 重写 `grpc_client.py::_channel_credentials()` 支持 PEM env 优先 + 文件 fallback
- [x] A2 引入 `RIG_DAEMON_DATA_DIR` 解析逻辑和默认路径选择（daemon 启动入口）
- [x] A3 实现 CA 自动生成（首次启动检测 `ca.key` 不存在则生成）
- [x] A4 实现 server cert 按需生成（基于 CA 签发，CN=`rig-daemon`）
- [x] A5 重写 executor `_agent_cert_env()` 为注入 PEM 内容（cert_pem / key_pem / ca_pem）
- [x] A6 daemon cert 签发函数改为返回 PEM str，不写文件系统
- [x] A7 session 路径从 `~/.rig/sessions/` 迁移到 `${data_dir}/sessions/`
- [x] A8 resume 逻辑调用签发函数重新生成 cert，不缓存旧 cert

## 2. Checks

- [x] C1 验证 grpc_client env PEM 加载路径
  - Covers: A1
  - Command: `python -c "import os; os.environ['RIG_CLIENT_CERT']='-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----'; from stockimformation_core.grpc_client import _load_pem; from pathlib import Path; assert _load_pem('RIG_CLIENT_CERT', Path('/nonexist')) == b'-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----'"`
  - Expect: env PEM 内容被 encode 为 bytes 返回

- [x] C2 验证 grpc_client 文件 fallback 路径
  - Covers: A1
  - Command: `python -c "import os; os.environ.pop('RIG_CLIENT_CERT', None); from stockimformation_core.grpc_client import _load_pem; from pathlib import Path; import tempfile, pathlib; f=tempfile.NamedTemporaryFile(suffix='.crt', delete=False, mode='w'); f.write('FAKEPEM'); f.close(); assert _load_pem('RIG_CLIENT_CERT', pathlib.Path(f.name)) == b'FAKEPEM'"`
  - Expect: 无 env 时从文件读取内容

- [x] C3 验证 daemon data dir 解析优先级
  - Covers: A2
  - Command: `python -c "import os; os.environ['RIG_DAEMON_DATA_DIR']='/tmp/test-rig-data'; from stockimformation_core.daemon import resolve_data_dir; assert str(resolve_data_dir(cli_arg=None)) == '/tmp/test-rig-data'"`
  - Expect: 环境变量优先于默认路径

- [x] C4 验证 CA 自动生成
  - Covers: A3
  - Command: `python -c "import tempfile; from pathlib import Path; from stockimformation_core.daemon import ensure_ca; d=Path(tempfile.mkdtemp()); ensure_ca(d); assert (d/'ca.key').exists(); assert (d/'ca.crt').exists(); assert oct((d/'ca.key').stat().st_mode)[-3:]=='600'"`
  - Expect: ca.key 和 ca.crt 生成，权限 0600

- [x] C5 验证 server cert 按需生成
  - Covers: A4
  - Command: `python -c "import tempfile; from pathlib import Path; from stockimformation_core.daemon import ensure_ca, ensure_server_cert; d=Path(tempfile.mkdtemp()); ensure_ca(d); ensure_server_cert(d, 'localhost'); assert (d/'server.crt').exists()"`
  - Expect: server.crt 基于 CA 签发生成

- [x] C6 验证 executor 注入 PEM 内容而非路径
  - Covers: A5, A6
  - Command: `python -c "from stockimformation_core.node.executor import _agent_cert_env; from types import SimpleNamespace; cert=SimpleNamespace(cert_pem='CERT_PEM', key_pem='KEY_PEM', ca_pem='CA_PEM'); env=_agent_cert_env(cert); assert env['RIG_CLIENT_CERT']=='CERT_PEM'; assert env['RIG_CLIENT_KEY']=='KEY_PEM'; assert env['RIG_CA_CERT']=='CA_PEM'"`
  - Expect: env dict 包含 PEM 文本内容，无文件路径

- [x] C7 验证 session 路径基于 data dir
  - Covers: A7
  - Evidence: grep `session` in executor.py
  - Expect: session 路径构造使用 `data_dir / "sessions"` 而非 `~/.rig/sessions`

- [x] C8 验证 resume 重新签发 cert
  - Covers: A8
  - Evidence: resume 代码路径调用 `sign_agent_cert()` 而非从缓存取
  - Expect: resume 分支无 cert 缓存逻辑，每次调用签发函数

## Remediation

- [x] [code_fix] A2 缺少用户可见 daemon 启动 `--data-dir` 参数；入口需把 `--data-dir` 传给 `stockimformation_core.daemon.serve(..., data_dir=...)`
