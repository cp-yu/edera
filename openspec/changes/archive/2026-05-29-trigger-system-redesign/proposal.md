## Why

当前 Web Console 缺少 DAG 触发源的配置入口，用户无法在控制台配置定时、事件触发，只能手动跑 DAG。同时后端存在两套互相打架的调度路径：`pipeline.py` 里的 APScheduler 给所有 DAG 套用全局 30 分钟 interval，`trigger.py` 里的 TriggerExecutor 是孤立的死代码。spec 里定义的 `wait_for: {mode, events}` schema 表达力不足，无法表达"9 点 AND（开市 OR 重大新闻）"这类复合条件。

## What Changes

- **BREAKING** 废弃 `pipeline.py` 里基于 APScheduler 的全局 interval 调度，改由 TriggerExecutor 唯一负责调度
- **BREAKING** Trigger Entity 的 `wait_for` 字段从 `{mode, events}` 结构改为自由布尔表达式字符串（支持 AND / OR / 括号），cron 条件用引号包裹如 `cron:"0 9 * * *"`
- **BREAKING** `DagService.Trigger` RPC 统一到 emit 机制；`manual:dag:{name}` / `manual:node:{id}` 为保留前缀，emit 时直接 fire 不走 wait_for 匹配
- 新增 `PipelineService.Emit(EmitRequest)` RPC 作为唯一事件注入入口，携带可选 payload
- 新增 cron emitter 内置在 edera-server，按 trigger entity 中声明的 cron 时间点自动 emit `cron:"..."` 事件；错过的 tick 直接跳过不补
- 新增 EventGroup 持久化层：bit 状态落到 DB，重启恢复；fire 后自动 consume 表达式中已置位的 bit
- 新增 `clear:` 前缀语义：`emit("clear:event:x")` 复位 bit；trigger 的 `target` 字段也支持 `clear:event:x` 表达"fire 后清除某 bit"
- 新增 emit 深度计数器，超过 `system.max_trigger_depth`（默认 3）拒绝并告警
- 新增 trigger entity 的 `enabled: bool` 字段，disabled 时跳过求值；fire 后对一次性 trigger（精确日期 cron）自动 disable
- Node Type schema 增加 `emits: [{event, condition}]` 声明，支持 instance 级覆盖；DAG Runner 在 node 完成后评估条件并 emit
- HotReloader 文件变更时自动 emit `event:config-changed`；EntityService 的 Create/Update/Delete 自动 emit `event:entity-changed:{ref}` 用于自举场景
- 新增 `edera trigger emit <event> [--payload-json ...]` CLI 命令，作为外部事件注入入口（mTLS 认证）
- Workbench Inspector 增加 Triggers tab：无选中时显示当前 DAG 级 trigger 列表（`target = dag:{name}`），选中 node 时显示 node 级 trigger 列表（`target = node:{id}`）
- Trigger 编辑器以表达式文本输入为主，提供"插入定时"闹钟式 picker 和"插入事件"事件源 picker 作为 token 片段生成器

## Capabilities

### New Capabilities

- `trigger-expression-language`: 触发器布尔表达式语言定义、词法语法、求值与 cron token 引号语义
- `event-group-engine`: FreeRTOS 风格事件组持久化引擎，覆盖 set/clear/consume bit 状态、DB 存储与重启恢复
- `cron-emitter`: 时钟 emitter 服务，按 trigger 表达式中声明的 cron 时间点 emit `cron:"..."` 事件，错过即跳过
- `trigger-emit-rpc`: `PipelineService.Emit` RPC 与 `edera trigger emit` CLI 命令，作为唯一事件注入入口
- `trigger-loop-guard`: emit 深度计数器与可配置阈值，循环触发防护机制
- `manual-trigger-prefix`: `manual:dag:*` / `manual:node:*` 保留前缀的直接 fire 语义
- `trigger-workbench-inspector`: Workbench Inspector Triggers tab，覆盖 DAG 级与 node 级 trigger 列表、表达式编辑器、闹钟 picker 与事件 picker
- `node-emits-declaration`: Node Type 的 `emits` 字段声明（含 instance 级覆盖）与 DAG Runner 的条件求值/emit 集成

### Modified Capabilities

- `trigger-system`: `wait_for` 改为自由布尔表达式；新增 `enabled` 字段；新增 `clear:` target 语义；fire 后自动 consume 已置位 bit；多 trigger 共享 bit first-wins
- `pipeline-control`: 删除 APScheduler 全局 interval 调度逻辑；统一由 TriggerExecutor 调度；`DagService.Trigger` 转为 emit 包装
- `config-hot-reload`: HotReloader 文件变更回调中追加 emit `event:config-changed`
- `entity-instance-crud-api`: Entity 写操作完成后 emit `event:entity-changed:{ref}`
- `edera-cli`: 新增 `edera trigger emit` 子命令
- `node-type-discriminated-union`: NodeConfig schema 增加 `emits` 字段
- `dag-workbench-ui`: Inspector 增加 Triggers tab

## Impact

- **代码**
  - `packages/core/src/edera_core/pipeline.py` — 移除 APScheduler interval 注册；改造 `start_run`/`run_now` 为 emit 包装
  - `packages/core/src/edera_core/trigger.py` — 重写 EventGroup 持久化、表达式求值、深度计数；新增 cron emitter 子模块
  - `packages/core/src/edera_core/hot_reload.py` — reload callback 调 `emit("event:config-changed")`
  - `packages/core/src/edera_core/storage/entities.py` — Entity 写操作后 emit `event:entity-changed:{ref}`
  - `packages/core/src/edera_core/config/schema.py` — `NodeConfigBase` 增加 `emits` 字段；trigger schema 调整
  - `packages/core/src/edera_core/dag/runner.py` — node 完成后评估 emits 条件
  - `packages/core/src/edera_core/server.py`、`pipeline_service.py`、`grpc_client.py` — 新增 `Emit` RPC 与 `dag_trigger` 行为重定向
  - `packages/core/src/edera_core/cli.py` — 新增 `trigger emit` 子命令
  - `apps/web-console/src/features/workbench/components/Inspector.tsx` — 新增 Triggers tab、表达式编辑器、闹钟 picker、事件 picker
  - `apps/web-console/src/api/queries.ts`、`mutations.ts`、`types.ts` — Trigger CRUD/Emit Hook 与类型
- **协议**
  - `proto/edera.proto` — 新增 `EmitRequest` message 与 `PipelineService.Emit` RPC
- **配置**
  - `config/schemas/trigger.yaml` — 重写 schema 适配新 `wait_for` 表达式与 `enabled` 字段
  - `config/system.toml` — 新增 `max_trigger_depth` 字段；移除 `schedule_minutes`（或标注废弃）
- **数据库**
  - 新增 `event_group_bits` 表持久化 bit 状态
  - 新增 `emit_records` 表存储 emit 历史与 payload
- **测试**
  - 新增 EventGroup 持久化、表达式求值、cron emitter、深度计数、循环防护单元测试
  - 新增 Web Console Triggers tab 交互测试
- **依赖**
  - 新增 `croniter` 或类似库用于 cron 表达式解析与下次触发时间计算
  - 新增表达式解析器（自实现或基于 `pyparsing`）
