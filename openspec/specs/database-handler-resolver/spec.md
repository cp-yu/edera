---
capabilities:
  - cap.core.database-handler-resolver
---
# database-handler-resolver Specification

## Purpose
定义从数据库安装扩展快照中按需解析 handler 元数据、计算 handler 文件路径并返回可执行入口信息的能力。
## Requirements
### Requirement: 覆盖率验证可复现性
registry-removal 针对 `database-handler-resolver` 的 coverage 验证命令 SHALL 可在项目 dev 环境中运行。

#### Scenario: coverage 命令具备依赖
- **WHEN** 项目 dev dependencies 已安装
- **THEN** `pytest-cov` SHALL 可被 pytest 使用
- **AND** `uv run pytest packages/core/tests/ --cov=edera_core --cov-report=term` SHALL 不会因未知 `--cov` 选项失败

### Requirement: 从数据库查询 handler 元数据
系统 SHALL 提供 `DatabaseHandlerResolver` 类，从 `installed_extensions` 表的 `manifest_snapshot` 字段查询 handler 元数据。

#### Scenario: 查询已安装扩展的 handler
- **WHEN** resolver 查询 handler name "my-handler"
- **THEN** 系统遍历所有 `enabled=true` 的 extensions
- **THEN** 解析每个 extension 的 `manifest_snapshot.handlers` 列表
- **THEN** 返回匹配的 `HandlerMeta(path, function)`

#### Scenario: Handler 不存在
- **WHEN** resolver 查询不存在的 handler name "nonexistent"
- **THEN** 系统抛出 `HandlerNotFoundError` 异常

### Requirement: 计算 handler 文件路径
系统 SHALL 根据配置的 `handlers_dir`、extension name 和 handler entry 计算 handler 文件的绝对路径。

#### Scenario: 计算标准 handler 路径
- **WHEN** `handlers_dir` 是 `data/handlers`，extension name 是 "my-ext"，handler entry 是 "handler.py"
- **THEN** 计算路径为 `data/handlers / "my-ext" / "handler.py"`

#### Scenario: 计算嵌套路径
- **WHEN** `handlers_dir` 是 `data/handlers`，extension name 是 "my-ext"，handler entry 是 "src/main.py"
- **THEN** 计算路径为 `data/handlers / "my-ext" / "src/main.py"`

### Requirement: 提取 handler function name
系统 SHALL 从 manifest 的 handler 定义中提取 function name，默认为 "run"。

#### Scenario: 使用默认 function
- **WHEN** manifest handler 没有指定 `function` 字段
- **THEN** 返回 function name "run"

#### Scenario: 使用自定义 function
- **WHEN** manifest handler 指定 `function: "execute"`
- **THEN** 返回 function name "execute"

### Requirement: Resolver 持有数据库 session
`DatabaseHandlerResolver` SHALL 在构造时接收数据库 session，查询时使用该 session。

#### Scenario: 构造 resolver
- **WHEN** 创建 `DatabaseHandlerResolver(session)`
- **THEN** resolver 内部保存 session 引用

#### Scenario: 查询时使用 session
- **WHEN** resolver 调用 `get(handler_name)`
- **THEN** 使用构造时传入的 session 查询 `installed_extensions` 表

### Requirement: Run-start resolver snapshot
`DatabaseHandlerResolver` SHALL support creating a run-start snapshot that freezes enabled extension handler metadata for one `DagExecutionSnapshot`.

#### Scenario: Snapshot freezes handlers
- **WHEN** `DatabaseHandlerResolver.snapshot(session)` is called at DAG run start
- **THEN** returned resolver SHALL contain the enabled handlers visible in DB at that time

#### Scenario: Later extension changes do not affect resolver snapshot
- **WHEN** an extension is installed or disabled after resolver snapshot creation
- **THEN** the existing resolver snapshot SHALL continue resolving only its frozen handler set

### Requirement: Extension table mapping freezes with resolver
System SHALL freeze extension storage table mappings in the same `DagExecutionSnapshot` that freezes `DatabaseHandlerResolver`.

#### Scenario: Handler storage table mapping is consistent
- **WHEN** a handler resolved by the snapshot calls `ctx.storage.table("items")`
- **THEN** system SHALL resolve the table name from the `extension_table_names` frozen for the same `DagExecutionSnapshot`

### Requirement: Handler runtime directory configuration

系统 SHALL 通过 `SystemConfig.handlers_dir` 配置 handler 运行目录。默认值 MUST 为 `data/handlers`。

#### Scenario: 使用默认 handler 运行目录
- **WHEN** `config/system.toml` 未声明 `handlers_dir`
- **THEN** 系统 SHALL 使用 `data/handlers` 作为 handler 运行目录

#### Scenario: 使用显式 handler 运行目录
- **WHEN** `config/system.toml` 声明 `handlers_dir = "custom/handlers"`
- **THEN** 系统 SHALL 使用 `custom/handlers` 作为 handler 运行目录

