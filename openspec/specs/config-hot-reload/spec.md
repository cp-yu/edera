# config-hot-reload Specification

## Purpose
此规约记录变更 core-architecture-overhaul 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 配置文件热加载
系统 SHALL 监听 `config/` 目录下的 YAML 文件变更，变更发生时 SHALL 重新解析受影响的配置并更新内存状态，无需重启服务。

#### Scenario: Node 配置变更热加载
- **WHEN** `config/nodes/my-node.yaml` 文件被修改
- **THEN** 系统 SHALL 重新解析该文件并更新内存中的 NodeConfig

#### Scenario: DAG 配置变更热加载
- **WHEN** `config/dags/my-dag.yaml` 文件被修改
- **THEN** 系统 SHALL 重新解析该文件并更新内存中的 DAG 配置

### Requirement: Handler 脚本热加载
系统 SHALL 监听 `extensions/` 目录下的 handler 脚本变更，变更发生时 SHALL 清除模块缓存，下次执行时重新加载。

#### Scenario: Handler 脚本修改后重新加载
- **WHEN** handler 脚本 `extensions/my-handler/handler.py` 被修改
- **THEN** 系统 SHALL 清除该模块的缓存，下次节点执行时重新 import

### Requirement: Manifest 热加载
系统 SHALL 监听 `extensions/` 目录下的 `manifest.yaml` 文件变更，变更发生时 SHALL 重新执行 bootstrap 扫描，原子替换 handler registry 和 entity type registry。

#### Scenario: Manifest 新增 handler 声明
- **WHEN** `extensions/my-ext/manifest.yaml` 新增 handler 声明
- **THEN** 系统 SHALL 重新扫描 manifest，将新 handler 注册到 handler registry

#### Scenario: Manifest 删除 handler 声明
- **WHEN** `extensions/my-ext/manifest.yaml` 删除 handler 声明，且该 handler 无活跃引用
- **THEN** 系统 SHALL 从 handler registry 移除该 handler

#### Scenario: Manifest 删除被引用 handler 拒绝
- **WHEN** `extensions/my-ext/manifest.yaml` 删除 handler 声明，但有运行中的 DAG 引用该 handler
- **THEN** 系统 SHALL 拒绝热加载并返回错误

### Requirement: 热加载不影响运行中 DAG
配置热加载 SHALL 仅影响新启动的 DAG run，不影响正在执行的 run。运行中的 DAG SHALL 继续使用启动时的配置快照。

#### Scenario: 运行中 DAG 不受热加载影响
- **WHEN** DAG 正在执行，期间其配置文件被修改
- **THEN** 该 run SHALL 继续使用启动时的配置，不受变更影响

#### Scenario: 新 run 使用更新后配置
- **WHEN** 配置热加载完成后，触发新的 DAG run
- **THEN** 新 run SHALL 使用更新后的配置

### Requirement: 文件监听机制
系统 SHALL 使用 `watchfiles` 库监听 `config/` 与 `extensions/` 文件系统变更，支持 debounce 机制避免快速连续变更触发多次重载。该 watcher SHALL 由 `edera-server` 生命周期启动和停止。

#### Scenario: Debounce 合并连续变更
- **WHEN** 同一文件在 1 秒内被修改 3 次
- **THEN** 系统 SHALL 仅触发一次热加载

#### Scenario: server 生命周期管理监听
- **WHEN** `edera-server` 正常运行
- **THEN** hot reload watcher SHALL 处于运行状态

### Requirement: 配置变更 emit 事件

系统 SHALL 在配置文件变更且 reload 成功后自动 emit `event:config-changed` 事件到 TriggerExecutor。失败 reload MUST NOT emit `event:config-changed`。

#### Scenario: 配置变更 emit 事件

- **WHEN** `config/` 目录下的文件被修改，HotReloader 检测到变更并成功执行 reload
- **THEN** 系统在 reload callback 成功后调用 `emit("event:config-changed")`

#### Scenario: trigger entity 变更触发 cron 重扫描

- **WHEN** `config/triggers/` 目录下的文件变更且 reload 成功
- **THEN** HotReloader reload 后，cron emitter 重新扫描所有 trigger entity 的 cron token 并更新注册表

#### Scenario: 失败 reload 不触发 cron 重扫描

- **WHEN** `config/triggers/` 目录下的文件变更但 reload 失败
- **THEN** 系统 MUST NOT emit `event:config-changed`
- **AND** cron emitter SHALL 继续使用失败前的注册表

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
Hot reload SHALL 隔离单次 reload 失败。配置解析、extension 扫描或 reload callback 失败时，系统 MUST NOT emit `event:config-changed`，MUST NOT 终止 watcher，MUST NOT 影响当前运行中的 DAG run。

#### Scenario: reload 失败不 emit
- **WHEN** 文件变更触发 reload，但新配置解析失败
- **THEN** 系统 MUST NOT emit `event:config-changed`
- **AND** watcher SHALL 继续监听后续变更

#### Scenario: callback 失败不终止 watcher
- **WHEN** reload callback 抛出错误
- **THEN** watcher SHALL 记录错误并继续监听后续变更
- **AND** 当前运行中的 DAG SHALL 继续使用启动时的配置快照

