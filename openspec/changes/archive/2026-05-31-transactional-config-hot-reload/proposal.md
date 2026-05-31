<!-- Smart routing: Design Summary found. input_length=17, detail_score=5/5 from confirmed explore summary, multi_subsystem=true, decision=proceed using Design Summary. -->
## Why

当前 hot reload 已经保证 watcher 生命周期和失败隔离，但 reload 成功后没有把 `AppConfig`、handler registry、entity type registry、trigger/cron 运行时视图作为一个事务快照提交。结果是文件变更、执行面和运行时读 API 可能出现半新半旧状态。

## What Changes

- 引入 controller-owned committed runtime snapshot，作为新 DAG run、TriggerExecutor、CronEmitter 和运行时读 API 的唯一生效视图。
- 将 hot reload commit 改为候选快照完整构建并验证成功后一次性替换；失败时旧 snapshot 保持不变且不 emit `event:config-changed`。
- 明确 B 方案边界：runtime read API 读取 committed snapshot，config edit API 继续读写文件。
- 保持 active DAG run isolation：运行中的 DAG 继续使用启动时捕获的 snapshot。
- 不引入新依赖，不重构配置编辑器为事务状态机。

## Capabilities

### New Capabilities

### Modified Capabilities
- `config-hot-reload`: 将热加载语义升级为跨 config、handler registry、entity type registry、trigger/cron 和 runtime read API 的事务性 committed snapshot。

## Impact

- Affected code:
  - `packages/core/src/edera_core/hot_reload.py`
  - `packages/core/src/edera_core/dag_controller.py`
  - `packages/core/src/edera_core/server.py`
  - `packages/core/src/edera_core/graph_service.py`
  - `packages/core/src/edera_core/query_service.py`
  - `packages/core/src/edera_core/service_common.py`
  - `packages/core/src/edera_core/bootstrap.py`
- Affected tests:
  - `tests/core/unit/test_hot_reload.py`
  - `tests/core/unit/test_server_hot_reload.py`
  - new focused unit tests for snapshot commit and runtime read API behavior
- No new runtime dependency.
- No protocol or wire API breaking change.
