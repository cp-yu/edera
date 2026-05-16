## 1. Actions

- [ ] A1 `PipelineRun` 模型新增 `dag_name: str = Field(default="default", index=True)` 字段
- [ ] A2 `repository.py` 中 `create_pipeline_run()` 接受 `dag_name` 参数并写入记录
- [ ] A3 `repository.py` 中 `recent_pipeline_runs()` 和 `current_pipeline_run()` 支持按 `dag_name` 过滤
- [ ] A4 新增 `DagRunContext` dataclass（`dag_name`, `cycle_id`, `task`, `started_at`）
- [ ] A5 重构 `PipelineController`：将 `current_task`/`current_cycle_id`/`_lock` 替换为 `active_runs: dict[str, DagRunContext]` + `_locks: defaultdict(asyncio.Lock)`
- [ ] A6 重构 `start_run(trigger, dag_name="default")` 使用 per-DAG lock 和 `active_runs`
- [ ] A7 重构 `_run(cycle_id, trigger, dag_name)` 从 `config.dags[dag_name]` 加载指定 DAG
- [ ] A8 重构 `stop_current(dag_name)` 取消指定 DAG 的 task
- [ ] A9 重构 `status(dag_name=None)` 返回指定 DAG 或全部 DAG 的状态
- [ ] A10 重构 `start()` 中调度器注册：遍历 `config/dags/*.yaml` 为每个 DAG 注册独立 job
- [ ] A11 新增路由 `POST /api/pipeline/dag/{dag_name}/run`
- [ ] A12 新增路由 `POST /api/pipeline/dag/{dag_name}/stop`
- [ ] A13 新增路由 `GET /api/pipeline/dag/{dag_name}/status`
- [ ] A14 移除所有 `HTMLResponse` 路由（`index`, `results_page`, `briefing_detail_page`, `advice_detail_page`, `pipeline_page`, `sources_page`, `config_page`, `save_config`, `save_portfolio_config`, `save_dag_config`, `dag_graph_page`）
- [ ] A15 移除所有表单 POST 路由（`form_pipeline_run`, `form_pipeline_pause`, `form_pipeline_resume`, `form_pipeline_stop`）
- [ ] A16 移除 `app.py` 中 `Jinja2Templates` 初始化和 `StaticFiles` 挂载
- [ ] A17 移除 `deps.py` 中 `templates()` 函数
- [ ] A18 删除 `src/stockimformation/web/templates/` 目录
- [ ] A19 删除 `src/stockimformation/web/static/` 目录
- [ ] A20 在 `create_app()` 中添加 `CORSMiddleware`（allow_origins: `["http://localhost:5173"]`）
- [ ] A21 更新现有全局 API 端点（`/api/pipeline/run` 等）作为 `dag_name="default"` 的别名或移除

## 2. Checks

- [ ] C1 Per-DAG 并发执行测试
  - Covers: A4, A5, A6, A7
  - Command: `pytest tests/ -k "test_per_dag" -v`
  - Expect: 不同 DAG 可并发启动；同一 DAG 并发触发返回 `RunAlreadyActiveError`

- [ ] C2 Per-DAG stop 测试
  - Covers: A8
  - Command: `pytest tests/ -k "test_stop_dag" -v`
  - Expect: 停止指定 DAG 不影响其他正在运行的 DAG

- [ ] C3 Per-DAG status API 测试
  - Covers: A9, A13
  - Command: `pytest tests/ -k "test_dag_status" -v`
  - Expect: 返回指定 DAG 的 cycle_id、status 和 recent_runs

- [ ] C4 Per-DAG run API 测试
  - Covers: A11, A12
  - Command: `pytest tests/ -k "test_dag_run_api" -v`
  - Expect: `POST /api/pipeline/dag/default/run` 返回 200 + cycle_id；不存在的 DAG 返回 404

- [ ] C5 SSR 路由已移除
  - Covers: A14, A15, A16, A17, A18, A19
  - Command: `pytest tests/ -k "test_" -v && grep -r "HTMLResponse\|Jinja2Templates\|StaticFiles" src/stockimformation/web/ | grep -v __pycache__`
  - Expect: 测试通过；grep 无匹配结果

- [ ] C6 CORS 中间件生效
  - Covers: A20
  - Command: `pytest tests/ -k "test_cors" -v`
  - Expect: OPTIONS 预检请求返回正确 CORS 头；`localhost:5173` origin 被允许

- [ ] C7 PipelineRun dag_name 字段
  - Covers: A1, A2, A3
  - Command: `pytest tests/ -k "test_pipeline_run" -v`
  - Expect: 新建运行记录包含 dag_name；按 dag_name 过滤查询正确

- [ ] C8 调度器 per-DAG 注册
  - Covers: A10
  - Command: `pytest tests/ -k "test_scheduler" -v`
  - Expect: 启动后 scheduler 中存在与 DAG 配置数量相同的 job
