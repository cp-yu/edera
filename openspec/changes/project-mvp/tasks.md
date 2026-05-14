## 1. 项目初始化

- [ ] 1.1 使用 `uv init --package stockimformation` 初始化项目结构
- [ ] 1.2 添加运行时依赖：apscheduler sqlmodel aiosqlite pydantic-settings httpx feedparser
- [ ] 1.3 添加开发依赖：pytest ruff mypy
- [ ] 1.4 创建 `src/stockimformation/` 目录结构（node/、dag/、models/、config/）
- [ ] 1.5 创建 `.env.example`、`.gitignore`
- [ ] 1.6 创建 `config/` 运行时配置目录（system.toml、portfolio.yaml）

## 2. 数据模型与数据库

- [ ] 2.1 定义 SQLModel 基类 + 数据库引擎初始化（SQLite WAL 模式）
- [ ] 2.2 定义 RawItem 模型（url 唯一约束、审计字段）
- [ ] 2.3 定义 AnalysisResult 模型（关联 RawItem、溯源字段）
- [ ] 2.4 定义 Advice 模型（审计字段完整性、版本化、投资情况快照）
- [ ] 2.5 定义 Briefing 模型（元数据区字段）
- [ ] 2.6 初始化 Alembic + 创建首个 migration
- [ ] 2.7 定义统一异常层级（StockImformationError 基类）

## 3. 配置管理

- [ ] 3.1 实现 pydantic-settings 配置加载（TOML 系统配置 + YAML 业务配置 + env 凭据）
- [ ] 3.2 定义 portfolio.yaml schema（标的列表、投资情况、信息源关联）
- [ ] 3.3 定义 Node 配置 YAML schema（Skills[] + Model + 输入源）
- [ ] 3.4 定义 DAG 配置 YAML schema（节点列表 + 连线 + fan-out/fan-in）

## 4. Node 执行框架

- [ ] 4.1 定义 Node/Skill 元数据模型（models.py）
- [ ] 4.2 实现 Skill 加载器（从 skills/<name>/ 加载 skill.md + workflow.md）
- [ ] 4.3 实现 Node executor（Agent 运行时调用、JSON I/O 序列化/反序列化、超时处理）
- [ ] 4.4 编写 Node executor 单元测试

## 5. DAG Runner

- [ ] 5.1 实现 DAG YAML 加载器 + 图校验（无环检测、节点引用校验）
- [ ] 5.2 实现拓扑排序
- [ ] 5.3 实现 asyncio 并发调度（同层节点 gather 并发）
- [ ] 5.4 实现数据路由（上游输出 → 下游输入、Pydantic 类型校验）
- [ ] 5.5 实现 Collector（fan-out/fan-in 汇聚）
- [ ] 5.6 实现降级处理（单节点失败标记、全部失败中止）
- [ ] 5.7 编写 DAG Runner 集成测试

## 6. Skill 定义

- [ ] 6.1 创建 fetch-rss Skill（skill.md + workflow.md：RSS 采集工作流）
- [ ] 6.2 创建 fetch-web Skill（非标准源抓取工作流）
- [ ] 6.3 创建 summarize Skill（摘要 + 关键词生成工作流）
- [ ] 6.4 创建 classify-sentiment Skill（利好/利空分类工作流）
- [ ] 6.5 创建 generate-advice Skill（交易建议生成工作流）
- [ ] 6.6 创建 generate-briefing Skill（简报生成工作流，含免责声明）
- [ ] 6.7 创建 notify-ntfy Skill（ntfy.sh 推送工作流）

## 7. Node 配置与 DAG 定义

- [ ] 7.1 创建 rss-fetcher Node 配置 YAML
- [ ] 7.2 创建 web-scraper Node 配置 YAML
- [ ] 7.3 创建 reader Node 配置 YAML（summarize + classify-sentiment Skills）
- [ ] 7.4 创建 advisor Node 配置 YAML
- [ ] 7.5 创建 briefing-generator Node 配置 YAML
- [ ] 7.6 创建 notifier Node 配置 YAML
- [ ] 7.7 创建 default DAG 定义（4 级管道：采集→研读→建议→推送）

## 8. 推送实现

- [ ] 8.1 实现 ntfy.sh HTTP POST 推送（httpx 异步调用）
- [ ] 8.2 实现推送优先级映射（priority 1/3/5）
- [ ] 8.3 实现推送摘要格式化（≤16字标题 + 必含字段）
- [ ] 8.4 实现周期性状态输出推送

## 9. 调度与入口

- [ ] 9.1 实现 main.py 入口（APScheduler 初始化 + DAG 加载 + 调度注册）
- [ ] 9.2 配置 30min 周期定时任务
- [ ] 9.3 端到端集成测试（模拟完整管道执行）

## 10. 容器化

- [ ] 10.1 编写 Dockerfile（Python 3.12 + uv + 项目依赖）
- [ ] 10.2 配置 Docker volume 挂载（logs/ + data/ + config/）
- [ ] 10.3 编写 docker-compose.yaml（含 .env 注入）
