# node-executor Specification

## Purpose
此规约记录变更 project-mvp 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Skill 加载
Node executor SHALL 根据 Node 类型分叉执行路径：LLM Node 通过 pi CLI 执行 Skill（agent 循环 + 渐进展开），纯工程 Node 直接调用已注册的 Python async callable。

#### Scenario: 加载 LLM Skill
- **WHEN** Node 配置类型为 `llm`，引用了 `summarize` Skill
- **THEN** executor 通过 pi print 模式（-p）调用，pi 自行加载 `skills/summarize/` 并执行 agent 循环

#### Scenario: 加载纯工程 Skill
- **WHEN** Node 配置类型为 `function`，引用了 `fetch-rss`
- **THEN** executor 直接调用已注册的 Python async callable，不经过 pi

#### Scenario: 加载不存在的 Skill
- **WHEN** Node 配置引用了一个不存在的 Skill 名称
- **THEN** executor 返回错误，明确指出缺失的 Skill 名称

### Requirement: Agent 调用
Node executor SHALL 按 Node 类型选择调用方式：LLM Node 通过 pi CLI print 模式（-p）子进程调用，传入结构化输入（JSON），收集结构化输出（JSON）；纯工程 Node 直接调用 Python 函数。

#### Scenario: 成功调用 LLM Skill
- **WHEN** executor 调用 summarize Skill，传入 RawItem JSON
- **THEN** pi 执行完整 agent 循环（含多步工具调用和 Skill 渐进展开），返回 AnalysisResult JSON

#### Scenario: 成功调用纯工程 Skill
- **WHEN** executor 调用 fetch-rss，传入信息源配置
- **THEN** executor 直接调用 Python async callable 执行 HTTP 请求和 RSS 解析，返回 RawItem[] JSON

#### Scenario: Agent 执行超时
- **WHEN** Agent 执行时间超过配置的超时阈值
- **THEN** executor 终止该 Agent 进程，返回超时错误

### Requirement: I/O 管理
Node executor SHALL 管理节点的输入和输出，MUST 确保输入输出均为 Pydantic 模型序列化后的 JSON。

#### Scenario: 输入序列化
- **WHEN** DAG Runner 传入 Pydantic 模型实例作为节点输入
- **THEN** executor 将其序列化为 JSON 字符串传递给 Agent

#### Scenario: 输出反序列化
- **WHEN** Agent 返回 JSON 字符串输出
- **THEN** executor 将其反序列化为对应的 Pydantic 模型实例返回给 DAG Runner

### Requirement: Node 执行隔离
Node executor MUST 保证每个 Node 实例独立执行，Node 之间无直接通信。Node 不感知自身在 DAG 中的位置。

#### Scenario: 并发 Node 隔离
- **WHEN** 同一 Skill 的两个 Node 实例并发执行
- **THEN** 两个实例互不影响，各自独立完成执行并返回结果

### Requirement: Agent Workspace 部署
Node executor SHALL 为每个 LLM Node 调用构建隔离的 pi CLI 工作空间，确保 pi 仅加载该 Node 所需的上下文。

#### 约束：pi CLI 已验证加载行为（实测确认）

| 资源 | 加载来源 | 行为 |
|------|---------|------|
| AGENTS.md | `PI_CODING_AGENT_DIR`/AGENTS.md **不涵盖**，父目录链从 cwd 独立向上遍历 + cwd | 全部拼接；父目录链遍历**不受** `PI_CODING_AGENT_DIR` 控制 |
| .pi/SYSTEM.md | cwd/.pi/SYSTEM.md | 替换默认 system prompt |
| .pi/settings.json | `PI_CODING_AGENT_DIR`/settings.json + cwd/.pi/settings.json | project 覆盖 global |
| skills/ | 禁用自动发现，仅 `--skill <abs_path>` 生效 | 渐进式加载（多步循环已验证） |
| stdout | LLM 最终回复，**无**工具日志/thinking 混入 | 纯净，可直接 JSON.parse |
| session | `--session-dir <path>` 生效，per-invocation .jsonl 文件 | print mode 下支持 |

**额外发现（影响实现）：**
- pi 无 `--cwd` flag，cwd 必须通过 `subprocess(cwd=...)` 在进程级设置
- `--session-dir` 目标目录必须预先存在，否则 pi 启动即 ENOENT 报错

#### 决策：显式白名单 + 双重环境隔离

**原则：不依赖 pi 的任何自动发现机制，全部显式控制。**

防御层（缺一不可）：
1. `PI_CODING_AGENT_DIR` → 指向受控空目录，阻断 `~/.pi/agent/` 全局污染（skills、extensions、settings、全局 AGENTS.md）
2. workspace cwd → 必须位于 `/tmp/stockimformation/` 下，确保 cwd 到根路径上**不存在任何 AGENTS.md**（父目录链遍历独立于 `PI_CODING_AGENT_DIR`，无法通过环境变量阻断）
3. `--no-skills --skill <abs_path>` → 精确加载，消除 skills 自动发现
4. `--no-extensions --no-prompt-templates --no-themes` → 禁用其余自动发现

