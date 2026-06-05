## ADDED Requirements

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
系统 SHALL 根据 extension name 和 handler entry 计算 handler 文件的绝对路径。

#### Scenario: 计算标准 handler 路径
- **WHEN** extension name 是 "my-ext"，handler entry 是 "handler.py"
- **THEN** 计算路径为 `handlers_dir / "my-ext" / "handler.py"`

#### Scenario: 计算嵌套路径
- **WHEN** extension name 是 "my-ext"，handler entry 是 "src/main.py"
- **THEN** 计算路径为 `handlers_dir / "my-ext" / "src/main.py"`

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
