### Task 1: ExtensionManager 覆盖安装路径

**Goal**: 让 `ExtensionManager.install()` 支持 `overwrite` 参数，已安装时执行 drop 扩展表 + 清空旧 import_records 全量重导 + 重建 handler/libs + upsert 记录，返回数据保留提醒。

**Files**:
- Modify: `packages/core/src/edera_core/extension_manager.py`
- Test: `tests/core/unit/test_extension_install.py`

**Requirements**:
- `install()` 增加 `overwrite: bool = False` 参数；未安装时行为不变，已安装且 `overwrite=False` 维持拒绝。
- 已安装且 `overwrite=True` 时：drop `ext_<name>_*` 扩展表（依据旧 `manifest_snapshot` 的 storage.tables）、清空旧 `import_records` 使 entity 全量重导、复用现有 `_copy_*` 重建 handler/libs、`save_installed_extension` upsert。
- 覆盖安装结果 dict 增加 `overwrite: bool` 与 `data_warning: str` 字段。
- 覆盖路径仍执行依赖检查（缺依赖仍拒绝）。

#### Checks

- [x] C1 验证默认重复安装仍拒绝
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展安装" / Scenario "默认重复安装已有扩展被拒绝"
  - Command: `pytest tests/core/unit/test_extension_install.py -k overwrite_rejected_by_default`
  - Expect: 已安装 extension 默认重复 install 抛出 "already installed"，无运行态变更
- [x] C2 验证覆盖安装重建扩展表与导入记录
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展覆盖安装" / Scenario "覆盖安装重建扩展表与导入记录"
  - Command: `pytest tests/core/unit/test_extension_install.py -k overwrite_rebuilds_tables_and_records`
  - Expect: ext_<>_ 表被 drop 后重建，import_records 全量重导且已存在 entity 被覆盖
- [x] C3 验证覆盖安装返回数据保留提醒
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展覆盖安装" / Scenario "覆盖安装返回数据保留提醒"
  - Command: `pytest tests/core/unit/test_extension_install.py -k overwrite_data_warning`
  - Expect: 返回 dict 含 `overwrite=True` 与非空 `data_warning`
- [x] C4 验证覆盖安装仍校验依赖
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展覆盖安装" / Scenario "覆盖安装仍校验依赖"
  - Command: `pytest tests/core/unit/test_extension_install.py -k overwrite_missing_dependency`
  - Expect: 覆盖安装缺失依赖时抛出 missing dependencies

### Task 2: proto 与 gRPC 层 Install overwrite + Delete + ImportEntities

**Goal**: 扩展 `ExtensionService` proto，新增 overwrite 语义、Delete RPC、ImportEntities RPC，并实现 gRPC handler 与 client 方法。

**Files**:
- Modify: `proto/edera.proto`
- Modify: `packages/core/src/edera_core/grpc_extension_service.py`
- Modify: `packages/core/src/edera_core/grpc_client.py`
- Test: `tests/core/unit/test_grpc_extension_service.py`

**Requirements**:
- proto 新增 `ExtensionInstallRequest{name, overwrite}` message；`Install` RPC 改用该 message；新增 `Delete(NameRequest)` 与 `ImportEntities` RPC。
- `Install` handler 透传 `overwrite` 至 `ExtensionManager.install()`；默认 `overwrite=false` 对已安装返回 `FAILED_PRECONDITION`。
- `Delete` handler：查 `installed_extensions`，已安装返回 `FAILED_PRECONDITION`，否则 rmtree `_extensions_dirs[-1]/<name>`；不存在返回 `NOT_FOUND`。
- `ImportEntities` handler：解 tar（复用 `_extract_tar`）→ 读 manifest `imports.entities` → 合并为 `{entities:[...]}` → 调 `import_entities_from_yaml`，返回 imported/updated。
- `GrpcClient` 新增 `extension_install(name, overwrite)`、`extension_delete(name)`、`extension_import_entities(path)` 方法。

#### Checks

- [x] C5 验证 proto 定义含全部 RPC 与 overwrite 字段
  - Verifies: `specs/extension-grpc-service/spec.md` / Requirement "ExtensionService proto 定义" / Scenario "proto 定义包含所有 RPC"
  - Command: `grep -E "rpc (Install|Delete|ImportEntities)" proto/edera.proto && grep "overwrite" proto/edera.proto`
  - Expect: 输出含 Delete、ImportEntities RPC 及 overwrite 字段
- [x] C6 验证 Install RPC 覆盖安装与默认拒绝
  - Verifies: `specs/extension-grpc-service/spec.md` / Requirement "Install RPC" / Scenario "覆盖安装刷新运行态"
  - Command: `pytest tests/core/unit/test_grpc_extension_service.py -k install_overwrite`
  - Expect: overwrite=true 返回结果含 `overwrite=True`；overwrite=false 对已安装返回 FAILED_PRECONDITION
- [x] C7 验证 Delete RPC 拒绝已安装、删除未安装
  - Verifies: `specs/extension-grpc-service/spec.md` / Requirement "Delete RPC" / Scenario "删除已安装扩展被拒绝"
  - Command: `pytest tests/core/unit/test_grpc_extension_service.py -k delete_rpc`
  - Expect: 已安装返回 FAILED_PRECONDITION，未安装删除源目录，不存在返回 NOT_FOUND
- [x] C8 验证 ImportEntities RPC 按 id upsert
  - Verifies: `specs/extension-grpc-service/spec.md` / Requirement "ImportEntities RPC" / Scenario "导入实体数据按 id upsert"
  - Command: `pytest tests/core/unit/test_grpc_extension_service.py -k import_entities_rpc`
  - Expect: 返回 imported/updated 计数；非法包返回 INVALID_ARGUMENT

