---
capabilities:
  - cap.core.edera-cli
---
# edera-cli Specification

## Purpose
定义 `edera` 控制 CLI 的完整子命令集、身份声明、gRPC 客户端契约、mTLS 加载和输出格式。
## Requirements
### Requirement: CLI binary 入口
系统 SHALL 提供名为 `edera` 的 CLI binary，作为 agent 和人类访问 Edera 控制面能力的统一入口。`edera` 是控制 CLI 的命令名，与 `edera-server`（后端引擎）、`edera-web`（网页 BFF）三个 console scripts 一同构成完整入口集合。

#### Scenario: CLI 可执行
- **WHEN** 用户或 agent 在终端执行 `edera --help`
- **THEN** 系统 SHALL 输出可用子命令列表（entity、relation、entity-type、node、node-type、skill、dag、event、system、client、config、query、source、handler、extension、handler-validate）

#### Scenario: 版本查询
- **WHEN** 用户执行 `edera --version`
- **THEN** 系统 SHALL 输出当前版本号

#### Scenario: Console scripts 集合
- **WHEN** 检查包的 console scripts
- **THEN** 系统 SHALL 注册 `edera = "edera_core.cli:main"`、`edera-server = "edera_core.server:main"`、`edera-web = "edera_core.web.__main__:main"`

### Requirement: 身份声明
`edera` CLI SHALL 支持双身份模式：通过 `EDERA_IDENTITY` 环境变量设置默认身份，通过 `--identity` flag 覆盖。

#### Scenario: 环境变量身份
- **WHEN** 环境变量 `EDERA_IDENTITY=node:llm-analyze` 已设置，用户执行 `edera entity get stock:AAPL`
- **THEN** 系统 SHALL 以 `node:llm-analyze` 身份执行权限检查

#### Scenario: Flag 覆盖环境变量
- **WHEN** 环境变量 `EDERA_IDENTITY=node:llm-analyze` 已设置，用户执行 `edera --identity human entity get stock:AAPL`
- **THEN** 系统 SHALL 以 `human` 身份执行权限检查，忽略环境变量

#### Scenario: 无身份声明
- **WHEN** 未设置 `EDERA_IDENTITY` 且未传 `--identity`
- **THEN** 系统 SHALL 以 `human` 身份作为默认值

### Requirement: 权限检查
`edera` CLI SHALL 通过 `edera-server` 在执行 entity 操作时检查调用者身份对应的 entity_permissions。

#### Scenario: 权限允许
- **WHEN** 身份为 `node:llm-analyze`，该节点配置 `entity_permissions: {stock: {sentiment: read-write}}`，执行 `edera entity update stock:AAPL --field sentiment --value bearish`
- **THEN** 系统 SHALL 允许操作并执行更新

#### Scenario: 权限拒绝
- **WHEN** 身份为 `node:llm-analyze`，该节点未配置对 `stock.code` 的写权限，执行 `edera entity update stock:AAPL --field code --value 001`
- **THEN** 系统 SHALL 拒绝操作并输出 "Permission denied: node:llm-analyze cannot write stock.code"

#### Scenario: Human 身份无限制
- **WHEN** 身份为 `human`，执行任意 entity 操作
- **THEN** 系统 SHALL 允许操作（human 身份不受 entity_permissions 限制）

### Requirement: 纯 gRPC 客户端契约
`edera` CLI SHALL 作为纯 gRPC client 连接 `edera-server`。所有数据子命令 MUST 通过 gRPC 调用 server，MUST NOT 直接读取 `EntityStore` 或 config 目录。

#### Scenario: 所有数据操作走 gRPC
- **WHEN** 用户执行 `edera entity get`、`edera node status`、`edera dag run` 等任意数据子命令
- **THEN** CLI SHALL 通过 `GrpcClient` 调用 `edera-server`，不实例化 `EntityStore`、不调用 `load_app_config`

#### Scenario: handler-validate 离线特例
- **WHEN** 用户执行 `edera handler-validate <path>`
- **THEN** CLI SHALL 直接读取 handler 文件并执行 schema 校验，MUST NOT 连接 gRPC server

#### Scenario: client init 与 edera-server 特例
- **WHEN** 用户执行 `edera client init` 或 `edera-server` 命令
- **THEN** 命令 SHALL 不通过 gRPC 主端口；`client init` 走 bootstrap 端口，`edera-server` 自身即 server

### Requirement: gRPC Client mTLS 加载
`edera` CLI SHALL 作为 gRPC client 连接 `edera-server`。证书加载语义：gRPC client 层 SHALL 仅从环境变量读取 PEM 内容，不读文件系统；文件读取由 CLI 入口层在 dispatch 子命令前显式完成。

#### Scenario: gRPC 连接 server
- **WHEN** 用户执行任意 `edera` 数据子命令
- **THEN** CLI SHALL 通过 gRPC 连接 `edera-server`，使用 mTLS 认证

#### Scenario: gRPC client 层只看环境变量
- **WHEN** `GrpcClient` 实例化（非 `EDERA_DEV` 模式）
- **THEN** 系统 SHALL 仅从 `EDERA_CLIENT_CERT` / `EDERA_CLIENT_KEY` / `EDERA_CA_CERT` 环境变量读取 PEM 内容
- **AND** SHALL NOT 访问 `~/.edera/` 或任何文件系统路径

