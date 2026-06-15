## Context

Extension 系统当前的生命周期入口分布在三层：CLI（`edera_core/cli.py`，argparse）、gRPC（`proto/edera.proto` + `grpc_extension_service.py` + `grpc_client.py`）、Web（`web/routes.py`）。`ExtensionManager.install()` 是安装的唯一实现，`extension_manager.py:59` 对已安装 extension 直接 `raise ValueError`，且 entity 导入遵循幂等语义（`import_entities_from_yaml` + import_records 跳过已存在 path）。删除 `extensions/<name>` 源目录没有任何受控入口。

本 change 补齐三类操作：覆盖安装、删除源目录、数据导入（与 export-entities 对称）。开发阶段无历史负担，可自由定义语义边界。

## Goals / Non-Goals

**Goals:**
- 显式区分「覆盖安装」「卸载」「删除源目录」三个操作，每个有明确的作用对象与边界。
- overwrite 安装能完整刷新 handlers/libs/import_records/installed_extensions/扩展表。
- delete 仅作为文件系统层操作，绝不触碰运行态。
- 提供与 export-entities 对称的 import-entities，让用户在 overwrite 后自行恢复运行时 entity 数据。
- CLI、gRPC、Web 行为一致（delete 与 import-entities 仅 CLI+gRPC，不暴露 Web）。

**Non-Goals:**
- **不做 schema migration 引擎**：不实现列映射、JSON 拆列识别、ALTER TABLE 迁移。扩展表的 schema 漂移由 overwrite 的 drop+rebuild 兜底，旧数据不自动保留。
- **不在 overwrite 流程内自动备份/迁移数据**：数据保留完全交还用户，仅提供 import-entities 入口。
- **delete 不处理已安装 extension**：已安装一律拒绝，无 `--force` 逃生口。
- **不暴露 Web 端 delete / import-entities**：与纯文件/数据操作的定位一致。

## Decisions

### Decision 1: overwrite = drop+rebuild+全量重导，不做数据迁移

overwrite 安装路径在已安装时的处理：drop `ext_<name>_*` 扩展表 → 清空旧 `import_records` → 按新 manifest 全量重导 entity → handlers/libs 走现有 rmtree 重建 → `installed_extensions` upsert。返回报告含 `data_warning`，明确告知扩展表运行时数据已重建、如需保留请用 export-entities/import-entities 迁移。

**Rationale**：覆盖安装的语义是「替换代码与定义」，运行时数据（用户在 ext 表中累积的行、对 manifest 初始 entity 的修改）按「恢复到 manifest 初始状态」处理。任何更精细的保留都需要区分「定义字段」与「数据字段」，当前 EntityStore/EntityType 模型没有这个边界。

**Alternatives considered**：
- *完整 schema migration 引擎*（对比新旧 manifest table 定义、JSON 列拆列保留、兼容/不兼容判定）：被否决。这会把「补齐控制入口」膨胀成「数据迁移引擎」，违反 YAGNI，且「JSON 列拆独立列算兼容」需要可机器判定的锚点（命名前缀 / manifest 显式标注），任一方案都引入新的复杂性。数据迁移交还用户 + import-entities 入口是更小的正确解。
- *uninstall(purge)-then-install*：被否决。purge 会销毁用户运行时数据，而 overwrite 的心智是「保留数据」，语义冲突。
- *纯刷新（只换代码，entity/表 skip_existing）*：被否决。这会让 `--overwrite` 对 entity 数据成为谎言，新版本 entity 定义不生效。

### Decision 2: delete 仅允许未安装 extension，无 --force

`extension delete <name>` 删除 `_extensions_dirs(daemon)[-1]/<name>`。前置检查：若 `installed_extensions` 存在该 name 的记录，拒绝（gRPC `FAILED_PRECONDITION`）。无 `--force` 参数。

**Rationale**：delete 是纯文件系统操作。若允许删已安装 extension 的源目录，会制造 handler 悬空引用与状态不一致（`handlers_dir/<name>.*` 拷贝仍在、`installed_extensions` 记录仍在）。未安装的 extension 不可能出现在任何 dependents 链（dependents 是 installed 记录间依赖），所以「未安装」前置检查已隐含排除依赖破坏。

