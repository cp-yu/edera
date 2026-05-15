## Context

现有 `runtime-config-editing` 已覆盖配置文件列表、读取、保存前校验、原子写入和运行中配置快照。代码证据显示 `NodeConfig` 目前支持 `model`、`timeout_seconds`、`source_names`，`reader.yaml` 已配置 `model`，采集节点已配置 `source_names`，`system.toml` 已配置 `llm_timeout_seconds`。

PRD FR45 只说“用户可调整分析参数”，验证报告要求限定可调参数范围、版本记录和回滚边界。当前项目没有参数数据库、版本表或配置历史能力；第一版应避免把 FR45 扩成新的参数系统。

## Goals / Non-Goals

**Goals:**
- 给 Web 用户一个直接的分析参数调优入口，避免在通用文件列表中猜哪些文件影响分析质量。
- 限定第一版可调参数，全部落在现有 `config/` YAML/TOML 文件和 schema 校验内。
- 复用现有原子保存和当前运行配置快照语义。
- 对 schema 不足处只增加 `NodeConfig.parameters`，用于承载节点私有分析参数。

**Non-Goals:**
- 不实现数据库参数版本记录、可视化 diff 或一键回滚。
- 不引入新的参数服务、权限模型或远程配置中心。
- 不修改分析算法语义，除非实现阶段需要让现有节点读取新增 `parameters`。
- 不扩大到 FR8/FR9/FR16/FR17/FR48 的事件归并、信源权重、概率归因等未实现能力。

## Decisions

1. 扩展 `runtime-config-editing`，不新增 capability。
   - 理由：现有 OPSX 中配置域只有 `runtime-config-editing`，且通用 editor 已覆盖 node/dag/system/portfolio/skill 文件。FR45 第一版是“入口 + 参数范围 + 校验”，属于该能力的新增 requirement。
   - 替代方案：新增 `analysis-parameter-tuning` capability。缺点是会制造一个与配置编辑器重叠的契约，实际实现仍要调用同一批配置读写代码。

2. 第一版参数白名单以现有 schema 为核心。
   - 包含 `NodeConfig.timeout_seconds`、`NodeConfig.model`、采集节点 `source_names`、`SystemConfig.llm_timeout_seconds`。
   - reader/advisor/briefing 节点若需要更细调优，统一放入 `NodeConfig.parameters`，而不是为每个节点新增顶层字段。
   - `parameters` 值限定为 JSON-like scalar/list/mapping，禁止凭据和不可序列化对象。

3. UI 使用“分析参数”入口筛选并编辑相关配置，不绕过通用保存路径。
   - 页面可以是现有配置页的一个 filter/tab，也可以是相邻 route；保存必须走同一套 `RuntimeConfigEditor.save()` 或等价校验路径。
   - 这样不会产生两套写文件逻辑，也不会破坏已有 DAG 校验和 path traversal 防护。

4. 版本记录与回滚边界先显式收窄。
   - 第一版保存成功后，以文件系统和 VCS/备份承担历史恢复；产品界面不承诺内置版本历史。
   - UI/文案和 spec 要明确“保存影响后续运行，当前运行不变”，并在测试中固定该行为。

## Risks / Trade-offs

- [Risk] `parameters` 过宽会变成无约束垃圾桶 → Mitigation: 限定只允许节点私有分析调优参数，保存前用 Pydantic 校验 JSON-like 内容，任务中补充节点级测试。
- [Risk] 用户误改 YAML 导致分析链不可用 → Mitigation: 继续复用保存前 schema/DAG 校验，并在分析参数入口只展示白名单字段或相关文件。
- [Risk] 没有内置回滚不满足长期 FR45 期望 → Mitigation: 第一版在 spec 中明确回滚边界，后续如需要再单独提出配置版本历史 capability。
- [Risk] `source_names` 既影响采集又影响分析输入 → Mitigation: 第一版只把采集节点的 `source_names` 作为分析输入范围调优项展示，不改变 portfolio source 管理语义。
