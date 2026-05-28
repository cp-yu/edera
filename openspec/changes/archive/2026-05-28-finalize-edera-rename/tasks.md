## 1. Actions

- [x] A1 重命名 `proto/rig.proto` 为 `proto/edera.proto`，将 `package rig.v1` 改为 `package edera.v1`，并在 `EntityService` 中新增 `Query(QueryRequest{string expression, string identity}) returns (EntityList)` rpc，保留 `List(EntityQuery)`
- [x] A2 编写 `scripts/gen_proto.sh` 重生成脚本，生成 `edera_pb2.py` / `edera_pb2_grpc.py` 至 `packages/core/src/edera_core/proto/`，新建 `__init__.py` 暴露 pb2 / pb2_grpc 符号，删除 `packages/core/src/edera_core/grpc_runtime.py`
- [x] A3 重命名 `packages/core/src/edera_core/daemon.py` 为 `server.py`，类 `RigDaemon` → `Server`，类 `_DagService` / `_NodeService` / `_EntityService` / `_SystemService` 内部 import 迁至 `from edera_core.proto import edera_pb2 as pb2, edera_pb2_grpc as pb2_grpc`，bootstrap 监听硬绑 `127.0.0.1:9091` 并删除 `bootstrap_address` 入参
- [x] A4 在 `server.py` 中实现 `EntityService.Query` 服务端 dispatch：搬迁 CLI 现有的 `_query`、`_relation_filters`、`_node_output_filters`、`_runtime_filters`、`_query_relations`、`_query_node_outputs`、`_query_runtime_facts` 解析逻辑至 server 侧，按 expression 字符串分发，无法解析时返回 `INVALID_ARGUMENT` 与支持字段列表
- [x] A5 在 `server.py` 中扩展 `SystemService.InitClient` 处理 `common_name="bff:web-console"` 时签发 TTL 7 天的 BFF cert；扩展 `ensure_server_cert` 读取 `EDERA_SERVER_PUBLIC_HOST` 设置 SAN，在 SAN 与已存在 server.crt 不一致时重签
- [x] A6 重命名 `packages/core/src/edera_core/rig_cli.py` 为 `cli.py`，类 `RigGrpcClient` 在 `grpc_client.py` 中改名为 `GrpcClient`，删除本地 `EntityStore` 直读路径（`_query`、`_readable_entities`、`_check_write`、`_identity_permissions`、`_query_relations`、`_query_node_outputs`、`_query_runtime_facts`、`_relation_filters`、`_node_output_filters`、`_runtime_filters` 等约 250 行），所有 entity / node / dag 子命令通过 `GrpcClient` 走 server，新增 `--server` flag 和 `EDERA_SERVER_ADDR` 环境变量解析（无 default）
- [x] A7 删除 `packages/core/src/edera_core/main.py`；新建 `packages/core/src/edera_core/web/__main__.py` 作为 `edera-web` 入口：解析 `--bind` / `--port` flag（fallback 到 `EDERA_WEB_BIND` / `EDERA_WEB_PORT` env，default `127.0.0.1:8000`），启动时调 `127.0.0.1:9091` 的 `SystemService.InitClient(common_name="bff:web-console")` 拿 BFF cert PEM 进内存，构造 `GrpcClient` 连 `EDERA_SERVER_ADDR`
- [x] A8 重写 `packages/core/src/edera_core/web/app.py` 中的 `create_app`：删除 `controller` / `config_dir` / `handler_registry` 入参，删除 `owns_grpc_client` 双模式分支与 `RIG_BFF_DIR` 持久化目录逻辑，签名简化为 `create_app(grpc_client)`
- [x] A9 在 `pyproject.toml` 中替换 console scripts 为 `edera = "edera_core.cli:main"`、`edera-server = "edera_core.server:main"`、`edera-web = "edera_core.web.__main__:main"`，删除任何 `rig` 入口
- [x] A10 全仓批量替换环境变量与路径：`RIG_IDENTITY` → `EDERA_IDENTITY`、`RIG_CLIENT_CERT/KEY` → `EDERA_CLIENT_CERT/KEY`、`RIG_CA_CERT` → `EDERA_CA_CERT`、`RIG_DAEMON_ADDR` → `EDERA_SERVER_ADDR`（client 视角）、`RIG_DAEMON_DATA_DIR` → `EDERA_DATA_DIR`、`RIG_ENV=dev` → `EDERA_DEV=1`、`~/.rig/` → `~/.edera/`，新增 `EDERA_SERVER_BIND`、`EDERA_SERVER_PUBLIC_HOST`、`EDERA_CONFIG_DIR`、`EDERA_WEB_BIND`、`EDERA_WEB_PORT`、`EDERA_LOG_LEVEL` 解析；删除 `RIG_BFF_DIR` 与 `RIG_DAEMON_BOOTSTRAP_ADDR` 引用
- [x] A11 修改 `node/executor.py` 的 agent subprocess 注入：环境变量 `RIG_IDENTITY` → `EDERA_IDENTITY`，`--session-dir` 路径模板从 `~/.rig/sessions/{...}` 改为 `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/{cycle_id}/`，绝对路径由 server 决定
- [x] A12 在 `config/system.toml` 与 `packages/core/src/edera_core/config/schema.py` 中删除 `web_host` / `web_port` 字段；`dev.sh` 拆分为同时启动 `edera-server --config-dir ./config &` 与 `edera-web`；`Dockerfile` / `docker-compose.yaml` 同步使用三件套 console scripts；`README.md` 更新启动命令并说明客户端 / 服务端拓扑与 SSH 隧道首次 init 流程
- [x] A13 重命名测试：`tests/core/unit/test_rig_cli.py` → `tests/core/unit/test_cli.py`，`tests/conftest.py` 新增 `module`-scope `running_server` fixture（启 `Server(tmp_path, "127.0.0.1:0")`，通过 `SystemService.InitClient` 签发 client cert 并注入 `EDERA_CLIENT_CERT/KEY/CA_CERT` / `EDERA_SERVER_ADDR` env），所有 entity / node / dag 用例的 `monkeypatch.setattr("sys.argv", ["rig", ...])` 改为 `["edera", ...]` 并依赖该 fixture；`tests/core/unit/test_core_architecture_overhaul.py` 内 `RigDaemon` / `RigGrpcClient` 引用同步改名
- [x] A14 将 `openspec/specs/rig-cli/`、`openspec/specs/rig-cli-full-crud/`、`openspec/specs/rig-daemon-grpc/` 三个目录移除（archive 时由 OpenSpec 工具处理），并在 `openspec/specs/` 下生成新 `edera-cli/`、`edera-server-grpc/`、`edera-web-bff/` 终态 spec；同步更新 `daemon-data-directory`、`node-executor`、`bff-web-gateway`、`local-web-console`、`project-identity`、`reflection-dag-pattern`、`llm-node-intervention` 七个 spec 中的命令 / env / 路径引用
- [x] A15 同步 `openspec/project.opsx.yaml`：移除 `cap.core.rig-cli`、`cap.core.rig-cli-full-crud`、`cap.core.rig-daemon-grpc` 三条 capability，新增 `cap.core.edera-cli`、`cap.core.edera-server-grpc`、`cap.web.edera-web-bff`，更新 `cap.core.project-identity` / `cap.core.daemon-data-directory` / `cap.operations.node-executor` / `cap.web.local-web-console` / `cap.core.bff-web-gateway` / `cap.operations.llm-node-intervention` / `cap.operations.reflection-dag-pattern` 七条 capability 的 intent

