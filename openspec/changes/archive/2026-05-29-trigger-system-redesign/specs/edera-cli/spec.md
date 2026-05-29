## ADDED Requirements

### Requirement: trigger emit 子命令

`edera` CLI SHALL 新增 `trigger` 子命令组，包含 `emit` 子命令用于外部事件注入。

#### Scenario: edera trigger emit 命令

- **WHEN** 用户执行 `edera trigger emit "event:website-updated" --payload-json '{"url":"https://..."}'`
- **THEN** CLI 通过 mTLS 连接 edera-server，调用 `PipelineService.Emit` 注入事件

#### Scenario: edera trigger emit clear 事件

- **WHEN** 用户执行 `edera trigger emit "clear:event:market-open"`
- **THEN** CLI 调用 `PipelineService.Emit` 复位 bit
