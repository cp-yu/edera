## MODIFIED Requirements

### Requirement: CLI binary 入口
系统 SHALL 提供名为 `edera` 的 CLI binary，作为 agent 和人类访问 Edera 控制面能力的统一入口。`edera` 是控制 CLI 的命令名，与 `edera-server`（后端引擎）、`edera-web`（网页 BFF）三个 console scripts 一同构成完整入口集合。

#### Scenario: CLI 可执行
- **WHEN** 用户或 agent 在终端执行 `edera --help`
- **THEN** 系统 SHALL 输出可用子命令列表（entity、node、dag、event、system、client、handler-validate）

#### Scenario: 版本查询
- **WHEN** 用户执行 `edera --version`
- **THEN** 系统 SHALL 输出当前版本号

#### Scenario: Console scripts 集合
- **WHEN** 检查包的 console scripts
- **THEN** 系统 SHALL 注册 `edera = "edera_core.cli:main"`、`edera-server = "edera_core.server:main"`、`edera-web = "edera_core.web.__main__:main"`
- **AND** 系统 SHALL NOT 注册名为 `rig` 的 console script

### Requirement: DAG 子命令
`edera dag` SHALL 提供 DAG 运行、停止、重试和状态查询能力。`edera dag trigger` 命令已废弃，改为 `edera dag run`。

#### Scenario: DAG 手动运行
- **WHEN** 用户执行 `edera dag run my-dag --inputs '{"symbol": "AAPL"}'`
- **THEN** 系统 SHALL 调用 `DagService.Run` 启动 DAG 并返回 run_id

#### Scenario: DAG 停止
- **WHEN** 用户执行 `edera dag stop my-dag`
- **THEN** 系统 SHALL 调用 `DagService.Stop` 停止当前运行的 DAG

#### Scenario: DAG 重试
- **WHEN** 用户执行 `edera dag retry my-dag --run-id abc123 --nodes node1,node2`
- **THEN** 系统 SHALL 调用 `DagService.Retry` 从指定节点重新执行

#### Scenario: DAG 状态查询
- **WHEN** 用户执行 `edera dag status my-dag`
- **THEN** 系统 SHALL 输出当前 run_id、状态和节点执行情况

## ADDED Requirements

### Requirement: Event 子命令
`edera event` SHALL 提供事件注入能力。`edera trigger emit` 命令已废弃，改为 `edera event emit`。

#### Scenario: 事件注入
- **WHEN** 用户执行 `edera event emit market-open --payload '{"time": "09:30"}'`
- **THEN** 系统 SHALL 调用 `EventService.Emit` 注入事件到 EventGroup

#### Scenario: 带 source 的事件注入
- **WHEN** 用户执行 `edera event emit breaking-news --source external-api`
- **THEN** 系统 SHALL 在 emit 记录中标注 source 为 `external-api`

### Requirement: System 子命令
`edera system` SHALL 提供全局系统控制能力，包括 scheduler 暂停、恢复和状态查询。

#### Scenario: 暂停 scheduler
- **WHEN** 用户执行 `edera system pause-scheduler`
- **THEN** 系统 SHALL 调用 `SystemService.PauseScheduler` 暂停 TriggerExecutor

#### Scenario: 恢复 scheduler
- **WHEN** 用户执行 `edera system resume-scheduler`
- **THEN** 系统 SHALL 调用 `SystemService.ResumeScheduler` 恢复 TriggerExecutor

#### Scenario: Scheduler 状态查询
- **WHEN** 用户执行 `edera system scheduler-status`
- **THEN** 系统 SHALL 输出 scheduler 当前状态（running/paused）

### Requirement: Node 子命令使用 run_id
`edera node` 子命令中所有涉及 cycle_id 的参数 SHALL 改为 run_id。

#### Scenario: 查看节点输出使用 run_id
- **WHEN** 用户执行 `edera node output llm-analyzer --run-id abc123`
- **THEN** 系统 SHALL 查询该 run_id 下的节点输出

#### Scenario: 恢复节点使用 run_id
- **WHEN** 用户执行 `edera node resume llm-analyze --run-id abc123 --prompt "关注宏观经济因素"`
- **THEN** 系统 SHALL 找到该 run_id 的 sandbox 并恢复执行
