---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - '_bmad-output/planning-artifacts/prd.md'
  - '_bmad-output/brainstorming/brainstorming-session-2026-04-02-1442.md'
workflowType: 'architecture'
project_name: 'stockImformation'
user_name: 'Yunxin'
date: '2026-04-09'
lastStep: 8
status: 'complete'
completedAt: '2026-04-09'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
48 条功能需求，覆盖 10 个功能域：

| 功能域 | FR 编号 | P1 | P2 | P3 |
|--------|---------|----|----|-----|
| 信息采集 | FR1-6 | 4 | 1 | 1 |
| 信息分析 | FR7-11 | 2 | 3 | 0 |
| 事件管理 | FR12-14,47 | 0 | 4 | 0 |
| 交易建议 | FR15-18,48 | 2 | 2 | 1 |
| 推送与通知 | FR19-25 | 4 | 0 | 3 |
| 简报生成 | FR26-28 | 2 | 1 | 0 |
| 配置管理 | FR29-34 | 4 | 2 | 0 |
| 信息源运维 | FR35-38 | 0 | 4 | 0 |
| Web 界面 | FR39-45 | 0 | 7 | 0 |
| 合规与免责 | FR46 | 1 | 0 | 0 |

MVP（P1）聚焦于「采集→分析→建议→推送」核心价值链的端到端打通，共 19 条需求。

**Non-Functional Requirements:**
- 性能：号外推送 ≤1min（目标）/≤5min（底线），常规周期 30min，单条分析 ≤30s
- 安全：凭据不入仓库，Web 界面授权访问，仅处理公开信息
- 可靠性：异常后 5min 内恢复，30min 至少一次状态输出，单源失败不阻塞全流程
- 集成：OpenAI 风格模型接口，至少一种通知通道，标准+自定义信息源

**Scale & Complexity:**
- Primary domain: Full-Stack（后端调度密集型 + Web 信息消费层）
- Complexity level: High
- Estimated architectural components: ~10（采集器、验证器、分析器、事件引擎、建议引擎、推送服务、简报生成器、配置管理、Web API、Web 前端）

### Technical Constraints & Dependencies

- **LLM 依赖：** 分析链核心依赖 LLM，通过统一接口层支持多 provider（OpenAI / Anthropic / Gemini 等）
- **推送渠道：** MVP 使用 ntfy.sh 单渠道，通过 priority 字段实现分级
- **信息源异构性：** 需同时处理标准 RSS 协议源和需自定义规则的非标准源
- **开发资源：** 个人开发者 + 自动化辅助，MVP 目标 1 周交付
- **数据合规：** 仅处理学习用途下可合法获取的公开信息
- **存储需求：** 审计字段完整性要求、版本化记录、状态历史追踪

### Cross-Cutting Concerns Identified

1. **溯源链一致性** — 从采集原文 → 分析引用 → 建议证据，全链路必须保持 URL + 原文引用的可追溯性
2. **采集降级感知** — 信息源采集失败需沿管道向下传递，影响验证、分析、建议的置信度评估和简报元数据标注
3. **事件去重** — URL 作为唯一标识，贯穿采集、验证、事件管理全流程
4. **LLM 幻觉防护** — 强制原文引用机制需嵌入分析和建议生成的每个环节
5. **审计留存** — 每条建议的完整生命周期（生成→更新→删除）均需可查询的审计记录
6. **时间窗口标注** — 所有输出（简报、建议）必须明确数据时效范围，防止基于过时信息的决策

### Architectural Principles (User-Directed)

1. **模块化优先** — 各功能域（采集/分析/事件/建议/推送）作为独立模块，接口明确、内部实现可独立演进
2. **模型接口可替换** — 通过统一接口层屏蔽模型差异，支持多 provider，支持 per-Agent 模型路由
3. **多用轮子** — 优先选用成熟库，减少自研代码量和维护负担
4. **Agent 并发执行** — 多个 Agent 可并发运行（如多标的采集并行、多源分析并行），管道编排需支持并发调度与结果汇聚

### Key ADRs Established

