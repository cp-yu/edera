## ADDED Requirements

### Requirement: TriggerExecutor 统一调度

系统 SHALL 通过 TriggerExecutor 统一管理所有 DAG/Node 的调度。系统 MUST 不再使用 APScheduler 全局 interval 调度。

#### Scenario: 启动时不注册 interval job

- **WHEN** edera-server 启动
- **THEN** 系统不创建 APScheduler interval job；调度完全由 trigger entity + cron emitter 驱动

#### Scenario: 手动运行走 emit 路径

- **WHEN** 用户通过 API 或 CLI 手动运行 DAG
- **THEN** 系统调用 `emit("manual:dag:<name>")` 而非直接调用 `start_run()`

## REMOVED Requirements

### Requirement: Scheduler pause and resume
**Reason**: 被 TriggerExecutor + cron emitter 替代；全局 interval 不支持 per-DAG 差异化，trigger entity 的 enabled 字段替代 pause/resume
**Migration**: 为现有每个 DAG 生成 `cron:"*/30 * * * *"` trigger entity；暂停功能通过 trigger enabled=false 实现
