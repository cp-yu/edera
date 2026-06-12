### Task 1: Spike — pi `--session` 语义验证

**Goal**: 在实现前实测 pi CLI 指定 session id 续接与新建会话的行为，定夺 session_id 捕获方式（解析 jsonl 文件名 vs 预生成传入）。

**Files**:
- Create: `openspec/changes/agent-session-association/spike-pi-session.md`

**Requirements**:
- 实测 `pi --session <id>` 对已存在会话的续接行为
- 实测新建会话时 session id 的产生方式与落盘形态
- 记录兜底方案适用性结论（每 run 独立目录退回 `--continue`）
- 输出 session_id 捕获方式决议供 Task 6 使用

#### Checks

- [x] C1 验证 pi 指定 session id 续接语义
  - Verifies: `specs/agent-executor/spec.md` / Requirement "Pi CLI subprocess 配置" / Scenario "续接执行精确指定会话"
  - Command: `cat openspec/changes/agent-session-association/spike-pi-session.md`
  - Evidence: spike 记录包含新建/续接两种调用的实测命令与输出，以及 session_id 捕获方式结论

### Task 2: `session` 字段校验与 `session_dir` 删除

**Goal**: `DagNodeInstance.config` 支持 `session` 字段语法校验，删除已废弃的 `session_dir` 校验与 `sandbox:` 语法。

**Files**:
- Modify: `packages/core/src/edera_core/config/schema.py`
- Modify: `packages/core/src/edera_core/service_common.py`
- Test: `tests/core/unit/test_node_instance_model.py`

**Requirements**:
- 合法格式：`<group>`、`<dag_name>/<group>@latest`、`<dag_name>/<group>@list`
- 非法格式拒绝并提示格式错误
- 删除 `_valid_session_dir` 与 `sandbox:` 引用语法
- 实例 config allowlist/JSON schema 中 `session_dir` 替换为 `session`

#### Checks

- [x] C2 验证组名与跨 DAG 引用格式通过校验
  - Verifies: `specs/node-instance-model/spec.md` / Requirement "Session 字段" / Scenario "组名配置" / Scenario "跨 DAG 引用配置"
  - Command: `uv run pytest tests/core/unit/test_node_instance_model.py -k session`
  - Expect: 组名与 `@latest`/`@list` 引用均保存成功

- [x] C3 验证非法格式被拒绝
  - Verifies: `specs/node-instance-model/spec.md` / Requirement "Session 字段" / Scenario "非法格式拒绝"
  - Command: `uv run pytest tests/core/unit/test_node_instance_model.py -k session`
  - Expect: `a/b/c@latest`、`task-1@unknown` 等格式触发 ValidationError

- [x] C4 验证 session_dir 字段已删除
  - Verifies: `specs/node-instance-model/spec.md` / REMOVED Requirement "Session_dir 字段"
  - Command: `grep -rn "session_dir\|_valid_session_dir" packages/core/src/edera_core/config/schema.py packages/core/src/edera_core/service_common.py`
  - Expect: 无匹配

### Task 3: Session run 注册表与消费账本

**Goal**: 新增 `session_runs` 与 `session_consumptions` 两张表及查询函数，支撑 `@latest`/`@list` 解析与启动对账。

**Files**:
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Modify: `packages/core/src/edera_core/storage/__init__.py`
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Test: `tests/core/unit/test_session_registry.py`

**Requirements**:
- `session_runs(dag_name, group, run_id, session_id, status, path)`：创建登记 `active`，DAG run 结束落 `completed/failed`
- `session_consumptions(source_session_id, consumer)`：成功才登记
- 查询函数：register / finish / latest（只取 completed）/ list（含 consumed 标记）
- daemon 启动对账：非活跃 run 的 `active` 行批量落 `failed`

#### Checks

