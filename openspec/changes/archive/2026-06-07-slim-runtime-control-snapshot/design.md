## Context

Edera 已将核心配置型 Entity 迁移到 DB-backed source of truth，但 `RuntimeSnapshot` 仍然保存全量 `AppConfig`，包括 DAG、Node、EntityType、Entity 和 relations。这个对象因此同时承担控制面提交边界、配置读模型和执行快照来源，导致 server start / hot reload 仍倾向全量加载 DAG/Node。

当前 `DagExecutionSnapshot` 已经存在，但它从 `RuntimeSnapshot.config` 接收全量 `nodes`，没有显式的 `DAG execution closure` 边界。Graph/Config/Query 服务也仍有多个 `runtime_snapshot().config.*` 读路径，阻止 runtime snapshot 瘦身。

## Goals / Non-Goals

**Goals:**
- 将 `RuntimeSnapshot` 重命名并收敛为 `RuntimeControlSnapshot`。
- 让 `RuntimeControlSnapshot` 只承载常驻控制面：`system/runtime settings`、`TriggerExecutor`、`CronEmitter` 和可选 generation/version id。
- 由 `DagController` 在 run start 统一构建 `DAG execution closure` 并创建 `DagExecutionSnapshot`。
- Graph/Config/Query 服务改为 DB-backed runtime read model。
- 删除 `ReloadEntityTypes` / `ReloadSkills`，不保留兼容 no-op。

**Non-Goals:**
- 不改变 DAG dispatcher 的事件驱动执行算法。
- 不改变 TriggerExecutor 保持全局 registry 的决策。
- 不为历史 trigger target 数据提供迁移兼容层。
- 不引入新的外部依赖。

## Decisions

### Decision: RuntimeSnapshot becomes RuntimeControlSnapshot

`RuntimeControlSnapshot` 只保留必须原子替换的常驻控制面对象。DAG/Node/EntityType/Skill 不进入该 snapshot；这些配置从 DB 读取，并在 run start 冻结进 `DagExecutionSnapshot`。

替代方案是保留 `RuntimeSnapshot.config: AppConfig` 但清空 DAG/Node。该方案改动小，但保留了错误抽象，后续容易重新塞入全量配置。

### Decision: DagController owns execution closure construction

`DagController` 提供统一内部路径构建 `DAG execution closure`。run、retry、resume、single-node trigger 都走同一入口。`DagRunner` 和 `NodeExecutor` 只消费已经冻结的 snapshot，不查询 DB。

替代方案是在 sub-DAG 到达时再懒加载。该方案会让同一次 run 可能混入 reload 后配置，除非额外实现版本 pinning，复杂度不值得。

### Decision: Graph/Config/Query services use DB-backed reads

Graph/Config/Query 不再从 `runtime_snapshot().config.dags/nodes/entities` 读取运行时视图。DAG/Node/Skill/EntityType 列表、详情和校验输入都从 repository 查询。

这样可避免为了服务读接口而保留全量 runtime config mirror。

### Decision: Node trigger target includes DAG name

Node trigger target 改为 `node:<dag_name>/<node_id>`。系统不再全局扫描所有 DAG 反查 node id 或 alias。

全局反查依赖全量 DAG map，且跨 DAG 同名 alias 天然歧义。显式 DAG 名是更小且正确的协议。

### Decision: Config changes still emit config-changed

DAG/Node/EntityType/Skill 变更保存 DB 后仍 emit `event:config-changed`，但不 rebuild `RuntimeControlSnapshot`。Trigger/system/extension 变更会 rebuild 控制面 snapshot，并通过新的 TriggerExecutor emit。

`event:config-changed` 表示配置数据发生变化，不等同于控制面 snapshot rebuild。

## Risks / Trade-offs

- [runtime_snapshot().config.* 调用点多] → 先引入 DB-backed repository 查询和 closure builder，再删除 snapshot config 字段，让测试暴露遗漏。
- [handler resolver 与 extension table mapping 版本错配] → 在同一个 `DagExecutionSnapshot` 构建流程中冻结 `handler_resolver` 和 `extension_table_names`。
- [trigger target 格式破坏旧数据] → 开发阶段直接更新 fixtures 和 specs，不加兼容路径。
- [GraphService reachable-only validation 可能允许其他 DAG 处于坏状态] → 只在保存或执行相关 DAG 时暴露错误，符合按需加载边界。
- [删除 reload RPC 影响客户端] → 同步删除 proto、generated client wrapper、CLI/Web 调用和测试，不提供 no-op。
