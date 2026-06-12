# edera-cli-control-plane Specification

## Purpose
此规约记录变更 expand-edera-cli-control-plane 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: DAG 定义命令
`edera dag` SHALL 提供 DAG 定义层命令，用于列出、读取、创建、保存、导入、导出 DAG 定义，并保留现有运行控制命令的语义。

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

### Requirement: Node type 命令
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

### Requirement: Handler 命令
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

### Requirement: Config 命令
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

### Requirement: Query 命令
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

### Requirement: Source 命令
`edera source` SHALL 提供 source health、source logs 和 source repair task 命令。

#### Scenario: 查询 source health
- **WHEN** 用户执行 `edera source health`
- **THEN** CLI SHALL 返回 source health 摘要

#### Scenario: 查询 source logs
- **WHEN** 用户执行 `edera source logs --source-name rss-main --limit 20`
- **THEN** CLI SHALL 返回 `rss-main` 的 source execution logs

#### Scenario: 创建 source repair task
- **WHEN** 用户执行 `edera source repair-task rss-main`
- **THEN** CLI SHALL 为 `rss-main` 请求创建 source repair task 并返回 task 元数据或 server 校验错误

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

