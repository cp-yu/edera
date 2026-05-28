## MODIFIED Requirements

### Requirement: 反思 DAG 独立编排
反思 DAG SHALL 作为独立 DAG 存在，通过 `session_dir` 引用目标节点的 sandbox 实现 session resume。

#### Scenario: 反思 DAG 配置
- **WHEN** 用户创建反思 DAG，其中 LLM 节点配置 `session_dir: "sandbox:llm-analyze:latest"`
- **THEN** 系统 SHALL 在执行时解析引用，resume 目标节点最近的 session

#### Scenario: 反思 DAG 访问历史输出
- **WHEN** 反思 DAG 的 source 节点通过 `edera entity query` 查询目标节点的历史输出
- **THEN** 系统 SHALL 返回目标节点的历史 NodeOutput entities

### Requirement: Cron + Idle 触发
反思 DAG SHALL 支持 cron 定时触发，触发时检测目标节点空闲状态。

#### Scenario: Cron 触发且目标空闲
- **WHEN** cron 定时触发反思 DAG，目标节点 `llm-analyze` 当前状态为 idle
- **THEN** 系统 SHALL 立即启动反思 DAG 执行

#### Scenario: Cron 触发但目标运行中
- **WHEN** cron 定时触发反思 DAG，目标节点 `llm-analyze` 当前状态为 running
- **THEN** 系统 SHALL 等待目标节点完成后再启动反思 DAG（wait_for 条件阻塞）

#### Scenario: 手动触发
- **WHEN** 用户通过 `edera dag trigger reflection-dag` 手动触发
- **THEN** 系统 SHALL 同样检测目标节点状态，空闲则执行，运行中则等待

### Requirement: 反思关系可观测性
系统 SHALL 支持通过 node ↔ node relation 声明反思 DAG 与目标节点的关联关系。

#### Scenario: 创建反思 relation
- **WHEN** 用户创建 relation `{from: "reflection-dag:analyzer-reflector", to: "default:llm-analyze", type: "reflects"}`
- **THEN** 系统 SHALL 持久化该 relation，可通过 entity query 查询

#### Scenario: 查询反思关系
- **WHEN** 用户执行 `edera entity query "relation_type=reflects AND to=default:llm-analyze"`
- **THEN** 系统 SHALL 返回所有反思该节点的 DAG/节点列表
