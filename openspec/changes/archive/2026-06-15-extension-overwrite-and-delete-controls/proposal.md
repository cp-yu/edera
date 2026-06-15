## Why

当前 extension 生命周期入口将「覆盖安装」「卸载」「删除源目录」三种语义混用：已安装 extension 重复 install 一律拒绝、`import` 同名目录直接失败、删除 `extensions/<name>` 源目录没有任何受控入口（只能 `rm -rf` 绕过运行态检查）。这导致用户无法热替换已安装扩展、无法安全移除不再使用的源目录，且任何「重新安装」尝试都会因为幂等导入语义而静默跳过 entity 更新。

## What Changes

- 新增**覆盖安装**语义：`install <name> --overwrite` 对已安装 extension 执行 drop 扩展表 + 全量重导 entity + 重建 handlers/libs + upsert `installed_extensions` 记录。
- 新增**删除源目录**入口：`extension delete <name>` 删除 `extensions/<name>` 源目录，**仅允许针对未安装的 extension**（已安装一律拒绝，无 `--force` 逃生口）。
- `import <path>` 新增 `--overwrite`：目标 `extensions/<name>` 已存在时，默认拒绝，`--overwrite` 则先 `rmtree` 再 `copytree`。
- 新增 `import-entities -f <tar>` 命令，吃 `export-entities` 产生的 tar 包，作为 overwrite 后用户自行恢复运行时 entity 数据的入口（与 `export-entities` 对称）。
- **BREAKING（语义层）**：overwrite 安装会重建扩展表并清空旧 `import_records` 全量重导，这改变了 `extension-entity-imports` 现有的「重新安装一律跳过」「不覆盖已有 Entity」幂等承诺。overwrite 是用户显式触发的非幂等路径；默认 install 路径仍保持幂等。

## Capabilities

### New Capabilities

（无新增 capability，全部复用现有 extension capability 集合。）

### Modified Capabilities

- `extension-installation-lifecycle`：新增「覆盖安装」「删除源目录」「import 覆盖」三类行为 Requirement；原有「重复安装已有扩展」Requirement 收窄为「默认拒绝，overwrite 例外」。
- `extension-entity-imports`：MODIFIED「Extension entity imports are idempotent」与「Record existing entity without overwrite」——默认路径维持幂等，overwrite 路径全量重导（清空旧 import_records、强制覆盖已有 Entity）。
- `extension-grpc-service`：Install RPC 增加 overwrite 语义；新增 Delete RPC 与 ImportEntities RPC。
- `extension-management-web`：`POST /api/extensions/{name}/install` 支持 overwrite 参数。（delete 与 import-entities 不暴露 Web，仅 CLI+gRPC。）

## Impact

- **代码**：`ExtensionManager.install()` 增加 `overwrite` 参数与覆盖路径；`extension_manager.py` / `cli.py` / `grpc_extension_service.py` / `grpc_client.py` / `web/routes.py`；新增 import-entities 解包逻辑（复用 `_extract_tar` + `import_entities_from_yaml`）。
- **proto**：`edera.proto` `ExtensionService` 新增 `Delete`、`ImportEntities` RPC；`Install` 引入 overwrite 语义（新增专用 message 或复用 `NamedJsonRequest`，由 design.md 定夺）。
- **数据**：overwrite 时 `ext_<name>_*` 扩展表 drop+rebuild、`installed_extensions.import_records` 重置、运行时 entity 数据被 manifest 初始值覆盖。
- **测试**：`test_extension_install.py` / `test_cli_extension.py` / `test_grpc_extension_service.py` 补齐 overwrite、delete、import-entities 场景。
