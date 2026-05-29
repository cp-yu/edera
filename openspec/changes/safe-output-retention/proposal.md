<!--
propose routing: Design Summary found from prior explore confirmations.
input length: short command plus confirmed conversation context
detail score: 5/5 from confirmed architecture, core components, data flow, technology stack, testing strategy, and risks
multi-subsystem: false; one retention policy change touches config and DAG controller implementation
decision: proceed with artifact generation
-->
## Why

一次失败或取消的 DAG run 不应删除最后一批可展示的 `advice` / `briefing` 输出。当前 retention 在 run 最终状态确认前执行，导致失败 run 也可能按 24 小时窗口清掉旧结果，使 `/results` 变空。

## What Changes

- 将默认输出保留时间从 24 小时调整为 720 小时。
- 将当前项目 `config/system.toml` 的 `retention_hours` 调整为 `720`。
- 将 output retention cleanup 的触发时机改为完整 DAG 成功完成之后。
- 失败、取消、单节点运行和 partial retry 不触发 output retention cleanup。
- 不修改 `cleanup_node_output_entities()` 的清理算法本身。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `entity-storage-tiers`: 修改输出型 Entity retention 策略，明确默认保留时间为 720 小时，并且 cleanup 只在完整 DAG 成功完成后触发。

## Impact

- `config/system.toml`
- `packages/core/src/edera_core/config/schema.py`
- `packages/core/src/edera_core/dag_controller.py`
- `tests/core/integration/test_per_dag.py` 或同等 focused backend test
- `/api/results` 间接受益：失败 run 不再清掉旧的可展示结果