- [x] C5 验证注册与状态流转
  - Verifies: `specs/llm-session-reuse/spec.md` / Requirement "Session run 注册表" / Scenario "创建时登记 active" / Scenario "Run 结束更新状态"
  - Command: `uv run pytest tests/core/unit/test_session_registry.py`
  - Expect: 创建后 status 为 active，run 结束后为 completed

- [x] C6 验证启动对账清理残留
  - Verifies: `specs/llm-session-reuse/spec.md` / Requirement "Session run 注册表" / Scenario "启动对账清理残留"
  - Command: `uv run pytest tests/core/unit/test_session_registry.py -k reconcile`
  - Expect: 孤儿 active 行启动后变为 failed

- [x] C7 验证 latest 只取最近 completed
  - Verifies: `specs/llm-session-reuse/spec.md` / Requirement "跨 DAG latest 解析" / Scenario "解析到最近完成的 run" / Scenario "无可用记录"
  - Command: `uv run pytest tests/core/unit/test_session_registry.py -k latest`
  - Expect: 多条 completed 取最近一条；无 completed 时返回空并由调用方产生失败

- [x] C8 验证消费账本登记与过滤
  - Verifies: `specs/llm-session-reuse/spec.md` / Requirement "List 解析与消费账本" / Scenario "成功后登记消费" / Scenario "失败不登记可重试" / Scenario "默认取最旧未消费"
  - Command: `uv run pytest tests/core/unit/test_session_registry.py -k consumption`
  - Expect: 成功登记后 consumed 为 true，失败不登记，默认选取最旧未消费项

- [x] C9 确认本变更不引入 session TTL 清理承诺
  - Verifies: `specs/llm-session-reuse/spec.md` / REMOVED Requirement "Session 目录独立管理"
  - Command: `grep -rni "session.*ttl\|ttl.*session" packages/core/src/edera_core/`
  - Expect: 无匹配

### Task 4: Loader 隐式 resource 注入

**Goal**: DAG 加载时识别 session 组并自动注入 `session:{dag}/{group}`（permits=1）resource，跨 DAG 引用挂源组同名 resource。

**Files**:
- Modify: `packages/core/src/edera_core/dag/loader.py`
- Test: `tests/core/unit/test_session_group_loader.py`

**Requirements**:
- 同组 agent 实例自动挂载 `session:{dag_name}/{group}` resource，permits=1
- 跨 DAG 引用实例挂源 DAG 组的同名 resource
- 用户已配置的 resource 与隐式 resource 共存，按 resource 名固定排序获取
- 未声明 `session` 的实例不注入

#### Checks

- [x] C10 验证隐式 resource 零配置注入
  - Verifies: `specs/llm-session-reuse/spec.md` / Requirement "Session 组串行" / Scenario "用户零配置"
  - Command: `uv run pytest tests/core/unit/test_session_group_loader.py`
  - Expect: 仅声明 `session: task-1` 的两个实例均挂载 `session:{dag}/task-1`，permits=1

- [x] C11 验证跨 DAG 引用挂源组 resource
  - Verifies: `specs/llm-session-reuse/spec.md` / Requirement "Session 组串行" / Scenario "跨 DAG 引用方等待"
  - Command: `uv run pytest tests/core/unit/test_session_group_loader.py -k cross_dag`
  - Expect: 声明 `relay-main/task-1@latest` 的实例挂载 `session:relay-main/task-1`

### Task 5: Session 引用解析接入 executor

**Goal**: 新增 `node/sessions.py` 解析纯函数，executor 执行 agent 节点前解析 `session` 字段；未声明节点行为不变。

**Files**:
- Create: `packages/core/src/edera_core/node/sessions.py`
- Modify: `packages/core/src/edera_core/node/executor.py`
- Test: `tests/core/unit/test_node_executor.py`

**Requirements**:
- 组名解析为 `sessions/{dag_name}/{group}/{run_id}/`
- `@latest`/`@list` 经注册表解析为源组会话（session_id + path）
- 未声明 `session` 按 `instance_id` 推导，路径与既有行为一致
- 同一 run 内重复执行（重试）复用既有目录

