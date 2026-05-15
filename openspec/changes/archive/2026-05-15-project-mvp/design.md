## Context

stockImformation 是 greenfield 项目，核心架构已在 `_bmad-output/planning-artifacts/architecture.md` 中完成决策。技术栈：Python ≥3.12 + uv + asyncio + SQLite + SQLModel + APScheduler。架构采用 Node/Skill/DAG 三层解耦设计：Node 是通用执行框架，Skill 是自包含工作流定义，DAG Runner 负责编排调度。

MVP 管道 4 级：采集(Source) → 研读(Analysis) → 建议(Advisory) → 推送(Delivery)。Agent 运行时使用 pi CLI（详见 ADR: `adr-agent-runtime.md`）。

约束：个人开发者 + 自动化辅助，目标 1 周交付。

## Goals / Non-Goals

**Goals:**
- 端到端打通「采集→分析→建议→推送」管道
- DAG Runner 支持 asyncio 并发 fan-out/fan-in
- 数据模型从一开始使用 Alembic 管理 migration
- 配置驱动 — 新增 Node 类型零代码改动
- 全链路可追溯 — 建议→分析→原文 URL

**Non-Goals:**
- Web Dashboard（P2）
- 跨源验证与事件态势分析（P2）
- 多假设建议分析（P2）
- 实时源监听（P2）
- 信息源异常自动恢复（P2）
- 前端任何功能

## Decisions

### 1. Agent 运行时选型

**决策：** 使用 pi CLI 作为 LLM Node 的 Agent 运行时，通过 print 模式（-p）子进程调用。纯工程 Node 直接 Python 原生实现，不经过 pi。

**备选方案及排除理由：**
- LiteLLM 直接调用 — LiteLLM 仅是 API 封装层，不具备 agent 循环、渐进式 Skill 加载、多步工具调用等能力，无法满足 LLM Node 的 agentic 需求
- 自研 Agent 执行器 — 渐进式 Skill 加载 + agent loop + 工具注册 + 上下文管理，自建成本 500+ 行，违背「多用轮子」原则
- pydantic-ai / smolagents — 支持 agent loop 但不具备 pi 的渐进式 Skill 加载能力

**理由：** 详见 `adr-agent-runtime.md`。核心原因：LLM Node 内部需要多步 agent 循环（工具调用 + Skill 渐进展开），pi 原生提供此能力。

**调用规范：**
- MVP 使用 print 模式（`pi -p`），每次调用 spawn 子进程 → pi 内部完成完整 agent 循环 → stdout 输出结果 → 进程退出
- P2 按需切换 RPC 常驻模式（`pi --mode rpc`）以消除冷启动开销
- Node executor 负责：输出 Pydantic 校验、重试（最多 3 次尝试）、超时、降级

### 2. DAG 定义格式

**决策：** YAML 手写 DAG 定义，由 DAG Runner 解析执行。

**理由：** MVP 管道固定为 4 级，YAML 定义足够表达。P2 Node Graph UI 可视化编辑 DAG 时，底层仍使用同一 YAML 格式。

### 3. 数据持久化策略

**决策：** 结果 → SQLite 数据库，日志 → 文件。SQLite 启用 WAL 模式。

**理由：** 结果需结构化查询（审计、复盘），日志按时间流式写入无需查询。WAL 模式应对 asyncio 并发读写场景。

### 4. 推送渠道

**决策：** MVP 仅使用 ntfy.sh，通过 priority 字段实现分级推送。

**理由：** ntfy.sh 零成本、零运维、支持 HTTP POST 推送。priority 字段可映射为手机通知级别（1=静默, 3=普通, 5=紧急）。P3 扩展其他渠道。

### 5. LLM 接口层

**决策：** 由 pi 自身的 LLM 接口能力（内置 LiteLLM，支持 100+ provider）提供。

**理由：** pi 已内置 LiteLLM 做 provider 路由，无需在 Python 端额外引入 LiteLLM 依赖。

### 6. Node 执行路径分叉

**决策：** Node executor 按 Node 类型分叉：LLM Node 通过 pi 执行（agent 循环 + Skill 渐进展开），纯工程 Node 直接调用 Python async 函数。

**理由：** 确定性工程逻辑（HTTP 请求、RSS 解析、数据库写入）不应经过概率性 agent 壳。纯工程 Node 直接注册 Python callable，可测试、可预测。

## Risks / Trade-offs

- **pi CLI 成熟度风险** → MVP 优先验证 pi print 模式的可编程调用、结构化 I/O、Skill 渐进加载。若 pi 不稳定，评估 Python-native agent 框架（pydantic-ai / smolagents）作为替代
- **pi 进程开销** → fan-out 阶段每条 item 可能 spawn 独立 pi 进程，Node.js 冷启动开销累积。P2 切 RPC 常驻模式缓解
- **Docker 镜像双运行时** → Python + Node.js，镜像体积增大。可接受的 MVP trade-off
- **软结构化输出** → LLM 输出非原生 schema 保证，依赖 prompt 约束 + Pydantic 验证 + 重试（最多 3 次）。失败走降级，不阻塞管道
- **SQLite 并发写入瓶颈** → WAL 模式缓解。MVP 单进程 asyncio 场景下不构成实际瓶颈
- **1 周交付压力** → 严控 MVP 范围，仅实现 P1 需求。配置驱动减少硬编码
