## ADDED Requirements

### Requirement: Node 作为 Entity 执行

Node executor SHALL 从 Entity Store 加载 Node Entity（替代直接 NodeConfig 加载），根据 EntityType schema 中的能力字段分叉执行路径：有 `handler` 字段的 Entity 为可执行节点。

#### Scenario: 加载 Node Entity 并执行

- **WHEN** DAG Runner 调度执行一个 Node Entity
- **THEN** executor 从 Entity Store 读取该 Entity 的 attributes，根据 `type`（function/llm）分叉执行

#### Scenario: Node Entity 缺少 handler 字段

- **WHEN** executor 尝试执行一个 attributes 中无 `handler` 且无 `system_prompt_file` 的 Entity
- **THEN** executor 返回错误 "Entity is not executable: missing handler or system_prompt_file"

### Requirement: Handler 每次 run 重新加载

Node executor SHALL 在每次 DAG run 时重新加载 handler 文件，确保 handler 修改在下次 run 生效。

#### Scenario: Handler 文件被修改后生效

- **WHEN** 用户修改了 `config/handlers/fetchrss.py`，下一次 DAG run 开始
- **THEN** executor 重新加载该 handler 文件，使用新版本执行

#### Scenario: Handler 加载失败走容错

- **WHEN** handler 文件存在语法错误，DAG run 执行到该节点
- **THEN** executor 记录错误到 run metadata，该节点标记为 failed，走容错流程（不阻塞其他节点）

### Requirement: Node 输出存储为 Entity

Node executor SHALL 将节点执行输出存储为输出型 Entity（存储在数据库层），替代当前的独立数据模型表。

#### Scenario: 存储 Node 输出为 Entity

- **WHEN** 节点执行成功产出结果
- **THEN** executor 将输出存储为一个 Entity（type 由节点的 `output_type` 决定），包含 `cycle_id`、`node_id`、`payload` 等 attributes

#### Scenario: 输出 Entity 可被后续节点引用

- **WHEN** 下游节点需要引用上游的输出
- **THEN** 系统通过 Entity Store 查询对应 cycle_id 和 node_id 的输出 Entity

### Requirement: Session ID 记录

Node executor SHALL 为 LLM 节点记录 pi session ID 到输出 Entity 的 attributes 中，支持后续 session resume。

#### Scenario: 记录 session ID

- **WHEN** LLM 节点通过 pi 执行完成
- **THEN** executor 将 session 目录路径记录到输出 Entity 的 `attributes.session_id` 字段

#### Scenario: Session ID 可查询

- **WHEN** 用户查询某次 Node 执行的 session ID
- **THEN** 系统从输出 Entity 的 attributes 中返回 `session_id` 值
