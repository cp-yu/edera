### Task 1: InstalledExtension 数据模型与 Repository

**Goal**: 新增 `InstalledExtension` SQLModel，移除 `ExtensionImportRecord`，提供安装/卸载/查询的 repository 函数。

**Files**:
- Modify: `packages/core/src/edera_core/storage/entities.py`
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Test: `tests/core/unit/test_installed_extensions_repo.py`

**Requirements**:
- 新增 `InstalledExtension` model，含 `name`、`version`、`manifest_snapshot`、`import_records`、`enabled`、`installed_by`、timestamps
- 移除 `ExtensionImportRecord` model
- 提供 `save_installed_extension()`、`get_installed_extension()`、`list_installed_extensions()`、`delete_installed_extension()` repository 函数
- 提供 `list_enabled_extensions()` 查询 `enabled=true` 的记录

#### Checks

- [x] C1 验证 InstalledExtension model 表结构
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "installed_extensions 数据模型" / Scenario "表结构完整"
  - Command: `python -m pytest tests/core/unit/test_installed_extensions_repo.py -k test_table_schema`
  - Expect: 测试通过，表含所有必需字段

- [x] C2 验证 CRUD repository 函数
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "installed_extensions 数据模型" / Scenario "manifest_snapshot 存储完整 manifest"
  - Command: `python -m pytest tests/core/unit/test_installed_extensions_repo.py -k test_save_and_get`
  - Expect: save/get/list/delete 全部通过

### Task 2: Bootstrap 重构

**Goal**: 移除 `scan_extensions()` 自动扫描，新增 `discover_available_extensions()` 和 `load_installed_extensions()`，适配所有调用方。

**Files**:
- Modify: `packages/core/src/edera_core/bootstrap.py`
- Modify: `packages/core/src/edera_core/engine.py`
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `packages/core/src/edera_core/hot_reload.py`
- Modify: `packages/core/src/edera_core/config/loader.py`
- Test: `tests/core/unit/test_bootstrap_refactor.py`

**Requirements**:
- 新增 `discover_available_extensions()` 扫描 `extensions/` 返回可用扩展列表
- 新增 `load_installed_extensions()` 从数据库加载已安装扩展构建 `HandlerRegistry` 和 `EntityTypeRegistry`
- 移除 `scan_extensions()` 函数
- 适配 `engine.py`、`dag_controller.py`、`hot_reload.py`、`config/loader.py` 的启动流程

#### Checks

- [x] C3 验证启动不自动扫描
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "Bootstrap 加载已安装扩展" / Scenario "启动时不自动扫描 extensions/"
  - Command: `python -m pytest tests/core/unit/test_bootstrap_refactor.py -k test_no_auto_scan`
  - Expect: 系统启动时不调用 `scan_extensions()`

- [x] C4 验证从数据库加载已安装扩展
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "Bootstrap 加载已安装扩展" / Scenario "启动加载已安装扩展"
  - Command: `python -m pytest tests/core/unit/test_bootstrap_refactor.py -k test_load_installed`
  - Expect: HandlerRegistry 和 EntityTypeRegistry 从 installed_extensions 表正确构建

- [x] C5 验证跳过已停用扩展
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "Bootstrap 加载已安装扩展" / Scenario "跳过已停用扩展"
  - Command: `python -m pytest tests/core/unit/test_bootstrap_refactor.py -k test_skip_disabled`
  - Expect: `enabled=false` 的扩展不被注册

### Task 3: 扩展安装服务

**Goal**: 实现扩展安装核心逻辑：manifest 校验、依赖检查、代码复制、数据库写入、Entity 导入。

**Files**:
- Create: `packages/core/src/edera_core/extension_manager.py`
- Modify: `packages/core/src/edera_core/extension_imports.py`
- Test: `tests/core/unit/test_extension_install.py`

**Requirements**:
- 安装时读取 `extensions/<name>/manifest.yaml` 并校验
- 安装前检查依赖是否已安装
- 将 handler 代码复制到 `handlers/<name>/`，`_lib/` 依赖复制到 `handlers/_lib/`
- 写入 `installed_extensions` 表，导入 Entity 并记录到 `import_records`
- 重复安装已有扩展 MUST 拒绝