| ADR | 决策 | 理由 |
|-----|------|------|
| 模型接口 | LiteLLM 统一代理 + per-Agent 模型路由 | 100+ provider 支持，零成本切换模型 |
| 并发模型 | asyncio 异步并发，Agent 间通过共享数据模型协作 | 多标的/多源并行采集与分析；单进程内 asyncio 避免多进程通信复杂度 |
| DAG 编排 | DAG Runner 支持并发 fan-out / fan-in | 采集阶段多源并行 fan-out，汇聚后进入验证/分析阶段；降级处理在汇聚点统一执行 |
| 数据契约 | Pydantic 模型定义 Agent I/O schema | 并发环境下明确的类型约束保证数据安全 |
| 调度 | APScheduler 进程内调度 | 支持多节奏（定时+实时+随机），避免迁移成本 |
| 存储 | SQLite + SQLModel | MVP 零运维，审计需求可满足；SQLite 支持 WAL 模式应对并发读写 |
| 配置 | 分层：TOML(系统) + YAML(业务) + env(凭据) | 职责清晰，P2 业务配置可平滑迁入数据库 |

### First Principles Insights

**MVP DAG 简化：**
实际 MVP DAG 为 4 级（采集→研读→建议→推送），验证和事件引擎作为可插入模块 P2 激活。DAG Runner 按配置决定激活哪些阶段。

**模块按数据域划分：**
4 个核心模块：Source（源）、Analysis（析）、Advisory（判）、Delivery（达）。Agent 是模块内的执行单元，不是模块本身。P2 新增能力通过向已有模块添加 Agent 实现，不改变顶层结构。

**DAG 执行模型：**
管道非线性 — 采集阶段按源并发、研读阶段按条目并发、建议阶段按标的并发。MVP 用 asyncio.gather 实现 fan-out/fan-in。

**LLM 依赖最小化：**
仅研读、建议、简报生成 3 个 Agent 强依赖 LLM。其余模块为纯工程逻辑，不引入模型接口依赖。

### Agent & Skill Architecture

**核心概念**

| 概念 | 定义 | 类比 |
|------|------|------|
| **Skill** | 一套完整的处理工作流定义，包含多步骤指令、模板、资源。自包含、可复用。 | Claude Code 的 `.claude/skills/<name>/` 目录 |
| **Agent** | 执行单元。加载一组 Skill，绑定 Model 和输入源，按工作流处理并输出。 | Claude Code 加载 Skill 后的运行态 |
| **Node** | Agent 在节点图中的可视化表示，展示运行状态、输入输出连线。 | ComfyUI 节点 |

**关系模型**

Agent ←N:M→ Skill

- 一个 Agent 可配备多个 Skill（如"研读Agent"同时具备"摘要生成"和"利好利空分类"两个 Skill）
- 一个 Skill 可被多个 Agent 复用（如"关键词提取"Skill 可同时用于"研读Agent"和"验证Agent"）

**Agent 组成**

Agent = Skills[] + Model + 输入源

| 组件 | 说明 |
|------|------|
| **Skills[]** | Agent 可调用的 Skill 集合，每个 Skill 是一套自包含的工作流定义 |
| **Model** | Agent 使用的 LLM（通过 LiteLLM 统一接口），纯逻辑 Skill 可无需 Model |
| **输入源** | Agent 的数据来源（上游 Agent 输出、外部数据源、定时触发等） |

**Agent 执行周期**

1. 获取输入（如果有）
2. 按 Skill 工作流处理（多步骤、可分支、可调用多个 Skill）
3. 输出

**Skill 结构（遵循 Claude Code Skill 规范）**

```
skills/<skill-name>/
├── skill.md           # 入口：元数据 + 工作流入口
├── workflow.md         # 工作流编排（多步骤流程定义）
├── steps/              # 分步骤指令（可选）
├── templates/          # 输出模板（可选）
└── resources/          # 辅助资源（可选）
```

Skill 定义规范完全遵循 Claude Code 的 Skill 约定，不另起标准。

**Dashboard 页面（P2+）**

1. **Node Graph 页面** — ComfyUI 风格的节点图
   - 每个节点 = 一个 Agent 实例，展示实时执行状态
   - 节点间连线 = 数据流向
   - 侧边栏：配置 Agent = 选择 Skills[] + Model + 输入源 + 输出定义
   - 支持运行时状态观察和事后回放

