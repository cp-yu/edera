# trigger-emit-rpc Specification

## Purpose
此规约记录变更 trigger-system-redesign 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: PipelineService.Emit RPC

系统 SHALL 在 `PipelineService` 中提供 `Emit(EmitRequest) returns (JsonResponse)` RPC，作为唯一外部事件注入入口。`EmitRequest` MUST 包含 `event` 字段（事件名）和 `payload_json` 字段（可选 payload）。

#### Scenario: 注入普通事件

- **WHEN** 客户端调用 `PipelineService.Emit({event: "event:website-updated", payload_json: "{\"url\":\"https://...\"}"})`
- **THEN** 系统置位 `event:website-updated` bit，并将 payload 写入 emit 记录表

#### Scenario: 注入 clear 事件

- **WHEN** 客户端调用 `PipelineService.Emit({event: "clear:event:market-open"})`
- **THEN** 系统复位 `event:market-open` bit

#### Scenario: 注入 manual 事件

- **WHEN** 客户端调用 `PipelineService.Emit({event: "manual:dag:default"})`
- **THEN** 系统直接 fire `dag:default`，绕过 wait_for 匹配

### Requirement: emit 记录持久化

系统 SHALL 将每次 emit 调用记录到 `emit_records` 表，包含事件名、payload、调用时间、来源标识、深度。

#### Scenario: 记录 emit 历史

- **WHEN** 任意来源调用 emit
- **THEN** 系统在 `emit_records` 表插入一条记录

#### Scenario: target DAG 通过 runtime context 查询 payload

- **WHEN** trigger fire 后 DAG run 启动，DAG 内 source node 需要读取最近的 emit payload
- **THEN** node 通过 runtime context 查询 `emit_records` 中该事件的最近一条记录

### Requirement: edera trigger emit CLI 命令

`edera` CLI SHALL 提供 `trigger emit <event> [--payload-json <json>]` 子命令，作为外部事件注入入口。该命令 MUST 通过 mTLS 连接 edera-server 并调用 `PipelineService.Emit`。

#### Scenario: CLI 注入事件

- **WHEN** 用户在 shell 中执行 `edera trigger emit "event:website-updated" --payload-json '{"url":"https://..."}'`
- **THEN** CLI 通过 mTLS 调用 `PipelineService.Emit` 注入事件

#### Scenario: CLI 缺少证书拒绝

- **WHEN** 用户在未初始化客户端证书时执行 `edera trigger emit`
- **THEN** CLI 报错并提示先运行客户端初始化

### Requirement: emit 路径统一

系统 SHALL 让所有 DAG/Node 触发都经过 emit 路径，包括手动触发、定时触发、事件触发。

#### Scenario: 手动运行 DAG 走 emit

- **WHEN** 用户在 Web Console 点击"运行"按钮触发 `dag:default`
- **THEN** 系统调用 `emit("manual:dag:default", payload={inputs: ...})`

#### Scenario: cron emitter 走 emit

- **WHEN** cron tick 到达
- **THEN** cron emitter 调用 `emit("cron:\"...\"")`，与外部 emit 走同一路径

