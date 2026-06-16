## Why

Agent 节点（基于 pi 的 LLM 执行器）当前装配残缺：`AgentNodeConfig` 声明了 `skills`、`tools`、`system_prompt`、`system_prompt_file` 四个能力字段，但 `_build_agent_command` 实际只把 `--model/--session-dir/--session*/-p` 传给 pi，四个字段全部断路；`generate_skill_files` 把技能文件写进 `session_dir/skills/`，而 session_dir 仅为会话存储，pi 不从中发现 skills（已由 `pi --help` 实测确认），这些是死文件。结果是 agent 行为既无 skills、无 system prompt、也无 tools 控制，完全不可配置。

## What Changes

- **Skills 接入 pi**：以 DB 为唯一源（single source of truth），DB skills 物化到固定目录 `data/skills/<name>/`（与 `data/handlers/` 对称），agent 执行时用 `--skill {dir}/{name}` 逐个装配本节点声明的技能，并恒定附加 `--no-skills` 关闭 pi 自动发现。
- **Per-node skill 装配**：废弃 `_closure_skills` 的全 DAG 并集聚合，改为按 `effective.skills`（本节点声明）过滤装配。
- **system_prompt 接入 pi**：双入口执行时现读——内联 `system_prompt` 走 `--system-prompt <text>`，`system_prompt_file` 走 `--append-system-prompt <file>`，改盘立即生效。删除 `loader.py` 中配置加载期的文件快照合并逻辑（违反 DB 唯一源）。
- **Tools 接入 pi**：`AgentNodeConfig.tools` 走白名单 `--tools <csv>`；空列表或缺省走 `--no-tools`，agent 节点不存在"pi 默认全工具集"路径。
- **强制上下文隔离**：所有 agent 调用恒定附加 `--no-context-files`，阻断 workdir 的 AGENTS.md/CLAUDE.md 注入。
- **BREAKING — `tools` 字段收归 AgentNodeConfig**：从 `FunctionNodeConfig` 移除死字段 `tools`（function 节点不走 pi），仅保留在 `AgentNodeConfig`。
- **死代码清理**：移除零引用的 `node/skills.py:load_skill` 与 `SkillDefinition`（Python 侧）。

## Capabilities

### New Capabilities

（无新增 capability——本次变更落在现有 capability 的 requirement 上。）

### Modified Capabilities

- `agent-executor`：扩写「Pi CLI subprocess 配置」requirement，纳入 skills / system_prompt / tools / context 隔离的完整装配契约；新增「Skills DB-SoT 物化与复用」「Per-node 能力装配」「Agent tools 白名单」requirement。

> 注：`dag-execution-snapshot` 的「创建 DAG 执行快照」已声明 skills 为副本、且独立于后续变更——per-node 过滤是 executor 层实现，不改变 snapshot 的外部可观测行为，故不纳入本次 spec 变更。`node-executor` spec 存在过时表述（声称核心不含 pi 调用），与当前实现相悖，其清理另立 change，不在本次范围；`tools` 字段收归 AgentNodeConfig 的 schema 变更以 `agent-executor` 的「Agent tools 白名单」requirement 表达。

## Impact

- **核心代码**：`packages/core/src/edera_core/node/executor.py`（`_build_agent_command` 重写、`_execute_agent` per-node 过滤、移除 session_dir 物化）、`config/schema.py`（SystemConfig 增 `skills_dir`、FunctionNodeConfig 去 tools）、`snapshot.py`（废弃 `_closure_skills` 聚合语义）、`config/loader.py`（删 system_prompt_file 快照合并）、`skills/generator.py`（物化目标改为 skills_dir）、`storage/repository.py` + `graph_service.py`（`upsert_skill`/`delete_skill` 单点同步 `data/skills/`）、`service_common.py`（inspector/payload tools gate）。
- **线程路径**：`skills_dir` 从 SystemConfig → DagController → NodeExecutor，复用 `handlers_dir` 现有范式。
- **测试**：两个 C21（skills 物化断言从 session_dir/skills 改为 data/skills + per-node `--skill`）、`test_node_instance_model` 与 `test_node_executor` 的 function tools 断言、新增 mock-pi argv 装配验证。
- **并发竞态**（Non-Goal）：`data/skills/` 物化期间 agent 正在执行可能读到中途状态，开发阶段接受此风险，不上版本化目录。