#### Scenario: 环境变量 PEM 内容缺失即失败
- **WHEN** `EDERA_CLIENT_CERT`、`EDERA_CLIENT_KEY`、`EDERA_CA_CERT` 任一环境变量未设置，且未启用 `EDERA_DEV` 模式
- **THEN** `GrpcClient` SHALL 抛出 `FileNotFoundError`（或等价错误），SHALL NOT 静默回退到任何文件路径

#### Scenario: 人类 CLI 入口显式注入
- **WHEN** 用户执行 human-facing 子命令（如 `edera entity list`），且环境变量 `EDERA_CLIENT_CERT` 等未预先设置
- **THEN** CLI 入口层 SHALL 在调用 `GrpcClient` 前读取 `~/.edera/client.crt`、`~/.edera/client.key`、`~/.edera/ca.crt` 内容并写入对应环境变量

#### Scenario: 环境变量已设置时不覆盖
- **WHEN** 用户执行 human-facing 子命令，且 `EDERA_CLIENT_CERT` 环境变量已显式设置
- **THEN** CLI 入口层 SHALL NOT 读取 `~/.edera/client.crt`，SHALL 保留环境变量原值

#### Scenario: bootstrap 子命令跳过注入
- **WHEN** 用户执行 `edera client init` 或 `edera-server` 子命令
- **THEN** CLI 入口层 SHALL NOT 读取 `~/.edera/` 文件，SHALL NOT 写入 `EDERA_CLIENT_CERT` 等环境变量

### Requirement: 服务端连接环境变量
`edera` CLI SHALL 使用 `EDERA_SERVER_ADDR` 环境变量或 `--server` flag 指定连接 `edera-server` 的地址，无默认值。

#### Scenario: 通过 env 指定 server addr
- **WHEN** 环境变量 `EDERA_SERVER_ADDR=server.lan:9090` 已设置
- **THEN** CLI SHALL 连接 `server.lan:9090`

#### Scenario: 通过 flag 覆盖
- **WHEN** 环境变量 `EDERA_SERVER_ADDR=a.lan:9090` 已设置，用户执行 `edera --server b.lan:9090 entity list`
- **THEN** CLI SHALL 连接 `b.lan:9090`，忽略环境变量

#### Scenario: 未设置 server addr 即失败
- **WHEN** 用户执行任意数据子命令，但 `EDERA_SERVER_ADDR` 未设置且未传 `--server`
- **THEN** CLI SHALL 输出错误 "EDERA_SERVER_ADDR not set" 并以非零状态退出

### Requirement: CLI 输出模式
`edera` CLI SHALL 支持 `--output json|yaml|table` 全局输出模式。未指定 `--output` 时，CLI SHALL 保持现有 JSON stdout 行为。

#### Scenario: 默认 JSON 输出
- **WHEN** 用户执行 `edera query briefing latest`
- **THEN** CLI SHALL 将结果作为 JSON 写入 stdout

#### Scenario: YAML 输出
- **WHEN** 用户执行 `edera query briefing latest --output yaml`
- **THEN** CLI SHALL 将同一结果作为 YAML 写入 stdout

#### Scenario: 表格输出
- **WHEN** 用户执行 `edera source logs --limit 2 --output table`
- **THEN** CLI SHALL 将列表结果渲染为包含表头和行的文本表格
- **AND** 嵌套对象或数组 SHALL 作为 JSON 字符串保留在单元格中

#### Scenario: 不支持的输出模式
- **WHEN** 用户执行 `edera entity list --output xml`
- **THEN** CLI MUST 返回非零状态
- **AND** stderr SHALL 包含无效 `--output` 的错误信息

### Requirement: CLI watch 模式
`edera` CLI SHALL 为运行观察命令提供 `--watch` 模式。watch 模式 SHALL 按 `--interval` 指定的秒数重复查询并输出结果；未指定 `--watch-count` 时 SHALL 持续运行直到用户中断。

#### Scenario: 观察 DAG 运行状态
- **WHEN** 用户执行 `edera dag status default --watch --interval 1 --watch-count 2`
- **THEN** CLI SHALL 查询并输出 2 次 `default` DAG 状态

#### Scenario: 观察 runtime graph 状态
- **WHEN** 用户执行 `edera dag runtime-status --run-id run-1 --watch --watch-count 2`
- **THEN** CLI SHALL 查询并输出 2 次 `run-1` 的 runtime graph 状态

#### Scenario: 观察 scheduler 状态
- **WHEN** 用户执行 `edera system scheduler-status --watch --watch-count 2`
- **THEN** CLI SHALL 查询并输出 2 次 scheduler 状态

#### Scenario: 观察 source health
- **WHEN** 用户执行 `edera source health --watch --watch-count 2`
- **THEN** CLI SHALL 查询并输出 2 次 source health 摘要

### Requirement: CLI tail 模式
`edera` CLI SHALL 为日志类命令提供 `--tail` 模式。tail 模式 SHALL 重复查询最近日志，并只输出本次会话尚未输出过的日志项。

#### Scenario: 跟随节点执行日志
- **WHEN** 用户执行 `edera node logs reader --run-id run-1 --tail --interval 1 --watch-count 2`
- **THEN** CLI SHALL 重复查询节点 execution logs
- **AND** CLI SHALL 只输出未在本次 tail 会话中出现过的日志项