**Alternatives considered**：
- *--force 走 uninstall(purge) 后删除*：被否决。purge 静默销毁用户数据，与「避免静默破坏运行时状态」的验收标准冲突。
- *--force 配合 --strategy*：被否决。让 delete 的接口复杂化，且用户需要彻底移除时可以显式 `uninstall` 后再 `delete`。

### Decision 3: import --overwrite 用 rmtree+copytree

`_extension_import` 命中 `target.exists()` 时，默认拒绝；`--overwrite` 则 `shutil.rmtree(target)` 后 `copytree`。

**Rationale**：与 install overwrite 的「替换」语义一致。不用 `dirs_exist_ok=True`，避免新旧目录文件残留混合。

### Decision 4: proto 用专用 message 表达 overwrite

`Install` 当前用 `NameRequest`。引入 overwrite 时新增专用 message（如 `ExtensionInstallRequest{name, overwrite}`）而非复用 `NamedJsonRequest` 传 JSON。

**Rationale**：overwrite 是稳定语义而非临时参数，proto 显式声明优于 JSON 约定，类型安全且自文档。`Delete` 与 `ImportEntities` 用 `NameRequest` / 新增 message。

**Alternatives considered**：
- *复用 `NamedJsonRequest` 传 `{"overwrite":bool}`*：被否决。与 `Uninstall` 的 strategy JSON 风格一致，但牺牲类型安全，且 overwrite 是布尔标志不是结构化 payload。

### Decision 5: import-entities 吃 tar 包，与 export-entities 对称

`import-entities -f <tar>` 解 tar（复用 `_extract_tar`）→ 定位 `manifest.yaml` 读 `imports.entities` → 合并所有 entity yaml 为 `{entities:[...]}` → 调现有 `import_entities_from_yaml`（按 id upsert，返回 imported/updated 计数）。

**Rationale**：与现有 `export-entities`（产出 tar：`manifest.yaml` + `entities/<type>-<id>.yaml`）严格对称，形成 `export → overwrite → import` 数据恢复闭环。复用现成 `import_entities_from_yaml`，后端增量最小。

**Alternatives considered**：
- *吃单 YAML `{entities:[...]}`*（复用 storage 层 `export_entities_to_yaml`/`import_entities_from_yaml`，零后端代码）：被否决。与现有 CLI `export-entities` 的 tar 输出不对称，用户备份与恢复格式不匹配。
- *支持两种格式*：被否决。接口与测试复杂度上升，无额外价值。

### Decision 6: delete 与 import-entities 不暴露 Web

仅 CLI+gRPC。delete 删的是 daemon 端源目录（必须经 gRPC），但其定位是纯文件操作，不进 Web 控制台。import-entities 是数据导入，同理。

**Rationale**：Web 控制台面向运行态管理（install/uninstall/查看），源目录删除与批量数据导入属于运维操作，暴露 Web 会扩大攻击面且与控制台定位不符。

## Risks / Trade-offs

- **[overwrite 丢失扩展表运行时数据]** → 设计如此。`data_warning` 明确提醒 + import-entities 提供恢复入口；用户可在 overwrite 前先 `export-entities` 备份。文档需强调此工作流。
- **[overwrite 违反现有幂等承诺]** → 直接 MODIFIED `extension-entity-imports` 的 idempotent / no-overwrite 两个 Requirement。默认 install 路径维持幂等，仅 overwrite 显式触发非幂等。
- **[overwrite 时 import_records 全量重导覆盖用户对初始 entity 的修改]** → 与上一条同源，overwrite 语义即「恢复到 manifest 初始状态」。
- **[proto 新增 message 需重新生成 `edera_pb2`]** → 标准 protobuf codegen 流程，已有 `NamedJsonRequest` 等先例。
- **[delete 不检查 dependents]** → 未安装 extension 不在 dependents 链，「未安装」前置检查已隐含排除，无需额外检查。

## Migration Plan

开发阶段无历史负担，无需数据迁移。proto 改动后重新生成 `edera_pb2`/`edera_pb2_grpc`。现有 install/uninstall 调用方无需改动（overwrite 默认 false，向后兼容）。

## Open Questions

（explore 阶段已全部澄清，无遗留。）
