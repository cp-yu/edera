## Context

当前系统是单进程 Python 后台管道：`main.py` 启动 `AsyncIOScheduler`，立即运行一次默认 DAG，并按 `system.schedule_minutes` 周期重复。结果持久化到 SQLite 的 `RawItem`、`AnalysisResult`、`Advice`、`Briefing` 表；失败状态主要存在于 `DagRunResult.failures` 和简报 metadata 中，没有独立运行记录表。配置由 `config/` 下 TOML/YAML 文件和 `.env` 组成，DAG/Node/Skill 目前通过文件直接维护。

用户现在需要本机 WebUI 同时覆盖查看、操作、编辑，包括 DAG/Node/Skill 配置。该变更跨 Web 层、调度生命周期、数据库模型、配置写入和部署入口，必须把控制面和管道执行边界拆清楚。

## Goals / Non-Goals

**Goals:**
- 提供默认仅绑定 `127.0.0.1` 的本机 Web 控制台。
- 支持浏览最新和历史结果，并能从建议追溯到分析和原文。
- 支持手动运行、暂停/恢复调度、停止当前运行，并持久化运行状态。
- 支持编辑 portfolio、source、system、node、dag、skill 配置，并在保存前校验。
- 保持现有管道核心逻辑可测试、可复用，不把业务执行逻辑塞进 Web handler。

**Non-Goals:**
- 不做远程多用户访问、登录、权限系统或公网部署。
- 不在第一版实现 DAG 拖拽式图编辑器；DAG/Node/Skill 以结构化表单或文本编辑加校验为主。
- 不改变现有采集、分析、建议、通知算法。
- 不引入独立 Node 前端构建链，除非实现阶段证明 Python 模板无法满足最小交互需求。

## Decisions

### 1. 使用 Python 原生 Web 层

**决策：** 使用 FastAPI + Uvicorn 提供 HTTP API，页面层优先使用 Jinja2/静态资源实现。

**理由：** 项目现有栈是 Python + asyncio + SQLModel。WebUI 是本机个人控制台，交互密度有限，独立 SPA 会增加构建链和部署面。FastAPI 与现有 async 数据访问、APScheduler 和测试方式兼容。

**备选方案及排除理由：**
- React/Vite SPA：适合复杂前端状态，但当前第一版不需要独立前端应用，会引入 Node 依赖和额外打包路径。
- Streamlit/Gradio：启动快，但不适合稳定控制调度生命周期、编辑配置文件和长期维护 API 边界。

### 2. 引入 PipelineController 管理运行生命周期

**决策：** 将调度器、当前运行 task、手动运行、暂停/恢复、停止当前运行封装到 `PipelineController`，Web handler 只能调用控制器方法。

**理由：** 当前 `serve()` 把调度启动、立即执行和无限 sleep 混在一起。Web 控制台需要清晰的运行状态和互斥控制，必须把生命周期从入口函数中抽出。

**关键约束：**
- 同一时间只允许一个默认 DAG 周期运行。
- 手动运行与调度运行使用同一执行路径和持久化路径。
- `stop_current()` 通过取消当前 asyncio task 停止运行，并将运行记录标记为 `cancelled` 或 `failed`。
- 暂停调度不影响用户手动运行。

### 3. 新增运行记录模型作为状态来源

**决策：** 新增 `PipelineRun` 和 `NodeRun` 表，记录 cycle、触发来源、状态、开始/结束时间、失败原因和节点级状态。

**理由：** 只靠结果表无法回答“现在是否运行”“哪个节点失败”“上次耗时多久”“停止是否生效”。运行记录是 WebUI 操作台的事实来源，也利于后续排障。

**状态建议：**
- `PipelineRun.status`: `running`、`succeeded`、`failed`、`cancelled`
- `NodeRun.status`: `pending`、`running`、`succeeded`、`failed`、`skipped`、`cancelled`
- `trigger`: `startup`、`schedule`、`manual`

### 4. 配置编辑采用校验后原子保存

**决策：** 配置编辑服务负责读取、校验、备份和原子写入 `config/` 与 `skills/` 文件。Web handler 不直接写文件。

**理由：** `portfolio.yaml`、`system.toml`、`nodes/*.yaml`、`dags/*.yaml` 是运行时契约，坏配置会让管道无法启动。保存前必须复用现有 Pydantic schema 和 DAG loader 校验；写入采用临时文件 + replace，避免半写入。

**策略：**
- portfolio/system 使用字段级表单或 JSON API。
- node/dag/skill 第一版允许文本编辑，但保存前必须校验对应 schema、DAG 引用和 I/O 类型。
- `.env` 凭据不在第一版 WebUI 中明文编辑；ntfy topic/url 可通过 runtime settings 或安全提示处理。

### 5. 默认本机访问，不做鉴权

**决策：** 默认监听 `127.0.0.1`，不实现用户登录。

**理由：** 用户明确要求本机即可。本机绑定比弱密码登录更简单可靠。若后续要远程访问，应作为独立变更添加鉴权和 CSRF 策略。

## Risks / Trade-offs

- **停止当前运行无法中断已发出的外部 HTTP 请求或 pi 子进程** → 使用 asyncio cancellation 标记运行状态，并在 Node executor 中补齐子进程取消清理。
- **配置编辑可能破坏运行中周期的一致性** → 运行周期开始时加载配置快照；保存配置不影响已开始的周期，只影响后续运行。
- **文本编辑 Node/DAG/Skill 容易写入语义错误** → 保存前执行 schema 校验、DAG 校验和 skill 文件存在性检查；失败时不写入。
- **SQLite 写并发冲突** → 继续使用 WAL；运行记录写入和结果写入复用 async session 边界，避免长事务。
- **无鉴权依赖本机绑定** → 默认 host 固定为 `127.0.0.1`；若用户显式改为 `0.0.0.0`，需要配置层给出风险提示或拒绝。

## Migration Plan

1. 添加 Web/API 依赖和运行记录模型 migration。
2. 引入 `PipelineController`，让 CLI/服务入口通过控制器执行默认 DAG。
3. 增加只读结果查询接口和页面。
4. 增加运行控制接口，并用运行记录覆盖成功、失败和取消场景。
5. 增加配置读取/校验/保存服务，再接入编辑页面。
6. 更新 Docker/compose 暴露本机端口。

回滚时可恢复旧入口 `stockimformation.main:main` 直接运行后台调度；新增运行记录表可保留，不影响现有结果表读取。

## Open Questions

- `.env` 中的敏感字段是否需要 WebUI 管理，还是继续由文件/环境维护。
- DAG/Node 编辑第一版使用纯文本编辑还是轻量表单编辑；两者都必须通过同一校验服务。
