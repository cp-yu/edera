## Context

现有 `runtime-config-editing` 已覆盖 `portfolio.yaml` 的读取、校验、原子保存和运行快照语义。`PortfolioConfig` 已定义 `targets`、`sources`、`holding`、`source_map()`；`SourceConfig` 当前只支持 `rss` 与 `web`。Web 端已有 `/config` textarea 和 `/api/config/{kind}/{name}` 通用保存接口。

FR33 的第一版不需要独立配置系统。正确做法是给 `portfolio.yaml` 加结构化入口，让用户在不理解 YAML 细节的情况下管理标的和信息源，同时继续由 Pydantic schema 和 `RuntimeConfigEditor.save()` 把关。

## Goals / Non-Goals

**Goals:**
- 在 Web 配置界面展示当前标的、持仓、信息源和绑定关系。
- 提供结构化保存 API，接收 targets/sources 数据并写回 `portfolio.yaml`。
- 保存前执行 `PortfolioConfig` 校验，并复用 `RuntimeConfigEditor.save()` 原子写入。
- 保留通用 YAML 编辑入口，满足高级用户和回退需求。

**Non-Goals:**
- 不实现 Node Graph、拖拽式配置或多文件编排。
- 不引入数据库版本记录、审批流、权限模型或远程配置中心。
- 不新增信息源类型；第一版仅支持现有 `rss` 与 `web`。
- 不改变 pipeline 运行中配置快照语义。

## Decisions

1. 继续修改 `runtime-config-editing`，不新增 capability。
   - 理由：标的/信息源管理本质是 portfolio 配置编辑的结构化入口，仍然写同一个 `portfolio.yaml`。

2. 增加轻量结构化 API，而不是前端直接拼 YAML。
   - API 接收 JSON，服务端用 `PortfolioConfig.model_validate()` 校验，再序列化为 YAML，最后调用 `RuntimeConfigEditor.save("portfolio", "portfolio", content)`。
   - 这样可以避免两套写文件逻辑，也能复用现有错误格式。

3. UI 第一版只做表格和 JSON textarea。
   - 表格负责让用户快速查看关系。
   - JSON textarea 负责结构化编辑，避免一次性实现复杂动态表单带来的代码膨胀。
   - 高级 YAML 编辑仍通过现有 textarea 可用。

## Risks / Trade-offs

- [Risk] JSON textarea 仍可能误填字段 → Mitigation: 服务端 schema 校验，错误通过现有 `.error` 或 API error 返回。
- [Risk] YAML 序列化改变字段顺序或格式 → Mitigation: 只序列化 `PortfolioConfig.model_dump(mode="json")` 的稳定字段，避免保留注释承诺。
- [Risk] 信息源名称被 target 引用但 source 不存在 → Mitigation: 保存 API 显式校验 target sources 必须存在于 sources 列表。
