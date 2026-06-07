## ADDED Requirements

### Requirement: Handler runtime directory configuration

系统 SHALL 通过 `SystemConfig.handlers_dir` 配置 handler 运行目录。默认值 MUST 为 `data/handlers`。

#### Scenario: 使用默认 handler 运行目录
- **WHEN** `config/system.toml` 未声明 `handlers_dir`
- **THEN** 系统 SHALL 使用 `data/handlers` 作为 handler 运行目录

#### Scenario: 使用显式 handler 运行目录
- **WHEN** `config/system.toml` 声明 `handlers_dir = "custom/handlers"`
- **THEN** 系统 SHALL 使用 `custom/handlers` 作为 handler 运行目录

## MODIFIED Requirements

### Requirement: 计算 handler 文件路径
系统 SHALL 根据配置的 `handlers_dir`、extension name 和 handler entry 计算 handler 文件的绝对路径。

#### Scenario: 计算标准 handler 路径
- **WHEN** `handlers_dir` 是 `data/handlers`，extension name 是 "my-ext"，handler entry 是 "handler.py"
- **THEN** 计算路径为 `data/handlers / "my-ext" / "handler.py"`

#### Scenario: 计算嵌套路径
- **WHEN** `handlers_dir` 是 `data/handlers`，extension name 是 "my-ext"，handler entry 是 "src/main.py"
- **THEN** 计算路径为 `data/handlers / "my-ext" / "src/main.py"`
