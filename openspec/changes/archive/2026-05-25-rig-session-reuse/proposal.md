## Why

LLM 节点当前每次执行都创建全新 session，无法跨 DAG 复用对话上下文。这导致三个场景无法实现：(1) 跨 DAG 的 session 复用（agent 保持记忆）；(2) 失败/运行中节点的侵入式干预（stop + resume）；(3) 反思 DAG 驱动的 skill 自优化（resume 后让 agent 修改自身 skill）。同时系统缺少一个 CLI 工具让 agent 在运行时访问 entity store 和引擎控制能力。

## What Changes

- 引入 `rig` CLI binary，支持 `--identity` 身份声明（env 默认 + flag 覆盖），暴露 entity/node/dag 子命令
- LLM 节点 sandbox 路径重构为 `workspace_root/sandbox/{node_id}/{origin_cycle}`，session 目录独立于 workspace 生命周期
- `NodeConfig` 类型层增加 `tools` 默认值字段；`model` 字段移至 `DagNodeInstance.config` 实例层
- `DagNodeInstance.config` 增加 `session_dir`（支持引用解析，指向已有 sandbox 即隐含 resume）和 `tools`（覆盖类型层默认值）
- `run_pi` 改造：根据 `tools` 配置生成 `--tools` 白名单参数；根据 `session_dir` 判断新建或 `--continue` resume；注入 `RIG_IDENTITY` 环境变量
- 支持 stop + resume 干预机制：对运行中节点 soft stop 后，通过 resume session 附带干预指令重启
- 反思 DAG 模式：独立 DAG 通过 cron + wait_for idle 触发，resume 目标节点 session 进行 skill 自优化

## Capabilities

### New Capabilities
- `rig-cli`: `rig` CLI binary，支持 entity/node/dag 子命令，双身份模式（agent/human），权限继承 entity_permissions
- `llm-session-reuse`: LLM 节点 session 复用机制，覆盖 sandbox 路径管理、session_dir 引用解析、resume 判定和 TTL 清理
- `llm-node-intervention`: LLM 节点侵入式干预，覆盖 stop + resume with prompt 的完整流程
- `reflection-dag-pattern`: 反思 DAG 模式，覆盖 cron + idle 触发、session resume、skill 自优化闭环

### Modified Capabilities
- `node-executor`: 执行器需支持 `tools` 白名单传递和 `RIG_IDENTITY` 环境变量注入
- `node-instance-model`: 实例模型增加 `session_dir`、`tools` 字段，`model` 从类型层移至实例层

## Impact

- `extensions/_lib/llm.py`：`run_pi` 和 `prepare_workspace` 重构
- `packages/core/src/stockimformation_core/config/schema.py`：`NodeConfig` 和 `DagNodeInstance` schema 变更
- `packages/core/src/stockimformation_core/node/executor.py`：执行器适配新参数
- `packages/core/src/stockimformation_core/pipeline.py`：pipeline 层传递新配置
- 新增 `rig` CLI binary（独立包或脚本）
- 前端 Inspector 面板：增加 tools 权限多选框 + entity_permissions 配置器
- **BREAKING**：`model` 字段从 `NodeConfig` 移至实例层，现有 node YAML 配置需迁移