#### Scenario: 跟随 source execution logs
- **WHEN** 用户执行 `edera source logs --source-name rss-main --tail --watch-count 2`
- **THEN** CLI SHALL 重复查询 `rss-main` 的 source execution logs
- **AND** CLI SHALL 只输出未在本次 tail 会话中出现过的日志项

### Requirement: CLI 错误输出
`edera` CLI SHALL 将运行时错误作为结构化 JSON object 写入 stderr，并保持非零退出状态。错误对象 SHALL 包含 `error`、`type` 和 `detail` 字段。

#### Scenario: 缺少 server 地址
- **WHEN** 用户执行数据子命令但未设置 `EDERA_SERVER_ADDR` 且未传 `--server`
- **THEN** CLI SHALL 以非零状态退出
- **AND** stderr SHALL 包含 `{"error":...,"type":"ValueError","detail":"EDERA_SERVER_ADDR not set"}`

#### Scenario: gRPC 错误
- **WHEN** server 对 CLI 请求返回 gRPC 错误
- **THEN** CLI SHALL 以非零状态退出
- **AND** stderr SHALL 在 `detail` 字段中保留 server 返回的错误详情

### Requirement: 控制面分页展示
`edera` 控制面 CLI SHALL 为列表型读命令提供统一 `--limit` 和 `--offset` 展示参数。`limit` SHALL 优先传递给已有 server 查询参数；`offset` SHALL 只影响 CLI 输出展示，不改变 server 查询范围。

#### Scenario: briefing 列表分页展示
- **WHEN** 用户执行 `edera query briefing list --limit 20 --offset 10`
- **THEN** CLI SHALL 将 `limit=20` 传递给 briefing list 查询
- **AND** CLI SHALL 从返回列表的第 11 项开始展示结果

#### Scenario: advice 列表分页展示
- **WHEN** 用户执行 `edera query advice list --limit 20 --offset 10`
- **THEN** CLI SHALL 将 `limit=20` 传递给 advice list 查询
- **AND** CLI SHALL 从返回列表的第 11 项开始展示结果

#### Scenario: node outputs 分页展示
- **WHEN** 用户执行 `edera query node-outputs --limit 50 --offset 25`
- **THEN** CLI SHALL 将 `limit=50` 传递给 node outputs 查询
- **AND** CLI SHALL 从返回列表的第 26 项开始展示结果

#### Scenario: source logs 分页展示
- **WHEN** 用户执行 `edera source logs --limit 50 --offset 25`
- **THEN** CLI SHALL 将 `limit=50` 传递给 source logs 查询
- **AND** CLI SHALL 从返回列表的第 26 项开始展示结果

#### Scenario: DAG 定义列表分页展示
- **WHEN** 用户执行 `edera dag list --limit 20 --offset 10`
- **THEN** CLI SHALL 对 DAG 定义列表输出应用分页展示

#### Scenario: handler 列表分页展示
- **WHEN** 用户执行 `edera handler list --limit 20 --offset 10`
- **THEN** CLI SHALL 对 handler 列表输出应用分页展示

### Requirement: Entity 子命令
`edera entity` SHALL 提供 entity 的完整 CRUD、查询和文件操作。

#### Scenario: Entity create
- **WHEN** 用户执行 `edera entity create --type stock --id stock-new --attributes '{"code":"AAPL","name":"Apple"}'`
- **THEN** 系统 SHALL 创建 entity 并返回创建结果

#### Scenario: 获取单个 entity
- **WHEN** 用户执行 `edera entity get stock:AAPL`
- **THEN** 系统 SHALL 输出该 entity 的完整 attributes

#### Scenario: 显示 entity 详情
- **WHEN** 用户执行 `edera entity show stock:00700.HK`
- **THEN** 系统 SHALL 显示该 entity 的完整 attributes（JSON 格式）

#### Scenario: Entity 不存在
- **WHEN** 用户执行 `edera entity show nonexistent`
- **THEN** 系统 SHALL 返回错误："Entity not found: nonexistent"

#### Scenario: 列出指定类型的 entities
- **WHEN** 用户执行 `edera entity list --type stock`
- **THEN** 系统 SHALL 输出所有 type 为 stock 的 entity 列表

#### Scenario: 通用列过滤
- **WHEN** 用户执行 `edera entity list --type relation --filter from_entity_id=stock:00700.HK`
- **THEN** 系统 SHALL 查询满足条件的 relations

#### Scenario: 多列组合过滤
- **WHEN** 用户执行 `edera entity list --type relation --filter from_entity_id=stock:00700.HK --filter relation_type=uses-source`
- **THEN** 系统 SHALL 应用所有过滤条件（AND 逻辑）

#### Scenario: 更新 entity 字段
- **WHEN** 用户执行 `edera entity update stock:AAPL --field sentiment --value bearish`
- **THEN** 系统 SHALL 更新该字段并持久化

#### Scenario: 更新 entity attributes
- **WHEN** 用户执行 `edera entity update stock:00700.HK --attributes '{"holding":{"quantity":200}}'`
- **THEN** 系统 SHALL 合并 attributes 并更新数据库

#### Scenario: 查询 entity
- **WHEN** 用户执行 `edera entity query "type=analysis AND confidence>0.8"`
- **THEN** 系统 SHALL 通过 `EntityService.Query` rpc 返回满足条件的 entity 列表