### Task 3: CLI install --overwrite / delete / import --overwrite

**Goal**: CLI 层补齐 `install --overwrite`、`delete <name>`、`import --overwrite` 三个入口。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `tests/core/unit/test_cli_extension.py`

**Requirements**:
- `install` subparser 新增 `--overwrite` flag，`_grpc_extension` 透传至 `client.extension_install(name, overwrite)`。
- `_extension_import` 新增 overwrite 参数：`target.exists()` 时默认拒绝，overwrite 则 `rmtree` 后 `copytree`。
- 新增 `delete` subparser 与 `_grpc_extension` 分支，调用 `client.extension_delete(name)`。

#### Checks

- [x] C9 验证 install --overwrite 透传
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展覆盖安装" / Scenario "覆盖安装重建扩展表与导入记录"
  - Command: `pytest tests/core/unit/test_cli_extension.py -k install_overwrite`
  - Expect: 带 --overwrite 的 install 触发覆盖路径，不带则对已安装拒绝
- [x] C10 验证 import --overwrite 替换目录
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "导入扩展目录支持覆盖" / Scenario "覆盖导入替换已有目录"
  - Command: `pytest tests/core/unit/test_cli_extension.py -k import_overwrite`
  - Expect: 同名目录默认拒绝，--overwrite 先 rmtree 再 copytree
- [x] C11 验证 delete 命令行为
  - Verifies: `specs/extension-grpc-service/spec.md` / Requirement "Delete RPC" / Scenario "删除未安装扩展源目录"
  - Command: `pytest tests/core/unit/test_cli_extension.py -k delete_command`
  - Expect: 删除未安装源目录成功，已安装报错提示先卸载

### Task 4: CLI import-entities 与 Web install overwrite

**Goal**: CLI 新增 `import-entities -f <tar>`；Web `POST /api/extensions/{name}/install` 支持 overwrite。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Modify: `packages/core/src/edera_core/web/routes.py`
- Test: `tests/core/unit/test_cli_extension.py`
- Test: `tests/core/unit/test_web_extensions.py`

**Requirements**:
- 新增 `import-entities` subparser（`-f/--file`），`_grpc_extension` 调 `client.extension_import_entities(path)`。
- Web `api_extension_install` 读取 body 的 `overwrite`（默认 false），透传 `client.extension_install(name, overwrite)`。
- Web 不暴露 delete 与 import-entities 端点（确认 routes 无新增）。

#### Checks

- [x] C12 验证 import-entities CLI 导入闭环
  - Verifies: `specs/extension-grpc-service/spec.md` / Requirement "ImportEntities RPC" / Scenario "导入实体数据按 id upsert"
  - Command: `pytest tests/core/unit/test_cli_extension.py -k import_entities_command`
  - Expect: export-entities 产出的 tar 经 import-entities 导回，entity 按 id upsert
- [x] C13 验证 Web install 支持 overwrite 并展示提醒
  - Verifies: `specs/extension-management-web/spec.md` / Requirement "安装操作" / Scenario "从页面覆盖安装已安装扩展"
  - Command: `pytest tests/core/unit/test_web_extensions.py -k install_overwrite`
  - Expect: POST install 带 `{"overwrite":true}` 触发覆盖安装，响应含 data_warning
- [x] C14 验证 Web 不暴露 delete/import-entities
  - Verifies: `specs/extension-management-web/spec.md` / Requirement "安装操作" / Scenario "从页面安装扩展"
  - Command: `grep -E "extensions/.*/(delete|import-entities)" packages/core/src/edera_core/web/routes.py || echo "no such routes"`
  - Expect: 无 delete / import-entities 的 Web 路由

### Task 5: 全量回归与跨层一致性

**Goal**: 确保三层行为一致、现有 install/uninstall/幂等路径未被破坏。

**Files**:
- Test: `tests/core/unit/test_extension_install.py`
- Test: `tests/core/unit/test_extension_uninstall.py`
- Test: `tests/core/unit/test_extension_entity_imports.py`

**Requirements**:
- 现有默认 install 幂等路径（skip_existing）未被破坏。
- 现有 uninstall 三策略未被破坏。
- overwrite → export-entities → import-entities 数据恢复闭环端到端可用。

#### Checks

- [x] C15 验证默认幂等导入未被破坏
  - Preserves: `openspec/specs/extension-entity-imports/spec.md` / Requirement "Extension entity imports are idempotent" / Scenario "Skip already imported path on default install"
  - Command: `pytest tests/core/unit/test_extension_entity_imports.py`
  - Expect: 默认安装跳过已有 import path，不覆盖 DB Entity
- [x] C16 验证 uninstall 三策略未被破坏
  - Preserves: `openspec/specs/extension-installation-lifecycle/spec.md` / Requirement "扩展卸载" / Scenario "purge 策略卸载"
  - Command: `pytest tests/core/unit/test_extension_uninstall.py`
  - Expect: purge/keep-modified/deactivate 三策略行为与变更前一致
- [x] C17 验证 overwrite 数据恢复闭环
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展覆盖安装" / Scenario "覆盖安装返回数据保留提醒"
  - Command: `pytest tests/core/unit/test_extension_install.py -k overwrite_restore_roundtrip`
  - Expect: export-entities 备份 → overwrite 安装 → import-entities 导回，运行时 entity 数据恢复