#### Workspace 目录结构

```
/tmp/stockimformation/runs/<dag-run-id>/<node-name>-<instance-id>/
├── AGENTS.md              # Node 工作契约（I/O schema + 约束 + 质量标准）
├── .pi/
│   ├── SYSTEM.md          # Agent 身份定义（替换默认 coding agent prompt）
│   └── settings.json      # Node 级配置（model + thinking level）
├── sessions/              # 预创建，--session-dir 指向此处（debug 用）
└── pi-home/               # 预创建空目录，PI_CODING_AGENT_DIR 指向此处
```

- Skill 源文件存放于项目 `skills/<name>/` 目录，通过 `--skill` 绝对路径引用，workspace 中无 skill 副本
- AGENTS.md 从项目源码 Node 模板生成（可含运行时注入的动态上下文，如 portfolio context）
- SYSTEM.md、settings.json 为 Node 类型级静态配置，从项目源码 copy 到 workspace

#### 职责三分法

| 文件 | 回答的问题 | 内容 |
|------|-----------|------|
| `.pi/SYSTEM.md` | "你是谁" | Agent 身份 + 硬约束（JSON-only 输出、无 markdown 包装） |
| `AGENTS.md` | "你在做什么、遵循什么约定" | I/O schema 定义、质量标准、边界条件处理规则 |
| `SKILL.md`（通过 `--skill` 加载） | "怎么做这件事" | 具体执行步骤（分析方法、分类标准、建议生成逻辑） |

#### Session 持久化（debug / 提示词优化用）

Node executor SHALL 通过 `--session-dir` 指定 per-invocation session 存储路径，executor 在创建 workspace 时预创建该目录。Session 生命周期：
- 失败（超时 / 输出校验失败 / 进程异常）→ 保留 workspace + session，供推理链分析
- 成功 → 可配置保留策略（默认保留最近 N 次，超出按 TTL 清理）

#### Scenario: Workspace 创建与隔离
- **WHEN** executor 准备调用 LLM Node
- **THEN** executor 在 `/tmp/stockimformation/runs/<dag-run-id>/` 下创建 per-invocation workspace，预创建 `sessions/` 和 `pi-home/` 子目录，设置 `PI_CODING_AGENT_DIR=<workspace>/pi-home`，以 `cwd=<workspace>` 启动 pi 子进程

#### Scenario: 全局配置污染防御
- **WHEN** 用户 `~/.pi/agent/` 目录存在个人 AGENTS.md、skills、extensions
- **THEN** pi 进程不加载任何全局资源（`PI_CODING_AGENT_DIR` 阻断全局目录；`/tmp` cwd 确保父目录链无 AGENTS.md 泄漏）

#### Scenario: 失败时 workspace 保留
- **WHEN** LLM Node 执行失败（超时 / 输出校验失败 / 进程异常退出）
- **THEN** executor 保留完整 workspace 目录（含 session .jsonl），记录 workspace 路径到错误日志

#### Scenario: 成功时 workspace 清理
- **WHEN** LLM Node 执行成功且输出通过 Pydantic 校验
- **THEN** executor 按配置保留策略处理 workspace（默认：保留最近 20 次，TTL 24h）

#### Scenario: Stale workspace 定期清理
- **WHEN** `/tmp/stockimformation/runs/` 下存在超过 TTL 的残留 workspace
- **THEN** 应用启动时 sweep 清理过期目录

### Requirement: pi CLI 调用规范

Node executor SHALL 使用固定参数组合调用 pi CLI（`subprocess.run`，`cwd` 设为 workspace 根）：

```
env:
  PI_CODING_AGENT_DIR = <workspace>/pi-home

args:
  pi -p
  --no-skills --skill <abs_path_to_skill_dir>
  --no-extensions
  --no-prompt-templates
  --no-themes
  --session-dir <workspace>/sessions
  "<input JSON>"

cwd: <workspace>/          # 无 --cwd flag，进程级设置
stdin: (可选，input JSON 超长时走 stdin)
```

**前置条件（executor 在 spawn 前完成）：**
1. `mkdir -p <workspace>/pi-home` — `PI_CODING_AGENT_DIR` 目标必须存在
2. `mkdir -p <workspace>/sessions` — `--session-dir` 目标必须存在
3. `<workspace>/AGENTS.md` 已写入
4. `<workspace>/.pi/SYSTEM.md` 已 copy
5. `<workspace>/.pi/settings.json` 已 copy

#### Scenario: 使用固定 pi CLI 参数
- **WHEN** executor 启动 LLM Node
- **THEN** 子进程 cwd 为 workspace 根，env 包含 `PI_CODING_AGENT_DIR=<workspace>/pi-home`，args 包含 `pi -p --no-skills --skill <abs_path_to_skill_dir> --no-extensions --no-prompt-templates --no-themes --session-dir <workspace>/sessions`

