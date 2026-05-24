## 1. Actions

- [x] A1 在 `NodeConfig` schema 中添加 `tools` 字段（可选字符串数组），移除 `model` 字段
- [x] A2 在 `DagNodeInstance` schema 中添加 `session_dir`、`tools` 字段，将 `model` 移至 `config` 字段
- [x] A3 创建 `rig` CLI binary 骨架，支持 `--identity` flag 和 `RIG_IDENTITY` 环境变量
- [x] A4 实现 `rig entity` 子命令（get、list、update、query）
- [x] A5 实现 `rig node` 子命令（status）
- [x] A6 实现 `rig dag` 子命令（trigger）
- [x] A7 在 `rig` CLI 中实现 entity_permissions 权限检查逻辑
- [x] A8 修改 `run_pi` 函数，支持 sandbox 路径结构 `workspace_root/sandbox/{node_id}/{origin_cycle}`
- [x] A9 在 `run_pi` 中实现 `session_dir` 引用解析（支持 `sandbox:node_id:latest` 和 `sandbox:node_id:cycle_id` 格式）
- [x] A10 在 `run_pi` 中实现自动 `--continue` 判定（检测 session 文件存在性）
- [x] A11 在 `run_pi` 中根据 `tools` 配置生成 `--tools` 参数
- [x] A12 在 `run_pi` 中注入 `RIG_IDENTITY` 环境变量
- [x] A13 修改 `NodeExecutor` 以支持类型层 `tools` 默认值与实例层覆盖合并
- [x] A14 修改 `NodeExecutor` 以支持实例层 `model` 字段（从 `DagNodeInstance.config` 读取）
- [x] A15 实现 sandbox 清理策略（TTL/size 基础逻辑）
- [x] A16 实现节点 stop + resume 干预 API 端点
- [x] A17 编写 `model` 字段迁移脚本（从 `config/nodes/*.yaml` 移至 DAG 配置）
- [x] A18 更新现有 node YAML 配置文件，移除 `model` 字段
- [x] A19 更新现有 DAG YAML 配置文件，在实例 `config` 中添加 `model` 字段

## 2. Checks

- [x] C1 验证 NodeConfig schema 变更
  - Covers: A1
  - Command: `python -c "from stockimformation_core.config.schema import NodeConfig; print(NodeConfig.model_fields.keys())"`
  - Expect: 输出包含 `tools`，不包含 `model`

- [x] C2 验证 DagNodeInstance schema 变更
  - Covers: A2
  - Command: `python -c "from stockimformation_core.config.schema import DagNodeInstance; print(DagNodeInstance.model_fields['config'])"`
  - Expect: `config` 字段为 dict，可包含 `session_dir`、`tools`、`model`

- [x] C3 验证 rig CLI 可执行
  - Covers: A3
  - Command: `rig --help`
  - Expect: 输出包含 `entity`、`node`、`dag` 子命令

- [x] C4 验证 rig entity get
  - Covers: A4
  - Command: `rig entity get stock:AAPL`
  - Expect: 输出该 entity 的 attributes JSON

- [x] C5 验证 rig entity list
  - Covers: A4
  - Command: `rig entity list --type stock`
  - Expect: 输出所有 stock 类型 entity 列表

- [x] C6 验证 rig entity update
  - Covers: A4
  - Command: `rig entity update stock:AAPL --field sentiment --value bearish && rig entity get stock:AAPL`
  - Expect: sentiment 字段值为 bearish

- [x] C7 验证 rig entity query
  - Covers: A4
  - Command: `rig entity query "type=stock"`
  - Expect: 返回所有 stock 类型 entity

- [x] C8 验证 rig node status
  - Covers: A5
  - Command: `rig node status llm-analyze`
  - Expect: 输出节点状态（idle/running/failed）

- [x] C9 验证 rig dag trigger
  - Covers: A6
  - Command: `rig dag trigger default --payload '{}'`
  - Expect: 输出新创建的 cycle_id

- [x] C10 验证 RIG_IDENTITY 环境变量
  - Covers: A3, A7
  - Command: `RIG_IDENTITY=node:test-node rig entity get stock:AAPL`
  - Expect: 以 node:test-node 身份执行权限检查

- [x] C11 验证 --identity flag 覆盖
  - Covers: A3, A7
  - Command: `RIG_IDENTITY=node:test-node rig --identity human entity get stock:AAPL`
  - Expect: 以 human 身份执行，忽略环境变量

- [x] C12 验证权限拒绝
  - Covers: A7
  - Command: `RIG_IDENTITY=node:restricted-node rig entity update stock:AAPL --field code --value 001`
  - Expect: 输出 "Permission denied" 错误

- [x] C13 验证 sandbox 路径创建
  - Covers: A8
  - Command: 执行包含 LLM 节点的 DAG，检查文件系统
  - Evidence: `ls workspace_root/sandbox/{node_id}/{cycle_id}/`
  - Expect: 目录存在且包含 `.pi/`、`sessions/`、`pi-home/` 子目录

