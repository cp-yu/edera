---
capabilities:
  - cap.core.config-hot-reload
---
# config-hot-reload Specification

## Purpose
定义 配置文件热加载、Handler 脚本热加载、Manifest 热加载、热加载不影响运行中 DAG等能力。
## Requirements
### Requirement: 配置文件热加载
系统 SHALL 监听 DB-backed core Entity、system config 和 extension manifest 的变更，变更发生时 SHALL 构建候选运行时快照，并在候选配置完整解析和提交成功后更新 committed runtime snapshot，无需重启服务。失败 reload MUST 保留旧 committed runtime snapshot。

#### Scenario: Node type Entity 变更热加载
- **WHEN** DB-backed Node type Entity 被修改且 reload commit 成功
- **THEN** 系统 SHALL 在 committed runtime snapshot 中更新对应的 NodeConfig

#### Scenario: DAG Entity 变更热加载
- **WHEN** DB-backed DAG Entity 被修改且 reload commit 成功
- **THEN** 系统 SHALL 在 committed runtime snapshot 中更新对应的 DAG 配置

#### Scenario: 配置解析失败保留旧快照
- **WHEN** DB-backed core Entity 或 system config 变更触发 reload 但候选配置解析失败
- **THEN** 系统 MUST 保留失败前的 committed runtime snapshot

### Requirement: Handler 脚本热加载
系统 SHALL 监听 `extensions/` 目录下的 handler 脚本变更，变更发生时 SHALL 让后续新 DAG run 使用 committed runtime snapshot 中的 handler registry 和新的 NodeExecutor handler module cache。运行中的 DAG run MUST 继续使用启动时捕获的 executor 与 module cache。

#### Scenario: Handler 脚本修改后重新加载
- **WHEN** handler 脚本 `extensions/my-handler/handler.py` 被修改且 reload commit 成功
- **THEN** 后续新节点执行 SHALL 从新 NodeExecutor 的 module cache 重新 import handler

#### Scenario: 运行中 handler 不被替换
- **WHEN** DAG run 正在执行且 handler 脚本变更成功 commit
- **THEN** 该运行中的 DAG run MUST 继续使用启动时捕获的 executor 状态

### Requirement: Manifest 热加载
系统 SHALL 监听 `extensions/` 目录下的 `manifest.yaml` 文件变更，变更发生时 SHALL 构建候选 bootstrap 结果，并在候选 extension 扫描、extension table 创建和 trigger 加载全部成功后，原子替换 committed runtime snapshot 中的 handler registry、entity type registry、extension table names、TriggerExecutor 和 CronEmitter。

#### Scenario: Manifest 新增 handler 声明
- **WHEN** `extensions/my-ext/manifest.yaml` 新增 handler 声明且 reload commit 成功
- **THEN** 系统 SHALL 在 committed runtime snapshot 中注册新 handler

#### Scenario: Manifest 删除 handler 声明
- **WHEN** `extensions/my-ext/manifest.yaml` 删除 handler 声明且 reload commit 成功
- **THEN** 系统 SHALL 在 committed runtime snapshot 中移除该 handler

#### Scenario: Manifest candidate 失败保留旧 registries
- **WHEN** `extensions/my-ext/manifest.yaml` 变更触发 reload 但 extension 扫描、table 创建或 trigger 加载失败
- **THEN** 系统 MUST 保留失败前 committed runtime snapshot 中的 handler registry、entity type registry、extension table names、TriggerExecutor 和 CronEmitter

### Requirement: 热加载不影响运行中 DAG
配置热加载 SHALL 仅影响新启动的 DAG run，不影响正在执行的 run。运行中的 DAG SHALL 继续使用启动时捕获的 committed runtime snapshot。

#### Scenario: 运行中 DAG 不受热加载影响
- **WHEN** DAG 正在执行，期间配置或 extension 文件变更并成功 commit 新 snapshot
- **THEN** 该 run SHALL 继续使用启动时捕获的 snapshot，不受变更影响

#### Scenario: 新 run 使用更新后配置
- **WHEN** reload commit 成功后触发新的 DAG run
- **THEN** 新 run SHALL 使用最新 committed runtime snapshot

### Requirement: 文件监听机制
系统 SHALL 监听 DB-backed core Entity/system config 变更，并使用 `watchfiles` 库监听 `extensions/` 文件系统变更，支持 debounce 机制避免快速连续变更触发多次重载。该 watcher SHALL 由 `edera-server` 生命周期启动和停止。

#### Scenario: Debounce 合并连续变更
- **WHEN** 同一文件在 1 秒内被修改 3 次
- **THEN** 系统 SHALL 仅触发一次热加载

#### Scenario: server 生命周期管理监听
- **WHEN** `edera-server` 正常运行
- **THEN** hot reload watcher SHALL 处于运行状态

### Requirement: 配置变更 emit 事件

系统 SHALL 在 DB-backed core Entity、system config 或 extension 文件变更且 reload commit 成功后自动 emit `event:config-changed` 事件到 committed runtime snapshot 中的 TriggerExecutor。失败 reload MUST NOT emit `event:config-changed`，且 emit 路径 MUST NOT 为该事件重新从文件构建 trigger registry。

#### Scenario: 配置变更 emit 事件

- **WHEN** DB-backed core Entity 或 system config 被修改，HotReloader 检测到变更并成功 commit runtime snapshot
- **THEN** 系统在 reload callback 成功后调用 `emit("event:config-changed")`

#### Scenario: trigger entity 变更触发 cron 重扫描

- **WHEN** trigger entity 配置变更且 reload commit 成功
- **THEN** committed runtime snapshot SHALL 包含基于新 trigger entity 构建的 TriggerExecutor 和 CronEmitter

#### Scenario: 失败 reload 不触发 cron 重扫描

- **WHEN** trigger entity 配置变更但 reload commit 失败
- **THEN** 系统 MUST NOT emit `event:config-changed`
- **AND** CronEmitter SHALL 继续使用失败前 committed runtime snapshot 中的注册表

#### Scenario: config-changed 事件不绕过 snapshot
- **WHEN** reload commit 成功后系统 emit `event:config-changed`
- **THEN** emit 路径 MUST 使用已提交 snapshot 中的 TriggerExecutor
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
系统 SHALL 让运行时读 API 读取最新 committed runtime snapshot，而不是直接读取未提交文件状态。Config edit API SHALL 保持文件读写语义，保存成功 MUST NOT 表示运行时已生效。

#### Scenario: Runtime read API sees committed snapshot
- **WHEN** reload commit 成功后客户端读取 DAG、Node 或 Entity runtime view
- **THEN** 系统 SHALL 返回最新 committed runtime snapshot 中的运行时视图

#### Scenario: Runtime read API ignores failed candidate
- **WHEN** 文件已保存但 reload commit 失败
- **THEN** runtime read API SHALL 继续返回失败前 committed runtime snapshot 中的运行时视图

#### Scenario: Config edit API reads file state
- **WHEN** 文件已保存但 reload commit 尚未成功
- **THEN** config edit API SHALL 仍可读取已保存的文件内容
- **AND** 该文件内容 MUST NOT 被视为运行时已生效

### Requirement: Snapshot commit serialization
系统 SHALL 串行化 runtime snapshot commit。并发 reload 请求 MUST 按提交顺序完整构建并替换 snapshot，MUST NOT 暴露部分提交状态。

#### Scenario: Concurrent reload commits are serialized
- **WHEN** 多个文件变更触发并发 reload commit
- **THEN** 系统 SHALL 串行处理每个候选 snapshot commit
- **AND** 任一时刻 runtime consumers SHALL 只看到某一个完整 committed runtime snapshot