#### Checks

- [x] C6 验证完整安装流程
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展安装" / Scenario "安装完整扩展"
  - Command: `python -m pytest tests/core/unit/test_extension_install.py -k test_install_complete`
  - Expect: 数据库记录写入、handler 代码复制、Entity 导入全部成功

- [x] C7 验证依赖检查
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展安装" / Scenario "安装前校验依赖"
  - Command: `python -m pytest tests/core/unit/test_extension_install.py -k test_dependency_check`
  - Expect: 缺失依赖时拒绝安装

- [x] C8 验证 Entity 导入幂等
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展安装" / Scenario "Entity 导入遵循幂等语义"
  - Command: `python -m pytest tests/core/unit/test_extension_install.py -k test_import_idempotent`
  - Expect: 已存在的 Entity 不被覆盖，status 为 skipped_existing

### Task 4: 扩展卸载服务

**Goal**: 实现三种卸载策略（purge、keep-modified、deactivate）和依赖检查。

**Files**:
- Modify: `packages/core/src/edera_core/extension_manager.py`
- Test: `tests/core/unit/test_extension_uninstall.py`

**Requirements**:
- purge 策略：删除所有导入 Entity + 扩展表 + handler 代码 + 数据库记录
- keep-modified 策略：比较 digest 保留修改的 Entity，删除未修改的
- deactivate 策略：仅设置 `enabled=false`
- 卸载前检查依赖，有依赖者时阻止卸载

#### Checks

- [x] C9 验证 purge 策略
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展卸载" / Scenario "purge 策略卸载"
  - Command: `python -m pytest tests/core/unit/test_extension_uninstall.py -k test_purge`
  - Expect: 所有 Entity、扩展表、handler 代码、数据库记录全部删除

- [x] C10 验证 keep-modified 策略
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展卸载" / Scenario "keep-modified 策略卸载"
  - Command: `python -m pytest tests/core/unit/test_extension_uninstall.py -k test_keep_modified`
  - Expect: 修改过的 Entity 被保留，未修改的被删除

- [x] C11 验证依赖阻止卸载
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展卸载" / Scenario "卸载前依赖检查"
  - Command: `python -m pytest tests/core/unit/test_extension_uninstall.py -k test_dependency_block`
  - Expect: 存在依赖者时拒绝卸载

### Task 5: gRPC ExtensionService

**Goal**: 定义 proto 消息和 service，实现 server 端 ExtensionService handler。

**Files**:
- Modify: `proto/edera.proto`
- Modify: `packages/core/src/edera_core/proto/edera_pb2.py`
- Create: `packages/core/src/edera_core/grpc_extension_service.py`
- Test: `tests/core/unit/test_grpc_extension_service.py`

**Requirements**:
- proto 新增 `ExtensionService`，含 `ListAvailable`、`ListInstalled`、`Show`、`Install`、`Uninstall`、`Reactivate` RPC
- server 端实现调用 `extension_manager` 完成各操作
- Install RPC 失败时回滚

#### Checks

- [x] C12 验证 proto 定义完整
  - Verifies: `specs/extension-grpc-service/spec.md` / Requirement "ExtensionService proto 定义" / Scenario "proto 定义包含所有 RPC"
  - Evidence: `proto/edera.proto`
  - Expect: `ExtensionService` 包含 ListAvailable、ListInstalled、Show、Install、Uninstall、Reactivate

- [x] C13 验证 Install RPC 端到端
  - Verifies: `specs/extension-grpc-service/spec.md` / Requirement "Install RPC" / Scenario "安装成功"
  - Command: `python -m pytest tests/core/unit/test_grpc_extension_service.py -k test_install_rpc`
  - Expect: gRPC Install 调用成功，扩展安装到数据库

### Task 6: CLI extension 子命令

