## Why

stockImformation 项目需要完成 MVP 的端到端实现：将「采集→分析→建议→推送」核心价值链打通，使个人交易者能够自动获取港股/A股标的的信息分析与交易建议。MVP 聚焦 PRD 中 19 条 P1 功能需求，目标 1 周交付。

## What Changes

- 新建完整项目结构（uv + Python ≥3.12）
- 实现 Node 通用执行框架（加载 Skill、调用 Agent、管理 I/O）
- 实现 DAG Runner 编排层（拓扑排序、asyncio 并发调度、数据路由、fan-out/fan-in）
- 实现共享数据模型（SQLModel + SQLite + Alembic migration）
- 实现信息采集能力：RSS 采集 + 非标准源抓取 + URL 去重 + 定时触发
- 实现信息分析能力：摘要生成 + 关键词提取 + 利好/利空分类 + 原文溯源
- 实现交易建议能力：基于当期信息 + 用户投资情况生成买/卖/持有建议 + 原文溯源
- 实现推送通知能力：ntfy.sh 分级推送 + 结构化摘要 + 周期性状态输出
- 实现简报生成能力：结构化简报 + 元数据区（配置源/成功源/失败源/时间窗口）
- 实现配置管理：TOML(系统) + YAML(业务/标的/信息源) + env(凭据)
- 实现免责声明输出
- 实现完成门禁：PRD 门禁 + P1 验收映射 + 单元/契约/集成/E2E 测试命令
- Docker 容器化部署

## Capabilities

### New Capabilities
- `dag-runner`: DAG 编排引擎 — 图解析、拓扑排序、asyncio 并发调度、数据路由、fan-out/fan-in、状态追踪与降级处理
- `node-executor`: Node 通用执行框架 — Skill 加载、Agent 调用、I/O 管理
- `data-models`: 共享数据模型 — RawItem、AnalysisResult、Advice、Briefing 的 SQLModel 定义 + Alembic migration + SQLite WAL
- `source-collection`: 信息采集 — RSS 订阅拉取、非标准源抓取、URL 去重、30min 周期定时触发
- `information-analysis`: 信息分析 — 摘要生成、关键词提取、利好/利空分类、原文引用+URL 溯源
- `trade-advisory`: 交易建议 — 基于当期分析结果+用户投资情况生成买/卖/持有建议，附带原文引用与溯源
- `notification-delivery`: 推送通知 — ntfy.sh 分级推送、结构化摘要（≤16字标题+必含字段）、周期性状态输出
- `briefing-generation`: 简报生成 — 结构化简报、元数据区、免责声明
- `config-management`: 配置管理 — 分层配置（TOML系统+YAML业务+env凭据）、标的/信息源配置、非标准源接入规则
- `goal-completion`: 完成门禁 — PRD 门禁、P1 FR 验收映射、测试金字塔、E2E 产物断言、命令门禁

### Modified Capabilities
（无 — greenfield 项目）

## Impact

- **代码**: 新建 `src/stockimformation/` 完整源码结构，包含 `node/`、`dag/`、`models/`、`config/` 模块
- **配置**: 新建 `config/` 运行时配置目录（system.toml、portfolio.yaml、nodes/*.yaml、dags/*.yaml）
- **Skill**: 新建 `skills/` 目录，包含 7 个 Skill 定义（fetch-rss、fetch-web、summarize、classify-sentiment、generate-advice、generate-briefing、notify-ntfy）
- **依赖**: apscheduler、sqlmodel、aiosqlite、pydantic-settings、httpx、feedparser + dev: pytest、ruff、mypy
- **部署**: Dockerfile + .env.example
- **数据库**: SQLite + Alembic migration
