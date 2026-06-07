## Why

当前 handler 运行目录由启动迁移隐式生成，默认落在项目根 `handlers/`，导致源码目录、安装后运行目录和 DB metadata 边界混杂。项目仍处于开发阶段，不需要保留自动版本迁移路径，应明确安装后的 handler 目录才是运行权威。

## What Changes

- **BREAKING**: 移除启动时 `migrate_existing_extensions` 自动迁移和复制 handler 的行为。
- 在 `SystemConfig` / `config/system.toml` 中声明 `handlers_dir`，默认 `data/handlers`。
- `DagController`、runtime config loading、extension install/export、`DatabaseHandlerResolver` 统一使用配置的 `handlers_dir`。
- `extensions/<name>/` 只作为可安装来源；运行时只从 `handlers_dir/<name>/<entry>` 加载 handler。
- 首次已有 handler 复制由 agent 或人工一次性执行，不写入程序启动逻辑。
- 清理 OpenSpec 中 `HandlerRegistry`、启动自动扫描复制、`extensions/` handler 热加载等过期语义。

## Capabilities

### New Capabilities

### Modified Capabilities
- `extension-installation-lifecycle`: 明确显式安装才复制 handler，启动不自动迁移，安装后目录是运行权威。
- `database-handler-resolver`: handler 路径来自 `SystemConfig.handlers_dir` 配置，默认 `data/handlers`。
- `core-bootstrap`: 启动 bootstrap 不再自动扫描 `extensions/` 并安装 handler。
- `config-hot-reload`: handler 脚本变更语义改为安装后目录生效，不再把 `extensions/` 当运行代码来源。
- `extension-cli-commands`: extension export 默认从配置的 `handlers_dir` 读取 handler 代码。

## Impact

- Affected code: `packages/core/src/edera_core/config/schema.py`, `packages/core/src/edera_core/config/loader.py`, `packages/core/src/edera_core/dag_controller.py`, `packages/core/src/edera_core/bootstrap.py`, `packages/core/src/edera_core/resolver.py`, `packages/core/src/edera_core/extension_manager.py`, `packages/core/src/edera_core/grpc_extension_service.py`, `packages/core/src/edera_core/cli.py`.
- Removed code path: `packages/core/src/edera_core/migration/migrate_extensions.py` and startup callers.
- Tests: extension install/uninstall, resolver path calculation, controller startup, config loading, CLI export, and stale migration tests.
- Operator action: existing handler files must be copied once to `data/handlers/` before relying on installed extension metadata.
