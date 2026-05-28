## Context

上一轮 `2026-05-27-rename-project-to-edera` 在"控制面 vs 项目面分离"的立场下，保留了 `rig` CLI、`RIG_*` env、`~/.rig/`、`proto/rig.proto` 与 `daemon` 术语。本次改造的触发因素是部署拓扑明确化：`edera-server` + `edera-web` 跑在服务端、`edera` CLI 跑在客户端、浏览器从客户端连服务端 Web 页面。在该拓扑下，"控制面 vs 项目面"的分割不再服务任何用户视角——客户端用户只感知一组命令、一组证书、一个家目录。同时三处架构欠账（web 双模式、CLI 双模式、`~/.rig/` 混居 daemon sessions）借此次重命名一并清理，避免后续再 touch 同一批文件。

约束：

- dev 阶段、无外部消费者（无 Rust tonic 客户端、无外部脚本依赖 `rig` 命名）。
- 用户已确认完全重构、不保留 `rig` 别名、不保留 `RIG_*` 兼容、proto package 一并改名、删除 `EDERA_BFF_DIR` 等持久化目录。
- 部署目标：客户端机 / 服务端机分离，需要支持远程 mTLS 连接。

## Goals / Non-Goals

**Goals:**

- 单一品牌：所有面向用户的命令、env、家目录、proto package、模块名统一以 `edera` 为根。
- 三命令拓扑：`edera`(CLI 控制) / `edera-server`(后端引擎) / `edera-web`(网页 BFF) 各自单进程入口。
- 单一数据路径：`edera-web` 纯 BFF（无内嵌 controller）、`edera` CLI 纯 gRPC（无本地 EntityStore）。
- 客户端 / 服务端 env 语义分离，避免 bind addr 与 connect addr 共用一个 env。
- Bootstrap 端口安全姿态显式化：硬绑 `127.0.0.1:9091`，远程客户端走 SSH 隧道。
- BFF 无状态：cert 不落盘，启动时调本地 bootstrap 拿 cert 进内存。
- 测试基础设施统一：`module`-scope `running_server` fixture + 真 mTLS。

**Non-Goals:**

- 不保留任何 `rig` 别名或 `RIG_*` env 兼容（user 明确）。
- 不引入 admin token / 鉴权 middleware（依赖 SSH 隧道 + bootstrap localhost-only）。
- 不引入 BFF cert 续签机制（7 天 TTL + 重启自愈）。
- 不引入 proto 类型化 filter 消息（YAGNI，`Query` rpc 用字符串语法即可）。
- 不引入 `dev/staging/prod` 环境枚举（只有 `EDERA_DEV=1` 单一布尔开关）。
- 不修改 `openspec/changes/archive/**` 历史制品。
- 不在本变更内拆 server 的水平扩展、HA、observability 等运行时增强。

## Decisions

### Console scripts 三件套与模块落点

```
edera        = "edera_core.cli:main"
edera-server = "edera_core.server:main"
edera-web    = "edera_core.web.__main__:main"
```

`main.py` 整体删除——其原有的 "argv 分流到 rig_cli" 逻辑随 `edera`(无参) 启动 web 的语义一并消失。`rig_cli.py` → `cli.py`、`daemon.py` → `server.py`，平铺改名而非升包。`web/app.py` 保留，新增 `web/__main__.py` 承载 `edera-web` 入口。

**替代方案：**(a) 平铺新建文件 — 引入孤儿模块；(b) 引入子包 — `cli/`、`server/` 目前各自只有一个 dispatch 入口，过度结构。

### `edera-web` 纯 BFF

`create_app(config_dir, controller, handler_registry, grpc_client)` 简化为 `create_app(grpc_client)`。删除 `owns_grpc_client` 分支、删除 `PipelineController` 在 web 进程内的实例化、删除 `RIG_DAEMON_ADDR` 探测分流。`edera-web` 启动顺序：

1. 读 `--bind`/`--port` flag 或 `EDERA_WEB_BIND`/`EDERA_WEB_PORT` env（flag 优先），default `127.0.0.1:8000`。
2. 调本地 `127.0.0.1:9091` 的 `SystemService.InitClient(common_name="bff:web-console")` 拿 BFF client cert（PEM 进内存）。
3. 用该 cert 构造 `GrpcClient` 连 `EDERA_SERVER_ADDR`（必须显式设置）。
4. `create_app(grpc_client)` 启 FastAPI / SPA。

**替代方案：**(a) 保留双模式 — 与"分离部署"语义自相矛盾；(c) systemd Credentials 投递 cert — 绑死 systemd，docker / 裸跑场景失效。

### `edera` CLI 纯 gRPC

