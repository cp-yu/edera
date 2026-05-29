## Context

当前 Edera 的调度系统存在两条互相独立的路径：

1. `pipeline.py` 中的 APScheduler 为每个 DAG 注册全局 `interval` job（`system.schedule_minutes`，默认 30 分钟），所有 DAG 共享同一间隔
2. `trigger.py` 中的 TriggerExecutor 实现了 FreeRTOS 风格事件组，但无人调用 `emit()`——是死代码

Web Console 仅有手动"运行"按钮（`useRunDag` → `DagService.Trigger`），无法配置定时或事件触发。Trigger Entity 虽有 schema 定义（`wait_for: {mode, events}`），但表达力不足且无 UI 入口。

已有基础设施可复用：
- `EventBus`（`events.py`）：进程内 pub/sub，已用于 `dag.status` / `node.stdout`
- `HotReloader`（`hot_reload.py`）：`watchfiles.awatch` 监听 config 目录变更
- `EntityService` gRPC CRUD：可在写操作后挂 emit hook
- `edera` CLI：mTLS 认证的 gRPC 客户端

## Goals / Non-Goals

**Goals:**
- TriggerExecutor 成为唯一调度入口，废弃 APScheduler
- 支持自由布尔表达式（AND/OR/括号）描述触发条件
- EventGroup bit 状态持久化到 DB，重启恢复
- 提供 `PipelineService.Emit` RPC 作为唯一事件注入入口
- 在 Workbench Inspector 中提供 Trigger 配置 UI（表达式编辑 + 闹钟/事件 picker）
- Node Type 声明 `emits` 字段，DAG Runner 自动评估条件并 emit

**Non-Goals:**
- 不实现分布式调度（多实例竞争）
- 不实现 catch-up（错过的 cron tick 不补跑）
- 不实现嵌套 trigger（trigger fire 另一个 trigger 的 wait_for 不做特殊处理，走正常 emit 路径）
- 不实现 payload 聚合（EventGroup 只管 bit，payload 存 emit 记录，target 按需查）
- 不实现 interval 格式（只支持 cron）

## Decisions

### D1: 废弃 APScheduler，TriggerExecutor 统一调度

**选择**: 删除 `pipeline.py` 中 APScheduler interval 注册逻辑，所有调度走 TriggerExecutor

**替代方案**: 两者并存（APScheduler 兜底 + TriggerExecutor 高级配置）

**理由**: interval 是全局 30min 一刀切，不支持 per-DAG 差异化；TriggerExecutor 能力严格超集；两条路径并存让用户困惑

### D2: wait_for 改为自由布尔表达式字符串

**选择**: `wait_for: 'cron:"0 9 * * *" AND (event:market-open OR event:breaking-news)'`

**替代方案 A**: 保持 `{mode, events}` 结构化 schema
**替代方案 B**: 两层嵌套（外 AND，内 OR 子组）

**理由**: 用户明确要求直接写表达式而非表单；表达力完整；UI 提供 picker 辅助生成 token 插入表达式即可

### D3: cron token 用引号包裹

**选择**: `cron:"0 9 * * *"` — cron 字段含空格，引号消歧义

**替代方案**: 上下文敏感词法器（遇 `cron:` 后吞 5 字段）

**理由**: 引号是通用语义，解析器简单，未来 `event:"name with spaces"` 也可复用

### D4: 纯 FreeRTOS 语义 + 持久化

**选择**: bit 持久化到 DB，永久保留直到被 consume（trigger fire）或 clear（`clear:` emit）

**替代方案**: bit 有 TTL 自动过期

**理由**: 用户选择 FreeRTOS 原始语义；跨日/跨重启状态由用户通过 `clear:` 事件显式管理

### D5: fire 后自动 consume 表达式中已置位 bit

**选择**: trigger fire 后清除表达式中所有当前已置位的 bit

**理由**: 防止同一 trigger 反复 fire；和 FreeRTOS `xClearOnExit` 一致

### D6: 共享 bit first-wins

**选择**: 多 trigger 监听同一 bit 时，先匹配的 consume 掉 bit，后续 trigger 不触发

**替代方案**: 每个 trigger 独立持有 bit 副本

**理由**: 和 FreeRTOS 一致；需要广播时用前缀派生事件

### D7: manual:* 保留前缀直接 fire

**选择**: `emit("manual:dag:default")` 由 TriggerExecutor 识别保留前缀后直接 fire，不需要 trigger entity

**替代方案**: 为每个 DAG/Node 创建隐式 system trigger entity

**理由**: manual 是 fire 入口的形态，不是规则；避免虚拟 entity 概念污染

### D8: Emit 携带可选 payload，存 emit 记录表

**选择**: EventGroup 只管 bit；payload 存 `emit_records` 表；target 通过 runtime context 按需查

**替代方案**: payload 流经 trigger 传递给 target

**理由**: FreeRTOS event group 不传数据；避免 AND 场景下 payload 合并/冲突

### D9: emit 深度计数器防循环

**选择**: 每次 emit 带 depth 参数，超过 `max_trigger_depth`（默认 3）拒绝并告警

**替代方案**: trigger 级 cooldown / 同 cycle 事件去重

**理由**: 和 `max_dag_depth` 同一思路；简单可靠

### D10: Trigger target 支持 clear:event:*

**选择**: trigger fire 后的动作不限于运行 DAG/Node，也可以是复位某个 bit

**理由**: 统一 emit 机制；用户可配"每天 16:00 清除 market-open bit"

### D11: Node Type 声明 emits，instance 可覆盖

**选择**: `emits: [{event: "event:negative-news", condition: "output.sentiment == 'negative'"}]` 在 Node Type 上声明

**替代方案 A**: 条件配在 node instance 上
**替代方案 B**: 条件配在 trigger entity 上（拉模型）

**理由**: 和半封闭词汇表一致——node type 声明能力，UI 从声明中枚举；和 manifest 声明模式一致

### D12: Inspector Triggers tab

**选择**: 无选中时显示 DAG 级 trigger（`target = dag:{name}`），选中 node 时显示 node 级 trigger（`target = node:{id}`）

**理由**: 复用已有 Inspector tab 切换模式；"选中目标 → 看属性"是 workbench 心智模型

## Risks / Trade-offs

- **[表达式解析器复杂度]** → 自实现轻量递归下降解析器，仅支持 AND/OR/括号/引号字面量，不引入通用 parser 库
- **[APScheduler 移除后无兜底]** → 迁移时为现有 DAG 自动生成 `cron:"*/30 * * * *"` trigger entity
- **[first-wins 反直觉]** → 文档明确说明；UI 中如果检测到多 trigger 监听同一 bit 给出警告
- **[EventGroup 持久化性能]** → bit 数量有限（和 trigger 数量线性相关），DB 写入频率低（仅 emit 时）
- **[cron 精度]** → 内置 cron emitter 以 1 分钟为 tick 间隔扫描，精度为分钟级
- **[表达式求值时机]** → 每次 bit 变化时，仅重新求值引用了该 bit 的 trigger（建立 bit→trigger 反向索引）

## Migration Plan

1. 为现有每个 DAG 生成 trigger entity：`wait_for: 'cron:"*/30 * * * *"'`，`target: "dag:{name}"`
2. 移除 `system.toml` 中 `schedule_minutes` 字段（或标注 deprecated，下个版本删除）
3. 前端 `useRunDag` mutation 改为调用 `PipelineService.Emit("manual:dag:{name}")`
4. 数据库 migration 新增 `event_group_bits` 和 `emit_records` 表
