### Task 1: Manifest Schema 扩展

**Goal**: 扩展 manifest schema 支持 `type`、`imports.providers`、`imports.libraries` 字段和 glob patterns。

**Files**:
- Modify: `edera_core/bootstrap/manifest_schema.py`
- Modify: `edera_core/bootstrap/extension_loader.py`
- Test: `tests/bootstrap/test_manifest_schema.py`

**Requirements**:
- 新增 `type` 字段验证（workflow_extension | handler_provider）
- 新增 `imports.providers` 和 `imports.libraries` 字段（可选，list[str]）
- `imports.entities` 支持 glob patterns 展开

#### Checks

- [x] C1 验证 type 字段解析
  - Verifies: `specs/extension-manifest-system/spec.md` / Requirement "Manifest 文件解析" / Scenario "解析 type 字段"
  - Command: `pytest tests/bootstrap/test_manifest_schema.py::test_parse_type_field -v`
  - Expect: 测试通过，type: workflow_extension 解析正确

- [x] C2 验证 imports.providers glob 展开
  - Verifies: `specs/extension-manifest-system/spec.md` / Requirement "Manifest 文件解析" / Scenario "解析 imports.providers 并展开 glob"
  - Command: `pytest tests/bootstrap/test_manifest_schema.py::test_expand_providers_glob -v`
  - Expect: 测试通过，_providers/*/manifest.yaml 正确展开

- [x] C3 验证 glob pattern 无匹配时报错
  - Verifies: `specs/extension-manifest-system/spec.md` / Requirement "Manifest 文件解析" / Scenario "Glob pattern 无匹配时报错"
  - Command: `pytest tests/bootstrap/test_manifest_schema.py::test_glob_no_match_error -v`
  - Expect: 测试通过，无匹配时抛出错误

### Task 2: Extension Loader 改造

**Goal**: Extension Loader 识别 workflow_extension 类型并递归处理内部 providers 和 libraries。

**Files**:
- Modify: `edera_core/bootstrap/extension_loader.py`
- Test: `tests/bootstrap/test_extension_loader.py`

**Requirements**:
- 识别 `type: workflow_extension` 并递归处理 `imports.providers`
- 展开 glob patterns（`**/*.yaml`, `*/manifest.yaml`）
- 复制 `imports.libraries` 到 `data/libs/{package}.{library}/`
- 解析 provider 相对路径依赖（`depends: ["_lib/http_fetch"]`）
- 记录所有 provider handlers 到主扩展的 `manifest_snapshot`

#### Checks

- [x] C4 验证 workflow extension 递归安装 providers
  - Verifies: `specs/workflow-extension-type/spec.md` / Requirement "Workflow extension 支持 imports.providers 声明" / Scenario "安装 workflow extension 时递归安装 providers"
  - Command: `pytest tests/bootstrap/test_extension_loader.py::test_install_workflow_extension -v`
  - Expect: 测试通过，7 个 providers 的 handlers 安装到命名空间路径

- [x] C5 验证 libraries 复制
  - Verifies: `specs/workflow-extension-type/spec.md` / Requirement "Workflow extension 支持 imports.libraries 声明" / Scenario "安装 workflow extension 时复制 libraries"
  - Command: `pytest tests/bootstrap/test_extension_loader.py::test_copy_libraries -v`
  - Expect: 测试通过，_lib/http_fetch 复制到 data/libs/{package}.http_fetch/

- [x] C6 验证 provider 相对路径依赖解析
  - Verifies: `specs/workflow-extension-type/spec.md` / Requirement "Workflow extension 支持 imports.providers 声明" / Scenario "Provider depends 相对路径解析"
  - Command: `pytest tests/bootstrap/test_extension_loader.py::test_provider_relative_deps -v`
  - Expect: 测试通过，depends: ["_lib/http_fetch"] 正确解析

### Task 3: Handler 命名空间路径

**Goal**: Handler 安装路径改为 `{package}.{handler}` 命名空间格式，DatabaseHandlerResolver 适配查找逻辑。

**Files**:
- Modify: `edera_core/runtime/database_handler_resolver.py`
- Modify: `edera_core/bootstrap/extension_loader.py`
- Test: `tests/runtime/test_database_handler_resolver.py`

**Requirements**:
- Handler 安装到 `data/handlers/{package}.{handler}/`
- DatabaseHandlerResolver 支持命名空间路径查找
- `manifest_snapshot` 记录完整命名空间路径

#### Checks

- [x] C7 验证独立扩展 handler 命名空间
  - Verifies: `specs/handler-namespace/spec.md` / Requirement "Handler 使用命名空间路径格式" / Scenario "独立扩展的 handler 命名空间"
  - Command: `pytest tests/runtime/test_database_handler_resolver.py::test_resolve_standalone_handler -v`
  - Expect: 测试通过，uzi-skill.legacy-script-adapter 正确解析

- [x] C8 验证 workflow provider handler 命名空间
  - Verifies: `specs/handler-namespace/spec.md` / Requirement "Handler 使用命名空间路径格式" / Scenario "Workflow extension 内部 provider 的 handler 命名空间"
  - Command: `pytest tests/runtime/test_database_handler_resolver.py::test_resolve_provider_handler -v`
  - Expect: 测试通过，default-news-workflow.rss-fetcher 正确解析

- [x] C9 验证命名空间避免冲突
  - Verifies: `specs/handler-namespace/spec.md` / Requirement "Handler 命名空间避免冲突" / Scenario "不同包的同名 handler 不冲突"
  - Command: `pytest tests/runtime/test_database_handler_resolver.py::test_namespace_no_conflict -v`
  - Expect: 测试通过，不同包的 reader handler 不冲突

### Task 4: Extension CLI 适配

**Goal**: Extension CLI 命令适配 workflow extension，export 打包 _providers/ 和 _lib/，install 输出 provider 进度。

**Files**:
- Modify: `edera_core/cli/extension.py`
- Test: `tests/cli/test_extension_commands.py`

**Requirements**:
- `edera extension export` 打包 _providers/ 和 _lib/ 目录
- `edera extension install` 输出 provider 安装进度
- 支持 workflow extension 的 import/export 完整性

#### Checks

- [x] C10 验证 export 包含 providers
  - Verifies: `specs/extension-cli-commands/spec.md` / Requirement "extension export 命令" / Scenario "导出 workflow extension 包含 providers"
  - Command: `pytest tests/cli/test_extension_commands.py::test_export_workflow_extension -v`
  - Expect: 测试通过，导出包包含 _providers/ 和 _lib/ 结构

- [x] C11 验证 install 递归处理进度输出
  - Verifies: `specs/extension-cli-commands/spec.md` / Requirement "extension install 命令" / Scenario "安装 workflow extension 递归处理 providers"
  - Command: `pytest tests/cli/test_extension_commands.py::test_install_workflow_progress -v`
  - Expect: 测试通过，输出包含 provider 安装进度和汇总信息

### Task 5: Extension gRPC Service 适配

**Goal**: ExtensionService RPC 支持 workflow_extension 类型，递归处理 providers 和展开 glob patterns。

**Files**:
- Modify: `edera_core/grpc/extension_service.py`
- Test: `tests/grpc/test_extension_service.py`

**Requirements**:
- InstallExtension RPC 识别 workflow_extension
- 递归读取 provider manifests 并安装 handlers
- 展开所有 glob patterns

#### Checks

- [x] C12 验证 InstallExtension RPC 处理 workflow extension
  - Verifies: `specs/extension-grpc-service/spec.md` / Requirement "InstallExtension RPC 支持 workflow extension" / Scenario "安装 workflow extension 递归处理 providers"
  - Command: `pytest tests/grpc/test_extension_service.py::test_install_workflow_extension_rpc -v`
  - Expect: 测试通过，RPC 正确安装 workflow extension 及其 providers

- [x] C13 验证 glob pattern 展开失败报错
  - Verifies: `specs/extension-grpc-service/spec.md` / Requirement "InstallExtension RPC 支持 workflow extension" / Scenario "安装时 glob pattern 无匹配"
  - Command: `pytest tests/grpc/test_extension_service.py::test_glob_no_match_rpc_error -v`
  - Expect: 测试通过，返回 gRPC error 包含未匹配的 pattern

### Task 6: 目录结构重组

**Goal**: 重组 extensions/ 为两个 workflow extension 包，更新 manifest 文件使用 glob patterns。

**Files**:
- Modify: `extensions/default-news-workflow/manifest.yaml`
- Modify: `extensions/uzi-skill/manifest.yaml`
- Create: `extensions/default-news-workflow/_providers/`
- Create: `extensions/default-news-workflow/_lib/`

**Requirements**:
- 移动 7 个 handler providers 到 `default-news-workflow/_providers/`
- 移动 `_lib/http_fetch` 到 `default-news-workflow/_lib/`
- 更新 manifest 文件使用 glob patterns
- web-scraper 归入 default-news-workflow 包

#### Checks

- [x] C14 验证目录重组完整性
  - Verifies: `specs/default-news-workflow/spec.md` / Requirement "Default news workflow extension package" / Scenario "Manifest 声明内部 providers"
  - Evidence: `find extensions/default-news-workflow/_providers -name manifest.yaml`
  - Expect: 输出 7 个 provider manifest 文件路径

- [x] C15 验证 default-news-workflow manifest 使用 glob
  - Verifies: `specs/default-news-workflow/spec.md` / Requirement "Default news workflow extension package" / Scenario "Manifest 使用 glob patterns 声明 entities"
  - Evidence: `grep "entities/\*\*/\*.yaml" extensions/default-news-workflow/manifest.yaml`
  - Expect: manifest 包含 glob pattern

- [x] C16 验证 uzi-skill manifest 使用 glob
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "UZI-Skill workflow extension imports" / Scenario "Manifest 使用 glob pattern 导入所有 entities"
  - Evidence: `grep "entities/\*\*/\*.yaml" extensions/uzi-skill/manifest.yaml`
  - Expect: manifest 包含 glob pattern，替代 59 行手动列举

### Task 7: 迁移测试与回归验证

**Goal**: 执行完整迁移流程，验证扩展卸载重装和 DAG 运行正常。

**Files**:
- Test: `tests/integration/test_extension_migration.py`

**Requirements**:
- 卸载所有现有扩展
- 重新安装 default-news-workflow 和 uzi-skill
- 验证 entity 数量和 handler 路径
- 运行 default DAG 和 uzi-skill-analysis DAG

#### Checks

- [x] C17 验证扩展重装完整性
  - Verifies: `specs/extension-installation-lifecycle/spec.md` / Requirement "扩展安装" / Scenario "安装 workflow extension 时递归处理 providers"
  - Command: `edera extension uninstall default-news-workflow --strategy=purge && edera extension install default-news-workflow`
  - Expect: 输出显示 7 个 providers 安装成功，14 个 entities 导入

- [x] C18 验证 default DAG 运行
  - Verifies: `specs/default-news-workflow/spec.md` / Requirement "Default workflow seed sources are extension-owned" / Scenario "Source seeds imported with workflow"
  - Command: `edera dag run default --wait`
  - Expect: DAG 运行成功，所有节点状态为 completed

- [x] C19 验证 uzi-skill DAG 运行
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "UZI-Skill workflow extension imports" / Scenario "Imported UZI trigger targets DAG"
  - Command: `edera dag run uzi-skill-analysis --wait`
  - Expect: DAG 运行成功，sub-DAG 执行正常