- [x] C14 验证 session_dir 引用解析（latest）
  - Covers: A9
  - Command: 配置节点 `session_dir: "sandbox:llm-analyze:latest"`，执行 DAG
  - Evidence: pi 进程的 `--session-dir` 参数
  - Expect: 解析为最近一次 llm-analyze 的 sandbox 路径

- [x] C15 验证 session_dir 引用解析（指定 cycle）
  - Covers: A9
  - Command: 配置节点 `session_dir: "sandbox:llm-analyze:run-20260524-001"`，执行 DAG
  - Evidence: pi 进程的 `--session-dir` 参数
  - Expect: 解析为 `workspace_root/sandbox/llm-analyze/run-20260524-001/sessions/`

- [x] C16 验证自动 --continue 判定（存在 session）
  - Covers: A10
  - Command: 在 session_dir 中放置 `.jsonl` 文件，执行节点
  - Evidence: pi 进程启动参数
  - Expect: 包含 `--continue` flag

- [x] C17 验证自动 --continue 判定（不存在 session）
  - Covers: A10
  - Command: 使用空 session_dir 执行节点
  - Evidence: pi 进程启动参数
  - Expect: 不包含 `--continue` flag

- [x] C18 验证 tools 白名单传递
  - Covers: A11, A13
  - Command: 配置节点 `tools: [bash, read, edit]`，执行 DAG
  - Evidence: pi 进程启动参数
  - Expect: 包含 `--tools bash,read,edit`

- [x] C19 验证类型层 tools 默认值
  - Covers: A1, A13
  - Command: NodeConfig 定义 `tools: [bash]`，实例未覆盖，执行节点
  - Evidence: pi 进程启动参数
  - Expect: 包含 `--tools bash`

- [x] C20 验证实例层 tools 覆盖
  - Covers: A2, A13
  - Command: NodeConfig 定义 `tools: [bash]`，实例配置 `tools: [bash, read]`，执行节点
  - Evidence: pi 进程启动参数
  - Expect: 包含 `--tools bash,read`

- [x] C21 验证 RIG_IDENTITY 环境变量注入
  - Covers: A12
  - Command: 执行节点 `llm-analyze`，在 pi 进程中执行 `echo $RIG_IDENTITY`
  - Evidence: pi 进程环境变量
  - Expect: `RIG_IDENTITY=node:llm-analyze`

- [x] C22 验证实例层 model 配置
  - Covers: A2, A14
  - Command: 实例配置 `model: "hf-share/deepseek-v4-flash"`，执行节点
  - Evidence: workspace `.pi/settings.json`
  - Expect: `{"defaultModel": "hf-share/deepseek-v4-flash"}`

- [x] C23 验证 model 字段迁移脚本
  - Covers: A17
  - Command: `python scripts/migrate_model_to_instance.py --dry-run`
  - Expect: 输出需要迁移的文件列表和变更预览

- [x] C24 验证迁移后配置可加载
  - Covers: A18, A19
  - Command: `python -c "from stockimformation_core.config.loader import load_app_config; load_app_config('config')"`
  - Expect: 无异常，所有 DAG 配置加载成功

- [x] C25 验证 stop + resume API
  - Covers: A16
  - Command: `curl -X POST http://localhost:8000/api/node/llm-analyze/stop && curl -X POST http://localhost:8000/api/node/llm-analyze/resume -d '{"prompt":"调整方向"}'`
  - Expect: stop 返回 200，resume 返回新的 cycle_id

- [x] C26 验证 sandbox 清理策略
  - Covers: A15
  - Command: 创建过期 sandbox，执行清理任务
  - Evidence: 文件系统
  - Expect: 过期 sandbox 被删除，未过期的保留

- [x] C27 验证反思 DAG session resume
  - Covers: A9, A10
  - Command: 创建反思 DAG，配置 `session_dir: "sandbox:llm-analyze:latest"`，执行
  - Evidence: pi 进程启动参数和 session 文件
  - Expect: resume 目标节点的 session，对话历史连续

- [x] C28 验证 payload 覆盖 session_dir
  - Covers: A9
  - Command: 节点配置 `session_dir: "sandbox:llm-analyze:latest"`，input payload 包含 `resume_session: "sandbox:llm-analyze:run-20260524-001"`
  - Evidence: pi 进程的 `--session-dir` 参数
  - Expect: 使用 payload 中的值

## Remediation

- [x] [code_fix] Persist successful node resume outputs against the original cycle and preserve the same sandbox session_id.
- [x] [code_fix] Apply entity_permissions read checks to `rig entity get`, `list`, and `query`.
- [x] [code_fix] Add CLI-accessible NodeOutput history queries for reflection DAG source nodes.
- [x] [code_fix] Implement target-node idle gating for reflection DAG cron and manual triggers.
- [x] [code_fix] Extend `rig entity query` to support `relation_type`/`from`/`to` relation filters.