#### Scenario: Entity delete
- **WHEN** 用户执行 `edera entity delete stock:00700.HK`
- **THEN** 系统 SHALL 检查 relations 引用，如无引用则删除

#### Scenario: 强制删除
- **WHEN** 用户执行 `edera entity delete stock:00700.HK --force`
- **THEN** 系统 SHALL 删除相关 relations 和 entity

#### Scenario: Import entity from YAML file
- **WHEN** 用户执行 `edera entity import entities.yaml`
- **THEN** CLI SHALL 通过 `GrpcClient.entity_import` 将完整 Entity 文档提交给 server
- **AND** 系统 SHALL 显示导入统计："Imported 5 entities, 0 errors"

#### Scenario: Reject invalid import file
- **WHEN** `edera entity import --file bad.yaml` 中缺少 `type` 或 `attributes`
- **THEN** 系统 MUST 拒绝导入并返回非零状态

#### Scenario: Export entity to YAML file
- **WHEN** 用户执行 `edera entity export -o entities.yaml`
- **THEN** CLI SHALL 通过 gRPC 从 server 获取 Entity 并写出完整 Entity YAML 文档

#### Scenario: 按 type 导出
- **WHEN** 用户执行 `edera entity export --type stock -o stocks.yaml`
- **THEN** 系统 SHALL 只导出 stock 类型的 entities

#### Scenario: Export template from entity type
- **WHEN** 用户执行 `edera entity template --type node --file node.yaml`
- **THEN** CLI SHALL 通过 gRPC 请求 server 根据 EntityType 生成模板并写出 YAML 文档

### Requirement: Relation 子命令
`edera relation` SHALL 提供 relation 的语法糖命令，简化常见 relation 操作。

#### Scenario: relation list
- **WHEN** 用户执行 `edera relation list --from stock:00700.HK --to rss-source:hn --type uses-source`
- **THEN** 系统 SHALL 转换为 `edera entity list --type relation` 加对应 filter 执行查询

#### Scenario: relation create
- **WHEN** 用户执行 `edera relation create --from stock:00700.HK --to rss-source:hn --type uses-source`
- **THEN** 系统 SHALL 转换为 `edera entity create --type relation` 加对应 attributes 创建

#### Scenario: relation delete
- **WHEN** 用户执行 `edera relation delete <relation-id>`
- **THEN** 系统 SHALL 转换为 `edera entity delete <relation-id>`

#### Scenario: relation import
- **WHEN** 用户执行 `edera relation import entity-relations.yaml`
- **THEN** 系统 SHALL 导入 `relations:` YAML 格式的 entity relations

#### Scenario: relation export
- **WHEN** 用户执行 `edera relation export -o entity-relations.yaml`
- **THEN** 系统 SHALL 导出 `relations:` YAML 格式的 entity relations

### Requirement: Entity-type 子命令
`edera entity-type` SHALL 提供 EntityType 字段物化维护命令。命令 MUST 通过 gRPC 调用 server。

#### Scenario: Plan field materialization
- **WHEN** 用户执行 `edera entity-type materialize plan stock --field code`
- **THEN** CLI SHALL 返回将要创建的列、索引和回填数量摘要

#### Scenario: Apply field materialization
- **WHEN** 用户执行 `edera entity-type materialize apply stock --field code`
- **THEN** server SHALL 物化该字段并更新 EntityType metadata

#### Scenario: Inspect materialized fields
- **WHEN** 用户执行 `edera entity-type materialize inspect stock`
- **THEN** CLI SHALL 展示 `stock` 的 materialized fields 和 deprecated fields

### Requirement: DAG 运行控制子命令
`edera dag` SHALL 提供 DAG 运行控制命令。`edera dag trigger` 命令已废弃，改为 `edera dag run`。

#### Scenario: DAG 手动运行
- **WHEN** 用户执行 `edera dag run my-dag --inputs '{"symbol": "AAPL"}'`
- **THEN** 系统 SHALL 调用 `DagService.Run` 启动 DAG 并返回 run_id

#### Scenario: DAG 停止
- **WHEN** 用户执行 `edera dag stop my-dag`
- **THEN** 系统 SHALL 调用 `DagService.Stop` 停止当前运行的 DAG

#### Scenario: DAG 重试
- **WHEN** 用户执行 `edera dag retry my-dag --run-id abc123 --nodes node1,node2`
- **THEN** 系统 SHALL 调用 `DagService.Retry` 从指定节点重新执行

#### Scenario: DAG 重试传递临时输入
- **WHEN** 用户执行 `edera dag retry default --run-id run-1 --nodes reader --source-shared-inputs '{"symbol":"AAPL"}' --node-inputs '{"reader":{"limit":1}}' --append-nodes reader`
- **THEN** CLI SHALL 将 `sourceSharedInputs`、`nodeInputs` 和 `appendNodes` 传递给 retry 请求

#### Scenario: DAG 状态查询
- **WHEN** 用户执行 `edera dag status my-dag`
- **THEN** 系统 SHALL 输出当前 run_id、状态和节点执行情况

### Requirement: DAG 定义管理子命令
`edera dag` SHALL 提供 DAG 定义层命令。

#### Scenario: 列出 DAG 定义
- **WHEN** 用户执行 `edera dag list`
- **THEN** CLI SHALL 返回 server 中所有 DAG 定义摘要

