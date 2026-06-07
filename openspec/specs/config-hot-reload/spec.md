---
capabilities:
  - cap.core.config-hot-reload
---
# config-hot-reload Specification

## Purpose
定义 配置文件热加载、Handler 脚本热加载、Manifest 热加载、热加载不影响运行中 DAG等能力。
## Requirements
### Requirement: 配置文件热加载
系统 SHALL 监听会影响常驻控制面的配置变更，并在候选控制面完整构建和提交成功后更新 committed `RuntimeControlSnapshot`，无需重启服务。DAG、Node、EntityType 和 Skill 变更 MUST 写入 DB source of truth 并 emit `event:config-changed`，但 MUST NOT 因这些变更 rebuild `RuntimeControlSnapshot`。失败 reload MUST 保留旧 committed `RuntimeControlSnapshot`。

#### Scenario: Node type Entity 变更不重建控制面
- **WHEN** DB-backed Node type Entity 被修改并保存成功
- **THEN** 系统 SHALL emit `event:config-changed`
- **AND** 系统 MUST NOT rebuild `RuntimeControlSnapshot`
- **AND** 后续 DAG run SHALL 从 DB 读取新 Node type 并冻结到 `DagExecutionSnapshot`

#### Scenario: DAG Entity 变更不重建控制面
- **WHEN** DB-backed DAG Entity 被修改并保存成功
- **THEN** 系统 SHALL emit `event:config-changed`
- **AND** 系统 MUST NOT rebuild `RuntimeControlSnapshot`
- **AND** 后续 DAG run SHALL 从 DB 读取新 DAG 并冻结到 `DagExecutionSnapshot`

#### Scenario: 控制面配置解析失败保留旧快照
- **WHEN** system config、trigger entity 或 extension manifest 变更触发控制面 rebuild 但候选构建失败
- **THEN** 系统 MUST 保留失败前的 committed `RuntimeControlSnapshot`

### Requirement: Handler 脚本热加载
系统 SHALL 以配置的 `handlers_dir` 中的已安装 handler 文件作为 handler 脚本变更来源。handler 脚本变更 SHALL 只影响后续新 DAG run 或新 `NodeExecutor` module cache；运行中的 DAG run MUST 继续使用启动时捕获的 executor 与 module cache。

#### Scenario: Handler 脚本修改后重新加载
- **WHEN** handler 脚本 `handlers_dir/my-handler/handler.py` 被修改且后续启动新的 DAG run
- **THEN** 后续新节点执行 SHALL 从新 `NodeExecutor` 的 module cache 重新 import handler

#### Scenario: 运行中 handler 不被替换
- **WHEN** DAG run 正在执行且 handler 脚本变更
- **THEN** 该运行中的 DAG run MUST 继续使用启动时捕获的 executor 状态

### Requirement: Manifest 热加载
系统 SHALL 通过显式 extension install、uninstall 或 reactivate 操作更新 extension metadata，并在操作成功后刷新 committed `RuntimeControlSnapshot` 中的 `TriggerExecutor` 和 `CronEmitter`。Handler resolver 和 extension table mapping MUST 在每次 DAG run 启动时冻结到 `DagExecutionSnapshot`，MUST NOT 作为全局 handler registry 或 extension table names 保存在 `RuntimeControlSnapshot`。

#### Scenario: Manifest 新增 handler 声明
- **WHEN** extension install 操作成功且 manifest 包含新增 handler 声明
- **THEN** 后续新 DAG run SHALL 在 `DagExecutionSnapshot` 中冻结包含新 handler 的 resolver

#### Scenario: Manifest 删除 handler 声明
- **WHEN** extension uninstall 或 deactivate 操作成功
- **THEN** 后续新 DAG run 的 `DagExecutionSnapshot` MUST NOT 解析到已删除或已停用 extension 的 handler

#### Scenario: Manifest candidate 失败保留旧控制面
- **WHEN** extension lifecycle 操作失败
- **THEN** 系统 MUST 保留失败前 committed `RuntimeControlSnapshot` 中的 `TriggerExecutor` 和 `CronEmitter`

### Requirement: 热加载不影响运行中 DAG
配置热加载 SHALL 仅影响新启动的 DAG run，不影响正在执行的 run。运行中的 DAG SHALL 继续使用启动时捕获的 `DagExecutionSnapshot`。

#### Scenario: 运行中 DAG 不受热加载影响
- **WHEN** DAG 正在执行，期间配置或 extension 文件变更并成功 commit
- **THEN** 该 run SHALL 继续使用启动时捕获的 `DagExecutionSnapshot`，不受变更影响

#### Scenario: 新 run 使用更新后配置
- **WHEN** reload commit 或 DB-backed config 保存成功后触发新的 DAG run
- **THEN** 新 run SHALL 从 DB 和当前控制面状态构建新的 `DagExecutionSnapshot`

### Requirement: 文件监听机制
系统 SHALL 监听 DB-backed core Entity/system config 变更，并使用 `watchfiles` 库监听运行时需要的文件系统变更，支持 debounce 机制避免快速连续变更触发多次重载。该 watcher SHALL 由 `edera-server` 生命周期启动和停止。

#### Scenario: Debounce 合并连续变更
- **WHEN** 同一文件在 1 秒内被修改 3 次
- **THEN** 系统 SHALL 仅触发一次热加载

#### Scenario: server 生命周期管理监听
- **WHEN** `edera-server` 正常运行
- **THEN** hot reload watcher SHALL 处于运行状态