删除 `_query`、`_readable_entities`、`_query_relations`、`_query_node_outputs`、`_query_runtime_facts`、`_check_write`、`_identity_permissions`、`_relation_filters`、`_node_output_filters`、`_runtime_filters` 等本地路径（约 250 行）。所有 entity / node / dag 子命令通过 `GrpcClient` 走 `edera-server`。`handler-validate` 子命令保留为离线 dev 工具特例（不走 gRPC）。`client init` 与 `server` 子命令保留为不需要 gRPC 主端口的特例。

新增 proto rpc `EntityService.Query(QueryRequest{string expression, string identity}) returns (EntityList)`，server 端实现原 CLI 的字符串语法解析（`type=X AND field>Y`、`relation_type=X AND to=Y`、`node_output:<id>`、`runtime:<scope>`），逻辑单点化。保留 `EntityService.List`(by type 简单列表)。

**替代方案：**(b) 类型化 filter 消息 — 服务多语言客户端，目前不存在；(c) 多个细粒度 query rpc — proto 膨胀。

### Proto vendor + scripts 重生成

`grpc_runtime.py` 删除（lazy 生成路径不复存在）。生成的 pb2 vendor 到 `packages/core/src/edera_core/proto/`：

```
packages/core/src/edera_core/proto/
├── __init__.py        # 暴露 edera_pb2 / edera_pb2_grpc
├── edera_pb2.py        # vendor，git 跟踪
└── edera_pb2_grpc.py   # vendor，git 跟踪
```

`scripts/gen_proto.sh` 重生成命令，proto 改动需手动跑该脚本并入 git。

**替代方案：**(a) 保持 lazy 生成 — mypy/IDE 看不到 pb2，类型缺失；(c) vendor + CI 校验"proto 改了未重生成" — 等真出问题再加。

`package rig.v1` → `package edera.v1`：保留 `v1` 版本号（proto 是 wire 协议，版本是少数值得"过度设计"的地方）。

### Env 客户端 / 服务端分离

| 类别 | 服务端 | 客户端 |
|---|---|---|
| 主端口 | `EDERA_SERVER_BIND`(default `0.0.0.0:9090`) | `EDERA_SERVER_ADDR`(无 default) |
| Bootstrap | （硬绑 `127.0.0.1:9091`，无 env） | `EDERA_SERVER_BOOTSTRAP_ADDR`(client init 用，无 default) |
| 证书 SAN | `EDERA_SERVER_PUBLIC_HOST`(server cert SAN，启动时签 cert 用) | — |
| 数据目录 | `EDERA_DATA_DIR`(daemon 存 CA / server cert / sessions，default `~/.local/share/edera-server/`) | `EDERA_HOME`(default `~/.edera/`，存 client cert / config) |
| 配置目录 | `EDERA_CONFIG_DIR`(无 default，flag-first + env-fallback) | — |
| 客户端证书 | — | `EDERA_CLIENT_CERT/KEY/CA_CERT`(PEM 内容) |
| 身份 | — | `EDERA_IDENTITY`(default `human`) |
| Web 监听 | `EDERA_WEB_BIND`/`EDERA_WEB_PORT`(default `127.0.0.1:8000`) | — |
| Dev 模式 | `EDERA_DEV=1`(布尔开关，CLI / server / web 共享) | `EDERA_DEV=1` |
| 日志级别 | `EDERA_LOG_LEVEL`(default `info`) | `EDERA_LOG_LEVEL` |

`config/system.toml.web_host` / `web_port` 删除（web 进程不再读 system config）。

### Bootstrap 端口硬绑 localhost

`Server` 构造时 bootstrap 监听强制 `127.0.0.1:9091`，不暴露 env / flag 配置。远程客户端首次拿 cert 必须 SSH 隧道 (`ssh -L 9091:localhost:9091 server.lan`)。文档明示该约束。

**替代方案：**(b) admin token 鉴权 — 引入 token 生命周期管理，scope 灾难；(c) 推给运维防火墙 — 没有强制约束的 spec 等于祝福"反正会出事"。

### `~/.edera/` 物理分离

```
客户端 ~/.edera/                    服务端 ~/.local/share/edera-server/
├── client.crt                       ├── ca.crt
├── client.key                       ├── ca.key
├── ca.crt                            ├── server.crt
└── config.json                       ├── server.key
                                       └── sessions/
                                              └── {dag}/{instance}/{cycle}/
```

agent subprocess `--session-dir` 收 daemon 决定的绝对路径（`{EDERA_DATA_DIR}/sessions/{dag}/{instance}/{cycle}/`），不假设位置。

### BFF cert 内存模式

`SystemService.InitClient(common_name="bff:web-console")` TTL 7 天，签发后 PEM 注入 `edera-web` 进程内存（不写盘）。BFF 进程通常按部署生命周期（容器重建、systemd reload）远早于 7 天重启，重启时重新 init 自愈。删除 `EDERA_BFF_DIR` / `RIG_BFF_DIR` 持久化目录 env。

### dev 模式：单一布尔开关