#### Scenario: 读取 DAG 定义
- **WHEN** 用户执行 `edera dag show default`
- **THEN** CLI SHALL 返回 `default` 的完整 DAG graph payload

#### Scenario: 创建空 DAG
- **WHEN** 用户执行 `edera dag create new-dag`
- **THEN** CLI SHALL 创建名为 `new-dag` 的空 DAG 定义并返回创建结果

#### Scenario: 保存 DAG 定义文件
- **WHEN** 用户执行 `edera dag save default --file dag.json`
- **THEN** CLI SHALL 读取 `dag.json` 并保存为 `default` 的 DAG 定义

#### Scenario: 导出 DAG 定义文件
- **WHEN** 用户执行 `edera dag export default --file dag.json`
- **THEN** CLI SHALL 将 `default` 的完整 DAG graph payload 写入 `dag.json`

#### Scenario: 导入 DAG 定义文件
- **WHEN** 用户执行 `edera dag import default --file dag.json`
- **THEN** CLI SHALL 读取 `dag.json` 并保存为 `default` 的 DAG 定义

#### Scenario: 查询 runtime graph 状态
- **WHEN** 用户执行 `edera dag runtime-status --run-id run-1`
- **THEN** CLI SHALL 返回 `run-1` 的 runtime graph 状态

### Requirement: DAG 运行时编辑子命令
`edera dag edit` SHALL 提供运行时 DAG 图编辑能力，支持添加节点、添加边和移除边。

#### Scenario: 添加节点
- **WHEN** 用户执行 `edera dag edit default add-node --type agent --alias analyzer --config '{}'`
- **THEN** CLI SHALL 调用 `DagService.Edit` 在指定 DAG 添加节点

#### Scenario: 添加边
- **WHEN** 用户执行 `edera dag edit default add-edge --from reader --to analyzer`
- **THEN** CLI SHALL 调用 `DagService.Edit` 在指定 DAG 添加边

#### Scenario: 添加可选边
- **WHEN** 用户执行 `edera dag edit default add-edge --from reader --to analyzer --optional`
- **THEN** CLI SHALL 添加标记为 optional 的边

#### Scenario: 移除边
- **WHEN** 用户执行 `edera dag edit default remove-edge --from reader --to analyzer`
- **THEN** CLI SHALL 调用 `DagService.Edit` 从指定 DAG 移除边

### Requirement: Node 子命令
`edera node` SHALL 提供节点状态查询、停止、恢复、输出查看和日志查看能力。

#### Scenario: 查询节点状态
- **WHEN** 用户执行 `edera node status llm-analyze`
- **THEN** 系统 SHALL 输出该节点当前状态（running、idle、failed）

#### Scenario: 停止节点
- **WHEN** 用户执行 `edera node stop llm-analyze`
- **THEN** 系统 SHALL 对该节点当前运行实例执行 soft stop

#### Scenario: 恢复节点
- **WHEN** 用户执行 `edera node resume llm-analyze --run-id abc123 --prompt "关注宏观经济因素"`
- **THEN** 系统 SHALL 找到该 run_id 的 sandbox 并恢复执行

#### Scenario: 查看节点输出
- **WHEN** 用户执行 `edera node output llm-analyzer --run-id abc123`
- **THEN** 系统 SHALL 通过 `NodeService.Output` rpc 返回该节点在指定 run 中的业务输出内容

#### Scenario: node output export
- **WHEN** 用户执行 `edera node output export --run-id run-1 --node reader --out payload.json`
- **THEN** CLI SHALL 将指定 run/node 的业务 output payload 写入 `payload.json`
- **AND** CLI MUST NOT 将 execution logs 写入该 payload 文件

#### Scenario: 查看节点执行日志
- **WHEN** 用户执行 `edera node logs llm-analyzer --run-id abc123`
- **THEN** CLI SHALL 通过 gRPC 查询该 run 中该节点的 execution logs

#### Scenario: 无业务输出仍可看日志
- **WHEN** 用户执行 `edera node logs reader --run-id abc123`，且该节点已执行但没有业务 output entity
- **THEN** CLI SHALL 输出该节点的 execution summary log

#### Scenario: 节点输出命令保持业务语义
- **WHEN** 用户执行 `edera node output reader --run-id abc123`
- **THEN** CLI SHALL 只返回业务 output 内容
- **AND** CLI MUST NOT 将 execution logs 作为 output 返回

### Requirement: Node-type 子命令
`edera node-type` SHALL 提供 DB-backed node type 定义管理命令。

#### Scenario: 列出 node types
- **WHEN** 用户执行 `edera node-type list`
- **THEN** CLI SHALL 返回所有 node type 定义摘要

#### Scenario: 读取 node type
- **WHEN** 用户执行 `edera node-type show fetch-rss`
- **THEN** CLI SHALL 返回 `fetch-rss` 的 node type 定义

#### Scenario: 创建 node type
- **WHEN** 用户执行 `edera node-type create fetch-rss --file node-type.json`
- **THEN** CLI SHALL 读取 `node-type.json` 并创建 `fetch-rss` node type

#### Scenario: 保存 node type
- **WHEN** 用户执行 `edera node-type save fetch-rss --file node-type.json`
- **THEN** CLI SHALL 读取 `node-type.json` 并更新 `fetch-rss` node type

