## Why

FR33 要求用户可通过 Web 界面管理标的和信息源配置。当前系统只能通过通用 YAML textarea 编辑 `portfolio.yaml`，容易误改结构，也无法让用户快速确认标的、持仓、信息源和关联关系。

## What Changes

- 在现有配置页面增加 portfolio 结构化管理入口，展示标的、持仓、信息源和标的绑定的信息源。
- 提供受 schema 校验的 Web/API 保存路径，用于更新 `portfolio.yaml` 中的 targets 和 sources。
- 保存继续复用 `RuntimeConfigEditor.save()` 的校验与原子写入语义；当前运行仍使用启动时配置快照，新配置只影响后续运行。
- 第一版只管理现有 `PortfolioConfig` schema 字段，不引入配置数据库、权限系统或图形化 Node Graph。

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `runtime-config-editing`: 增加标的与信息源的结构化 Web 管理入口、受限保存 API、schema 校验和保存反馈要求。

## Impact

- **代码**: 预计修改 `src/stockimformation/web/routes.py`、`src/stockimformation/web/templates/config.html`、`src/stockimformation/web/static/styles.css`，必要时补充配置序列化辅助函数。
- **配置**: 继续写入现有 `config/portfolio.yaml`，不新增配置文件。
- **API/UI**: 增加 portfolio 管理页面或 API；通用 `/api/config` 与 `/config` 继续保留。
- **依赖**: 不新增运行时依赖，不引入前端构建链。