#### Checks

- [x] C12 验证组名解析为组路径
  - Verifies: `specs/node-executor/spec.md` / Requirement "Session 引用解析" / Scenario "组名解析为当前 run 组路径"
  - Command: `uv run pytest tests/core/unit/test_node_executor_session.py -k session_group`
  - Expect: session 目录为 `sessions/{dag}/task-1/{run_id}/`

- [x] C13 验证首次执行创建组目录与路径确定性
  - Verifies: `specs/llm-session-reuse/spec.md` / Requirement "Session 路径结构" / Scenario "首次执行创建 session 目录" / Scenario "Session 路径确定性"
  - Command: `uv run pytest tests/core/unit/test_node_executor_session.py -k session_group`
  - Expect: 组内首次执行创建目录，同 run 重复执行复用同一目录

- [x] C14 验证未声明 session 行为不变
  - Verifies: `specs/node-executor/spec.md` / Requirement "Session 引用解析" / Scenario "未声明 session 行为不变"
  - Command: `uv run pytest tests/core/unit/test_node_executor_session.py -k no_session`
  - Expect: 未声明实例路径仍为 `sessions/{dag}/{instance_id}/{run_id}/`

- [x] C15 验证跨 DAG 引用经注册表解析
  - Verifies: `specs/node-executor/spec.md` / Requirement "Session 引用解析" / Scenario "跨 DAG 引用经注册表解析"
  - Command: `uv run pytest tests/core/unit/test_node_executor_session.py -k cross_dag`
  - Expect: `@latest` 解析到注册表中最近 completed run 的 session_id 与 path

- [x] C16 验证 session_dir 解析路径已删除
  - Verifies: `specs/node-executor/spec.md` / REMOVED Requirement "Session_dir 解析与传递"
  - Command: `grep -rn "session_dir" packages/core/src/edera_core/node/`
  - Expect: 无匹配

### Task 6: `--session` 续接与 invocation 命名空间

**Goal**: agent 执行改为显式 `--session <id>` 续接，逐次产物移入 `invocations/{node_id}/`，默认 workdir 改为 invocation 目录。

**Files**:
- Modify: `packages/core/src/edera_core/node/executor.py`
- Test: `tests/core/unit/test_node_executor.py`
- Test: `tests/core/unit/test_core_architecture_overhaul.py`

**Requirements**:
- 目标会话已登记 session id 时命令含 `--session <id>`，无登记时不传
- 删除 `has_session` glob 与 `--continue` 自动判定
- prompt.md、runtime-context.json、stdout.log、result.json 写入 `invocations/{node_id}/`
- 未配置 `workdir` 时 cwd 为 invocation 目录
- 同组 skills/ 共用且重复生成幂等

#### Checks

- [ ] C17 验证首次执行与续接的命令构造
  - Verifies: `specs/agent-executor/spec.md` / Requirement "Pi CLI subprocess 配置" / Scenario "首次执行不带 session 参数" / Scenario "续接执行精确指定会话"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py -k pi_session_flag`
  - Expect: 无登记不含 `--session`；有登记含 `--session S`

- [ ] C18 验证 --continue 自动判定已删除
  - Verifies: `specs/node-executor/spec.md` / REMOVED Requirement "自动 --continue 判定"
  - Command: `grep -rn '"--continue"\|has_session' packages/core/src/edera_core/node/executor.py`
  - Expect: 无匹配

- [ ] C19 验证逐次产物命名空间
  - Verifies: `specs/agent-executor/spec.md` / Requirement "Invocation 产物命名空间" / Scenario "逐次产物写入节点专属目录" / Scenario "同组节点产物互不覆盖"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py -k invocation`
  - Expect: 产物位于 `invocations/{node_id}/`，同组两节点产物并存