#### Scenario: 删除 node type
- **WHEN** 用户执行 `edera node-type delete fetch-rss`
- **THEN** CLI SHALL 删除 `fetch-rss` node type 或返回 server 校验错误

### Requirement: Skill 子命令
`edera skill` SHALL 提供 skill 的完整 CRUD 和文件操作。

#### Scenario: 列出所有 skills
- **WHEN** 用户执行 `edera skill list`
- **THEN** 系统 SHALL 显示所有 skills 的 name、display_name、description

#### Scenario: 显示 skill 详情
- **WHEN** 用户执行 `edera skill show SKILL_NAME`
- **THEN** 系统 SHALL 显示该 skill 的所有字段，包括文件列表

#### Scenario: 从文件夹创建 skill
- **WHEN** 用户执行 `edera skill create --from-dir ./my-skill/`
- **THEN** 系统 SHALL 扫描文件夹，读取所有文件并创建 skill
- **AND** 系统 SHALL 验证 SKILL.md 存在

#### Scenario: 从文件夹更新 skill
- **WHEN** 用户执行 `edera skill update SKILL_NAME --from-dir ./my-skill/`
- **THEN** 系统 SHALL 读取文件夹内容并更新数据库

#### Scenario: 导入单个 skill 文件夹
- **WHEN** 用户执行 `edera skill import-dir ./skills/openspec-impact-sweeper/`
- **THEN** 系统 SHALL 导入该文件夹为一个 skill

#### Scenario: 批量导入多个 skill 文件夹
- **WHEN** 用户执行 `edera skill import-batch ./skills/`
- **THEN** 系统 SHALL 扫描目录下所有包含 SKILL.md 的子文件夹并逐个导入

#### Scenario: 导出单个 skill 到文件夹
- **WHEN** 用户执行 `edera skill export SKILL_NAME -o ./output/`
- **THEN** 系统 SHALL 在 `./output/SKILL_NAME/` 创建文件夹并生成所有文件

#### Scenario: 删除 skill
- **WHEN** 用户执行 `edera skill delete SKILL_NAME`
- **THEN** 系统 SHALL 从数据库删除该 skill

### Requirement: Event 子命令
`edera event` SHALL 提供事件注入能力。`edera trigger emit` 命令已废弃，改为 `edera event emit`。

#### Scenario: 事件注入
- **WHEN** 用户执行 `edera event emit "event:website-updated" --payload-json '{"url":"https://..."}'`
- **THEN** CLI 通过 mTLS 连接 edera-server，调用 `EventService.Emit` 注入事件到 EventGroup

#### Scenario: 带 source 的事件注入
- **WHEN** 用户执行 `edera event emit breaking-news --source external-api`
- **THEN** 系统 SHALL 在 emit 记录中标注 source 为 `external-api`

#### Scenario: emit clear 事件
- **WHEN** 用户执行 `edera event emit "clear:event:market-open"`
- **THEN** CLI 调用 `EventService.Emit` 复位 bit

### Requirement: System 子命令
`edera system` SHALL 提供全局系统控制能力。

#### Scenario: 暂停 scheduler
- **WHEN** 用户执行 `edera system pause-scheduler`
- **THEN** 系统 SHALL 调用 `SystemService.PauseScheduler` 暂停 TriggerExecutor

#### Scenario: 恢复 scheduler
- **WHEN** 用户执行 `edera system resume-scheduler`
- **THEN** 系统 SHALL 调用 `SystemService.ResumeScheduler` 恢复 TriggerExecutor

#### Scenario: Scheduler 状态查询
- **WHEN** 用户执行 `edera system scheduler-status`
- **THEN** 系统 SHALL 输出 scheduler 当前状态（running/paused）

#### Scenario: 创建 source repair task
- **WHEN** 用户执行 `edera system repair-source rss-main`
- **THEN** CLI SHALL 请求 server 为 `rss-main` 创建 source repair task
- **AND** CLI SHALL 输出 task_id、task_path、source_name 和 created_at

### Requirement: Client 子命令
`edera client` SHALL 提供客户端证书初始化能力。

#### Scenario: Client init 成功
- **WHEN** 用户执行 `edera client init --server 127.0.0.1:9091`
- **THEN** CLI SHALL 通过 `SystemService.InitClient` 请求签发 client cert
- **AND** CLI SHALL 将 cert 保存到 `~/.edera/client.crt`、`~/.edera/client.key`、`~/.edera/ca.crt`

#### Scenario: 远程 init 走 SSH 隧道
- **WHEN** server 部署在远程主机，用户希望执行 `client init`
- **THEN** 用户 SHALL 通过 SSH 隧道（如 `ssh -L 9091:localhost:9091 server.lan`）转发 bootstrap 端口
- **AND** 然后本地执行 `edera client init --server 127.0.0.1:9091`

### Requirement: Config 子命令
`edera config` SHALL 提供 system config、通用 config 文件和 entity type config 的脚本化读写命令。

#### Scenario: 列出可编辑 config
- **WHEN** 用户执行 `edera config list`
- **THEN** CLI SHALL 返回 server 中可编辑 config 文件列表

#### Scenario: 读取 system config
- **WHEN** 用户执行 `edera config system show`
- **THEN** CLI SHALL 返回当前 system config 文本内容

#### Scenario: 保存 system config
- **WHEN** 用户执行 `edera config system save --file system.toml`
- **THEN** CLI SHALL 读取 `system.toml` 并保存为 system config

