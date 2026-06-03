## Context

当前系统已经将 `node`、`dag`、`trigger`、`resource` 定位为 DB-backed core Entity，但 runtime 仍有两类残留隐式行为：`DagController.start()` 可通过 `start_run("startup")` 启动 `default`，并且 `install_snapshot()` / `materialize_runtime_app_config()` 会自动为已有 DAG 生成 `<dag>-default-cron` trigger。这些行为绕开用户可见配置边界，和统一 trigger 调度模型冲突。

extension 当前是能力包：`manifest.yaml` 声明 handler、entity type、storage 和 depends。新的导入机制不改变这个边界：manifest 只增加 `imports.entities` 声明，`scan_extensions()` 仍只解析和携带声明，不写 DB。写入 DB 的职责归属独立 importer。

## Goals / Non-Goals

**Goals:**
- 让所有 DAG 发起入口收敛到 `TriggerExecutor.emit()`。
- 删除 startup run、默认 cron 自动生成和 hard-coded default 路由。
- 让 extension manifest 可以声明要导入的 Entity YAML。
- 用 `extension_imports` 记录导入状态，保证自动导入幂等且不覆盖用户实体。
- 删除新运行中的 `DagRun.source = startup`。

**Non-Goals:**
- 不实现完整 extension uninstall API。
- 不迁移现有 `default` / `uzi-skill-analysis` DAG 内容；该工作由后续 change 完成。
- 不新增 `event:startup` emit。
- 不改变 extension handler/entity type/storage 的现有加载语义。

## Decisions

1. `scan_extensions()` 只解析 manifest，不导入 Entity。

   直接在 scan 阶段写 DB 会把能力发现和用户配置写入耦合。保留 scan 的只读语义，输出 `BootstrapResult.manifests` 中的 import declarations，由启动/materialization 流程显式调用 importer。

2. manifest 使用 `imports.entities`，路径相对 extension 根目录。

   目录布局由 extension 作者决定，不固定 `examples/`。manifest 是唯一规范入口，避免通过目录名猜测导入范围。

3. `extension_imports` 以 `extension_name + import_path` 作为导入单元。

   每条 import path 对应一个 Entity YAML。已存在导入记录时跳过；无记录但 DB 中已有实体时记录 `skipped_existing`，不覆盖。记录 `content_digest` 和 `imported_entity_digest`，为后续卸载判断用户是否修改过实体提供依据。

4. 删除 core 生成默认配置实例。

   `_ensure_default_cron_triggers()` 和 `_default_trigger_entities()` 都要删除。core 不再根据“当前有哪些 DAG”推导 trigger。定时运行只来自 DB 中已有 Trigger Entity。

5. 手动 DAG run 走 `emit("manual:dag:<name>")`。

   `manual:*` 是保留前缀，由 `TriggerExecutor.emit()` 直接 fire target，不置位 EventGroup bit，不匹配 Trigger Entity。最终 `DagRun.source` 仍为 `manual`。

6. `startup` source 直接删除。

   项目仍处于开发阶段，无历史兼容负担。未来若需要启动时运行 DAG，必须通过显式 trigger 和明确系统事件设计另行提出。

## Risks / Trade-offs

- [Risk] extension 自动导入仍是隐式写 DB。→ Mitigation: 只导入 manifest 显式列出的 `imports.entities`，写入 `extension_imports`，已有实体永不覆盖。
- [Risk] 热加载反复扫描 extension。→ Mitigation: importer 先查 `extension_imports`，已导入路径直接跳过。
- [Risk] 删除 hard-coded default route 影响旧调用方。→ Mitigation: 使用规范 `/api/dags/{dag_name}/...` 路由；开发阶段不保留兼容。
- [Risk] 手动 run 改走 emit 后多出 emit record。→ Mitigation: 这是统一可观测性的一部分，manual event 不置位 bit。
- [Risk] 删除 `startup` source 可能影响旧测试。→ Mitigation: 同步更新 specs/tests，直接拒绝 `startup`。

## Migration Plan

1. 增加 manifest import parsing 和 `extension_imports` 表。
2. 增加 importer，并在 runtime config materialization 读取 DB-backed core entities 之前执行。
3. 删除 startup run 和默认 cron 自动生成路径。
4. 修改 `DagService.Run` 使用 emit 路径。
5. 删除 hard-coded default Web routes。
6. 更新 specs/tests，验证启动不运行 DAG、不生成 trigger、manual run 走 emit、导入幂等。
