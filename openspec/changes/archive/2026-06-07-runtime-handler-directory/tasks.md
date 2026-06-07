### Task 1: Handler directory config

**Goal**: Add `SystemConfig.handlers_dir` and route controller/runtime loading through it.

**Files**:
- Modify: `packages/core/src/edera_core/config/schema.py`
- Modify: `packages/core/src/edera_core/config/loader.py`
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `config/system.toml`
- Test: `tests/core/unit/test_config.py`

**Requirements**:
- Add `handlers_dir` with default `data/handlers`.
- Resolve controller handler directory from loaded system config.
- Keep `handlers_dir` available to runtime snapshot creation.

#### Checks

- [x] C1 Verify default handler runtime directory
  - Verifies: `specs/database-handler-resolver/spec.md` / Requirement "Handler runtime directory configuration" / Scenario "使用默认 handler 运行目录"
  - Command: `uv run pytest tests/core/unit/test_config.py -q`
  - Expect: default `SystemConfig.handlers_dir` is `data/handlers`

- [x] C2 Verify explicit handler runtime directory
  - Verifies: `specs/database-handler-resolver/spec.md` / Requirement "Handler runtime directory configuration" / Scenario "使用显式 handler 运行目录"
  - Command: `uv run pytest tests/core/unit/test_config.py -q`
  - Expect: explicit `handlers_dir` in system config is respected

### Task 2: Remove startup migration

**Goal**: Remove automatic extension migration and startup handler copying.

**Files**:
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `packages/core/src/edera_core/config/loader.py`
- Delete: `packages/core/src/edera_core/migration/migrate_extensions.py`
- Test: `tests/core/unit/test_extension_migration.py`
- Test: `tests/core/unit/test_bootstrap_refactor.py`

**Requirements**:
- Startup MUST NOT scan `extensions/` to install extensions.
- Startup MUST NOT copy handler code.
- Runtime config loading MUST NOT call migration code.

#### Checks

- [x] C3 Verify startup does not install extensions
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "Bootstrap 加载已安装扩展" / Scenario "启动时不自动扫描 extensions/"
  - Command: `uv run pytest tests/core/unit/test_extension_migration.py tests/core/unit/test_bootstrap_refactor.py -q`
  - Expect: startup leaves available-but-uninstalled extensions uninstalled and does not create `handlers_dir/<name>/`

- [x] C4 Verify bootstrap minimal startup
  - Verifies: `specs/core-bootstrap/spec.md` / Requirement "Engine 启动入口" / Scenario "最小启动"
  - Command: `uv run pytest tests/core/unit/test_bootstrap_refactor.py -q`
  - Expect: startup loads installed metadata without automatic extension installation

### Task 3: Install and lifecycle use handlers_dir

**Goal**: Ensure explicit extension lifecycle operations use configured `handlers_dir`.

**Files**:
- Modify: `packages/core/src/edera_core/extension_manager.py`
- Modify: `packages/core/src/edera_core/grpc_extension_service.py`
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/unit/test_extension_install.py`
- Test: `tests/core/unit/test_extension_uninstall.py`
- Test: `tests/core/unit/test_cli_extension.py`

**Requirements**:
- [已有本地 `handlers/` 不会自动搬迁] -> 由 agent 一次性复制到 `data/handlers/`。
- Install copies handler code to `handlers_dir/<name>/`.
- Uninstall deletes `handlers_dir/<name>/` for destructive strategies.
- Deactivate keeps files but disables metadata for new runs.
- Export reads handler code from configured `handlers_dir`.

#### Checks

- [x] C5 Verify install copies to configured directory
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展安装" / Scenario "安装完整扩展"
  - Command: `uv run pytest tests/core/unit/test_extension_install.py -q`
  - Expect: installed handler code exists under configured `handlers_dir/<name>/`

- [x] C6 Verify uninstall and deactivate semantics
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展卸载" / Scenario "purge 策略卸载", Scenario "keep-modified 策略卸载", Scenario "deactivate 策略卸载"
  - Command: `uv run pytest tests/core/unit/test_extension_uninstall.py -q`
  - Expect: destructive uninstall removes configured handler directory; deactivate keeps code and disables metadata

- [x] C7 Verify extension export uses handlers_dir
  - Verifies: `specs/extension-cli-commands/spec.md` / Requirement "extension export 命令" / Scenario "导出已安装扩展", Scenario "handler 代码不在 handlers_dir 下"
  - Command: `uv run pytest tests/core/unit/test_cli_extension.py -q`
  - Expect: export includes handler code from configured `handlers_dir` and warns when missing or outside it

### Task 4: Runtime resolver and executor path

**Goal**: Keep DAG execution resolving handlers only from installed runtime handler directory.

**Files**:
- Modify: `packages/core/src/edera_core/bootstrap.py`
- Modify: `packages/core/src/edera_core/resolver.py`
- Modify: `packages/core/src/edera_core/snapshot.py`
- Modify: `packages/core/src/edera_core/node/executor.py`
- Test: `tests/core/unit/test_database_handler_resolver.py`
- Test: `tests/core/unit/test_node_executor.py`

**Requirements**:
- Resolver path calculation uses configured `handlers_dir`.
- Run-start resolver snapshot freezes enabled installed metadata.
- `handlers_dir` is on `sys.path` for `_lib` imports.

#### Checks

- [x] C8 Verify resolver path calculation
  - Verifies: `specs/database-handler-resolver/spec.md` / Requirement "计算 handler 文件路径" / Scenario "计算标准 handler 路径", Scenario "计算嵌套路径"
  - Command: `uv run pytest packages/core/tests/test_resolver.py -q`
  - Expect: resolver returns paths under configured `handlers_dir`

- [x] C9 Verify handler import path
  - Verifies: `specs/core-bootstrap/spec.md` / Requirement "Module Path 设置" / Scenario "Handler import _lib 模块"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py -q`
  - Expect: installed handlers can import `_lib` from configured `handlers_dir`

### Task 5: Spec and stale test cleanup

**Goal**: Align stale specs/tests with the installed handler directory model.

**Files**:
- Modify: `openspec/specs/extension-installation-lifecycle/spec.md`
- Modify: `openspec/specs/core-bootstrap/spec.md`
- Modify: `openspec/specs/config-hot-reload/spec.md`
- Modify: `openspec/specs/database-handler-resolver/spec.md`
- Modify: `openspec/specs/extension-cli-commands/spec.md`
- Test: `openspec/changes/runtime-handler-directory/specs/**/*.md`

**Requirements**:
- Remove stale `HandlerRegistry` wording from affected specs.
- Remove startup auto-migration expectations.
- Keep change-local specs valid.

#### Checks

- [x] C10 Verify OpenSpec change
  - Verifies: `specs/core-bootstrap/spec.md` / Requirement "扩展目录扫描" / Scenario "启动不扫描扩展目录"
  - Command: `openspec validate runtime-handler-directory --type change --json`
  - Expect: validation succeeds or reports only accepted warning-only issues