#### Scenario: 读取通用 config
- **WHEN** 用户执行 `edera config read dag default.yaml`
- **THEN** CLI SHALL 返回指定 kind/name 的 config 内容

#### Scenario: 保存通用 config
- **WHEN** 用户执行 `edera config save dag default.yaml --file default.yaml`
- **THEN** CLI SHALL 读取 `default.yaml` 并保存为指定 kind/name 的 config 内容

#### Scenario: 列出 entity type config
- **WHEN** 用户执行 `edera config entity-type list`
- **THEN** CLI SHALL 返回所有 entity type config 摘要

#### Scenario: 读取 entity type config
- **WHEN** 用户执行 `edera config entity-type show stock`
- **THEN** CLI SHALL 返回 `stock` 的 entity type YAML 内容

#### Scenario: 创建 entity type config
- **WHEN** 用户执行 `edera config entity-type create stock --file stock.yaml`
- **THEN** CLI SHALL 读取 `stock.yaml` 并创建 `stock` entity type config

#### Scenario: 保存 entity type config
- **WHEN** 用户执行 `edera config entity-type save stock --file stock.yaml`
- **THEN** CLI SHALL 读取 `stock.yaml` 并更新 `stock` entity type config

#### Scenario: 删除 entity type config
- **WHEN** 用户执行 `edera config entity-type delete stock --cascade`
- **THEN** CLI SHALL 删除 `stock` entity type config，并将 `cascade=true` 传递给 server 校验

### Requirement: Handler 子命令
`edera handler` SHALL 提供已注册 handler 的列表、读取和保存命令。`edera handler-validate` SHALL 继续作为离线校验工具存在。

#### Scenario: 列出 handlers
- **WHEN** 用户执行 `edera handler list`
- **THEN** CLI SHALL 返回所有已注册 handler 名称

#### Scenario: 读取 handler
- **WHEN** 用户执行 `edera handler show rss.fetch`
- **THEN** CLI SHALL 返回 `rss.fetch` 对应 handler 文件内容

#### Scenario: 保存 handler
- **WHEN** 用户执行 `edera handler save rss.fetch --file handler.py`
- **THEN** CLI SHALL 读取 `handler.py` 并保存为 `rss.fetch` 对应 handler 内容

#### Scenario: handler-validate 离线校验
- **WHEN** 用户执行 `edera handler-validate extensions/my-handler/handler.py`，文件 schema 合法
- **THEN** 系统 SHALL 输出 "ok" 并以 0 状态退出

#### Scenario: handler-validate 非法文件
- **WHEN** 用户执行 `edera handler-validate <path>`，文件 schema 不合法
- **THEN** 系统 SHALL 输出错误信息列表并以非零状态退出

### Requirement: Query 子命令
`edera query` SHALL 提供 QueryService 读模型的脚本化查询入口。

#### Scenario: 查询最新 briefing
- **WHEN** 用户执行 `edera query briefing latest`
- **THEN** CLI SHALL 返回最新 briefing 查询结果

#### Scenario: 列出 briefings
- **WHEN** 用户执行 `edera query briefing list --limit 20`
- **THEN** CLI SHALL 返回不超过 20 条 briefing 记录

#### Scenario: 查询 briefing 详情
- **WHEN** 用户执行 `edera query briefing show briefing-1`
- **THEN** CLI SHALL 返回 `briefing-1` 的完整 briefing 数据

#### Scenario: 列出 advices
- **WHEN** 用户执行 `edera query advice list --stock-code 600000 --direction buy --limit 20`
- **THEN** CLI SHALL 按过滤条件返回 advice 列表

#### Scenario: 查询 advice 详情
- **WHEN** 用户执行 `edera query advice show advice-1`
- **THEN** CLI SHALL 返回 `advice-1` 的完整 advice 数据

#### Scenario: 查询 results summary
- **WHEN** 用户执行 `edera query results summary --stock-code 600000`
- **THEN** CLI SHALL 返回 results summary 聚合数据

#### Scenario: 查询 node outputs
- **WHEN** 用户执行 `edera query node-outputs --node-id reader --run-id run-1 --limit 10`
- **THEN** CLI SHALL 返回匹配条件的 node output entity 列表

#### Scenario: 查询 node history
- **WHEN** 用户执行 `edera query node-history default reader --limit 10`
- **THEN** CLI SHALL 返回 `default` 中 `reader` 的历史执行记录

#### Scenario: 查询 child run
- **WHEN** 用户执行 `edera query child-run --parent-run-id parent-1 --parent-node-id subdag-node`
- **THEN** CLI SHALL 返回对应的 child run 查询结果

### Requirement: Source 子命令
`edera source` SHALL 提供 source health、source logs 和 source repair task 命令。

#### Scenario: 查询 source health
- **WHEN** 用户执行 `edera source health`
- **THEN** CLI SHALL 返回 source health 摘要

#### Scenario: 查询 source logs
- **WHEN** 用户执行 `edera source logs --source-name rss-main --limit 20`
- **THEN** CLI SHALL 返回 `rss-main` 的 source execution logs

#### Scenario: 创建 source repair task
- **WHEN** 用户执行 `edera source repair-task rss-main`
- **THEN** CLI SHALL 为 `rss-main` 请求创建 source repair task 并返回 task 元数据

