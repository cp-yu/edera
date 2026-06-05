# Codex Exec Agent Integration Guide

面向 agent 程序化调用 `codex exec` 的操作手册。

## 1. 基本调用

```bash
codex exec [OPTIONS] "prompt"
# 简写
codex e [OPTIONS] "prompt"
# 从 stdin 读取 prompt
echo "prompt" | codex exec -
```

## 2. 认证

```bash
# 方式一：环境变量（推荐自动化场景，仅 codex exec 支持）
CODEX_API_KEY=<key> codex exec "task"

# 方式二：复用已保存的 CLI 认证（默认行为）
codex exec "task"
```

## 3. 必要参数

长任务必须指定 sandbox 权限，否则写操作会被拒绝：

```bash
--sandbox workspace-write    # 允许写工作区文件
--sandbox danger-full-access # 完全访问，仅在隔离环境中使用
```

默认 sandbox 为 read-only。

## 4. 输出模式

### 4.1 默认模式

- **stderr**：实时 progress 流
- **stdout**：任务完成后输出最终 agent message

### 4.2 `--json` 模式（推荐）

实时流式输出 JSONL 事件流：

```bash
codex exec --json "task"
```

事件类型：
- `thread.started` — 会话开始，包含 `thread_id`
- `turn.started` / `turn.completed` — 一轮对话
- `item.started` / `item.completed` — 具体操作（command_execution, agent_message, file change 等）
- `turn.failed` / `error` — 失败

解析最终 message：
```python
for line in stdout.strip().splitlines():
    event = json.loads(line)
    if event.get("type") == "item.completed":
        item = event.get("item", {})
        if item.get("type") == "agent_message":
            final_text = item.get("text")
```

### 4.3 输出到文件

```bash
# 最终 message 写入文件
codex exec -o result.txt "task"

# 结构化输出（JSON Schema）
codex exec --output-schema schema.json -o result.json "task"
```

## 5. 会话恢复（Resume）

串行任务的核心能力。每条结果出来后，可以基于上一轮结果继续。

```bash
# 恢复最近一次会话（同目录）
codex exec resume --last "根据上次结果调整：..."

# 恢复指定会话
codex exec resume <thread_id> "继续任务：..."

# 跨目录搜索最近会话
codex exec resume --last --all "继续：..."
```

`thread_id` 从 `--json` 输出的 `thread.started` 事件获取。

## 6. Subagent

`codex exec` 支持在 prompt 中显式请求 spawn subagent 并行执行：

```bash
codex exec --sandbox workspace-write "Spawn one agent per point, wait for all:
1. Security review
2. Code quality
3. Test coverage"
```

约束：
- Subagent 继承父进程 sandbox 策略
- 非交互模式下需要审批的操作会直接失败，必须预设 `--sandbox` 权限
- 可在 `.codex/agents/*.toml` 定义自定义 subagent

## 7. 串行长任务工作流

```
┌─────────────────────────────────────────────┐
│ Task 1: codex exec --json --sandbox         │
│         workspace-write "任务1"              │
│         → 解析 JSONL 获取 thread_id + 结果   │
└──────────────────┬──────────────────────────┘
                   │ 审查结果，构造 follow-up prompt
┌──────────────────▼──────────────────────────┐
│ Task 2: codex exec resume --last            │
│         "基于上次结果调整：..."               │
│         → 解析 JSONL 获取结果                 │
└──────────────────┬──────────────────────────┘
                   │ 审查结果，构造 follow-up prompt
┌──────────────────▼──────────────────────────┐
│ Task 3: codex exec resume --last            │
│         "继续完善：..."                       │
│         → 最终输出                            │
└─────────────────────────────────────────────┘
```

## 8. 其他实用选项

| 选项 | 说明 |
|---|---|
| `--ephemeral` | 不持久化 session 文件到磁盘 |
| `--skip-git-repo-check` | 允许在非 Git 目录运行 |
| `--model, -m` | 覆盖模型，如 `-m gpt-5.4` |
| `-c key=value` | 内联覆盖配置，可重复 |
| `--ignore-user-config` | 不加载用户全局 config |
| `--cd, -C` | 指定工作目录 |

## 9. 不支持项

| 功能 | 状态 |
|---|---|
| `/goal` 等 slash commands | ❌ 仅交互式 TUI 模式 |
| 交互式审批 | ❌ 需审批的操作直接失败 |
| 实时 stdout 输出（非 --json） | ❌ 默认模式 stdout 要等任务完成 |

## 10. 完整调用模板

```bash
# Step 1: 初始任务
codex exec \
  --json \
  --sandbox workspace-write \
  --model gpt-5.4 \
  "具体任务描述" \
  2>progress.log >output.jsonl

# Step 2: 从 JSONL 提取 thread_id 和结果
thread_id=$(jq -r 'select(.type=="thread.started") | .thread_id' output.jsonl)
result=$(jq -r 'select(.type=="item.completed" and .item.type=="agent_message") | .item.text' output.jsonl | tail -1)

# Step 3: 基于结果 resume
codex exec \
  --json \
  --sandbox workspace-write \
  resume --last \
  "基于上次结果的调整指令" \
  2>progress2.log >output2.jsonl
```
