<!-- propose routing: Design Summary found in explore conversation (agent-session-association); input length n/a; detail score n/a; multi-subsystem: no; decision: proceed using Design Summary -->

## Why

Agent node 之间无法复用会话：session 路径由 `(dag_name, instance_id, run_id)` 硬推导，三个 specs（llm-session-reuse、node-executor、node-instance-model）要求的 session 引用解析从未实现，`server.py` Resume RPC 发出的 `resume_session` payload 无任何消费者。同时 agent 节点输出只有裸 stdout，下游 function node 无法可靠消费。本变更实现 session 关联模型，让同 DAG / 跨 DAG 的 agent node 共享会话（接力处理、ctx2skill 等场景），并补上结构化输出契约。

## What Changes

- **BREAKING** `DagNodeInstance.config` 新增 `session` 字段（组名 / `<dag>/<group>@latest` / `<dag>/<group>@list`），废弃并删除 `session_dir` 字段及 `sandbox:` 引用语法；术语统一为 session
- **BREAKING** agent 续接机制由 `has_session` glob + `--continue` 自动判定改为显式 `pi --session <session-id>`
- 同组 agent node 共享 session：先运行者创建会话（主），后续节点精确续接（从）；主从不落字段——同 DAG 靠抢锁顺序，跨 DAG 靠引用方向
- loader 为 session 组自动注入隐式 resource `session:{dag}/{group}`（permits=1），复用现有 resource semaphore 实现组内串行与跨 DAG 等待，用户零配置
- 新增 session run 注册表与消费账本（DB 两张小表）：支撑 `@latest`（最近 completed run）与 `@list`（含 consumed 标记，自动处理未消费 session，从端成功才登记消费）
- session 存储改为 `sessions/{dag}/{group}/{run_id}/`，逐次产物（prompt.md、runtime-context.json、stdout.log、result.json）下放 `invocations/{node_id}/`；默认 workdir 改为 invocation 目录（解开与 session 路径的纠缠）
- agent 结构化输出契约：runtime-context 注入 `result_path` + `output_schema`，executor 退出后读取校验，失败降级 `{"stdout": ...}` 并打 metadata 标记
- 删除 `server.py` Resume RPC 中无消费者的 `resume_session` payload（resume 机制本身不动）
- 新增测试扩展 `extensions/session-relay-test/`：两个 DAG（同 DAG 接力 + 条件边；跨 DAG ctx2skill 引用）
- 未声明 `session` 的 agent node 行为完全不变（路径按 instance 推导，零迁移）

## Capabilities

### New Capabilities
- `session-relay-test-extension`: 测试扩展，包含 relay-main（a→B→c→D 同组接力 + 条件边跳过）与 relay-skill（跨 DAG `@latest`/`@list` 引用消费）两个 DAG 及配套 function handler

### Modified Capabilities
- `llm-session-reuse`: 重写为 session 关联模型——`session` 字段语法、组共享路径结构、隐式 resource 串行、run 注册表与 `@latest`/`@list` 解析、消费账本；删除 `session_dir` 引用格式与 TTL 延迟清理承诺
- `node-executor`: session 解析改走新 `session` 字段（未声明回退原路径）；`--session <id>` 显式续接替代 `--continue` 自动判定；agent workdir 默认值改为 invocation 目录
- `agent-executor`: pi CLI 命令契约更新（`--session`）；逐次产物 invocation 命名空间；结构化输出契约与降级行为
- `node-instance-model`: `session_dir` 字段删除，`session` 字段新增及校验规则
- `skill-dynamic-generation`: 共享 session 下 `{session_dir}/skills/` 由组内节点共用、生成幂等的措辞修正

## Impact

- 代码：`config/schema.py`、`dag/loader.py`、`node/sessions.py`（新）、`node/executor.py`、`storage/repository.py` + migration、`server.py`、`extensions/session-relay-test/`（新）
- 测试：`test_core_architecture_overhaul.py`、`test_node_executor.py`、`test_node_instance_model.py`、`test_grpc_control_services.py` 中钉死旧行为的断言需同步更新
- 外部依赖：pi CLI `--session <id>` 语义需 spike 验证（兜底：每 run 独立目录退回 `--continue`）
- 不做：TTL 清理、被引用保护、Web Inspector session 编辑 UI、session 实体化