2. **Skill 编辑页面** — 创建和管理 Skill 工作流定义
   - 编辑 Skill 的工作流步骤、模板、资源
   - Skill 与 Agent 解耦：独立创建，按需分配给 Agent

### Agent Execution Model

**Agent 运行时：** 使用现有开源 CLI 工具（暂定 pi），实施阶段全面选型评估。

Agent 运行时必要能力清单：
- 加载 Skill 定义（遵循 Claude Code Skill 规范）
- 绑定 LLM 后端（多 provider）
- 接受/产出结构化 I/O（JSON）
- 可编程调用（非交互式）
- 开源可修改

Agent 生命周期管理由所选工具自身负责。

**Node 间数据流：**
- Agent 在执行过程中不与其他 Agent 通信，仅产出结果
- Node 间通过 DAG 连线传递数据：上游 Node 的产出作为下游 Node 的输入
- Agent 本身无感知其他 Node 的存在
- Fan-out/fan-in 由 DAG Runner 内置 Collector 处理

### DAG Runner

系统核心编排层，纯工程逻辑，不依赖 LLM：
- 图解析（加载 YAML/JSON DAG 定义）
- 拓扑排序 + asyncio 并发调度
- 数据路由（上游 Node 产出 → 下游 Node 输入，类型校验）
- Fan-out/Fan-in（Collector 汇聚多上游产出）
- 状态追踪 + 降级处理（单 Node 失败不阻塞整体）
- 事件广播（向 Node Graph UI 推送状态变更）

MVP：YAML 手写 DAG 定义 + asyncio 调度
P2：Node Graph UI 可视化编辑 DAG

## Starter Template Evaluation

### Starter 策略

**不使用第三方 starter 模板。** 直接使用 `uv init` 初始化标准 Python 项目。

理由：
1. `uv init` 已提供 PEP 621 标准化项目结构（pyproject.toml + lockfile + .venv）
2. 本项目架构特殊（Agent 编排 + DAG Runner），通用模板无法覆盖
3. P2 Web 层启动时可参考 fastapi/full-stack-fastapi-template 的结构，按需采用

**初始化命令：**

```bash
uv init --package stockimformation
cd stockimformation
uv add apscheduler sqlmodel aiosqlite pydantic-settings httpx feedparser
uv add --dev pytest ruff mypy
```

### 后端技术栈

| 组件 | 版本 | 用途 |
|------|------|------|
| Python | ≥3.12 | 运行时 |
| uv | latest | 包管理 + 虚拟环境 + lockfile |
| APScheduler | 3.11.x | AsyncIOScheduler 原生 asyncio 支持 |
| SQLModel | 0.0.38 | ORM（Pydantic + SQLAlchemy 融合） |
| aiosqlite | latest | SQLite 异步驱动 |
| Pydantic | v2 | 数据契约（SQLModel 内置） |
| pydantic-settings | latest | 分层配置管理 |
| httpx | latest | 异步 HTTP 客户端（信息源采集） |
| feedparser | latest | RSS 解析 |
| FastAPI | latest（P2） | Web API 层 |
| LLM 接口 | 待定 | LiteLLM 或 pi 自身能力，实施阶段决定 |

### 前端技术栈（P2 Dashboard）

| 组件 | 版本 | 用途 |
|------|------|------|
| React | latest | UI 框架 |
| TypeScript | latest | 类型安全 |
| Vite | latest | 构建工具 |
| @xyflow/react | 12.10.x | Node Graph 节点图（原 React Flow） |
| shadcn/ui | latest | UI 组件库 |

### 部署

Docker 容器化部署，MVP 阶段单容器。

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- 数据架构：Alembic migration + SQLite WAL
- Agent/Skill/Node 架构 + DAG Runner
- 日志策略：文件存日志，数据库存结果

**Important Decisions (Shape Architecture):**
- 缓存：cachetools 进程内缓存
- 认证：JWT（P2）
- 实时通信：WebSocket（P2）

**Deferred Decisions (Post-MVP):**
- 前端状态管理方案（P2 启动时决定）
- Redis 缓存升级（如进程内缓存不足时）
- CI/CD workflow 具体方案

### Data Architecture

