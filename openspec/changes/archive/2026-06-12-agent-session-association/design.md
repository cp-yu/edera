## Context

session 路径目前由 `_agent_session_dir(root, dag_name, instance_id, run_id)` 硬推导（`node/executor.py:291,644`），实例级 `session_dir` 配置与 `resume_session` payload 均无消费者；续接依赖 `has_session = glob("*.jsonl")` → `--continue` 的自动判定。规格层（llm-session-reuse / node-executor / node-instance-model）早已要求引用解析但从未实现，且规格用 `session:` 前缀、代码校验 `sandbox:` 前缀，术语分裂。agent 输出 payload 为 `{"stdout": 全部原始文本}`，无结构化契约。项目处于开发期，无历史负担（CLAUDE.md），破坏性变更可接受。

探索阶段已确认的术语决议：概念统一为 **session**；`session_dir` 废弃；`sandbox:` 为无关概念。"主从"不落字段——同 DAG 为抢锁顺序（先运行者建会话），跨 DAG 为引用方向（`@` 引用者恒为从）。

## Goals / Non-Goals

**Goals:**
- 同 DAG / 跨 DAG 的 agent node 通过 `session` 字段声明共享会话，先运行者创建、后续精确续接
- 组内串行与跨 DAG 等待复用现有 resource semaphore，用户零配置
- `@latest` / `@list`（含消费账本）支撑跨 DAG 自动化流水线（ctx2skill 等）
- agent 结构化输出契约（结果文件 + schema 校验 + 降级标记）
- 未声明 `session` 的节点行为完全不变

**Non-Goals:**
- TTL 清理与被引用 session 保护（llm-session-reuse 旧承诺一并移除，留后续变更）
- Web Inspector 的 session 编辑 UI
- session 实体化（Entity Store 接入）
- resume / retry 机制本身的改动（仅删除死的 `resume_session` payload）

## Decisions

### D1: 薄模块而非 SessionManager
新逻辑分摊到现有组件：`node/sessions.py` 只放引用解析/路径推导纯函数，组串行压在 loader 的隐式 resource 注入上（runner 零改动），`@latest`/`@list` 查询走 repository。**拒绝** SessionManager 组件——当前三个机制各有现成落点，强行聚合只是把三次委托调用改名（YAGNI）；**拒绝** session 实体化——声明仍需组名，等于在前两者之上加层，且每次 agent 运行多一次 entity 写入。待 TTL/清理需求真实出现时再聚合不迟。

### D2: 声明语法 = 组名 + 有向引用（混合）
同 DAG 用对称组名（`session: task-1`，先运行者为主，贴合数据流动态性）；跨 DAG 用有向引用（`session: main/task-1@latest|@list`，引用方恒为从，主从无需额外字段）。**拒绝**统一有向引用（同 DAG 失去"先运行者为主"的动态性，主被静态钉死）。

### D3: 串行机制 = 隐式 resource semaphore
loader 识别同组 agent 实例后注入 `session:{dag}/{group}`（permits=1）；跨 DAG 引用挂源组同名 resource，复用其已有跨 DAG 共享语义。同 DAG 并行分支（`a→B`、`a→D` 同组）与跨 DAG 等待是同一把锁。**拒绝**用户手配 resource（忘配 = 静默竞写）；**拒绝**调度期隐式依赖边（跨 DAG 并发 run 无防护）。等待超时复用节点 `timeout_seconds`，不发明新机制。

### D4: 显式 `--session <session-id>` 替代 `--continue` 自动判定
共享目录下 `glob("*.jsonl")` 只能回答"有没有会话"，回答不了"是不是这个会话"，`--continue` 可能续接到错误 session。主节点创建会话后捕获 session_id 登记注册表，后续节点一律 `--session <id>` 精确续接。session_id 捕获方式（解析 jsonl 文件名 vs 预生成传入）依赖 pi 实际语义，由 spike #1 定夺。

### D5: 注册表 + 消费账本（两张小表）
`session_runs(dag, group, run_id, session_id, status, path)`：创建时 `active`，DAG run 结束落 `completed/failed`；`@latest` 只取最近 completed。`session_consumptions(source_session_id, consumer)`：从端节点**成功**（result.json 校验通过）才登记，降级/失败不登记 → 自动重试、不重复、不漏。**拒绝** ctx2skill 专用表——"哪些 session 未被我处理"对任意从端场景成立，通用账本只多一列 consumer。

### D6: 共享物最小化 + invocation 命名空间
组目录 `sessions/{dag}/{group}/{run_id}/` 下共享物仅 `*.jsonl`（会话本体）与 `skills/`（生成幂等）；prompt.md、runtime-context.json、stdout.log、result.json 全部下放 `invocations/{node_id}/`，互踩在路径层消除。默认 workdir 从 `session_dir.parent` 改为 invocation 目录（清 todo.md:102 欠账）。

### D7: 结构化输出 = 约定结果文件
runtime-context 注入 `result_path` + `output_schema`（`output_type` → entity-type schema，无 schema 则自由 JSON），prompt 尾部拼接写入指令；退出后读取校验，失败降级 `{"stdout": ...}` + metadata 标记（条件边可路由降级分支）。**拒绝**解析 session 末条消息（耦合 pi 内部格式、合法性不可控）；**拒绝**依赖 pi 原生 structured output（能力未证实）。

### D8: ctx2skill 两种模式均为编排层模式，引擎无感知
"本上下文直接 2skill" = 从端节点 `--session <id>` 直接续接源会话；"先 handoff 再 2skill" = 主 DAG 末尾加同组总结节点，从端续接浓缩后的上下文。跨 DAG 触发复用现有 node emits + trigger。

## Risks / Trade-offs

- [pi `--session` 语义未验证（仓库内不可证实）] → spike #1 前置于一切实现代码；兜底：组路径下每 run 独立目录、目录内单一会话，退回 `--continue` 仍无歧义
- [崩溃残留 `active` 注册行，`@latest` 解析不到] → daemon 启动对账：非活跃 run 的 `active` 行批量落 `failed`（semaphore 在内存中重启自清，DB 行不会）
- [用户 resource + 隐式 session resource 双锁死锁] → 每节点至多一个 session 组（单值字段），多锁按 resource 名固定排序获取，消除 hold-and-wait 环
- [从端阻塞时长不可控] → 等待计入节点 `timeout_seconds`，超时即节点失败，由 trigger 重试消化
- [共享 session 上下文无界膨胀] → 本期接受；编排层 handoff 总结模式缓解，TTL/压缩留后续
- [降级输出静默流向下游] → metadata 降级标记 + 消费账本不登记降级 run
- [从端续接会向历史会话追加轮次] → 接受：会话本就是 append-only，账本防重复，主端每 run 新建目录互不影响
- [废弃 `session_dir` 是破坏性变更] → 开发期无历史负担；钉死旧行为的测试同步更新

## Migration Plan

无存量数据迁移（开发期）。实施顺序：spike #1 → schema/loader → 注册表 migration → executor → server 清理 → 测试扩展 → 测试更新。回滚 = revert 分支，无 DB 回滚负担（新表只增不改旧表）。

## Open Questions

- session_id 捕获方式（解析 jsonl 文件名 vs 预生成传入 `--session`）：spike #1 输出定夺
- `@list` 模式下从端单次处理多个未消费 session 时的输出聚合形态：实现时按测试扩展实际需要从简决定
