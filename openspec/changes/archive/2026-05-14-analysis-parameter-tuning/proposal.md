## Why

FR45 要求用户可调整分析参数。当前 Web 配置编辑器已经能编辑 `system.toml`、`nodes/*.yaml`、`dags/*.yaml`、`portfolio.yaml` 和 `skills/*` 文档，但入口仍是通用文件编辑，用户无法快速定位会影响分析链质量的参数。

## What Changes

- 在现有运行时配置编辑能力上增加“分析参数调优入口”，聚合展示第一版允许调整的分析相关配置。
- 第一版参数范围限定为已有配置体系能承载的字段：`NodeConfig.timeout_seconds`、`NodeConfig.model`、采集节点 `source_names`，以及 reader/advisor/briefing 节点 YAML 中经 schema 明确允许的分析参数字段。
- 若现有 `NodeConfig` schema 不足，做最小扩展：为节点配置增加一个受 schema 校验的 `parameters` mapping，仅用于节点私有、非凭据、可序列化的调优参数。
- 保存继续复用现有配置编辑器的校验、原子写入和“当前运行使用启动快照”语义，不引入数据库参数表或独立版本系统。

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `runtime-config-editing`: 增加面向 FR45 的分析参数调优入口、受限参数集合、schema 校验和保存反馈要求。

## Impact

- **代码**: 预计修改 `src/stockimformation/config/schema.py`、`src/stockimformation/config/editor.py`、`src/stockimformation/web/routes.py`、`src/stockimformation/web/templates/config.html` 或相邻模板。
- **配置**: 可能在 `config/nodes/reader.yaml`、`config/nodes/advisor.yaml`、`config/nodes/briefing-generator.yaml` 中加入最小 `parameters` 示例；不得把凭据写入配置文件。
- **API/UI**: 复用 `/api/config` 与 `/api/config/{kind}/{name}` 保存路径，必要时增加轻量的分析参数列表/页面入口。
- **依赖**: 不新增运行时依赖，不引入独立前端构建链。