| 决策 | 选择 | 理由 |
|------|------|------|
| ORM | SQLModel 0.0.38 | Pydantic + SQLAlchemy 融合，模型定义复用为 API schema |
| 数据库 | SQLite + aiosqlite（WAL 模式） | MVP 零运维，异步支持，WAL 应对并发读写 |
| Schema 演进 | Alembic | 从一开始规范化 migration，避免后续迁移成本 |
| 缓存 | cachetools（进程内） | 零依赖，适配单容器部署，重启失效可接受 |
| 数据分离 | 结果 → 数据库，日志 → 文件 | 结果需结构化查询（审计），日志按时间流式写入 |

### Authentication & Security

| 决策 | 选择 | 理由 |
|------|------|------|
| Web 认证（P2） | JWT | 无状态，前后端分离友好 |
| 凭据管理 | .env + pydantic-settings | 环境变量注入，不入仓库 |
| 访问控制 | 单用户模式（个人工具） | 无需 RBAC，JWT 仅做身份验证 |

### API & Communication Patterns

| 决策 | 选择 | 理由 |
|------|------|------|
| API 风格（P2） | REST（FastAPI） | 简单直接，FastAPI 原生支持 |
| 实时事件推送（P2） | WebSocket | Node Graph UI 需要双向实时状态更新 |
| 错误处理 | 统一错误模型（Pydantic BaseModel） | 所有模块返回结构化错误，DAG Runner 统一处理 |

### Logging & Monitoring

| 决策 | 选择 | 理由 |
|------|------|------|
| 日志框架 | Python logging（标准库） | 零依赖，生态兼容 |
| 日志存储 | 文件（RotatingFileHandler） | 按时间/大小轮转，Docker volume 持久化 |
| 执行结果存储 | 数据库（SQLite） | 结构化查询，支持审计和回溯 |
| Agent 执行追踪 | 日志文件记录过程，数据库记录结果 | 调试看日志，业务查数据库 |

### Decision Impact Analysis

**Implementation Sequence:**
1. 项目初始化（uv init + 依赖安装）
2. 数据模型定义（SQLModel） + Alembic 初始化
3. DAG Runner 核心编排
4. Source 模块（采集 Agent）
5. Analysis 模块（研读 Agent）
6. Advisory 模块（建议 Agent）
7. Delivery 模块（推送 Agent + 简报生成）
8. 调度集成（APScheduler）
9. Docker 容器化

**Cross-Component Dependencies:**
- Alembic 依赖 SQLModel 模型定义先完成
- DAG Runner 依赖 Pydantic I/O schema 先定义
- 所有 Agent 模块依赖 DAG Runner 接口规范
- 推送模块依赖建议模块的输出 schema

## Implementation Patterns & Consistency Rules

### Naming Patterns

**数据库：**
- 表名：`snake_case` 复数（`raw_items`, `analysis_results`, `advices`）
- 列名：`snake_case`（`created_at`, `stock_code`）
- 外键：`{表名单数}_id`（`advice_id`）
- 索引：`ix_{表}_{列}`（`ix_raw_items_url`）

**API（P2）：**
- 端点：`/api/v1/{资源复数}`（`/api/v1/briefings`）
- 查询参数：`snake_case`
- JSON 字段：`snake_case`

