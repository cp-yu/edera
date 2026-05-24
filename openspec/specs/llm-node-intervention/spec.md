# llm-node-intervention Specification

## Purpose
此规约记录变更 rig-session-reuse 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Stop + Resume 干预
系统 SHALL 支持对 LLM 节点执行 soft stop 后通过 resume session 附带干预指令重启。

#### Scenario: Soft stop 运行中节点
- **WHEN** 用户对正在运行的 LLM 节点执行 soft stop（通过 API 或 `rig` CLI）
- **THEN** 系统 SHALL 设置 stop_event，pi 进程在当前轮次完成后退出，session 文件保留完整

#### Scenario: Resume with intervention prompt
- **WHEN** 用户对已停止的 LLM 节点执行 resume，附带干预指令 `"调整分析方向，关注宏观经济因素"`
- **THEN** 系统 SHALL 以 `--continue` 模式启动 pi，将干预指令作为新的 user message 传入

#### Scenario: Resume 失败节点
- **WHEN** LLM 节点执行失败（pi exit code != 0），用户执行 resume
- **THEN** 系统 SHALL 以 `--continue` 模式启动 pi，使用原 sandbox 的 session_dir，允许 agent 从失败点继续

### Requirement: 干预后输出替换
Resume 执行完成后，系统 SHALL 用新输出替换原节点的输出记录。

#### Scenario: 干预后输出更新
- **WHEN** resume 执行成功产出新结果
- **THEN** 系统 SHALL 更新该节点在当前 cycle 中的 `NodeOutput`，session_id 指向同一 sandbox

#### Scenario: 干预后下游重新执行
- **WHEN** resume 执行成功且该节点有下游依赖
- **THEN** 系统 SHALL 标记下游节点为待重新执行状态（cascade retry）

### Requirement: CLI 干预入口
`rig` CLI SHALL 提供节点干预命令。

#### Scenario: CLI stop 节点
- **WHEN** 用户执行 `rig node stop llm-analyze`
- **THEN** 系统 SHALL 对该节点当前运行实例执行 soft stop

#### Scenario: CLI resume 节点
- **WHEN** 用户执行 `rig node resume llm-analyze --prompt "关注宏观经济因素"`
- **THEN** 系统 SHALL 找到该节点最近的 sandbox，以 `--continue` 模式启动 pi 并传入 prompt