## 2. Checks

- [x] C1 验证 proto 重命名与 Query rpc
  - Covers: A1
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "gRPC Service 定义" / Scenario "Proto package 为 edera.v1"
  - Command: `grep -E '^package|^service|EntityService\.Query|EntityService\.List' proto/edera.proto`
  - Expect: 输出包含 `package edera.v1;`、`service EntityService`，且 `EntityService` 中同时存在 `Query` 与 `List` rpc 定义；`proto/rig.proto` 不存在

- [x] C2 验证 vendor pb2 入库且启动不调 protoc
  - Covers: A2
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "Vendor 生成的 pb2" / Scenario "pb2 文件入库"
  - Command: `ls packages/core/src/edera_core/proto/ && git ls-files packages/core/src/edera_core/proto/ && grep -rn "grpc_tools.protoc\|grpc_runtime" packages/core/src/edera_core/`
  - Expect: 目录含 `__init__.py` / `edera_pb2.py` / `edera_pb2_grpc.py` 且均被 git 跟踪；源码中无 `grpc_tools.protoc` 引用与 `grpc_runtime` 模块

- [x] C3 验证 Server 类与 bootstrap 硬绑 localhost
  - Covers: A3
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "Bootstrap 端口硬绑 localhost" / Scenario "Bootstrap 监听限制"
  - Command: `grep -nE "class Server|bootstrap.*127\.0\.0\.1:9091|RigDaemon|bootstrap_address" packages/core/src/edera_core/server.py`
  - Expect: 文件中存在 `class Server` 与 bootstrap 硬绑 `127.0.0.1:9091` 的代码；不存在 `RigDaemon` 类或 `bootstrap_address` 入参

- [x] C4 验证 EntityService.Query 行为
  - Covers: A4
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "gRPC Service 定义" / Scenario "EntityService 提供 Query"
  - Command: `pytest tests/core/unit/test_cli.py -k "query" -v`
  - Expect: 既有 `entity query "type=stock"`、`relation_type=...`、`node_output:...`、`runtime:...` 表达式的端到端测试通过；server 侧解析失败返回 `INVALID_ARGUMENT`

- [x] C5 验证 BFF cert 与 server SAN 行为
  - Covers: A5
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "BFF 短期证书签发" / Scenario "BFF 启动时拿 cert"
  - Command: `pytest tests/core/unit/test_core_architecture_overhaul.py -k "bff_cert or server_cert_san" -v`
  - Expect: 调 `SystemService.InitClient(common_name="bff:web-console")` 返回 TTL 7 天的 PEM；`EDERA_SERVER_PUBLIC_HOST` 变化时 server.crt 被重签

