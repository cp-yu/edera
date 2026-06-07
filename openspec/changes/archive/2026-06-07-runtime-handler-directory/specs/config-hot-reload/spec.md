## MODIFIED Requirements

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

### Requirement: 文件监听机制
系统 SHALL 监听 DB-backed core Entity/system config 变更，并使用 `watchfiles` 库监听运行时需要的文件系统变更，支持 debounce 机制避免快速连续变更触发多次重载。该 watcher SHALL 由 `edera-server` 生命周期启动和停止。

#### Scenario: Debounce 合并连续变更
- **WHEN** 同一文件在 1 秒内被修改 3 次
- **THEN** 系统 SHALL 仅触发一次热加载

#### Scenario: server 生命周期管理监听
- **WHEN** `edera-server` 正常运行
- **THEN** hot reload watcher SHALL 处于运行状态
