## 1. Web 基础设施

- [x] 1.1 添加 FastAPI/Uvicorn/Jinja2 运行依赖和测试所需依赖
- [x] 1.2 创建 Web 模块结构，包含 app factory、路由注册、模板和静态资源目录
- [x] 1.3 实现默认 `127.0.0.1` 监听配置，拒绝默认公网绑定
- [x] 1.4 实现统一 API 错误响应和请求校验错误处理
- [x] 1.5 实现控制台首页和结果、管道控制、配置编辑导航

## 2. 运行记录模型

- [x] 2.1 新增 `PipelineRun` 和 `NodeRun` SQLModel 实体
- [x] 2.2 新增 Alembic migration 创建运行记录表和必要索引
- [x] 2.3 实现运行记录 repository，支持创建、更新状态、查询当前运行和最近运行
- [x] 2.4 为成功、失败、取消和节点失败记录补充单元测试

## 3. 管道控制器

- [x] 3.1 抽出 `PipelineController`，封装 scheduler、current_task 和默认 DAG 执行路径
- [x] 3.2 保证手动运行、定时运行和启动运行复用同一持久化执行路径
- [x] 3.3 实现并发运行拒绝逻辑，返回当前运行 cycle_id
- [x] 3.4 实现暂停和恢复调度，不取消当前运行
- [x] 3.5 实现停止当前运行，并将运行记录标记为 `cancelled` 或 `failed`
- [x] 3.6 调整 `main.py`，使 Web 控制台和后台调度在同一进程启动

## 4. 结果浏览

- [x] 4.1 实现简报查询接口，支持最新简报和空状态
- [x] 4.2 实现建议列表查询接口，按 created_at 倒序返回
- [x] 4.3 实现建议详情接口，关联展示 source_quotes、source_urls、AnalysisResult 和 RawItem
- [x] 4.4 实现失败源展示，从 Briefing metadata 读取 failed_sources
- [x] 4.5 实现结果浏览页面，覆盖最新简报、建议列表、证据链和失败源信息

## 5. 管道控制页面与 API

- [x] 5.1 实现运行状态 API，返回 scheduler 状态、暂停状态、当前 cycle_id 和最近运行
- [x] 5.2 实现手动运行 API
- [x] 5.3 实现暂停和恢复调度 API
- [x] 5.4 实现停止当前运行 API
- [x] 5.5 实现管道控制页面，接入状态展示和操作按钮
- [x] 5.6 为 API 补充集成测试，覆盖手动运行、并发拒绝、暂停恢复、停止无活动运行

## 6. 配置编辑

- [x] 6.1 实现配置读取服务，读取 `system.toml`、`portfolio.yaml`、`nodes/*.yaml`、`dags/*.yaml` 和 `skills/*` 文档
- [x] 6.2 实现 portfolio/source/system 编辑 API，并复用现有 Pydantic schema 校验
- [x] 6.3 实现 Node/DAG 文本编辑 API，保存前执行 Node schema、DAG 引用、环检测和 I/O 校验
- [x] 6.4 实现 Skill 文档编辑 API，并限制路径必须位于项目 `skills/` 目录内
- [x] 6.5 实现临时文件 + replace 的原子保存逻辑
- [x] 6.6 实现配置编辑页面，展示校验错误且失败时不写入文件
- [x] 6.7 为配置编辑补充测试，覆盖非法 schema、非法 DAG、路径穿越和运行中保存配置快照

## 7. 部署与验收

- [x] 7.1 更新 Dockerfile/docker-compose，使本机 Web 端口可访问且默认不暴露公网
- [x] 7.2 补充 README 运行说明，包含本机 Web 控制台地址和默认安全边界
- [x] 7.3 运行 `pytest tests/unit tests/contract tests/integration tests/e2e`
- [x] 7.4 运行 `ruff check .`
- [x] 7.5 运行 `mypy src`
