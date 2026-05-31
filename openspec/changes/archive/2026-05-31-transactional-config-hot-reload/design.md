## Context

现有 `HotReloader` 已由 `edera-server` 生命周期管理，并在失败时隔离单次 reload。但 reload callback 当前没有提交新运行时状态，`DagController` 的 run、trigger reload 和多个 API 仍会在不同路径直接读取文件或重新扫描 extension，缺少一个跨 registry 的一致生效点。

这次采用 B 方案：执行面、Trigger/Cron、运行时读 API 使用 committed runtime snapshot；配置编辑接口继续读写文件。文件保存成功不等于运行时生效，只有 reload commit 成功才替换 snapshot。

## Goals / Non-Goals

**Goals:**
- 让 `AppConfig`、`BootstrapResult`、handler registry、entity type registry、extension table names、`TriggerExecutor`、`CronEmitter` 作为一个 committed snapshot 生效。
- 保证 reload commit 成功后新 DAG run、Trigger/Cron 和 runtime read API 读取同一 snapshot。
- 保证 reload commit 失败时旧 snapshot 完整保留，且不 emit `event:config-changed`。
- 保证 active DAG run 继续使用启动时捕获的 snapshot。
- 保持 config edit API 的文件读写语义。

**Non-Goals:**
- 不实现 reload error UI、snapshot 版本展示、手动 rollback。
- 不把 `ConfigService` 重构为配置事务管理器。
- 不改变 gRPC protocol 或 Web BFF wire contract。
- 不引入新的 registry manager 抽象或外部依赖。

## Decisions

### Decision 1: Controller-owned `RuntimeSnapshot`

`DagController` 持有当前 committed snapshot。snapshot 包含已合并 extension entity types 的 `AppConfig`、`BootstrapResult`、`EntityStore`、`TriggerExecutor`、`CronEmitter` 和 extension table names。

理由：当前真正需要一致性的对象都由 controller 启动 run、emit trigger 或构建 executor 时消费。把 snapshot 放到 controller 内部，比新增全局 singleton 或 registry manager 更直接，影响面也更小。

Alternatives considered:
- 继续每个调用点按需读文件：无法保证跨 registry 事务一致。
- 全局 runtime singleton：隐藏依赖，测试隔离差。
- 通用 registry manager：对当前问题过度抽象。

### Decision 2: `install_snapshot()` 作为唯一 commit path

`HotReloader` 只构建 candidate `AppConfig` 和 `BootstrapResult`，然后调用 `DagController.install_snapshot()`。`install_snapshot()` 在 lock 内完成 merge、extension table creation、`EntityStore` 构建、`TriggerExecutor.load()`、`CronEmitter` 构建；全部成功后才替换当前 snapshot。

理由：事务边界必须在一个函数里，不能分散到 watcher、server 和 trigger reload 的多个路径。extension table creation 必须在替换前完成，否则新 handler 可能看到已提交 snapshot 但缺少表。

Alternatives considered:
- 先替换 snapshot 再异步补建 table：会产生运行时半提交状态。
- 在 `HotReloader` 内直接操作 controller 字段：职责混乱，测试困难。

### Decision 3: Run startup captures snapshot

`_run()` 和 `_run_single_node()` 在启动时捕获当前 snapshot，并用该 snapshot 构建 graph、executor、source refs 和 cleanup 输入。run 生命周期内不得再读取 controller 当前 snapshot。

理由：这是 active run isolation 的核心。如果 run 内部晚绑定当前 snapshot，热加载会污染正在执行的 DAG。

Alternatives considered:
- 每个节点执行前取最新 snapshot：破坏既有 spec 中“运行中 DAG 不受热加载影响”的承诺。

### Decision 4: Runtime read API 使用 committed snapshot，edit API 保持文件语义

`GraphService`、`EntityService`、相关 `QueryService` 的运行时读路径读取 committed snapshot。`ConfigService.ReadConfig/SaveConfig/ReadSystemConfig/SaveSystemConfig` 和保存 DAG/Node/Skill 的编辑路径继续读写文件。

理由：B 方案需要用户看到的运行时状态与执行状态一致，同时避免把配置编辑器改成状态机。保存坏配置后，编辑器可以看到文件内容，但 runtime read API 仍展示旧 committed snapshot。

Alternatives considered:
- A 方案只改执行面：reload 失败后 UI/API 可能显示未生效文件，语义太弱。
- C 方案所有读都 snapshot 化：会把配置编辑器语义、保存后可见性和错误恢复一起拖进来，超出本 change。

### Decision 5: `event:config-changed` 不再触发文件 reload

成功 commit 后 emit `event:config-changed` 只作为事件进入已提交的 `TriggerExecutor`。`DagController.emit()` 不应在该事件上重新从文件构建 trigger executor。

理由：如果 emit 路径再次从文件 reload trigger，就绕开了 committed snapshot，事务边界失效。

## Risks / Trade-offs

- Snapshot/file 双视图 → 在 spec 中明确保存成功不等于运行时生效；runtime read API 只展示 committed snapshot。
- API 边界滑向 C → 只改运行时读路径，raw config read 和写文件路径保持文件语义。
- Extension table creation 失败 → 在 snapshot 替换前执行，失败则保留旧 snapshot。
- 并发 reload 交错 → 使用 controller 内部 `asyncio.Lock` 串行化 commit。
- Active run 被新 snapshot 污染 → run 启动时捕获 snapshot，并把捕获对象贯穿 executor 构建。

## Migration Plan

无需数据迁移。部署后 server start 会构建第一个 committed snapshot；后续文件变更通过 hot reload commit path 生效。若实现出现问题，可回退到上一版本，配置文件格式和 gRPC wire contract 不变。

## Open Questions

无。B 方案边界已确认：runtime read 使用 committed snapshot，config edit 保持文件语义。
