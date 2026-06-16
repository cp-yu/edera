---
capabilities:
  - cap.operations.node-executor
---

# node-executor Delta

## MODIFIED Requirements

### Requirement: Node 执行隔离

Node executor MUST 保证每个 Node 实例独立执行，Node 之间无直接通信。Node 不感知自身在 DAG 中的位置。当 DAG run 启用 os-sandbox 时，agent 节点与 handler 节点 MUST 在沙箱子进程边界内执行：agent 节点不再二次包裹 `srt`（复用 run 级沙箱边界），handler 节点以同进程方式加载但仍受沙箱策略约束。

#### Scenario: 并发 Node 隔离

- **WHEN** 同一 Skill 的两个 Node 实例并发执行
- **THEN** 两个实例互不影响，各自独立完成执行并返回结果

#### Scenario: 沙箱内 handler 节点受策略约束

- **WHEN** DAG run 启用 os-sandbox 且执行 handler 节点
- **THEN** handler 节点 MUST 在沙箱子进程内加载执行，其文件系统与网络访问 MUST 受 os-sandbox 策略约束

#### Scenario: 沙箱内 agent 节点不二次包裹

- **WHEN** DAG run 启用 os-sandbox 且执行 agent 节点
- **THEN** agent 节点的子进程 MUST 直接由沙箱子进程拉起，MUST NOT 再次嵌套 `srt` 沙箱层
