## Context

当前 `PipelineController`（`src/stockimformation/pipeline.py`）采用全局单任务模型：

- 单一 `current_task: asyncio.Task` + `current_cycle_id: str` + 全局 `_lock: asyncio.Lock`
- `_run()` 硬编码 `config.dags["default"]`
- APScheduler 注册单一 job（ID `"default-dag"`，interval 30min）
- `PipelineRun` 模型无 `dag_name` 字段

前端正从 Jinja2 SSR 迁移到 React SPA，后端需要变为纯 API 服务器。

## Goals / Non-Goals

**Goals:**

- 支持多 DAG 并发执行（不同 DAG 并行，同一 DAG 互斥）
- 提供 per-DAG 粒度的 run/stop/status API
- 移除所有 SSR 相关代码（templates、static files、HTML routes）
- 添加 CORS 支持前端开发服务器

**Non-Goals:**

- 不实现 DAG 间依赖编排（DAG-of-DAGs）
- 不实现 WebSocket/SSE 实时推送（前端通过轮询获取状态）
- 不修改 DagRunner 内部执行逻辑
- 不实现前端 SPA（属于独立 change）

## Decisions

### Decision 1: Per-DAG 并发模型（而非全局互斥 + DAG 参数）

**选择**：`active_runs: dict[str, DagRunContext]` + per-DAG `asyncio.Lock`

**替代方案**：保持全局互斥，仅将 `dag_name` 作为参数传入 `start_run()`

**理由**：
- 全局互斥无法满足"同时运行 default DAG 和 realtime DAG"的场景
- per-DAG Lock 实现复杂度可控（`defaultdict(asyncio.Lock)`）
- 数据库层面 `PipelineRun` 已按 `cycle_id` 隔离，新增 `dag_name` 字段即可区分

### Decision 2: 调度器 per-DAG 注册

**选择**：启动时遍历 `config/dags/*.yaml`，为每个 DAG 注册独立 APScheduler job

**替代方案**：保持单一 job，在 job 内遍历所有 DAG 并逐个触发

**理由**：
- 独立 job 允许未来为不同 DAG 配置不同调度间隔
- 单一 job 内串行触发会导致后续 DAG 等待前序完成
- APScheduler 的 `max_instances=1` 天然提供 per-job 互斥

### Decision 3: 直接移除 SSR（而非渐进式保留）

**选择**：一次性移除所有 HTML 路由、templates、static files

**替代方案**：保留旧路由作为 fallback，逐步迁移

**理由**：
- 前端 SPA 将由 nginx 独立托管，不依赖 FastAPI 提供静态文件
- 保留旧路由增加维护负担且可能导致路由冲突
- API 路由已完整存在，前端可立即对接

### Decision 4: CORS 配置策略

**选择**：在 `create_app()` 中添加 `CORSMiddleware`，开发环境允许 `localhost:5173`

**理由**：
- 生产环境由 nginx 处理跨域，但后端保留 CORS 配置提供灵活性
- 仅允许已知开发端口，不使用 `allow_origins=["*"]`

## Risks / Trade-offs

- **[风险] 并发 DAG 共享数据库连接池** → 当前使用 SQLAlchemy async engine 的连接池，多 DAG 并发写入不会冲突（每个 session 独立事务）。若未来 DAG 数量增多，需监控连接池饱和。

- **[风险] 调度器 job 数量膨胀** → 当前 DAG 数量少（1-3 个），不构成问题。若未来 DAG 数量超过 10，需考虑 job 合并策略。

- **[风险] `PipelineRun.dag_name` 迁移** → 需要 ALTER TABLE 添加列。SQLite 支持 `ALTER TABLE ADD COLUMN`，对现有数据无影响。旧记录 `dag_name` 默认为 `"default"`。

- **[Trade-off] 移除 SSR 后旧客户端立即不可用** → 可接受，因为这是协调变更（前端 SPA 同步上线）。

## Migration Plan

1. 添加 `PipelineRun.dag_name` 字段（默认值 `"default"`，兼容旧数据）
2. 重构 `PipelineController` 为 per-DAG 模型
3. 新增 per-DAG API 端点
4. 移除 HTML 路由和 SSR 依赖
5. 添加 CORS 中间件
6. 更新测试

回滚策略：git revert 整个 change 的 commits，恢复 SSR 路由。
