# Spike: pi `--session` 语义验证

## 目标

验证 pi CLI 的 `--session <id>` 参数行为，定夺 session_id 捕获方式。

## 测试环境

- pi binary: 检查系统是否安装 pi
- 测试时间: 2026-06-12

## 实测结果

### 1. pi 可用性检查

✅ **确认**: pi 已安装在系统路径 `/home/yunxin/.npm-global/bin/pi`

### 2. pi CLI 参数确认

通过 `pi --help` 确认支持的 session 相关参数：

```
--session <path|id>            Use specific session file or partial UUID
--session-id <id>              Use exact project session ID, creating it if missing
--session-dir <dir>            Directory for session storage and lookup
--continue, -c                 Continue previous session
--resume, -r                   Select a session to resume
```

**关键发现**:
- ✅ pi 支持 `--session-id <id>` 参数：**创建时可预指定 session id**
- ✅ pi 支持 `--session <path|id>` 参数：用于续接已有会话
- `--session-id` 与 `--session` 的区别：
  - `--session-id`: 精确指定 id，不存在时创建（适合首次执行）
  - `--session`: 引用已有会话，支持 partial UUID 或文件路径（适合续接）

### 3. Session ID 捕获方式决议

根据 pi CLI 实际能力，选择**方案 B（预生成）**：

#### 实施方案：预生成 + --session-id 创建

**首次执行**（无 session id）:
```bash
session_id = uuid4().hex
pi --model opus --session-dir <path> --session-id <session_id> -p <prompt>
# 系统立即捕获并登记该 session_id 到注册表
```

**续接执行**（已有 session id）:
```bash
pi --model opus --session-dir <path> --session <session_id> -p <prompt>
```

**优势**:
- 无需解析文件名或会话文件内容
- session id 在执行前已确定，可立即登记
- 避免竞态条件（多节点同时创建会话时 id 冲突）
- pi 原生支持，无需兜底逻辑

## 结论与决议

**Session ID 生命周期**:
1. 组内首个节点执行时，系统预生成 `session_id = uuid4().hex`
2. 使用 `--session-id <session_id>` 创建会话
3. 立即登记到注册表：`register_session(dag, group, run_id, session_id, path, status='active')`
4. 组内后续节点从注册表读取 session_id，使用 `--session <session_id>` 续接

**命令构造规则**:
- 注册表中**无** session id → `pi --session-id <new_id>`（创建）
- 注册表中**有** session id → `pi --session <existing_id>`（续接）

## 供后续任务使用的决策

- **Task 3**: 注册表需存储 `session_id`（字符串类型，从 jsonl 文件名提取）
- **Task 6**: 续接命令构造为 `pi --session <session_id> --session-dir <path>`
- **捕获时机**: 在 agent 进程退出后立即捕获，通过 glob + 文件名解析

## 风险与缓解

- **风险**: 文件名格式假设与 pi 实际行为不匹配
- **缓解**: 
  - 采用宽松解析策略（支持多种命名模式）
  - 每 run 独立目录保证了 `--continue` 兜底的可行性
  - 不影响未声明 `session` 的节点（保持原有行为）