### Requirement: 配置变更 emit 事件

系统 SHALL 在 DB-backed DAG、Node、EntityType、Skill、Trigger、system config 或 extension 文件变更成功后自动 emit `event:config-changed`。失败 reload MUST NOT emit `event:config-changed`。DAG、Node、EntityType 和 Skill 变更的 emit MUST 使用当前 committed `RuntimeControlSnapshot` 中的 `TriggerExecutor`，且 MUST NOT 为这些变更 rebuild 控制面。

#### Scenario: 非控制面配置变更 emit

- **WHEN** DB-backed DAG、Node、EntityType 或 Skill 被修改并保存成功
- **THEN** 系统 SHALL 调用 `emit("event:config-changed")`
- **AND** 系统 MUST NOT rebuild `RuntimeControlSnapshot`

#### Scenario: trigger entity 变更触发 cron 重扫描

- **WHEN** trigger entity 配置变更且 reload commit 成功
- **THEN** committed `RuntimeControlSnapshot` SHALL 包含基于新 trigger entity 构建的 `TriggerExecutor` 和 `CronEmitter`

#### Scenario: 失败 reload 不触发 cron 重扫描

- **WHEN** trigger entity 配置变更但 reload commit 失败
- **THEN** 系统 MUST NOT emit `event:config-changed`
- **AND** `CronEmitter` SHALL 继续使用失败前 committed `RuntimeControlSnapshot` 中的注册表

#### Scenario: config-changed 事件不绕过控制面
- **WHEN** reload commit 成功后系统 emit `event:config-changed`
- **THEN** emit 路径 MUST 使用已提交 `RuntimeControlSnapshot` 中的 `TriggerExecutor`
- **AND** emit 路径 MUST NOT 重新从文件加载 trigger 配置

### Requirement: HotReloader server 生命周期
`edera-server` SHALL 在 server start 时启动 `HotReloader.watch()` 后台任务，并在 server stop 时取消该任务。Watcher 生命周期 SHALL 由 server 进程管理，不要求用户单独启动热重载进程。

#### Scenario: server 启动 watcher
- **WHEN** `edera-server` 成功启动
- **THEN** server SHALL 启动一个 `HotReloader.watch()` 后台任务监听配置和扩展目录

#### Scenario: server 停止 watcher
- **WHEN** `edera-server` 停止
- **THEN** server SHALL 取消 hot reload watcher task
- **AND** SHALL NOT 留下继续运行的 watcher task

### Requirement: 热加载失败隔离
Hot reload SHALL 隔离单次 reload 失败。配置解析、extension 扫描、extension table 创建、trigger 加载或 reload callback 失败时，系统 MUST NOT emit `event:config-changed`，MUST NOT 终止 watcher，MUST NOT 影响当前 running DAG run，MUST NOT 替换旧 committed runtime snapshot。

#### Scenario: reload 失败不 emit
- **WHEN** 文件变更触发 reload，但候选 runtime snapshot 构建或提交失败
- **THEN** 系统 MUST NOT emit `event:config-changed`
- **AND** watcher SHALL 继续监听后续变更

#### Scenario: callback 失败不终止 watcher
- **WHEN** reload callback 抛出错误
- **THEN** watcher SHALL 记录错误并继续监听后续变更
- **AND** 当前运行中的 DAG SHALL 继续使用启动时捕获的配置快照
- **AND** 系统 MUST 保留失败前 committed runtime snapshot

### Requirement: Runtime read APIs use committed snapshot
系统 SHALL 让 DAG、Node、EntityType、Skill、Entity 和 relation runtime read API 读取 DB-backed source of truth，而不是读取 `RuntimeControlSnapshot` 中的全量 config mirror。Config edit API SHALL 保持文件读写语义，保存成功 MUST NOT 表示运行时已生效，除非对应数据已写入 DB source of truth。

#### Scenario: Runtime read API sees DB-backed state
- **WHEN** 客户端读取 DAG、Node、EntityType、Skill 或 Entity runtime view
- **THEN** 系统 SHALL 从 DB-backed repository 返回运行时视图
- **AND** 系统 MUST NOT 依赖 `runtime_snapshot().config.dags` 或 `runtime_snapshot().config.nodes`

#### Scenario: Runtime read API ignores failed control-plane candidate
- **WHEN** system config、trigger 或 extension 文件已保存但控制面 reload commit 失败
- **THEN** control-plane runtime read API SHALL 继续返回失败前 committed `RuntimeControlSnapshot` 中的视图

#### Scenario: Config edit API reads file state
- **WHEN** 文件已保存但 reload commit 尚未成功
- **THEN** config edit API SHALL 仍可读取已保存的文件内容
- **AND** 该文件内容 MUST NOT 被视为控制面运行时已生效

### Requirement: Snapshot commit serialization
系统 SHALL 串行化 `RuntimeControlSnapshot` commit。并发 reload 请求 MUST 按提交顺序完整构建并替换控制面 snapshot，MUST NOT 暴露部分提交状态。

#### Scenario: Concurrent control-plane commits are serialized
- **WHEN** 多个控制面文件变更触发并发 reload commit
- **THEN** 系统 SHALL 串行处理每个候选 `RuntimeControlSnapshot` commit
- **AND** 任一时刻 runtime consumers SHALL 只看到某一个完整 committed `RuntimeControlSnapshot`