- [ ] C20 验证默认 workdir 为 invocation 目录
  - Verifies: `specs/node-executor/spec.md` / Requirement "Agent 节点 workdir 和 session 分离" / Scenario "未配置 workdir 时默认为 invocation 目录" / Scenario "Workdir 设置为 cwd"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py -k workdir`
  - Expect: 未配置时 cwd 为 invocation 目录，配置时为配置值

- [ ] C21 验证同组 skills 目录共用且幂等
  - Verifies: `specs/skill-dynamic-generation/spec.md` / Requirement "Agent 执行时生成 skill 文件" / Scenario "同组节点共用 skills 目录"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py -k skills_idempotent`
  - Expect: 同组第二个节点执行后 skills/ 内容一致且不报错

- [ ] C22 验证 resume 以 session id 精确续接
  - Verifies: `specs/agent-executor/spec.md` / Requirement "Resume 生命周期" / Scenario "Resume 启动新进程" / Scenario "Resume 注入新 prompt"
  - Command: `uv run pytest tests/core/unit/test_core_architecture_overhaul.py -k resume`
  - Expect: resume 启动的新 subprocess 以原会话 session id 续接并接受新 prompt

### Task 7: Agent 结构化输出契约

**Goal**: runtime-context 注入 `result_path` + `output_schema`，退出后读取校验，失败降级并打标记。

**Files**:
- Modify: `packages/core/src/edera_core/node/executor.py`
- Test: `tests/core/unit/test_agent_result_contract.py`

**Requirements**:
- runtime-context 含 `result_path` 与 `output_schema`（`output_type` → entity-type schema，无则自由 JSON）
- prompt 尾部拼接结果写入指令
- 校验通过则 payload 为解析后 JSON
- 缺失或校验失败降级 `{"stdout": ...}` + metadata 降级标记

#### Checks

- [ ] C23 验证结果文件校验通过路径
  - Verifies: `specs/agent-executor/spec.md` / Requirement "Agent 结构化输出契约" / Scenario "结果文件校验通过" / Scenario "无 schema 时自由 JSON"
  - Command: `uv run pytest tests/core/unit/test_agent_result_contract.py`
  - Expect: payload 为解析后 JSON；无 schema 时任意合法 JSON 通过

- [ ] C24 验证缺失与校验失败降级
  - Verifies: `specs/agent-executor/spec.md` / Requirement "Agent 结构化输出契约" / Scenario "结果文件缺失降级" / Scenario "校验失败降级"
  - Command: `uv run pytest tests/core/unit/test_agent_result_contract.py -k degrade`
  - Expect: payload 为 `{"stdout": ...}` 且 metadata 含降级标记

### Task 8: Server 死路径清理

**Goal**: 删除 Resume RPC 中无消费者的 `resume_session` payload，更新钉死旧行为的测试。

**Files**:
- Modify: `packages/core/src/edera_core/server.py`
- Test: `packages/core/tests/test_grpc_control_services.py`
- Test: `tests/core/unit/test_core_architecture_overhaul.py`

**Requirements**:
- Resume RPC 不再构造 `resume_session` 字段，resume 行为本身不变
- 全代码库清除 `resume_session` 残留引用

#### Checks

- [ ] C25 验证 resume_session payload 已删除
  - Verifies: `specs/llm-session-reuse/spec.md` / REMOVED Requirement "Payload 动态覆盖"
  - Command: `grep -rn "resume_session" packages/ tests/`
  - Expect: 无匹配

- [ ] C26 验证 glob 式自动 resume 判定已移除
  - Verifies: `specs/llm-session-reuse/spec.md` / REMOVED Requirement "自动 resume 判定"
  - Command: `uv run pytest packages/core/tests/test_grpc_control_services.py -k resume`
  - Expect: resume 测试通过且不依赖 `.jsonl` glob 判定

### Task 9: 同组串行与跨 DAG 集成测试（fake pi）

**Goal**: 用 fake pi 脚本端到端验证组串行、跨 DAG 等待/超时与消费流转。

**Files**:
- Test: `tests/core/integration/test_session_relay.py`

