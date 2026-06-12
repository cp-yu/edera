# session-relay-test-extension Specification

## Purpose
此规约记录变更 agent-session-association 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 测试扩展安装
扩展 `session-relay-test` SHALL 通过现有 extension manifest 体系安装，提供 `relay-main` 与 `relay-skill` 两个 DAG 及配套 function handler。

#### Scenario: 扩展安装后 DAG 可用
- **WHEN** 安装 `session-relay-test` 扩展
- **THEN** 系统 SHALL 注册 `relay-main` 和 `relay-skill` 两个 DAG，可被手动运行

### Requirement: relay-main 同 DAG 接力
`relay-main` DAG SHALL 包含拓扑 `a→B→c→D`：`a`、`c` 为 function 节点，`B`、`D` 为声明同一 session 组的 agent 节点；`c→D` 边 SHALL 带条件表达式，按 `c` 的输出决定是否执行 `D`。

#### Scenario: 接力共享会话
- **WHEN** `relay-main` 运行且 `c` 输出满足条件边
- **THEN** `D` SHALL 续接 `B` 创建的同一会话，其执行可见 `B` 的上下文

#### Scenario: 条件不满足跳过 D
- **WHEN** `c` 输出不满足条件边表达式
- **THEN** `D` SHALL 被跳过，run 正常结束

#### Scenario: B 产出结构化输出
- **WHEN** `B` 执行完成
- **THEN** `B` 的 payload SHALL 为结构化 JSON，`c` 的 handler 可直接读取其字段

### Requirement: relay-skill 跨 DAG 消费
`relay-skill` DAG SHALL 包含一个 agent 节点 `X`，以跨 DAG 引用消费 `relay-main` 的 session 组：续接源会话并产出结构化结果。

#### Scenario: latest 引用续接源会话
- **WHEN** `relay-main` 至少完成一次 run 后运行 `relay-skill`（`X` 声明 `@latest` 引用）
- **THEN** `X` SHALL 续接源组最近完成 run 的会话并成功产出结果

#### Scenario: list 模式不重复消费
- **WHEN** `X` 以 `@list` 模式连续两次成功处理同一源组
- **THEN** 第二次运行 SHALL 选取不同于第一次的未消费 session；无未消费项时 `X` 失败并提示无可消费 session

