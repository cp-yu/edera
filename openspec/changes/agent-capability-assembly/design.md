## Context

Agent 节点是 Edera 中唯一基于 pi（外部 LLM CLI）的执行分支。`AgentNodeConfig`（`packages/core/src/edera_core/config/schema.py:189-215`）声明了 `skills`、`tools`、`system_prompt`、`system_prompt_file` 四个能力字段，但 `_build_agent_command`（`executor.py:412-433`）只构造 `--model/--session-dir/--session*/-p`，四个字段全部断路。`generate_skill_files`（`executor.py:306`）把技能写进 `session_dir/skills/`，而 session_dir 仅为会话存储，pi 不从中发现 skills（`pi --help` 实测确认 skills 靠 `--skill`/`--no-skills`）。

运行时 skills 的唯一来源是 DB `skills` 表（`list_skill_configs` → `skill_to_config` 从 `config_body.files` 取内容）；`config/skills/*.yaml`（无 files）与 `skills/<name>/`（import 源）均非运行时依赖。`_closure_skills`（`snapshot.py:117`）对 closure 内所有 node 的 skills 声明做全量并集，无 per-node 过滤。

## Goals / Non-Goals

**Goals:**
- agent 节点的 skills / system_prompt / tools 三个能力字段正确接入 pi 真实 CLI 参数。
- skills 以 DB 为唯一源，物化到固定目录 `data/skills/<name>/` 供多 node 复用，物化由 `upsert_skill`/`delete_skill` 单点触发。
- per-node 装配：仅本节点 `effective.skills` 声明的技能被装配。
- system_prompt 支持内联与文件双入口，文件入口改盘立即生效。
- agent 调用行为完全由 Edera 配置决定（强制 `--no-context-files`，`--no-skills` 关闭自动发现）。
- `tools` 字段收归 `AgentNodeConfig`，修复标签化联合泄漏。

**Non-Goals:**
- 不处理 `data/skills/` 物化的并发竞态（agent 执行期间 DB 改 skill 触发覆盖写，正在跑的 agent 可能读到中途状态）。开发阶段无历史负担，并发改 skill 罕见，接受此风险，不上版本化目录/原子替换。
- 不实现 skill 版本控制、依赖管理。
- 不改动 function 节点的执行路径（仅移除其死字段 `tools`）。
- 不引入 pi 的 `--append-system-prompt` 之外的新 prompt 机制。

## Decisions

### D1: Skills 物化到固定目录 `data/skills/`（1A-i），DB 唯一源

**选择**：DB `skills` 表为唯一源；物化到 `SystemConfig.skills_dir`（默认 `data/skills`，与 `handlers_dir` 对称）；agent 用 `--skill {skills_dir}/{name}` 引用，`--no-skills` 关闭自动发现。

**备选**：
- 内存化 entity + per-invocation 临时目录（1A-ii）：执行快照隔离、无竞态，但每次执行拷贝、无跨 node 复用。
- 版本化目录：完全消除竞态，但引入版本管理复杂度，开发期 YAGNI。

**理由**：与 handler 范式一致（DB SoT + 固定磁盘目录 + 路径引用）；`upsert_skill`/`delete_skill`（`repository.py:552/570`）是所有 CRUD 路径（web/grpc/CLI）的单一汇聚点，物化同步可挂在此层单点；多 node 复用零拷贝。竞态显式接受（见 Non-Goals）。

### D2: system_prompt 双入口执行时现读（2C）

**选择**：内联 `system_prompt` → `--system-prompt <text>`；`system_prompt_file` → `--append-system-prompt <file>`（pi 执行时现读，改盘生效）。两者并存，`system_prompt` 为基线、`system_prompt_file` 追加。

**备选**：入库时合并（loader 读文件写 `system_prompt`）——但违反"DB 唯一源"，且 `loader.py:76-80/494-498` 的现有快照合并使改盘不生效，与 skills 的"DB 改→物化→生效"语义不一致。

**理由**：与 D1 的"DB 唯一源 + 磁盘投影 + 改盘生效"同构。**删除 loader.py 的文件快照合并**，使 system_prompt_file 仅在 executor 执行时现读。

### D3: Tools 白名单，空 = 全禁

**选择**：`AgentNodeConfig.tools` → `--tools <csv>`；空列表或缺省 → `--no-tools`。agent 节点无"pi 默认全工具"路径。

**理由**：声明即边界，最严格可预测。`PI_TOOLS`（`schema.py:11`）与 `_validate_tools` 已就绪。

### D4: 强制 `--no-context-files`

**选择**：所有 agent 调用恒定附加 `--no-context-files`。

**理由**：agent 行为须由 Edera 配置完全决定，阻断 workdir 的 AGENTS.md/CLAUDE.md 意外注入，保证同一 node 在不同 workdir 行为一致。

### D5: per-node skill 装配

**选择**：`_execute_agent` 用 `effective.skills`（本节点声明）过滤装配；废弃 `_closure_skills` 全量并集聚合。

**理由**：当前 A 节点声明 skill-X、B 节点声明 skill-Y，同 session 两者都被装配——违背 config 声明意图。per-node 装配恢复精确边界。

### D6: `tools` 字段收归 AgentNodeConfig

**选择**：从 `FunctionNodeConfig` 移除 `tools` 与 `_pi_tools` validator，仅保留于 `AgentNodeConfig`。

**理由**：标签化联合（discriminated union）泄漏——function 节点不走 pi，`tools` 是死字段。爆炸半径已查清（见下）。

## Risks / Trade-offs

- **`data/skills/` 物化竞态** → 显式接受（Non-Goal）。缓解：物化频率低（CRUD 触发），agent 单次执行读取窗口短。
- **D2 删除 loader 快照合并是破坏性变更** → 任何依赖"加载期 prompt 已合并进 system_prompt 字段"的行为会变。当前除 loader 自身无其他消费者（已 grep 确认），风险可控。
- **D6 破坏性字段移除** → DB `entity_node.tools` 列保留（共享表，function 恒空），无需迁移；4 处生产代码 + 2 个测试需同步修改。
- **`--no-skills` + `--no-context-files` 恒定附加** → 若未来某 agent 需要读 workdir context 文件，需新增 per-node 开关。当前无此需求。

## Migration Plan

开发阶段无历史负担，无线上数据迁移：

1. SystemConfig 增 `skills_dir`，线程到 NodeExecutor。
2. skills 物化机制（`generate_skill_files` 改目标 + `upsert_skill`/`delete_skill` 同步钩子 + 启动刷新）。
3. `_build_agent_command` 重写装配。
4. per-node 过滤 + 废弃 `_closure_skills`。
5. 删 loader 文件合并 + 死代码。
6. D6 字段移除 + 配套 4 生产 / 2 测试修复。
7. 测试更新（2 个 C21 + mock-pi argv 验证）。

回滚：单分支隔离（`apply.defaultIsolation: branch`），整支回退即可。

## Open Questions

无。所有张力点已在 explore 阶段裁决（D1 接受竞态、D2 删除 loader 合并）。
