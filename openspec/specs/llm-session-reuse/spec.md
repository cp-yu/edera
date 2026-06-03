---
capabilities:
  - cap.operations.llm-session-reuse
---
# llm-session-reuse Specification

## Purpose
定义 server 管理的 Session 路径结构、Session 目录独立管理、session_dir 配置、自动 resume 判定等能力。
## Requirements
### Requirement: Session 路径结构
LLM 节点执行时 SHALL 使用 server 管理的 `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/{run_id}/` 作为 session 目录。

#### Scenario: 首次执行创建 session 目录
- **WHEN** LLM 节点实例 `llm-analyze` 在 run `run-20260524-001` 中首次执行
- **THEN** 系统 SHALL 创建目录 `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/run-20260524-001/`

#### Scenario: Session 路径确定性
- **WHEN** 同一节点在同一 run 中重复执行（如重试）
- **THEN** 系统 SHALL 复用已有的 session 目录，不创建新目录

### Requirement: Session 目录独立管理
Session 目录 SHALL 独立于 workspace 生命周期，按 TTL/size 策略清理。

#### Scenario: Session 清理不影响其他 session
- **WHEN** session `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/run-20260524-001/` 达到 TTL 过期条件
- **THEN** 系统 SHALL 仅清理该 session 目录，不影响同 instance_id 下其他 run 的 session

#### Scenario: 被引用的 session 不被清理
- **WHEN** 某个 DAG 的节点配置 `session_dir` 引用了 `session:llm-analyze:run-20260524-001`，且该 session 达到 TTL
- **THEN** 系统 SHALL 延迟清理直到引用解除

### Requirement: session_dir 配置
`DagNodeInstance.config` SHALL 支持 `session_dir` 字段，控制 LLM 节点的 session 存储位置。

#### Scenario: 未设置 session_dir
- **WHEN** 节点实例未配置 `session_dir`
- **THEN** 系统 SHALL 使用默认路径 `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/{current_run}` 创建新 session

#### Scenario: 绝对路径 session_dir
- **WHEN** 节点实例配置 `session_dir: "/data/persistent/advisor-session"`
- **THEN** 系统 SHALL 使用该绝对路径作为 pi 的 `--session-dir` 参数

#### Scenario: 引用格式 session_dir（latest）
- **WHEN** 节点实例配置 `session_dir: "session:llm-analyze:latest"`
- **THEN** 系统 SHALL 解析为 `llm-analyze` 节点实例最近一次执行的 server-managed session 路径

#### Scenario: 引用格式 session_dir（指定 run）
- **WHEN** 节点实例配置 `session_dir: "session:llm-analyze:run-20260524-001"`
- **THEN** 系统 SHALL 解析为 `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/run-20260524-001/`

#### Scenario: 引用目标不存在
- **WHEN** `session_dir` 引用的 session 路径不存在（已被清理）
- **THEN** 系统 SHALL 返回 `NodeOutput(ok=False, error="session not found: ...")` 而非创建新 session

### Requirement: 自动 resume 判定
系统 SHALL 根据 session_dir 中是否存在已有 session 文件自动决定新建或 resume。

#### Scenario: 存在已有 session 文件
- **WHEN** `session_dir` 指向的目录中存在 `.jsonl` session 文件
- **THEN** 系统 SHALL 向 pi 传递 `--continue` flag 以 resume 该 session

#### Scenario: 不存在 session 文件
- **WHEN** `session_dir` 指向的目录中无 `.jsonl` session 文件
- **THEN** 系统 SHALL 不传 `--continue`，pi 创建新 session

### Requirement: Payload 动态覆盖
节点 input payload 中的 `resume_session` 字段 SHALL 覆盖静态配置的 `session_dir`。

#### Scenario: Payload 覆盖配置
- **WHEN** 节点配置 `session_dir: "session:llm-analyze:latest"`，但 input payload 包含 `resume_session: "session:llm-analyze:run-20260524-001"`
- **THEN** 系统 SHALL 使用 payload 中的值，忽略配置中的 `session_dir`

#### Scenario: Payload 无 resume_session
- **WHEN** input payload 不包含 `resume_session` 字段
- **THEN** 系统 SHALL 使用配置中的 `session_dir`（或默认行为）
