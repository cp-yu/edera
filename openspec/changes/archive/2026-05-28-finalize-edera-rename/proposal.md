## Why

上一轮 `2026-05-27-rename-project-to-edera` 重命名了项目身份，但保留了 `rig` 作为控制面 CLI 名称、`RIG_*` 控制面 env 前缀、`~/.rig/` 用户目录、`proto/rig.proto` 服务定义和 `daemon` 术语，理由是"控制面与项目面分离"。该立场在客户端/服务端拆分部署语境下不再成立——用户层只感知一个二进制、一组证书、一个家目录，"控制面"是实现细节，不应泄漏到命令名。该改造同时清理三个长期欠账：(1) `web` 进程双模式（内嵌 controller / BFF）；(2) `cli` 双模式（本地 EntityStore / gRPC）；(3) `~/.rig/` 混居客户端文件与 daemon sessions 数据。

## What Changes

- **BREAKING** 全量重命名命令、模块、proto、env、家目录、proto package；不保留 `rig` 别名、不保留 `RIG_*` env 兼容。
- **BREAKING** 拆分 console scripts 为 `edera`(CLI)、`edera-server`(后端引擎)、`edera-web`(网页 BFF)；删除 `edera`(无参) 启动 web 的隐式语义。
- **BREAKING** `edera-web` 改为纯 BFF：删除 `create_app(controller=...)` 内嵌路径，必须依赖运行中的 `edera-server`。
- **BREAKING** `edera` CLI 改为纯 gRPC：删除本地 `EntityStore` 直读路径，所有 entity/node/dag 操作走 `edera-server`。
- **BREAKING** `proto/rig.proto` → `proto/edera.proto`，package `rig.v1` → `edera.v1`；新增 `EntityService.Query(QueryRequest) returns (EntityList)` 取代 CLI 本地解析，保留 `List`。
- **BREAKING** Vendor 生成的 `*_pb2.py` / `*_pb2_grpc.py` 到 `packages/core/src/edera_core/proto/`，删除 `grpc_runtime.py` lazy 生成；提供 `scripts/gen_proto.sh` 重生成。
- **BREAKING** 客户端 / 服务端 env 完全分离：server 端 `EDERA_SERVER_BIND`(default `0.0.0.0:9090`)、`EDERA_SERVER_PUBLIC_HOST`(server cert SAN)、`EDERA_DATA_DIR`(default `~/.local/share/edera-server/`)、`EDERA_CONFIG_DIR`(无 default，flag 或 env)；客户端 `EDERA_SERVER_ADDR`(无 default)、`EDERA_CLIENT_CERT/KEY/CA_CERT`、`EDERA_IDENTITY`。
- **BREAKING** Bootstrap 端口硬绑 `127.0.0.1:9091`，不可配置外暴露；远程客户端首次 `client init` 必须通过 SSH 隧道。
- **BREAKING** BFF 不再持久化客户端证书：`edera-web` 启动时调用本地 bootstrap 的 `SystemService.InitClient(common_name="bff:web-console")` 拿 cert 进内存（TTL 7 天，重启自愈）。
- **BREAKING** `~/.rig/` → `~/.edera/`；daemon sessions 数据迁出客户端家目录，由 `EDERA_DATA_DIR` 管理；agent subprocess `--session-dir` 收 daemon 决定的绝对路径。
- **BREAKING** dev 模式开关 `RIG_ENV=dev` → `EDERA_DEV=1`（布尔开关，不假装环境枚举）。
- 合并 OpenSpec specs：归档 `rig-cli` + `rig-cli-full-crud` 为单一 `edera-cli`；归档 `rig-daemon-grpc` 为 `edera-server-grpc`。

## Capabilities

### New Capabilities

- `edera-cli`: 控制 CLI（`edera` 命令）的 binary 入口、子命令、身份声明、纯 gRPC 客户端契约和环境变量边界；吸收原 `rig-cli` + `rig-cli-full-crud` 全部 Requirements。
- `edera-server-grpc`: 后端引擎（`edera-server` 命令）的 gRPC service 定义、mTLS 传输、bootstrap 端口约束、agent 短期 cert 签发和 dev 模式语义；接替原 `rig-daemon-grpc`。
- `edera-web-bff`: 网页 BFF（`edera-web` 命令）作为纯 gRPC 客户端的启动语义、配置无知契约、BFF cert 内存模式和 `--bind/--port` flag 优先 + env fallback 行为。

