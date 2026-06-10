## Context

`packages/core/src/edera_core/grpc_client.py` 已封装 GraphService、ConfigService、QueryService 和部分 SystemService 能力，Web BFF 也已使用这些方法暴露控制面 API。`packages/core/src/edera_core/cli.py` 当前只暴露执行控制和部分 CRUD，缺少脚本化访问 DAG 定义、node type、handler、config、query 和 source 运维的入口。

## Goals / Non-Goals

**Goals:**
- 让 `edera` CLI 覆盖已有控制面 RPC，支持 agent 和脚本不经过 Web BFF 访问同一套 server 校验。
- 保持 CLI 为纯 gRPC client，数据操作继续由 `edera-server` 执行权限、schema 和存在性校验。
- 使用现有 argparse 风格和 JSON 输出格式，避免引入新的 CLI 框架或展示层。

**Non-Goals:**
- 不新增 protobuf RPC、数据库表、Web BFF route 或前端页面。
- 不在本阶段实现 `--output json|yaml|table`、分页统一、watch/tail 等 operator UX，这些属于 phase 3。
- 不改变已有 `entity`、`relation`、`skill`、`extension`、`event` 命令语义。

## Decisions

- 新增命令组直接映射已有 `GrpcClient` 方法。`dag` 定义管理使用 `graph_list_dags`、`graph_get_dag`、`graph_create_dag`、`graph_save_dag` 和 `graph_runtime_status`；`config` 使用 `config_*` 方法；`query` 使用 `query_*` 方法；`source repair-task` 使用 `system_create_repair_task`。这样避免在 CLI 层复制 server 端规则。
- `dag status` 继续表示 DagService 运行状态；新增 `dag show/export/import/save/runtime-status` 表示 GraphService 定义和 runtime graph 状态。替代方案是把定义命令放进 `graph` 命令组，但这会暴露内部 service 名称，用户语义更差。
- `node-type` 独立于现有 `node` 命令组。`node` 保持运行实例控制，`node-type` 表示 DB-backed node type 定义，避免 `edera node show` 同时可能指运行节点或 node type。
- `config entity-type` 只处理配置文件级 YAML CRUD；现有 `entity-type materialize` 继续处理字段物化维护。两个命令组不合并，避免把 schema 维护和配置文件编辑混在一个动词空间。
- 本阶段文件输入输出使用 JSON/TOML/YAML 的原始文本文件参数，命令结果仍打印 JSON。统一表格、YAML 输出和 stdout/file 切换留给 phase 3。

## Risks / Trade-offs

- 命令数量增加导致 `cli.py` 变大 -> 通过小型 parser/dispatcher helper 分组控制复杂度，不引入框架迁移。
- `dag` 同时包含运行和定义命令，用户可能混淆 -> 保留 `status/run/stop/retry` 的运行语义，定义命令使用 `show/export/import/save/create/list`，并在测试中覆盖路由。
- `config` 命令可能绕过 Web 的交互保护 -> server 端仍执行 ConfigService 校验，CLI 不做本地 source of truth 写入。
- QueryService 包含 advisory 领域查询 -> 放入 `query` 命令组而不是顶层 `advice/briefing`，避免污染顶层命令。