**Goal**: 实现 `edera extension` 子命令组：list、show、install、uninstall、reactivate、import、export、export-entities。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/unit/test_cli_extension.py`

**Requirements**:
- `list` 支持 `--available`、`--installed` flag
- `uninstall` 的 `--strategy` 为必填参数
- `import` 支持 `--install` flag
- `export` 打包 manifest + Entity YAML + handler 代码
- `export-entities` 从数据库导出指定 entity 子集

#### Checks

- [x] C14 验证 extension 子命令可用
  - Verifies: `specs/edera-cli/spec.md` / Requirement "Extension 子命令组" / Scenario "Extension 子命令可用"
  - Command: `edera extension --help`
  - Expect: 输出 list、show、install、uninstall、reactivate、import、export、export-entities

- [x] C15 验证 uninstall 必须指定 strategy
  - Verifies: `specs/extension-cli-commands/spec.md` / Requirement "extension uninstall 命令" / Scenario "未指定 strategy"
  - Command: `python -m pytest tests/core/unit/test_cli_extension.py -k test_uninstall_no_strategy`
  - Expect: 输出错误提示必须指定 --strategy

- [x] C16 验证 import 并安装
  - Verifies: `specs/extension-cli-commands/spec.md` / Requirement "extension import 命令" / Scenario "导入并立即安装"
  - Command: `python -m pytest tests/core/unit/test_cli_extension.py -k test_import_install`
  - Expect: 扩展包解压到 extensions/ 并完成安装

### Task 7: WebConsole 扩展管理页面

**Goal**: 新增 `/extensions` 页面，展示可用/已安装扩展，支持安装、卸载操作。

**Files**:
- Create: `apps/web-console/src/features/extensions/ExtensionPage.tsx`
- Create: `apps/web-console/src/features/extensions/ExtensionList.tsx`
- Create: `apps/web-console/src/features/extensions/ExtensionDetail.tsx`
- Modify: `apps/web-console/src/router/index.tsx`
- Modify: `apps/web-console/src/api/index.ts`
- Test: `apps/web-console/tests/extensions.spec.ts`

**Requirements**:
- 导航新增"扩展"入口，路由 `/extensions`
- 展示已安装扩展列表（name、version、enabled 状态）
- 展示可用但未安装扩展列表
- 安装操作调用 ExtensionService.Install
- 卸载操作弹出策略选择对话框

#### Checks

- [x] C17 验证扩展管理页面路由
  - Verifies: `specs/extension-management-web/spec.md` / Requirement "扩展管理页面路由" / Scenario "访问扩展管理页面"
  - Command: `npx playwright test apps/web-console/tests/extensions.spec.ts`
  - Expect: `/extensions` 路由可访问，展示扩展列表

- [x] C18 验证卸载策略对话框
  - Verifies: `specs/extension-management-web/spec.md` / Requirement "卸载操作" / Scenario "从页面卸载扩展"
  - Command: `npx playwright test apps/web-console/tests/extensions.spec.ts -g "uninstall dialog"`
  - Expect: 卸载按钮弹出三选一策略对话框

### Task 8: 迁移与测试适配

**Goal**: 迁移现有部署（自动注册已有扩展到 installed_extensions），适配所有使用 `scan_extensions()` 的测试。

**Files**:
- Create: `packages/core/src/edera_core/migration/migrate_extensions.py`
- Modify: `tests/core/test_core_extension_runtime.py`
- Modify: `tests/extensions/test_default_news_workflow.py`
- Modify: `tests/extensions/test_uzi_skill_dag.py`
- Modify: `tests/core/unit/test_hot_reload.py`
- Modify: `tests/core/unit/test_server_hot_reload.py`
- Modify: `tests/core/integration/test_per_dag.py`

**Requirements**:
- 迁移脚本：检测 `installed_extensions` 表为空时自动将 `extensions/` 下所有扩展注册为已安装
- 适配所有调用 `scan_extensions()` 的测试文件
- 确保现有测试套件通过

#### Checks

- [x] C19 验证迁移脚本
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展安装" / Scenario "安装完整扩展"
  - Command: `python -m pytest tests/core/unit/test_migration.py -k test_migrate_extensions`
  - Expect: 空表时自动迁移现有扩展，非空表时跳过

- [x] C20 验证现有测试套件通过
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "Bootstrap 加载已安装扩展" / Scenario "启动加载已安装扩展"
  - Command: `python -m pytest tests/`
  - Expect: 所有测试通过
