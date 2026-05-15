## Why

当前 Web 配置页只能用 YAML 编辑 DAG，用户需要手写节点和边，容易写错引用、fan flags 或形成非法图。项目已经具备运行时配置保存与 DAG 校验能力，现在需要把 DAG 的常见编辑动作变成可视化、结构化入口，同时保留原有校验边界。

## What Changes

- 在现有 `/config` 页面中，为 `kind=dag` 的配置提供 DAG 结构化编辑区。
- 展示当前 DAG 节点、边、`fan_in`、`fan_out`，并提供 SVG 预览。
- 支持通过 Web 表单选择节点、添加/删除边、切换 fan flags，并保存回现有 `config/dags/*.yaml`。
- 结构化保存继续复用 `RuntimeConfigEditor.save()` 和 `load_graph()`，非法 DAG 必须拒绝且不写入。
- 保留现有 YAML 原文编辑入口，作为高级编辑和无障碍兜底。
- 第一版不引入 React/Vite/重型图库，不实现拖拽连线、坐标持久化或前端 DAG 业务校验。

## Capabilities

### New Capabilities

### Modified Capabilities
- `runtime-config-editing`: 扩展 DAG 配置编辑需求，新增结构化可视化编辑、结构化保存和 YAML 兜底语义。

## Impact

- **代码**: 调整 `src/stockimformation/web/routes.py`、`src/stockimformation/web/templates/config.html`、`src/stockimformation/web/static/styles.css`，新增最小 Vanilla JS 静态资源。
- **API/Web**: 新增结构化 DAG 表单保存入口；现有通用 YAML 保存入口继续可用。
- **配置**: 写回现有 `config/dags/*.yaml`，不新增配置格式。
- **依赖**: 不新增 Python 或 Node 依赖，不引入前端构建链。
- **测试**: 增加结构化 DAG 保存、非法 DAG 不写入、DAG 页面渲染的单元/集成覆盖。
