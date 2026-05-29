## 1. Actions

- [x] A1 实现布尔表达式解析器（词法 + 递归下降），支持 AND/OR/括号/cron 引号 token
- [x] A2 实现 EventGroup 持久化层：DB schema（event_group_bits 表）、set/clear/consume 操作、启动恢复
- [x] A3 实现 bit→trigger 反向索引，bit 变化时仅求值受影响 trigger
- [x] A4 实现 cron emitter：扫描 trigger 中 cron token、注册内部定时任务、分钟级 tick emit
- [x] A5 新增 PipelineService.Emit RPC：proto 定义 EmitRequest、server handler、grpc_client 方法
- [x] A6 新增 emit_records 表与写入逻辑，记录每次 emit 的事件名/payload/时间/来源/深度
- [x] A7 实现 emit 深度计数器：depth 参数传递、超阈值拒绝、告警日志
- [x] A8 实现 manual:* 保留前缀直接 fire 逻辑，绕过 wait_for 匹配
- [x] A9 实现 clear: 前缀语义（emit clear 复位 bit）与 trigger target clear:event:* 支持
- [x] A10 NodeConfigBase 增加 emits 字段（EmitDeclaration model）
- [x] A11 DAG Runner node 完成后评估 emits 条件并 emit，instance 级覆盖优先
- [x] A12 移除 pipeline.py 中 APScheduler interval 注册逻辑，start_run/run_now 改为 emit 包装
- [x] A13 HotReloader reload callback 中追加 emit("event:config-changed") 与 cron 重扫描
- [x] A14 EntityService Create/Update/Delete handler 中追加 emit("event:entity-changed:{ref}")
- [x] A15 edera CLI 新增 trigger emit 子命令，调用 PipelineService.Emit
- [x] A16 Trigger Entity schema 改造：wait_for 改为 string、新增 enabled 字段、config/schemas/trigger.yaml 更新
- [x] A17 Trigger enabled 字段逻辑：disabled 跳过求值、一次性 trigger fire 后 auto-disable
- [x] A18 Workbench Inspector 增加 Triggers tab：DAG 级/node 级列表、CRUD 操作
- [x] A19 实现表达式文本编辑器组件（语法校验 + 错误提示）
- [x] A20 实现闹钟式 cron picker（时间选择 + 重复规则 + 高级 cron 直写）
- [x] A21 实现事件源 picker（从 Node Type emits + 系统事件枚举 + 手写自定义）
- [x] A22 前端 useRunDag mutation 改为调用 PipelineService.Emit("manual:dag:{name}")
- [x] A23 DB migration：新增 event_group_bits 和 emit_records 表
- [x] A24 为现有 DAG 生成迁移 trigger entity（cron:"*/30 * * * *"）

## 2. Checks

- [x] C1 验证表达式解析器正确解析 AND/OR/括号/cron 引号
  - Covers: A1
  - Verifies: `specs/trigger-expression-language/spec.md` / Requirement "布尔表达式语法" / Scenario "括号嵌套表达式"
  - Command: `pytest tests/core/unit/test_trigger_expression.py -v`
  - Expect: 所有表达式解析测试通过，含 AND/OR/括号/单 token 场景

- [x] C2 验证非法 cron 格式被拒绝
  - Covers: A1
  - Verifies: `specs/trigger-expression-language/spec.md` / Requirement "cron token 引号语义" / Scenario "非法 cron 格式拒绝"
  - Command: `pytest tests/core/unit/test_trigger_expression.py -k "invalid_cron"`
  - Expect: 无引号 cron 解析报语法错误

- [x] C3 验证 EventGroup bit 持久化与重启恢复
  - Covers: A2, A23
  - Verifies: `specs/event-group-engine/spec.md` / Requirement "Bit 持久化存储" / Scenario "启动恢复 bit 状态"
  - Command: `pytest tests/core/unit/test_event_group.py -k "persist_and_restore"`
  - Expect: 写入 bit 后重建 EventGroup 实例可恢复状态

- [x] C4 验证 set/clear/consume 语义
  - Covers: A2, A9
  - Verifies: `specs/event-group-engine/spec.md` / Requirement "bit 置位语义" / Scenario "复位 bit"
  - Command: `pytest tests/core/unit/test_event_group.py -k "set_clear_consume"`
  - Expect: set 置位、clear 复位、consume 清除已置位 bit

- [x] C5 验证 fire 后自动 consume 表达式中已置位 bit
  - Covers: A2, A3
  - Verifies: `specs/event-group-engine/spec.md` / Requirement "fire 后自动 consume" / Scenario "AND 表达式 consume"
  - Command: `pytest tests/core/unit/test_event_group.py -k "auto_consume"`
  - Expect: fire 后表达式中已置位 bit 被清除