`EDERA_DEV=1` 同时影响 server（接受无 cert 连接、默认身份 `human:dev`）与 client（gRPC channel insecure）。命名为 `EDERA_DEV` 而非 `EDERA_ENV=dev`：当前只有 dev 这一个特殊行为，没必要假装环境枚举；真有 staging/prod 配置语义需求再加。

### 测试改写：`module`-scope server fixture + 真 mTLS

`tests/conftest.py` 新增 `running_server` fixture（`module` scope）：

1. `tmp_path_factory` 准备 daemon data_dir。
2. `Server(data_dir, "127.0.0.1:0")` 启动（端口 0 = OS 自动分配）。
3. fixture 通过 `SystemService.InitClient` 签发 client cert，注入 `EDERA_CLIENT_CERT/KEY/CA_CERT`、`EDERA_SERVER_ADDR`。
4. fixture 完毕停 server。

`test_rig_cli.py` → `test_cli.py`，每个 case 仅改 `monkeypatch.setattr("sys.argv", ["edera", ...])`，其余基本不动。`test_core_architecture_overhaul.py` 内 `RigDaemon` / `RigGrpcClient` 等引用同步重命名。

**替代方案：**(b) Mock GrpcClient — permission 校验等语义在 server 端，mock 容易"测了一个不存在的世界"；(c) 直接测 service 层 — 跳过 CLI argparse / output 格式 / `--identity` 注入逻辑；(d) 拆两层测试 — 双重维护成本。

### OpenSpec spec 处理：`removed:` + `added:`

`rig-cli` + `rig-cli-full-crud` → `edera-cli`（合并）；`rig-daemon-grpc` → `edera-server-grpc`；新增 `edera-web-bff`。改用 `removed:` + `added:` 而非 `renamed:`，避免 OpenSpec 工具 rename 机制的不确定性。

被波及需 `modified:` 的 spec：`project-identity`、`daemon-data-directory`、`node-executor`、`pipeline-control`、`llm-node-intervention`、`llm-session-reuse`、`reflection-dag-pattern`、`multi-node-retry`、`bff-web-gateway`、`local-web-console`。

## Risks / Trade-offs

- **[大块原子重命名导致 review 难度]** → tasks.md 内分 8 phase 排版，每 phase 跑通编译后 commit，方便回看；不拆 change 避免同文件多次改写。
- **[远程客户端首次 init 需要 SSH 隧道，体验略差]** → 文档与 `client init` --help 说明该约束；运维场景中 SSH 隧道是标配。
- **[BFF cert 7 天 TTL + 不续签：长跑进程会过期]** → BFF 进程实际部署生命周期远短于 7 天；过期触发 crash → 重启 → 重 init 自愈；监控告警可覆盖异常情况。
- **[proto vendor 后忘记重生成]** → `scripts/gen_proto.sh` 提供单命令重生成；后续若真出问题，加 pre-commit hook 校验 proto 与 pb2 时间戳。
- **[`EntityService.Query` 字符串语法解析迁到 server，错误信息变远]** → server 端解析失败时返回结构化 `INVALID_ARGUMENT` + 支持字段列表；CLI 直接显示。
- **[`module`-scope server fixture 共享状态污染]** → 每个 test 用唯一 entity id（已是惯例）；如有冲突可降级为 `function` scope。
- **[server 端 `EDERA_SERVER_PUBLIC_HOST` 与已存在 server.crt SAN 不匹配时需重签]** → server 启动时检测，若不匹配则用新 SAN 重签 server.crt；旧 client cert 仍由原 CA 签发，不受影响。
- **[`EDERA_DEV=1` 同时影响 client 与 server，单机单 env 单进程外可能误用]** → 文档明示 dev 模式仅用于本机开发；server 启动时若同时检测到 `EDERA_DEV=1` 与外部网络监听（非 127.0.0.1）应输出 WARN。
- **[OpenSpec spec 大批 `removed:` + `added:` 导致 archive 后历史不连续]** → 新 spec 在 Purpose 节注明"接替原 rig-* spec"，给读者导航锚点。

## Migration Plan

不提供旧名兼容 / 回滚路径——dev 阶段、user 明确拒绝。Phase 划分（详细步骤见 tasks.md）：

1. Proto 改名 + vendor pb2。
2. `server.py` 改造（含 env 与 bootstrap 硬绑）。
3. CLI 纯 gRPC 改造（含 `EntityService.Query` 实现）。
4. Web 纯 BFF 改造（含 BFF cert 内存模式）。
5. 全量 env / 路径改名扫描。
6. 测试改写（含新 fixture）。
7. OpenSpec spec 改写（含 `modified:` 同步）。
8. 文档与部署脚本更新。

每个 phase 跑通编译 + 测试后 commit，便于回看；不分 PR、单一 change 一次合并。

## Open Questions

无。所有关键技术决策均已在 grill 流程中拍板。