### Requirement: Node execution by instance ID
系统 SHALL 按 DAG 拓扑顺序调度节点实例执行，使用实例 UUID 作为调度和状态上报的索引键。

#### Scenario: Schedule by instance ID
- **WHEN** DAG 执行引擎启动一个运行周期
- **THEN** 系统 SHALL 按拓扑顺序遍历节点实例（通过 UUID 标识），而非节点类型名

#### Scenario: Runtime status indexed by instance ID
- **WHEN** 节点实例执行完成并上报状态
- **THEN** 系统 SHALL 以实例 UUID 为键存储运行状态（running/succeeded/failed）

#### Scenario: Multiple instances of same type execute independently
- **WHEN** DAG 中存在同一类型的多个实例
- **THEN** 系统 SHALL 独立调度和执行每个实例，各自维护独立的运行状态

### Requirement: Dynamic handler loading
系统 SHALL 通过 `importlib` 从 `handlers/` 目录动态加载 Function 节点的 handler。

#### Scenario: Load handler by name
- **WHEN** 系统执行一个 Function 节点实例且其类型定义 `handler: fetch-rss`
- **THEN** 系统 SHALL 动态加载 `handlers/fetch-rss.py` 并调用其 `run(input_data, parameters, context)` 函数

#### Scenario: Handler not found
- **WHEN** handler 文件不存在于 `handlers/` 目录
- **THEN** 系统 SHALL 将该节点实例标记为 `failed` 并记录错误信息

#### Scenario: Handler runtime error
- **WHEN** handler 执行过程中抛出异常
- **THEN** 系统 SHALL 捕获异常，将节点实例标记为 `failed`，记录错误堆栈

### Requirement: Instance config resolution
系统 SHALL 在执行节点实例时合并类型定义和实例级配置，实例配置优先。

#### Scenario: Merge type and instance config
- **WHEN** 系统准备执行一个节点实例
- **THEN** 系统 SHALL 以类型定义为基础，用实例 `config` 中的字段覆盖对应运行时参数（source_names、parameters、model、skills）

#### Scenario: Structural fields from type only
- **WHEN** 系统解析节点实例的执行配置
- **THEN** 系统 SHALL 始终从类型定义获取 `input_type`、`output_type`、`role`、`handler`、`system_prompt_file`，忽略实例级对这些字段的任何覆盖

### Requirement: Entity context injection

Node executor SHALL 在节点执行时注入实体上下文，提供 `context.get_entity()`, `context.save_entity()`, `context.create_entity()` 接口。

#### Scenario: Get entity by reference

- **WHEN** 节点调用 `context.get_entity("stock:00700.HK")`
- **THEN** executor 解析引用（UUID 或业务 ID），返回对应的实体对象

#### Scenario: Get entity not found

- **WHEN** 节点调用 `context.get_entity()` 引用不存在的实体
- **THEN** executor 抛出异常 "Entity not found: <reference>"

#### Scenario: Save entity with permission check

- **WHEN** 节点修改实体后调用 `context.save_entity(entity)`
- **THEN** executor 检查字段权限，保存允许修改的字段，记录警告日志并忽略受保护字段

#### Scenario: Create new entity

- **WHEN** 节点调用 `context.create_entity(type="stock", attributes={...})`
- **THEN** executor 生成 UUID，验证 attributes，保存到 `entities.yaml`

### Requirement: Field permission enforcement

Node executor SHALL 在节点访问实体字段时检查权限，违反权限时发出警告并阻止操作。

#### Scenario: Read protected field

- **WHEN** 节点尝试读取权限为 `none` 或 `write-only` 的字段
- **THEN** executor 记录警告 "Permission denied: <entity_type>.<field> is not readable"，返回 None

#### Scenario: Write protected field

- **WHEN** 节点尝试修改权限为 `none` 或 `read-only` 的字段
- **THEN** executor 记录警告 "Permission denied: <entity_type>.<field> is not writable"，不保存修改

#### Scenario: Permission check uses instance overrides

- **WHEN** 节点实例配置了 `entity_permissions: {stock: {code: read-write}}`
- **THEN** executor 使用实例权限（`read-write`）而非默认权限（`read-only`）

### Requirement: Entity auto-discovery

Node executor SHALL 在节点配置只指定 source 而未指定 entities 时，自动从 `entity-relations.yaml` 发现关联实体。

#### Scenario: Auto-discover entities from source

- **WHEN** 节点配置 `config: {source: "rss-source:sample-rss"}`，未指定 `entities`
- **THEN** executor 查找 `entity-relations.yaml` 中包含该 source 的关系，返回关联的其他实体

#### Scenario: Explicit entities override auto-discovery

- **WHEN** 节点配置 `config: {source: "rss-source:sample-rss", entities: ["stock:600519.SH"]}`
- **THEN** executor 使用显式配置的 `entities`，忽略自动发现

#### Scenario: Empty entities disable auto-discovery

- **WHEN** 节点配置 `config: {source: "rss-source:sample-rss", entities: []}`
- **THEN** executor 不提供任何实体上下文

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