### Modified Capabilities

- `project-identity`: console scripts 集合扩展为 `edera`/`edera-server`/`edera-web`；删除 `edera`(无参) 启动 web 的隐式入口；`Control CLI remains rig` 需求作废，并入 `edera-cli`。
- `daemon-data-directory`: daemon 数据目录从 `~/.rig/` 物理迁出至 `~/.local/share/edera-server/`（`EDERA_DATA_DIR` 控制），移除与客户端家目录的混居；环境变量从 `RIG_DAEMON_DATA_DIR` 改为 `EDERA_DATA_DIR`。
- `node-executor`: agent subprocess 注入 `EDERA_IDENTITY` 而非 `RIG_IDENTITY`；session 路径从 `~/.rig/sessions/{...}` 迁移至 `{EDERA_DATA_DIR}/sessions/{...}`，由 daemon 决定绝对路径。
- `llm-node-intervention`: 节点 stop / resume 命令名 `rig node` → `edera node`。
- `reflection-dag-pattern`: 反思 DAG 中 `rig entity query` / `rig dag trigger` 命令名同步。
- `bff-web-gateway`: BFF cert 改内存模式；删除 `RIG_BFF_DIR` 持久化目录；BFF 启动时调用本地 bootstrap 拿 cert；dev 模式开关从 `RIG_ENV=dev` 改为 `EDERA_DEV=1`。
- `local-web-console`: `edera-web` 改为纯 BFF；删除内嵌 controller 路径；删除对 `system.toml.web_host` 的硬校验；`--bind/--port` flag-first + env-fallback。

## Impact

- **代码**: `packages/core/src/edera_core/` 整体重构 — 删除 `main.py`（合并入 `cli.py` 与 `web/__main__.py`），重命名 `rig_cli.py` → `cli.py`、`daemon.py` → `server.py`，删除 `grpc_runtime.py`，新增 `proto/` 子包（vendor pb2），重写 `web/app.py` 单一 BFF 路径，删除 CLI 本地查询逻辑（约 250 行）。
- **Proto**: `proto/rig.proto` → `proto/edera.proto`，package `edera.v1`，新增 `EntityService.Query`；类 `RigDaemon`/`RigGrpcClient`/`RigProto` → `Server`/`GrpcClient`/`Proto`。
- **Env / 路径**: `RIG_*` 全量迁移至 `EDERA_*`；新增 `EDERA_SERVER_PUBLIC_HOST`、`EDERA_SERVER_BIND`、`EDERA_DEV`；删除 `RIG_BFF_DIR` 等持久化目录 env；`~/.rig/` → `~/.edera/`；daemon sessions 移至 `EDERA_DATA_DIR/sessions/`。
- **测试**: `tests/core/unit/test_rig_cli.py` → `test_cli.py`，所有 entity/node/dag 用例改走 module-scope `running_server` fixture（`conftest.py` 新增）+ 真 mTLS（fixture 内调用 `SystemService.InitClient` 注入 client cert env）；`test_core_architecture_overhaul.py` 同步重命名引用。
- **配置**: `pyproject.toml` console scripts 三件套；`dev.sh` 拆为 `edera-server` + `edera-web` 双进程启动；`Dockerfile` / `docker-compose.yaml` 同步；`config/system.toml` 删除 `web_host`/`web_port`（迁至 `edera-web` flag/env）。
- **OpenSpec**: 归档 `specs/rig-cli/`、`specs/rig-cli-full-crud/`、`specs/rig-daemon-grpc/`；新增 `specs/edera-cli/`、`specs/edera-server-grpc/`、`specs/edera-web-bff/`；同步 9 个 modified spec 中的命令 / env / 路径引用；`openspec/project.opsx.yaml` capability 集合同步。
- **文档**: `README.md` 启动命令更新为 `edera-server` / `edera-web` / `edera`；说明客户端 / 服务端部署拓扑；说明 bootstrap 必须通过 SSH 隧道。