- [x] C6 验证 bit→trigger 反向索引仅求值受影响 trigger
  - Covers: A3
  - Verifies: `specs/trigger-expression-language/spec.md` / Requirement "表达式求值时机" / Scenario "无关 bit 变化不触发求值"
  - Command: `pytest tests/core/unit/test_trigger_expression.py -k "reverse_index"`
  - Expect: 无关 bit 变化不触发其他 trigger 求值

- [x] C7 验证 cron emitter 按时 emit
  - Covers: A4
  - Verifies: `specs/cron-emitter/spec.md` / Requirement "cron 时钟 emitter 内置" / Scenario "cron tick 自动 emit"
  - Command: `pytest tests/core/unit/test_cron_emitter.py -k "tick_emit"`
  - Expect: 模拟时钟到达 cron 时间点后 emit 被调用

- [x] C8 验证错过 tick 不补跑
  - Covers: A4
  - Verifies: `specs/cron-emitter/spec.md` / Requirement "错过 tick 不补跑" / Scenario "停机期间错过 tick"
  - Command: `pytest tests/core/unit/test_cron_emitter.py -k "missed_tick_skip"`
  - Expect: 启动后不 emit 错过的 tick

- [x] C9 验证 PipelineService.Emit RPC 注入事件
  - Covers: A5, A6
  - Verifies: `specs/trigger-emit-rpc/spec.md` / Requirement "PipelineService.Emit RPC" / Scenario "注入普通事件"
  - Command: `pytest tests/core/test_pipeline_service.py -k "emit_rpc"`
  - Expect: 调用 Emit RPC 后 bit 置位且 emit_records 有记录

- [x] C10 验证 emit 深度超限拒绝
  - Covers: A7
  - Verifies: `specs/trigger-loop-guard/spec.md` / Requirement "emit 深度计数" / Scenario "超过深度阈值拒绝"
  - Command: `pytest tests/core/unit/test_trigger_loop_guard.py`
  - Expect: depth >= max_trigger_depth 时 emit 被拒绝

- [x] C11 验证 manual:dag 直接 fire
  - Covers: A8
  - Verifies: `specs/manual-trigger-prefix/spec.md` / Requirement "manual 前缀直接 fire" / Scenario "manual:dag 直接 fire DAG"
  - Command: `pytest tests/core/unit/test_trigger_system.py -k "manual_prefix"`
  - Expect: emit("manual:dag:default") 直接启动 DAG 运行

- [x] C12 验证 manual 前缀不置位 bit
  - Covers: A8
  - Verifies: `specs/manual-trigger-prefix/spec.md` / Requirement "manual 前缀直接 fire" / Scenario "manual 事件不置位 bit"
  - Command: `pytest tests/core/unit/test_trigger_system.py -k "manual_no_bit"`
  - Expect: emit manual 后 event_group_bits 无新记录

- [x] C13 验证 NodeConfigBase emits 字段反序列化
  - Covers: A10
  - Verifies: `specs/node-type-discriminated-union/spec.md` / Requirement "NodeConfig Discriminated Union 模型" / Scenario "function node 声明 emits"
  - Command: `pytest tests/core/unit/test_entity_types.py -k "emits_field"`
  - Expect: 含 emits 字段的 node type yaml 反序列化成功

- [x] C14 验证 DAG Runner 评估 emits 条件并 emit
  - Covers: A11
  - Verifies: `specs/node-emits-declaration/spec.md` / Requirement "DAG Runner 评估 emits 条件" / Scenario "条件满足触发 emit"
  - Command: `pytest tests/core/integration/test_per_dag.py -k "node_emits"`
  - Expect: node 输出满足 condition 后 emit 被调用

- [x] C15 验证 APScheduler 移除后启动不注册 interval job
  - Covers: A12
  - Verifies: `specs/pipeline-control/spec.md` / Requirement "管道控制能力" / Scenario "启动时不注册 interval job"
  - Command: `pytest tests/core/test_pipeline_service.py -k "no_apscheduler"`
  - Expect: 启动后无 APScheduler job 注册

- [x] C16 验证 HotReloader 变更后 emit event:config-changed
  - Covers: A13
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "全量配置热加载" / Scenario "配置变更 emit 事件"
  - Command: `pytest tests/core/unit/test_hot_reload.py -k "emit_config_changed"`
  - Expect: reload callback 执行后 event:config-changed bit 置位

- [x] C17 验证 Entity 写操作后 emit entity-changed
  - Covers: A14
  - Verifies: `specs/entity-instance-crud-api/spec.md` / Requirement "Entity 写操作 emit 事件" / Scenario "Entity 创建 emit"
  - Command: `pytest tests/core/unit/test_entity_crud.py -k "emit_entity_changed"`
  - Expect: Create/Update/Delete 后对应 event:entity-changed:{ref} bit 置位

