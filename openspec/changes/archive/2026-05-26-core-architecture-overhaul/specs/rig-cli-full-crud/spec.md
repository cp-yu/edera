## ADDED Requirements

### Requirement: Entity CRUD 完整支持
Rig CLI SHALL 支持 entity 的完整 CRUD 操作：create、get、list、update、delete、query。

#### Scenario: Entity create
- **WHEN** 用户执行 `rig entity create --type node --id my-node --attr handler=my_handler`
- **THEN** 系统 SHALL 创建 entity 并返回创建结果

#### Scenario: Entity delete
- **WHEN** 用户执行 `rig entity delete node:my-node`
- **THEN** 系统 SHALL 删除该 entity

### Requirement: DAG 状态查询
Rig CLI SHALL 支持 `rig dag status <dag_name>` 查询 DAG 的运行历史和当前状态。

#### Scenario: 查询 DAG 运行历史
- **WHEN** 用户执行 `rig dag status my-dag`
- **THEN** 系统 SHALL 返回该 DAG 的最近 10 次运行记录（cycle_id、状态、时间）

### Requirement: DAG 拓扑编辑
Rig CLI SHALL 支持 `rig dag edit` 子命令，包含 `add-node`、`add-edge`、`remove-edge` 操作。

#### Scenario: 添加节点到 DAG
- **WHEN** 用户执行 `rig dag edit my-dag add-node --type fetch --alias fetcher-1`
- **THEN** 系统 SHALL 在 DAG 配置中添加该节点实例

#### Scenario: 添加边
- **WHEN** 用户执行 `rig dag edit my-dag add-edge --from node-a --to node-b`
- **THEN** 系统 SHALL 在 DAG 配置中添加该边

#### Scenario: 删除边
- **WHEN** 用户执行 `rig dag edit my-dag remove-edge --from node-a --to node-b`
- **THEN** 系统 SHALL 从 DAG 配置中删除该边

### Requirement: Node 输出查看
Rig CLI SHALL 支持 `rig node output <node_id> --cycle-id <cycle_id>` 查看节点的执行输出。

#### Scenario: 查看节点输出
- **WHEN** 用户执行 `rig node output llm-analyzer --cycle-id abc123`
- **THEN** 系统 SHALL 返回该节点在指定 cycle 中的输出内容

### Requirement: Client 一键初始化
Rig CLI SHALL 支持 `rig client init --server <addr>` 一键完成客户端配置，包括连接验证、证书获取、配置保存。

#### Scenario: Client init 成功
- **WHEN** 用户执行 `rig client init --server 10.0.0.1:9090`
- **THEN** CLI SHALL 连接 server、请求签发 client cert、保存到 `~/.rig/`

### Requirement: gRPC Client 实现
Rig CLI SHALL 作为 gRPC client 连接 daemon，自动读取 `~/.rig/` 中的证书和配置完成 mTLS 握手。

#### Scenario: 自动加载证书
- **WHEN** 用户执行任意 rig 命令
- **THEN** CLI SHALL 从 `~/.rig/client.crt` 和 `~/.rig/client.key` 加载证书

#### Scenario: 环境变量覆盖
- **WHEN** 环境变量 `RIG_CLIENT_CERT` 和 `RIG_DAEMON_ADDR` 已设置
- **THEN** CLI SHALL 优先使用环境变量中的配置
