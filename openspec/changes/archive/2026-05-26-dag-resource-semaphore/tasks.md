## 1. Actions

- [x] A1 新增 Resource EntityType 定义（`config/entity-types/resource.yaml`），声明 `permits: int` 属性
- [x] A2 `DagNodeInstance` 新增 `resource: str | None = None` 字段（`config/schema.py`）
- [x] A3 新增模块级 semaphore 池（`dag/resources.py`），提供 `get_semaphore(resource_id, entity_store)` → `asyncio.Semaphore`，缓存已创建实例
- [x] A4 修改 `DagRunner._start_ready_nodes`：对声明 resource 的节点执行非阻塞 acquire，失败则跳过
- [x] A5 修改 `DagRunner._store_result`：节点完成后 release semaphore，并触发 `_start_ready_nodes` 重新检查
- [x] A6 处理 CancelledError 路径：确保 cancel 时 release semaphore 不泄漏

## 2. Checks

- [x] C1 Resource EntityType 可加载
  - Covers: A1
  - Command: `python -c "from stockimformation_core.config.loader import load_config; c = load_config(); assert 'resource' in [et.id for et in c.entity_types]"`
  - Expect: resource EntityType 存在于加载结果中

- [x] C2 DagNodeInstance 接受 resource 字段
  - Covers: A2
  - Command: `python -c "from stockimformation_core.config.schema import DagNodeInstance; n = DagNodeInstance(id='test', type='x', resource='v8_isolate'); assert n.resource == 'v8_isolate'"`
  - Expect: 字段赋值成功，无 ValidationError

- [x] C3 semaphore 池正确创建和缓存
  - Covers: A3
  - Command: `pytest tests/dag/test_resource_semaphore.py::test_get_semaphore_caches`
  - Expect: 同一 resource_id 返回同一 Semaphore 实例

- [x] C4 permits=1 时同 resource 节点串行执行
  - Covers: A4, A5
  - Command: `pytest tests/dag/test_resource_semaphore.py::test_serial_execution`
  - Expect: 两个声明同一 resource（permits=1）的节点不重叠执行

- [x] C5 无 resource 声明的节点行为不变
  - Covers: A4
  - Command: `pytest tests/dag/test_resource_semaphore.py::test_no_resource_unchanged`
  - Expect: 无 resource 节点立即并发启动，与改动前行为一致

- [x] C6 permits=2 时允许 2 并发
  - Covers: A3, A4, A5
  - Command: `pytest tests/dag/test_resource_semaphore.py::test_permits_two`
  - Expect: 3 个节点声明同一 resource（permits=2），最多 2 个同时执行

- [x] C7 节点失败后 release 不泄漏
  - Covers: A5, A6
  - Command: `pytest tests/dag/test_resource_semaphore.py::test_release_on_failure`
  - Expect: 节点抛异常后 semaphore permit 被释放，后续节点可 acquire

- [x] C8 跨 DAG 共享验证
  - Covers: A3
  - Command: `pytest tests/dag/test_resource_semaphore.py::test_cross_dag_sharing`
  - Expect: 两个 DagRunner 实例并发运行，共享同一 resource 的 semaphore