**代码：**
- 文件名：`snake_case.py`
- 类名：`PascalCase`（`RawItem`, `AnalysisResult`）
- 函数/变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`

### Structure Patterns

**核心原则：代码只写通用框架，所有 Node 特化通过配置 + Skill 定义完成。**

新增一种 Node 类型 = 新增一个 Skill 目录 + 一个 Node YAML 配置，零代码改动。

**代码结构（通用框架）：**

```
src/stockimformation/
├── node/                # Node 通用执行框架
│   ├── executor.py      # Node 执行器（加载 Skill、调用 Agent、管理 I/O）
│   └── models.py        # Node/Skill 元数据模型
├── dag/                 # DAG Runner（编排、调度、数据路由）
├── models/              # 共享数据模型（Pydantic/SQLModel）
├── config/              # 配置管理
└── main.py              # 入口
```

**配置层（Node 特化）：**

```
config/
├── system.toml          # 系统配置（调度频率、日志级别等）
├── portfolio.yaml       # 业务配置（标的、投资情况）
├── nodes/               # Node 实例定义（Skills[] + Model + 输入源 + 输出）
└── dags/                # DAG 定义（Node 连线图）
```

**Skill 层（遵循 Claude Code Skill 规范）：**

```
skills/
├── fetch-rss/           # RSS 采集 Skill
├── fetch-web/           # 网页抓取 Skill
├── summarize/           # 摘要生成 Skill
├── classify-sentiment/  # 利好利空分类 Skill
├── generate-advice/     # 建议生成 Skill
├── generate-briefing/   # 简报生成 Skill
└── notify-ntfy/         # ntfy 推送 Skill
```

**测试：** `tests/` 顶层目录，镜像 `src/` 结构

### Format Patterns

**API 响应（P2）：**
```json
{"data": {...}, "meta": {"timestamp": "2026-04-09T14:30:00+08:00"}}
```

**错误响应：**
```json
{"error": {"code": "SOURCE_FETCH_FAILED", "message": "...", "detail": {...}}}
```

**时间格式：** ISO 8601，所有时间带时区

### Communication Patterns

**DAG 事件命名：** `{module}.{action}`（`source.fetch_completed`, `advisory.advice_generated`）

**日志格式：** `[%(asctime)s] %(levelname)s %(name)s: %(message)s`

**日志级别：**
- `DEBUG`：Agent 执行细节
- `INFO`：管道阶段完成、采集结果统计
- `WARNING`：单源采集失败（降级）
- `ERROR`：Agent 执行异常

### Process Patterns

**错误处理：**
- 单 Node 失败 → 标记降级，不阻塞管道
- 全部采集失败 → 中止当前周期，推送系统状态通知
- 异常统一用自定义 Exception 层级（`StockImformationError` 基类）

**重试：** 由 Agent 内部完成（Skill 工作流中定义），基础设施层不处理重试

## Project Structure & Boundaries

### Complete Project Directory Structure

```
stockimformation/
├── pyproject.toml              # uv 项目配置
├── uv.lock                     # 依赖锁文件
├── Dockerfile                  # 容器化
├── .env.example                # 凭据模板
├── .gitignore
│
├── src/stockimformation/       # 源码
│   ├── __init__.py
│   ├── main.py                 # 入口（APScheduler 初始化 + DAG 加载）
│   │
│   ├── node/                   # Node 通用执行框架
│   │   ├── __init__.py
│   │   ├── executor.py         # Node 执行器（加载 Skill、调用 Agent、管理 I/O）
│   │   └── models.py           # Node 实例模型、Skill 元数据模型
│   │
│   ├── dag/                    # DAG Runner
│   │   ├── __init__.py
│   │   ├── runner.py           # DAG 编排（拓扑排序、asyncio 并发调度）
│   │   ├── collector.py        # Fan-out/Fan-in 汇聚器
│   │   ├── loader.py           # DAG YAML 解析 + 校验
│   │   └── models.py           # DAG 图结构数据模型
│   │
│   ├── models/                 # 共享数据模型
│   │   ├── __init__.py
│   │   ├── base.py             # SQLModel 基类 + 数据库引擎
│   │   ├── raw_item.py         # 采集原始条目
│   │   ├── analysis_result.py  # 分析结果
│   │   ├── advice.py           # 交易建议
│   │   ├── briefing.py         # 简报
│   │   └── event.py            # 事件（P2）
│   │
│   ├── config/                 # 配置管理
│   │   ├── __init__.py
│   │   └── settings.py         # pydantic-settings 配置加载
│   │
│   └── errors.py               # 统一异常层级（StockImformationError）
│
├── config/                     # 运行时配置（非代码）
│   ├── system.toml             # 系统配置（调度频率、日志级别）
│   ├── portfolio.yaml          # 业务配置（标的、投资情况）
│   ├── nodes/                  # Node 实例定义
│   │   └── *.yaml              # 每个文件 = 一个 Node（Skills[] + Model + 输入源）
│   └── dags/                   # DAG 定义
│       └── default.yaml        # 默认管道连线图
│
├── skills/                     # Skill 定义（Claude Code 规范）
│   ├── fetch-rss/
│   │   ├── skill.md
│   │   └── workflow.md
│   ├── fetch-web/
│   ├── summarize/
│   ├── classify-sentiment/
│   ├── generate-advice/
│   ├── generate-briefing/
│   └── notify-ntfy/
│
├── alembic/                    # 数据库迁移
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│
├── tests/                      # 测试（镜像 src 结构）
│   ├── __init__.py
│   ├── node/
│   ├── dag/
│   ├── models/
│   └── conftest.py             # pytest fixtures
│
├── logs/                       # 日志输出（Docker volume）
└── data/                       # SQLite 数据库文件（Docker volume）
```

### Architectural Boundaries

**Node 执行边界：**
- Node executor 只关心：加载 Skill → 启动 Agent → 收集输出
- Node 不知道自己在哪个 DAG 中，不知道上下游 Node 存在

**DAG Runner 边界：**
- DAG Runner 只关心：图结构 → 拓扑排序 → 并发调度 → 数据路由
- DAG Runner 不关心 Node 内部执行逻辑

**数据边界：**
- `models/` 是唯一的数据模型定义位置，所有模块引用同一套模型
- 数据库访问仅通过 SQLModel AsyncSession

**配置边界：**
- `config/` 目录是纯数据，不含代码逻辑
- `src/config/settings.py` 负责加载和校验配置

### FR → Structure Mapping

| FR 功能域 | 对应 Skill | Node 配置 |
|----------|-----------|-----------|
| 信息采集（FR1-4） | `fetch-rss`, `fetch-web` | `nodes/rss-fetcher.yaml`, `nodes/web-scraper.yaml` |
| 信息分析（FR7,11） | `summarize`, `classify-sentiment` | `nodes/reader.yaml` |
| 交易建议（FR15,18） | `generate-advice` | `nodes/advisor.yaml` |
| 推送通知（FR19-22） | `notify-ntfy` | `nodes/notifier.yaml` |
| 简报生成（FR26-27） | `generate-briefing` | `nodes/briefing-generator.yaml` |
| 配置管理（FR29-32） | — | `config/portfolio.yaml`, `config/nodes/*.yaml` |
| 合规免责（FR46） | — | 简报模板内置 |

### Data Flow

```
APScheduler 触发
    → DAG Runner 加载 default.yaml
    → fan-out: [rss-fetcher, web-scraper, ...] 并发执行
    → Collector 汇聚 RawItem[]
    → reader Node 并发分析（per item）
    → Collector 汇聚 AnalysisResult[]
    → advisor Node 并发研判（per 标的）
    → briefing-generator Node 生成简报
    → notifier Node 分级推送
```

## Architecture Validation Results

### Coherence Validation ✅

- 全链路异步一致（asyncio + aiosqlite + httpx + APScheduler）
- 数据模型复用链路无冲突（SQLModel + Pydantic v2 + FastAPI）
- Node/Skill/DAG 三层架构与 Agent 运行时解耦
- 命名规范贯穿全栈（snake_case）
- 通用框架 + 声明式配置的结构模式与模块化原则对齐

### Requirements Coverage ✅

- P1 功能需求：19/19 条覆盖
- P2 功能需求：26/26 条架构预留
- P3 功能需求：3/3 条架构兼容
- 非功能需求：全部覆盖

### Implementation Readiness ✅

- 技术栈版本已验证
- 项目结构完整定义
- 实现模式和一致性规则已建立
- FR → 结构映射已完成
- 数据流已定义

### Gap Analysis

**非阻塞事项：**
- 审计版本化 schema 设计 → 延迟到 Story 实现阶段

### Architecture Completeness Checklist

- [x] 项目上下文分析
- [x] 架构原则定义
- [x] ADR 记录
- [x] 第一性原理分析
- [x] Agent & Skill 架构设计
- [x] Agent 执行模型
- [x] DAG Runner 定义
- [x] 技术栈评估与版本验证
- [x] 核心架构决策
- [x] 实现模式与一致性规则
- [x] 项目结构与边界
- [x] FR → 结构映射
- [x] 数据流定义
- [x] 架构验证

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High

**Key Strengths:**
- Node/Skill/DAG 三层解耦设计，可扩展性强
- 代码只写通用框架，新 Node 类型零代码改动
- 全链路异步，并发调度能力充分
- MVP 管道精简（4 级），P2 按需激活

**Areas for Future Enhancement:**
- Agent 运行时选型（pi CLI 需实施阶段验证）
- 前端状态管理方案（P2 启动时决定）
- LLM 接口层是否由 Agent 运行时替代（实施阶段决定）
