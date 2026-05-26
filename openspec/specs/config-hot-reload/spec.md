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
系统 SHALL 使用 `watchfiles` 库监听文件系统变更，支持 debounce 机制避免快速连续变更触发多次重载。

#### Scenario: Debounce 合并连续变更
- **WHEN** 同一文件在 1 秒内被修改 3 次
- **THEN** 系统 SHALL 仅触发一次热加载