- [x] C18 验证 edera trigger emit CLI 命令
  - Covers: A15
  - Verifies: `specs/edera-cli/spec.md` / Requirement "edera CLI 子命令集合" / Scenario "edera trigger emit 命令"
  - Command: `pytest tests/core/unit/test_cli.py -k "trigger_emit"`
  - Expect: CLI 调用成功注入事件

- [x] C19 验证 trigger entity schema 新字段
  - Covers: A16
  - Verifies: `specs/trigger-system/spec.md` / Requirement "Trigger Entity 定义" / Scenario "定义 cron 触发器"
  - Evidence: `config/schemas/trigger.yaml` 内容
  - Expect: schema 包含 wait_for(string)、target(string)、enabled(boolean) 字段

- [x] C20 验证 disabled trigger 不触发
  - Covers: A17
  - Verifies: `specs/trigger-system/spec.md` / Requirement "Trigger enabled 字段" / Scenario "disabled trigger 不触发"
  - Command: `pytest tests/core/unit/test_trigger_system.py -k "disabled_skip"`
  - Expect: enabled=false 的 trigger 即使表达式满足也不 fire

- [x] C21 验证一次性 trigger fire 后 auto-disable
  - Covers: A17
  - Verifies: `specs/trigger-system/spec.md` / Requirement "Trigger enabled 字段" / Scenario "一次性 trigger 自动 disable"
  - Command: `pytest tests/core/unit/test_trigger_system.py -k "oneshot_auto_disable"`
  - Expect: 精确日期 cron trigger fire 后 enabled 变为 false

- [x] C22 验证 Workbench Inspector Triggers tab 渲染
  - Covers: A18, A19
  - Verifies: `specs/trigger-workbench-inspector/spec.md` / Requirement "Inspector Triggers tab" / Scenario "无选中显示 DAG 级 trigger"
  - Command: `npx playwright test tests/workbench-triggers.spec.ts`
  - Expect: 无选中时 Triggers tab 列出 DAG 级 trigger

- [x] C23 验证闹钟 picker 生成 cron token
  - Covers: A20
  - Verifies: `specs/trigger-workbench-inspector/spec.md` / Requirement "闹钟式 cron 片段生成器" / Scenario "闹钟生成每日 cron"
  - Command: `npx playwright test tests/workbench-triggers.spec.ts -g "alarm_picker"`
  - Expect: 选择每天 09:00 后插入 cron:"0 9 * * *"

- [x] C24 验证事件 picker 枚举 Node Type emits
  - Covers: A21
  - Verifies: `specs/trigger-workbench-inspector/spec.md` / Requirement "事件源片段生成器" / Scenario "从 Node Type emits 选择事件"
  - Command: `npx playwright test tests/workbench-triggers.spec.ts -g "event_picker"`
  - Expect: picker 列出 node type 声明的 emits 事件

- [x] C25 验证前端手动运行走 emit 路径
  - Covers: A22
  - Verifies: `specs/trigger-emit-rpc/spec.md` / Requirement "emit 路径统一" / Scenario "手动运行 DAG 走 emit"
  - Evidence: `apps/web-console/src/api/mutations.ts` 中 useRunDag 实现
  - Expect: mutation 调用 /api/pipeline/emit 而非 /api/pipeline/dag/{name}/run

- [x] C26 验证 DB migration 成功
  - Covers: A23
  - Verifies: `specs/event-group-engine/spec.md` / Requirement "Bit 持久化存储" / Scenario "bit 写操作落盘"
  - Command: `alembic upgrade head && python -c "from sqlalchemy import inspect; ..."`
  - Expect: event_group_bits 和 emit_records 表存在

- [x] C27 验证迁移 trigger entity 生成
  - Covers: A24
  - Verifies: `specs/pipeline-control/spec.md` / Requirement "管道控制能力" / Scenario "手动运行走 emit 路径"
  - Evidence: `config/triggers/` 目录内容
  - Expect: 每个现有 DAG 有对应 trigger entity 文件，wait_for 为 cron:"*/30 * * * *"

## Remediation

- [x] [code_fix] Wire production node trigger targets through `PipelineController` so `target = node:<id>` and `manual:node:<id>` do not raise unsupported target.
- [x] [code_fix] Reject `manual:*` in backend trigger `wait_for` validation and remove manual events from the Workbench wait_for picker.
- [x] [code_fix] Route legacy `DagService.Trigger` through `emit("manual:dag:<name>")` instead of `start_run("manual", ...)`.
- [x] [code_fix] Complete cron picker rules for one-time date cron and custom weekday selection.
- [x] [code_fix] Route legacy `PipelineService.Run` and `/api/pipeline/run` through `emit("manual:dag:default")` instead of `start_run("manual")`.
