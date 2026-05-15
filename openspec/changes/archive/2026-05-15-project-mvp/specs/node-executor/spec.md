## ADDED Requirements

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
