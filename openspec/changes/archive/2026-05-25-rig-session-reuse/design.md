## Context

当前 LLM 节点（`run_pi`）每次执行创建全新 workspace 和 session，执行完毕后按 `retention_count` 策略清理。节点间无法共享对话上下文，也无法对失败节点进行干预式恢复。系统缺少运行时 CLI 工具供 agent 访问 entity store。

现有关键约束：
- Pi 的 session 存储在 `--session-dir` 指定的目录中，格式为 `.jsonl`
- Pi resume 时要求 session header 中记录的 `cwd` 目录仍然存在
- Pi 支持 `--tools` 白名单控制可用工具
- Pi 支持 `--continue` flag 恢复已有 session

## Goals / Non-Goals

**Goals:**
- LLM 节点 session 可跨 DAG 复用（通过 `session_dir` 引用解析）
- 提供 `rig` CLI binary 供 agent 和人类访问引擎能力（entity/node/dag 操作）
- 支持 stop + resume 干预机制
- 支持反思 DAG 模式（cron + idle 触发，resume 目标 session 优化 skill）
- `model` 字段从类型层移至实例层

**Non-Goals:**
- 引擎层 model provider 管理（Pi 原生 `models.json` 已满足）
- Bubblewrap 沙箱隔离（后续独立 change）
- 反思 DAG 的具体 skill 优化策略（由 DAG 编排者定义）
- 前端 Inspector 权限配置器 UI（独立 change）

## Decisions

### D1: Sandbox 路径结构

**决策**：`workspace_root/sandbox/{node_id}/{origin_cycle}`

**替代方案**：
- `workspace_root/node/{node_id}/{cycle_id}` — "node" 太泛，cycle_id 暗示归属关系
- `workspace_root/sessions/{session_id}` — session_id 由 pi 生成，目录创建时未知

**理由**：sandbox 明确表达隔离执行环境；origin_cycle 表示创建者而非使用者；路径确定性强，无需 rename。

### D2: Session 复用通过 `session_dir` 统一处理

**决策**：`DagNodeInstance.config.session_dir` 支持三种值：
1. 不设置 → 默认创建临时 sandbox
2. 绝对路径 → 使用指定目录（持久化，用户管理）
3. 引用格式 `sandbox:{node_id}:latest` → 运行时解析为最近的 sandbox 路径

存在已有 session 文件时自动传 `--continue`，否则新建。无需独立 `resume` 字段。

**替代方案**：独立 `resume` 字段 — 增加配置复杂度，语义与 `session_dir` 重叠。

### D3: Agent CLI 集成方式

**决策**：`rig` CLI binary，agent 通过 pi 的 bash tool 调用。身份通过 `RIG_IDENTITY` 环境变量注入，`--identity` flag 可覆盖。权限继承 `DagNodeInstance.config.entity_permissions`。

**替代方案**：
- MCP server — 额外进程管理开销
- Pi skill 封装 — entity 操作需要精确性，自然语言调用不可靠

### D4: 工具权限分层

**决策**：`NodeConfig.tools`（类型层默认值）+ `DagNodeInstance.config.tools`（实例层覆盖）。所有 LLM 节点最小工具集为 `[bash]`（engine CLI 访问）。`run_pi` 根据最终 tools 列表生成 `--tools` 参数。

**替代方案**：全局统一工具集 — 无法按场景差异化（反思节点需要 file tools，分析节点不需要）。

### D5: 干预机制

**决策**：stop（soft stop via asyncio.Event）+ resume（`--continue` + intervention prompt）。不支持运行中 stdin 注入。

**理由**：Pi 的 `-p` 模式不暴露 stdin；stop + resume 语义清晰，复用已有机制。

### D6: 反思 DAG 触发

**决策**：独立 DAG，cron 定时触发 + `wait_for` 条件检测目标节点空闲。冲突时等待完成后再执行。绑定关系通过 DAG 内节点的 `session_dir: "sandbox:{target_node}:latest"` 声明，辅以 node ↔ node relation 提供可观测性。

### D7: `model` 字段迁移

**决策**：从 `NodeConfig`（类型层）移至 `DagNodeInstance.config`（实例层）。类型层不再声明 model，同一 node type 在不同 DAG 中可使用不同模型。

**迁移**：现有 `config/nodes/*.yaml` 中的 `model` 字段移至引用该 node 的 DAG 配置中。

## Risks / Trade-offs

- [Pi cwd 依赖] sandbox 目录被清理后 resume 失败 → 清理策略需保证 session 引用期间目录存活；引用解析时校验目录存在性
- [工具权限扩大] 所有 agent 默认获得 bash 访问 → 后续通过 bubblewrap 沙箱限制；当前阶段接受风险
- [Breaking change] `model` 字段迁移 → 提供迁移脚本自动重写配置文件
- [Session 膨胀] 长期 resume 导致 session.jsonl 无限增长 → TTL 清理策略兜底

## Open Questions

- `session_dir` 引用格式的具体语法（`sandbox:node_id:latest` vs 其他格式）待实现时确定
- Sandbox TTL/size 清理策略的默认参数待性能测试后确定
- `rig` CLI 输出格式（JSON/human-readable/`--format` flag）待实现时确定
