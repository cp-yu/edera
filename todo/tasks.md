# Stale Test Cleanup Tasks

[x] Update `tests/core/test_core_extension_runtime.py` to remove `edera_core.registry.HandlerRegistry` import.
[x] Update `tests/core/test_core_extension_runtime.py` assertions from `handler_registry` / `entity_type_registry` to current installed-extension metadata.
[x] Update `tests/core/test_core_extension_runtime.py` `NodeExecutor(..., registry.seal())` calls to build and pass `DagExecutionSnapshot`.
[x] Update `tests/core/unit/test_hot_reload.py` to remove `HandlerRegistry` / `EntityTypeRegistry` imports.
[x] Update `tests/core/unit/test_hot_reload.py` old `BootstrapResult(...)` construction to current `BootstrapResult(manifests, storage_tables, table_names, extension_roots)` shape.
[x] Update `tests/core/unit/test_hot_reload.py` assertions using `runtime_snapshot().bootstrap.handler_registry`.
[x] Update `tests/core/unit/test_hot_reload.py` callback assertions using `snapshot.config`.
[x] Update `tests/core/unit/test_hot_reload.py` assertions using `NodeExecutor.handler_registry`.
[x] Replace `tests/core/unit/test_hot_reload.py` manual handler copy/install helper with the current explicit extension install path.
[x] Update `tests/core/unit/test_server_hot_reload.py` to remove old registry imports.
[x] Update `tests/core/unit/test_server_hot_reload.py` old `BootstrapResult(...)` construction.
[x] Update `tests/core/unit/test_server_hot_reload.py` reads of `controller.runtime_snapshot().config` to current config access.
[x] Remove the local `NodeExecutor` compatibility shim in `tests/core/integration/test_dag_runner.py`.
[x] Convert all `tests/core/integration/test_dag_runner.py` handler-dict `NodeExecutor` calls to explicit `DagExecutionSnapshot` construction.
[x] Remove the local `NodeExecutor` compatibility shim in `tests/core/integration/test_resource_semaphore.py`.
[x] Convert all `tests/core/integration/test_resource_semaphore.py` handler-dict `NodeExecutor` calls to explicit `DagExecutionSnapshot` construction.
[x] Update `tests/extensions/test_uzi_skill_dag.py` to put `bootstrap.table_names` into the snapshot instead of passing `extension_tables=`.
[x] Remove dead `extension_tables=` arguments from `tests/extensions/test_uzi_skill_dag.py`.
[x] Update `tests/core/integration/test_per_dag.py` fake startup flow so it does not install extensions during controller start.
[x] Remove package-core negative assertions for deleted `handler_registry` / `entity_type_registry` fields.
[x] Replace package-core `runtime_snapshot().config` negative assertion with current `runtime_config()` contract.
[x] Remove package-core `NodeExecutor(..., extension_tables=...)` compatibility usage from tests.
[x] Verify targeted stale-test files with focused pytest runs.
[x] Run the relevant broader core test subset after targeted fixes pass.
