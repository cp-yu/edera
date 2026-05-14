## Why

当前 MVP 只能作为后台管道运行，用户无法在浏览器中查看结果、控制执行或维护配置。项目需要一个仅本机访问的 Web 控制台，把现有「采集→分析→建议→推送」管道变成可观察、可操作、可维护的个人工具。

## What Changes

- 新增本机 Web 控制台，默认只监听 `127.0.0.1`，提供结果查看、管道操作和配置编辑入口。
- 新增结果浏览能力，展示最新简报、历史简报、建议列表、原文→分析→建议溯源链和失败源信息。
- 新增管道控制能力，支持手动运行、暂停/恢复定时调度、停止当前运行、查看当前运行状态和历史运行记录。
- 新增运行记录持久化能力，记录 cycle、节点状态、开始/结束时间、失败原因，为 WebUI 提供可靠状态来源。
- 新增配置编辑能力，支持编辑 `portfolio.yaml`、`system.toml`、`nodes/*.yaml`、`dags/*.yaml` 和 `skills/*` 文档类配置，并在保存前执行 schema/DAG 校验。
- 更新部署入口，使同一进程能够同时提供 Web 控制台和后台调度。

## Capabilities

### New Capabilities
- `local-web-console`: 仅本机访问的 Web 控制台，覆盖导航、页面渲染、HTTP API 和本地访问边界。
- `result-explorer`: 结果浏览能力，覆盖简报、建议、分析、原文和失败信息的查询与展示。
- `pipeline-control`: 管道控制能力，覆盖手动运行、暂停/恢复调度、停止当前运行、运行状态与运行记录。
- `runtime-config-editing`: 运行时配置编辑能力，覆盖 portfolio/system/node/dag/skill 配置读取、校验、保存与错误反馈。

### Modified Capabilities
（无）

## Impact

- **代码**: 新增 Web/API 模块、管道控制器、配置编辑服务、运行记录模型和数据库 repository 查询接口；调整 `main.py` 启动方式。
- **数据库**: 新增 `PipelineRun`、`NodeRun` 等运行记录表，并添加 Alembic migration。
- **配置**: Web 控制台需要读取和写入现有 `config/` 与 `skills/` 文件；默认监听地址必须保持本机访问。
- **依赖**: 预计新增 FastAPI、Uvicorn、Jinja2 或等价的 Python Web 层依赖；除非后续设计确认必要，不引入独立 Node 前端构建链。
- **部署**: Docker/compose 需要暴露本机 Web 端口；默认配置不得绑定公网地址。
