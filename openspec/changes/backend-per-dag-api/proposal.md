## Why

当前管道控制器采用全局单 DAG 执行模型（硬编码 `config.dags["default"]`），无法支持多 DAG 并发运行。前端正在迁移到 React SPA，需要纯 API 后端（移除 Jinja2 SSR 层）并提供 per-DAG 粒度的运行控制接口。

## What Changes

- **BREAKING** 新增 per-DAG 运行/停止/状态 API（`POST /api/pipeline/dag/{dag_name}/run`、`/stop`、`GET /status`）
- **BREAKING** 移除所有 Jinja2 模板路由（`GET /`、`/results`、`/pipeline`、`/config` 等 HTML 页面路由）和表单 POST 路由
- **BREAKING** 移除 `StaticFiles` 挂载和 `templates/` 目录引用
- `PipelineController` 重构为 per-DAG 并发模型：不同 DAG 可并行执行，同一 DAG 互斥
- `PipelineRun` 模型新增 `dag_name` 字段
- 调度器从单一 `"default-dag"` job 改为按 `config/dags/*.yaml` 注册独立 job
- 新增 CORS 中间件支持前端开发服务器跨域访问
- 移除 `Jinja2Templates` 依赖和 `templates()` 辅助函数

## Capabilities

### New Capabilities

- `per-dag-execution`: 覆盖 per-DAG 并发执行模型、per-DAG 锁机制、per-DAG 调度注册和 per-DAG 运行/停止/状态 API

### Modified Capabilities

- `pipeline-control`: 运行控制从全局单 DAG 扩展为指定 DAG 名称的 per-DAG 控制，并发模型从互斥变为 per-DAG 互斥
- `local-web-console`: 移除 SSR 页面渲染和静态文件托管，仅保留 JSON API 层；新增 CORS 中间件

## Impact

- `src/stockimformation/pipeline.py` — 核心重构：`PipelineController` 状态模型、锁机制、调度器
- `src/stockimformation/web/routes.py` — 移除 HTML 路由，新增 per-DAG API 端点
- `src/stockimformation/web/app.py` — 移除 Jinja2/StaticFiles，新增 CORS
- `src/stockimformation/web/deps.py` — 移除 `templates()` 函数
- `src/stockimformation/models/entities.py` — `PipelineRun` 新增 `dag_name` 字段
- `src/stockimformation/models/repository.py` — 查询函数适配 `dag_name` 过滤
- `src/stockimformation/web/templates/` — 整目录删除
- `src/stockimformation/web/static/` — 整目录删除
- 依赖变更：移除 `jinja2` 运行时依赖
