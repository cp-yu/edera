## Why

`cli.py`（1666 行）、`storage/repository.py`（1672 行）、`dag/runner.py`（1464 行）三个文件承载了过量的关注点，阻碍代码导航和新增功能定位。当前项目仍在活跃开发阶段（无历史负担），尽早拆分可避免后续模块持续膨胀。

## What Changes

- 将 `cli.py` 拆分为 `cli/` 子包，15 个子命令各占独立模块，通过 registry 统一注册
- 将 `storage/repository.py` 拆分为 `storage/repository/` 子包，按聚合根（EntityType、CoreEntity、OrdinaryEntity、Relation、Skill、Extension、LogIndex、Runtime）分模块，`__init__.py` 全量 re-export 保持消费者零改动
- 将 `dag/runner.py` 的 sub-dag、loop、资源管理逻辑及模块级纯函数提取到独立模块，`DagRunner` 类保留主循环
- `cli_help.py` 删除，各命令的 help 元数据下沉到对应子命令模块

## Capabilities

### New Capabilities

无。本次为纯结构重组，不引入新行为。

### Modified Capabilities

无。不改变任何规格级行为。

## Impact

- 受影响文件：`packages/core/src/edera_core/cli.py`、`packages/core/src/edera_core/storage/repository.py`、`packages/core/src/edera_core/dag/runner.py`、`packages/core/src/edera_core/dag/resources.py`、`packages/core/src/edera_core/cli_help.py`（删除）
- 测试文件：7 个 CLI 测试的 import 路径需更新；repository 和 runner 测试零改动
- 入口点 `edera = "edera_core.cli:main"` 保持有效（`cli/__init__.py` 自动解析）
- 无 API 变更，无依赖变更
