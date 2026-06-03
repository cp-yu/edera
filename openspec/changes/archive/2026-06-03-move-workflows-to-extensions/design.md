## Context

第一个 change `extension-import-clean-runtime` 已经把 runtime 入口清理为：core 不再生成默认配置实例，extension manifest 可以通过 `imports.entities` 声明 Entity YAML，启动/materialization 由 importer 幂等写入 DB。当前仓库仍保留两条顶层工作流配置：`config/dags/default.yaml` 和 `config/dags/uzi-skill-analysis.yaml`，以及它们对应的 node、trigger 和部分 seed Entity。

本 change 是迁移 change，不重新设计 importer。目标是把现有工作流配置整理成 extension-owned packages，使这些内容通过 manifest import 进入 DB-backed core entities。

## Goals / Non-Goals

**Goals:**
- 将 `default` 新闻工作流迁移为新的 `extensions/default-news-workflow/` package。
- 将 `uzi-skill-analysis` 工作流配置迁移到现有 `extensions/uzi-skill/` package。
- 为每个 workflow package 明确 manifest `imports.entities` 列表，覆盖 DAG、node、trigger、resource 和 DAG 直接引用的 source seed Entity。
- 从顶层 `config/` runtime source 中移除已迁移的 DAG、node、trigger 和 `v8_isolate` resource 文件/条目。
- 保持两个 DAG 的拓扑、alias、optional、resource、cron 和手动运行语义不变。

**Non-Goals:**
- 不迁移 stock Entity、portfolio seed 或 `config/entity-relations.yaml`。
- 不实现 extension uninstall。
- 不改变 UZI 外部脚本路径、LegacyScriptAdapter 调用协议或 handler 实现。
- 不新增 runtime import 机制；依赖第一个 change 提供的 importer。

## Decisions

1. 默认新闻工作流使用独立 package `extensions/default-news-workflow/`。

   该 package 不是 handler provider，而是 workflow package。它通过 `depends` 引用 `rss-fetcher`、`api-fetcher`、`reader`、`advisor`、`briefing-generator` 和 `notifier` 等 handler/entity type provider。替代方案是把 DAG 文件放进某个 handler extension，但这会让单一 handler extension 拥有跨多个 handler 的业务拓扑，边界不清晰。

2. UZI workflow 放入现有 `extensions/uzi-skill/`。

   UZI handler、业务 node type 和 DAG 实例都属于同一业务 extension。把 workflow 拆成 `uzi-skill-workflow` 会增加 package 依赖和 manifest 同步成本，但没有减少 ownership 复杂度。

3. Import 文件采用 extension-local `entities/` 目录，并由 manifest 显式枚举。

   建议布局为 `entities/dags/<name>.yaml`、`entities/nodes/<name>.yaml`、`entities/triggers/<name>.yaml`、`entities/resources/<name>.yaml`、`entities/sources/<name>.yaml`。manifest 是唯一导入入口，不能靠目录扫描猜测所有权。

4. Source seed Entity 只迁移 DAG 直接引用的 RSS/API source。

   `default` DAG 的 node config 直接引用 `rss-source:hn-rss` 和多个 `api-source:*`，没有这些 Entity 导入后无法完整运行。stock Entity 和 relation seed 没有被两个 DAG 直接引用，保留在用户/本地 seed 边界。

5. 顶层 `config/` 中已迁移 runtime 实例必须移除。

   第一个 change 已经禁止 core 生成默认实例。本 change 完成后，保留同一 DAG/node/trigger 的顶层配置会制造双重来源。顶层 `config/schemas/`、`config/skills/` 和未迁移 seed 数据不属于本次删除范围。

## Risks / Trade-offs

- [Risk] workflow package import 与用户 DB 中已有同 ref Entity 冲突。→ Mitigation: 第一个 change 的 importer 记录 `skipped_existing` 且不覆盖，测试需要覆盖已有实体场景。
- [Risk] 删除顶层配置导致开发者找不到示例。→ Mitigation: 示例仍存在于 extension-local `entities/`，manifest 显式列出入口。
- [Risk] UZI 节点很多，手动迁移易漏 node 或 edge。→ Mitigation: 使用现有 `uzi-skill-dag-instance` 拓扑测试和 import count/graph load 检查验证。
- [Risk] `v8_isolate` resource 迁移后仍被多个节点引用。→ Mitigation: 把 resource Entity 作为 UZI package import，并验证 resource semaphore 可 resolve。
- [Risk] 默认 workflow 依赖多个 handler provider。→ Mitigation: manifest `depends` 必须列出 provider extensions，bootstrap 依赖校验失败时拒绝加载。

## Migration Plan

1. 创建 `extensions/default-news-workflow/manifest.yaml` 和 extension-local Entity YAML。
2. 更新 `extensions/uzi-skill/manifest.yaml`，补充 node type 声明和 `imports.entities`，新增 UZI Entity YAML。
3. 从顶层 `config/dags/`、`config/nodes/`、`config/triggers/` 和 `config/entities.yaml` 移除已迁移的 runtime 实例。
4. 增加 import fixture 和 DAG graph tests，验证两个 workflow package 导入后可加载。
5. 增加边界回归测试，确认顶层 config 不再是迁移 DAG/node/trigger/resource 的规范来源。

Rollback 可以通过恢复顶层配置文件并移除新 extension manifest imports 完成；开发阶段无生产数据迁移承诺。

## Open Questions

无阻塞问题。stock Entity 和 relation seed 的 ownership 明确留待后续单独 change。
