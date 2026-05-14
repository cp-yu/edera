# ADR: Agent 运行时选型 — pi CLI

**状态：** 已裁定
**日期：** 2026-04-10
**决策者：** 项目方 + 三模型交叉验证（Codex/Gemini/Claude Opus）

## 决策

使用 pi CLI（badlogic/pi）作为 LLM Node 的 Agent 运行时。纯工程 Node 直接 Python 原生实现。

## 核心问题

项目的 LLM Node（summarize、classify-sentiment、generate-advice、generate-briefing）在 DAG 视角是"单输入→单输出"的黑盒，但内部需要多步 agent 循环：工具调用、Skill 渐进展开、中间推理。系统需要一个 Agent 运行时来承载这些能力。

## 评估过的方案

### 方案 A：pi 做全部 Node 统一运行时

**排除。**

纯工程 Node（fetch-rss、fetch-web、URL 去重、SQLite 写入、配置加载、ntfy 推送）是确定性逻辑，有成熟 Python 库直接实现。把它们塞进 agent 壳：
- 增加非确定性（LLM agent 壳引入概率性行为）
- fan-out 并发时放大进程开销
- 为了统一而统一，KISS 违反

### 方案 B：pi 仅做 LLM Node 运行时 ← 采纳

**采纳。**

pi 仅处理 4 个 LLM Node，纯工程 Node 直接 Python async callable。

### 方案 C：不用 pi，直接 LiteLLM / provider API

**排除。**

这是三模型初始分析中 Opus 推荐的方案，经修正后排除。排除原因见下一节。

## 为什么选 pi 而非 LiteLLM

### LiteLLM 无法满足的能力

| 能力 | pi | LiteLLM |
|------|-----|---------|
| 渐进式 Skill 加载（Progressive Disclosure） | ✅ 原生支持：启动时仅注入 Skill name + description，执行时 LLM 自主判断并按需加载完整 SKILL.md | ❌ 无此概念。LiteLLM 是 API 封装层，不管理 Skill |
| 多步 agent 循环 | ✅ 内置 agent-core（ReAct loop：推理→工具调用→观察→循环） | ❌ 仅提供单次 `completion()` 调用。agent loop 需自建 ~70 行，但 Skill 管理需额外 ~500 行 |
| 内置工具集（bash/read/write/edit） | ✅ 原生 | ❌ 无。需自行注册所有工具 |
| 上下文压缩（compaction） | ✅ 原生 | ❌ 无 |
| Skill 发现 + 元数据解析 | ✅ 扫描 skills/ 目录，解析 YAML frontmatter，XML 注入 system prompt | ❌ 无 |

### LiteLLM 的实际定位

LiteLLM 是 **API 统一层**（100+ provider 统一接口），不是 Agent 运行时。它能做的：
- 统一的 `completion()` / `acompletion()` 调用
- 跨 provider 的 tool calling 参数标准化
- provider 路由和 fallback

它不能做的：
- agent 循环（需在上层自建 while loop）
- Skill 管理（发现、加载、渐进展开）
- 工具注册和执行
- 上下文管理

用 LiteLLM 替代 pi = 只替代了 pi 的 API 调用层，还需要自建 pi 的 agent-core + skill loader + tool registry，总量 500+ 行。对 1 周 MVP 不合算。

### pi 的渐进式 Skill 加载如何工作

```
1. 启动/发现阶段
   扫描 skills/ 目录 → 提取每个 SKILL.md 的 name + description → 注入 system prompt
   （仅占 ~7-9% context，token 高效）

2. system prompt 中的 Skill 列表
   <skill name="summarize" description="..." />
   <skill name="classify-sentiment" description="..." />
   LLM 知道有哪些能力，但不消耗 token 加载完整内容

3. 按需展开
   LLM 推理时判断需要某个 Skill → 自动调用 read 工具加载完整 SKILL.md
   → 按 SKILL.md 中的指令执行后续步骤（bash 脚本、模板填充等）

4. 执行循环
   Skill 展开后 → agent 按指令执行工具调用 → 观察结果 → 继续推理
   → 直到产出最终结果
```

核心优势：**只加载当前任务需要的 Skill 内容**，避免一次性灌入所有 Skill 导致 context 爆炸。

### 也评估过的 Python-native 框架

| 框架 | 评估结论 |
|------|----------|
| pydantic-ai | 支持 agent loop + 类型安全输出，但不具备渐进式 Skill 加载 |
| smolagents | 超轻量 code-first agent，但 Skill 管理需自建 |
| Claude Agent SDK | Claude 专属，不支持多 provider |

这些框架支持 agent loop，但都缺少 pi 的渐进式 Skill 加载能力。若在这些框架上自建 Skill 管理，开发成本与自研无异。

## pi 的已知代价

| 代价 | 缓解措施 |
|------|----------|
| TypeScript/Node.js 进程，需跨语言 subprocess 调用 | MVP 用 print 模式（-p），接口简单：spawn → stdout → parse |
| Docker 镜像需 Python + Node.js 双运行时 | 可接受的 MVP trade-off |
| 每次调用有 Node.js 冷启动开销 | P2 切 RPC 常驻模式消除 |
| 结构化输出非原生保证 | Node executor 负责 Pydantic 验证 + 重试（最多 3 次） |
| pi 自动加载 AGENTS.md / CLAUDE.md 可能污染 Node 行为 | 双重防御（实测验证）：`PI_CODING_AGENT_DIR` 指向空目录（阻断全局 ~/.pi/agent/）+ cwd 置于 /tmp/stockimformation/ 下（阻断父目录链遍历，注：父目录链独立于 `PI_CODING_AGENT_DIR`，不受其控制）。详见 `specs/node-executor/spec.md` |

## 6 项操作裁定

| # | 项目 | 裁定 |
|---|------|------|
| 1 | pi 的 scope | 仅限 LLM Node（summarize、classify-sentiment、generate-advice、generate-briefing）。纯工程 Node 走 Python 原生 |
| 2 | 结构化输出 | 软保证可接受：prompt 约束 + Pydantic 验证 + 重试 |
| 3 | 重试次数 | 最多 3 次尝试（2 次重试）。失败走降级，不阻塞管道 |
| 4 | 调用模式 | 对 DAG 是 sync 单轮黑盒；对内是 agent 多步循环 |
| 5 | 集成模式 | MVP 用 print 模式（-p）。P2 按需切 RPC |
| 6 | fallback | 无 LiteLLM fallback（LiteLLM 无法满足 agentic 需求）。若 pi 不稳定，评估 Python-native agent 框架 + 自建 Skill loader |

## 职责边界

```
pi 负责：
├── Skill 发现与渐进加载
├── agent 循环（推理 → 工具调用 → 观察 → 循环）
├── 内置工具执行（bash/read/write/edit）
├── LLM provider 路由（内置 LiteLLM）
└── 上下文压缩

Node executor 负责：
├── 判断 Node 类型（llm / function）
├── LLM Node：spawn pi 子进程 + 传入输入 JSON + 收集 stdout
├── 纯工程 Node：直接调用 Python async callable
├── 输出 Pydantic 校验
├── 校验失败重试（最多 2 次）
├── 超时管理 + 进程 kill
└── 降级处理 + 错误上报
```