- [x] C6 验证 CLI 纯 gRPC 与本地路径删除
  - Covers: A6
  - Verifies: `specs/edera-cli/spec.md` / Requirement "纯 gRPC 客户端契约" / Scenario "所有数据操作走 gRPC"
  - Command: `grep -nE "EntityStore\(|load_app_config|_query\(|_readable_entities|_check_write\(" packages/core/src/edera_core/cli.py`
  - Expect: 输出为空（除 `handler-validate` 子命令外，`cli.py` 不再实例化 `EntityStore`、不再调用 `load_app_config`、不再含本地查询函数）

- [x] C7 验证 edera-web 入口与配置无知契约
  - Covers: A7, A8
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "配置无知契约" / Scenario "不读 config 目录"
  - Command: `grep -nE "load_app_config|PipelineController\(|controller=|config_dir=|owns_grpc_client" packages/core/src/edera_core/web/app.py packages/core/src/edera_core/web/__main__.py`
  - Expect: 输出为空；`web/__main__.py` 通过 `SystemService.InitClient` 拿 BFF cert，`web/app.py` 中 `create_app` 仅接受 `grpc_client` 参数

- [x] C8 验证 console scripts 三件套
  - Covers: A9
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI binary 入口" / Scenario "Console scripts 集合"
  - Command: `grep -A 5 "\[project.scripts\]" packages/core/pyproject.toml`
  - Expect: 仅注册 `edera = "edera_core.cli:main"`、`edera-server = "edera_core.server:main"`、`edera-web = "edera_core.web.__main__:main"`，无 `rig` 注册

- [x] C9 验证 RIG_* 环境变量与 ~/.rig/ 路径全量清除
  - Covers: A10
  - Verifies: `specs/edera-cli/spec.md` / Requirement "gRPC Client mTLS 加载" / Scenario "gRPC client 层只看环境变量"
  - Command: `grep -rn "RIG_\|~/.rig/\|\\.rig\b" packages/core/src/edera_core/ tests/ proto/ scripts/ dev.sh Dockerfile docker-compose.yaml README.md config/ 2>/dev/null | grep -v archive | grep -v __pycache__`
  - Expect: 输出为空（除 OpenSpec archive 目录外，仓库中无 `RIG_*` env 与 `~/.rig/` 路径残留）

- [x] C10 验证 agent subprocess 身份与 session 注入
  - Covers: A11
  - Verifies: `specs/node-executor/spec.md` / Requirement "EDERA_IDENTITY 环境变量注入" / Scenario "注入节点身份"
  - Command: `pytest tests/core/unit/test_node_context.py tests/core/integration/test_per_dag.py -k "identity or session_dir" -v`
  - Expect: agent subprocess 接收到 `EDERA_IDENTITY=node:llm-analyze` 与基于 `EDERA_DATA_DIR` 的 `--session-dir` 绝对路径；不出现 `RIG_IDENTITY` 与 `~/.rig/sessions/` 路径

- [x] C11 验证部署脚本与 system.toml
  - Covers: A12
  - Verifies: `specs/local-web-console/spec.md` / Requirement "Local-only web binding" / Scenario "不读 system.toml web 字段"
  - Evidence: `dev.sh` 的 diff 同时包含 `edera-server` 与 `edera-web` 两条启动命令；`config/system.toml` 与 `packages/core/src/edera_core/config/schema.py` 不再含 `web_host` / `web_port` 字段；`Dockerfile` / `docker-compose.yaml` 使用新 console scripts；`README.md` 含客户端 / 服务端拓扑与 SSH 隧道首次 init 章节
  - Expect: 上述 diff 全部到位且 `grep -n "web_host\|web_port" config/system.toml packages/core/src/edera_core/config/schema.py` 输出为空

- [x] C12 验证测试 fixture 与 CLI 端到端
  - Covers: A13
  - Verifies: `specs/edera-cli/spec.md` / Requirement "权限检查" / Scenario "权限拒绝"
  - Command: `pytest tests/core/unit/test_cli.py tests/core/unit/test_core_architecture_overhaul.py -v`
  - Expect: 所有 CLI 用例通过 `running_server` fixture 在真 mTLS 下启动 server 完成端到端调用；既有 `node:reader` 写权限拒绝、`human` 身份无限制、`entity query` 等用例继续通过；测试代码中无 `RigDaemon` / `RigGrpcClient` 引用

- [x] C13 验证 OpenSpec spec 与 capability 集合切换
  - Covers: A14, A15
  - Verifies: `specs/project-identity/spec.md` / Requirement "Project command and control command" / Scenario "Old project commands removed"
  - Command: `openspec validate finalize-edera-rename --type change --json && grep -E "rig-cli|rig-daemon-grpc|rig-cli-full-crud|cap\.core\.rig-" openspec/specs/ openspec/project.opsx.yaml -r 2>/dev/null | grep -v archive`
  - Expect: change 校验通过；`openspec/specs/` 下不再有 `rig-*` 目录；`project.opsx.yaml` 不再含 `cap.core.rig-*` capability 且新增 `cap.core.edera-cli` / `cap.core.edera-server-grpc` / `cap.web.edera-web-bff` 三条