### Requirement: Extension 子命令
`edera extension` SHALL 提供扩展生命周期管理命令集。所有安装/卸载/激活操作 MUST 通过 gRPC 调用 `edera-server`。

#### Scenario: 列出所有扩展
- **WHEN** 用户执行 `edera extension list`
- **THEN** CLI SHALL 输出已安装扩展（含 name、version、enabled 状态）和可用但未安装的扩展

#### Scenario: 仅列出已安装扩展
- **WHEN** 用户执行 `edera extension list --installed`
- **THEN** CLI SHALL 仅输出 `installed_extensions` 表中的记录

#### Scenario: 仅列出可用扩展
- **WHEN** 用户执行 `edera extension list --available`
- **THEN** CLI SHALL 扫描 `extensions/` 目录，输出所有包含合法 `manifest.yaml` 的子目录

#### Scenario: 查看扩展详情
- **WHEN** 用户执行 `edera extension show <name>`
- **THEN** CLI SHALL 展示 manifest 内容、提供的 handler、entity type、导入的 entity 列表

#### Scenario: 安装可用扩展
- **WHEN** 用户执行 `edera extension install <name>` 且扩展存在于 `extensions/`
- **THEN** CLI SHALL 调用 `ExtensionService.Install` 完成安装

#### Scenario: 安装 workflow extension 递归处理 providers
- **WHEN** 用户安装 `type: workflow_extension` 扩展
- **THEN** CLI SHALL 输出主扩展安装进度和每个 provider 的安装进度

#### Scenario: 卸载扩展
- **WHEN** 用户执行 `edera extension uninstall <name> --strategy=purge`
- **THEN** CLI SHALL 调用 `ExtensionService.Uninstall` 以指定策略执行卸载

#### Scenario: 未指定卸载策略
- **WHEN** 用户执行 `edera extension uninstall <name>`（无 `--strategy`）
- **THEN** CLI MUST 输出错误提示用户必须指定 `--strategy=purge|keep-modified|deactivate`

#### Scenario: 重新激活已停用扩展
- **WHEN** 用户执行 `edera extension reactivate <name>` 且该扩展 `enabled=false`
- **THEN** CLI SHALL 调用 `ExtensionService.Reactivate` 并输出成功信息

#### Scenario: 导入扩展包
- **WHEN** 用户执行 `edera extension import my-ext.tar.gz`
- **THEN** CLI SHALL 解压到 `extensions/<manifest.name>/`

#### Scenario: 导入并立即安装
- **WHEN** 用户执行 `edera extension import my-ext.tar.gz --install`
- **THEN** CLI SHALL 解压后自动执行 install 流程

#### Scenario: 导出已安装扩展
- **WHEN** 用户执行 `edera extension export <name> -o pkg.tar.gz`
- **THEN** CLI SHALL 打包 manifest、Entity 实例、handler 代码为 tar.gz

#### Scenario: 导出 workflow extension 包含 providers 和 libraries
- **WHEN** 用户导出 `type: workflow_extension` 扩展
- **THEN** 导出包 MUST 包含 `_providers/` 和 `_lib/` 目录结构

#### Scenario: 导出 entity 子集
- **WHEN** 用户执行 `edera extension export-entities --entities node:my-node,dag:my-dag --name my-ext --version 1.0.0 -o my-ext.tar.gz`
- **THEN** CLI SHALL 从数据库查询指定 entity 并打包输出，不含 handler 代码

### Requirement: CLI Help Surface
`edera` CLI SHALL 在三个层级（顶层、一级子命令、二级子命令）暴露文档化的 help 文本，使用户无需查阅外部文档即可理解命令用途与典型用法。

#### Scenario: 顶层 help 包含顶层描述与示例
- **WHEN** 用户执行 `edera --help`
- **THEN** 系统 SHALL 输出包含顶层 description、EXAMPLES 段、以及全部 16 个一级子命令的一行说明的 help 文本
- **AND** SHALL 以退出码 0 退出

#### Scenario: 顶层 help 全局选项分组
- **WHEN** 用户执行 `edera --help`
- **THEN** 系统 SHALL 将全局选项 `--identity` 与 `--server` 归入 `Connection` 分组
- **AND** SHALL 将 `--output` 归入 `Output` 分组
- **AND** SHALL 将 `--help` 与 `--version` 归入通用分组

#### Scenario: 一级子命令 help 包含描述与示例
- **WHEN** 用户执行 `edera <command> --help`（其中 `<command>` 为 16 个一级子命令之一，包括 `handler-validate`）
- **THEN** 系统 SHALL 输出该子命令的 description、EXAMPLES 段、以及该子命令全部二级 subcommand 的一行说明
- **AND** SHALL 以退出码 0 退出

#### Scenario: 二级子命令 help 包含参数说明
- **WHEN** 用户执行 `edera <command> <subcommand> --help`（如 `edera entity get --help`）
- **THEN** 系统 SHALL 输出该 subcommand 的 usage 与全部参数的 help 文本
- **AND** SHALL 以退出码 0 退出

#### Scenario: handler-validate help
- **WHEN** 用户执行 `edera handler-validate --help`
- **THEN** 系统 SHALL 输出 `handler-validate` 的 description 与 EXAMPLES 段，与其它一级子命令保持一致的 help 结构
- **AND** SHALL 以退出码 0 退出

