## Context

`cli.py`（1666 行，60+ 函数）、`storage/repository.py`（1672 行，70+ 函数）、`dag/runner.py`（1464 行，40+ 方法）是项目中三个最大的文件。均承担超过 1000 行的职责，阻碍代码导航和新增功能定位。项目处于活跃开发阶段，无历史包袱，是拆分的合适时机。

## Goals / Non-Goals

**Goals:**
- 将三个超大文件按关注点拆分为粒度适中的模块（每模块 < 400 行）
- 拆分过程零消费者 import 改动（对 `repository.py` 和 `runner.py` 的消费者）
- 不改变任何运行时行为——纯结构重组

**Non-Goals:**
- 不拆分 `server.py`（1281 行）和 `dag_controller.py`（1313 行）——保留给后续迭代
- 不引入新的抽象层、策略模式或依赖注入框架
- 不修改测试逻辑——仅更新必要的 import 路径

## Decisions

### CLI：Registry 模式 + 一子命令一模块

`cli.py` 的 15 个子命令（`entity`、`dag`、`node`、`config` 等）每个都有独立的 parser 定义函数和 gRPC dispatch 函数。拆分后每个子命令模块暴露 `add_parser(subparser)` 和 `async dispatch(args, client)` 两个入口。

`cli/__init__.py` 中的 `COMMANDS` registry dict 映射命令名到 `(module_path, add_parser_fn, dispatch_fn)`。`_dispatch()` 通过 `importlib.import_module` 动态加载对应模块并调用其 dispatch 函数。

**替代方案被拒绝**：按领域分组（entity+dag+config 3 个模块）——边界不清晰，entity 和 entity-type 究竟算不算同一个领域有歧义；保留单文件仅提取工具函数——治标不治本，核心文件仍 1000+ 行。

**帮助元数据下沉**：`cli_help.py:COMMANDS` 中每条命令的 help/description/epilog/subcommands 下沉到对应子命令模块的 `HELP` 常量。`cli_help.py` 删除。`test_cli_help.py` 改为逐模块验证 `HELP` 常量。

### Repository：子包 + 全量 re-export

`repository.py` 按聚合根自然分为 9 个模块：

| 模块 | 聚合根 | 约行数 |
|------|--------|--------|
| `_entity_type.py` | EntityType 记录管理 | 150 |
| `_core_entity.py` | 核心实体 CRUD（DAG/Node/Trigger/Resource/InputMapping） | 350 |
| `_ordinary.py` | 普通实体 CRUD | 250 |
| `_relation.py` | 关系 CRUD | 100 |
| `_skill.py` | 技能 CRUD | 100 |
| `_extension.py` | 扩展记录 | 80 |
| `_log_index.py` | 日志索引 | 30 |
| `_runtime.py` | DAG run/node run/edge/source 追踪 | 500 |
| `_helpers.py` | 私有 SQL/转换工具 | 200 |

`repository/__init__.py` 全量 re-export 所有公开 API，50+ 消费者零改动。

模块间引用使用相对导入（`from ._relation import force_delete_entity_relations`）。依赖关系单向无环：`_helpers` ← 叶子模块 ← `__init__.py`。

**替代方案被拒绝**：3 大类分组——`entity_store.py` 仍有 700 行，边界模糊；仅提取辅助函数——`repository.py` 仍 1000+ 行。

### DagRunner：函数委托，不引入策略类

`DagRunner` 类的主循环和 fan-in/out 逻辑是紧密耦合的状态机（共享 `outputs`、`failures`、`acquired_resources` 可变 dict 和 `asyncio.Queue`），不拆分。仅提取 3 个已清晰的边界：

- `_subdag.py`：`_execute_sub_dag()` + input mapping 逻辑（~100 行）
- `_loop.py`：`_execute_parallel_loop()` + `_execute_serial_loop()`（~150 行）
- `_helpers.py`：10 个模块级纯函数（不碰 `self`，~150 行）
- `resources.py`：追加 `_acquire_resource` / `_release_resource` / `_wait_for_resource_release`

提取方式：`DagRunner` 的方法变薄壳，委托到独立模块函数，传递显式参数而非引入 Context 对象。

**替代方案被拒绝**：策略类分解——引入 `DagContext` 传递对象变相增加间接层，1464 行引入 5 个策略类属于过度工程；仅提取纯函数——`DagRunner` 仍 1100 行，改善有限。

### Git 历史保留

`cli.py` → `cli/__init__.py` 和 `repository.py` → `repository/__init__.py` 使用 `git mv` 保留文件历史。新增子模块无历史负担。

## Risks / Trade-offs

- **CLI 15 个模块碎片化** → 通过 `__init__.py` 中的 `COMMANDS` registry 集中注册，新增子命令只需在 registry 加一行
- **`_helpers.py` 可能成为新上帝模块** → 设 200 行硬上限；超限时按工具类别再拆（`_sql.py` / `_convert.py`）
- **sub-dag 提取后闭包断裂** → `self.executor.dag_executor` 保持在 `DagRunner.__init__` 中设置，不搬到 `_subdag.py`
- **`_runtime.py` 500 行仍偏大** → 可后续拆为 `_runtime_dag.py` / `_runtime_node.py` / `_runtime_source.py`，暂合并以减少 import 噪音
- **提取函数参数爆炸** → 接受：显式参数列表如实反映依赖，比隐藏 `self` 更透明
