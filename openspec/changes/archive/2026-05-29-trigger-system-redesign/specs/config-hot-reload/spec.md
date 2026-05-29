## ADDED Requirements

### Requirement: 配置变更 emit 事件

系统 SHALL 在配置文件变更时自动 emit `event:config-changed` 事件到 TriggerExecutor。

#### Scenario: 配置变更 emit 事件

- **WHEN** `config/` 目录下的文件被修改，HotReloader 检测到变更并执行 reload
- **THEN** 系统在 reload callback 中调用 `emit("event:config-changed")`

#### Scenario: trigger entity 变更触发 cron 重扫描

- **WHEN** `config/triggers/` 目录下的文件变更
- **THEN** HotReloader reload 后，cron emitter 重新扫描所有 trigger entity 的 cron token 并更新注册表