**Requirements**:
- fake pi 记录调用参数与起止时间，产出 jsonl + result.json
- 覆盖并行同组串行、跨 DAG 阻塞与超时、组共享续接、消费不重复

#### Checks

- [ ] C27 验证同 DAG 并行分支串行化
  - Verifies: `specs/llm-session-reuse/spec.md` / Requirement "Session 组串行" / Scenario "同 DAG 并行分支串行化"
  - Command: `uv run pytest tests/core/integration/test_session_relay.py -k parallel_serialized`
  - Expect: 同组两个 agent 进程运行时间不重叠

- [ ] C28 验证组共享与精确续接
  - Verifies: `specs/llm-session-reuse/spec.md` / Requirement "Session 组共享与续接" / Scenario "首个节点创建会话" / Scenario "后续节点精确续接"
  - Command: `uv run pytest tests/core/integration/test_session_relay.py -k relay`
  - Expect: 首节点创建并登记 session id，后续节点收到 `--session <同一 id>`

- [ ] C29 验证跨 DAG 等待与超时
  - Verifies: `specs/llm-session-reuse/spec.md` / Requirement "Session 组串行" / Scenario "跨 DAG 引用方等待" / Scenario "等待超时"
  - Command: `uv run pytest tests/core/integration/test_session_relay.py -k wait`
  - Expect: 源组持锁时引用方阻塞；超过 timeout_seconds 后节点失败

- [ ] C30 验证 list 消费不重复且可重试
  - Verifies: `specs/llm-session-reuse/spec.md` / Requirement "List 解析与消费账本" / Scenario "默认取最旧未消费" / Scenario "失败不登记可重试" / Scenario "输入显式指定 run"
  - Command: `uv run pytest tests/core/integration/test_session_relay.py -k consumption`
  - Expect: 连续两次成功消费选取不同 session；失败 run 再次触发被重新选取；显式 run_id 忽略 consumed

### Task 10: 测试扩展 session-relay-test

**Goal**: 创建包含 relay-main 与 relay-skill 两个 DAG 的测试扩展，作为真 pi E2E 验收载体。

**Files**:
- Create: `extensions/session-relay-test/`
- Test: `tests/core/integration/test_session_relay_extension.py`

**Requirements**:
- manifest 按现有 extension manifest 体系编写
- relay-main：`a→B→c→D`，B/D 声明 `session: task-1`，`c→D` 条件边
- relay-skill：X 声明 `relay-main/task-1@latest`（含 `@list` 用法说明）
- handler `a` 产出种子输入，handler `c` 读取 B 结构化输出并产出条件字段

#### Checks

- [ ] C31 验证扩展安装后 DAG 可用
  - Verifies: `specs/session-relay-test-extension/spec.md` / Requirement "测试扩展安装" / Scenario "扩展安装后 DAG 可用"
  - Command: `uv run pytest tests/core/integration/test_session_relay_extension.py -k install`
  - Expect: 安装后 relay-main 与 relay-skill 可被列出并运行

- [ ] C32 验证 relay-main 接力与条件边
  - Verifies: `specs/session-relay-test-extension/spec.md` / Requirement "relay-main 同 DAG 接力" / Scenario "接力共享会话" / Scenario "条件不满足跳过 D" / Scenario "B 产出结构化输出"
  - Command: `uv run pytest tests/core/integration/test_session_relay_extension.py -k relay_main`
  - Expect: 条件满足时 D 续接 B 的会话；不满足时 D 跳过；c 可读取 B 的结构化字段

- [ ] C33 验证 relay-skill 跨 DAG 消费
  - Verifies: `specs/session-relay-test-extension/spec.md` / Requirement "relay-skill 跨 DAG 消费" / Scenario "latest 引用续接源会话" / Scenario "list 模式不重复消费"
  - Command: `uv run pytest tests/core/integration/test_session_relay_extension.py -k relay_skill`
  - Expect: X 续接源组最近完成会话；list 模式两次运行不重复消费
