---
capabilities:
  - cap.core.agent-realtime-observability
---
# agent-realtime-observability Specification

## Purpose
定义 Agent 节点 Stdout Event Bus、SSE 推送到 Web Console、Web Console 实时展示、历史输出持久化等能力。
## Requirements
### Requirement: Agent 节点 Stdout Event Bus
Executor 执行 agent 节点时，SHALL 将 subprocess 的 stdout 逐行读取并发送到 event bus。Event bus SHALL 支持订阅者实时接收事件。

#### Scenario: Stdout 逐行发送到 event bus
- **WHEN** agent 节点的 pi subprocess 输出一行文本
- **THEN** executor SHALL 立即读取该行并发送到 event bus，事件类型为 `node.output`

### Requirement: SSE 推送到 Web Console
BFF SHALL 订阅 event bus 的 `node.output` 事件，通过 SSE 推送到浏览器。

#### Scenario: SSE 推送 node 输出
- **WHEN** event bus 收到 `node.output` 事件
- **THEN** BFF SHALL 通过 SSE 推送该事件到订阅该 node 的浏览器

### Requirement: Web Console 实时展示
Web Console SHALL 提供 node 运行详情页面，实时展示 agent 节点的 stdout 输出。

#### Scenario: 实时展示 stdout
- **WHEN** 用户在 Web Console 打开 agent 节点的运行详情页
- **THEN** 页面 SHALL 通过 SSE 接收并实时展示该节点的 stdout 输出

### Requirement: 历史输出持久化
Agent 节点的 stdout 输出 SHALL 持久化到数据库，支持历史查询。

#### Scenario: 历史输出可查
- **WHEN** 用户查询已完成的 agent 节点输出
- **THEN** 系统 SHALL 从数据库返回该节点的完整 stdout 历史

### Requirement: 输出流式传输
Agent 节点的实时输出 SHALL 支持流式传输，不等待节点执行完成。

#### Scenario: 执行中即可查看输出
- **WHEN** agent 节点正在执行，用户打开运行详情页
- **THEN** 页面 SHALL 立即开始接收并展示已输出的内容，并持续接收新输出
