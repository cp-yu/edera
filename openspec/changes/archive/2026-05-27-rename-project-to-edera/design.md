## Context

当前仓库仍以 `stockImformation` / `stockimformation_core` / `stockimformation_types` 命名，但活 OpenSpec 已经把系统重心推进到通用 Entity、DAG、Trigger、Agent runtime、rig daemon/CLI 和 Web Console。旧名称不仅拼写错误，也把项目身份锁在股票信息场景上。

用户明确当前仍处开发阶段，无需向后兼容。因此本次按一次性破坏性迁移处理：旧包名、旧命令、旧环境变量前缀、旧默认数据路径不保留 alias。

## Goals / Non-Goals

**Goals:**
- 将 canonical project name 统一为 `Edera`，slug 统一为 `edera`。
- 将 Python import 包、分发包、workspace 配置、默认启动命令、默认路径和 OpenSpec 元数据统一迁移到 `edera`。
- 在 README 中解释 `Edera` 名称来源和项目定位。
- 保留 `rig` 作为控制面 CLI / daemon / gRPC 术语，避免把已有控制面语义打散。
- 同步活 OpenSpec 术语，不修改 `openspec/changes/archive/**`。

**Non-Goals:**
- 不提供 `stockimformation_*` import alias。
- 不保留 `stockimformation` console script。
- 不迁移旧数据库文件或旧运行目录。
- 不做商标、域名、包注册可用性检查。
- 不借机重构非命名相关架构。

## Decisions

### D1: `Edera` 是项目身份，`rig` 是控制面命令

`Edera` 作为项目名、包名前缀、环境变量前缀和默认数据路径。`rig` 保留为控制面 CLI，因为它已经承载 daemon/gRPC/mTLS/entity 操作语义。

替代方案：把 `rig` 也改为 `edera` 子命令。否决：`rig` 短、清晰，且已经是控制面领域语言；全量替换会降低命令可读性。

### D2: 全包名迁移，不做兼容层

`stockimformation_core` 迁移为 `edera_core`，`stockimformation_types` 迁移为 `edera_types`。对应分发包迁移为 `edera-core` 和 `edera-types`。

替代方案：保留旧包名 re-export。否决：开发阶段无兼容要求，alias 只会留下双命名面。

### D3: `EDERA_*` 管项目配置，`RIG_*` 管控制面身份和连接

`STOCKIMFORMATION_` env prefix 迁移为 `EDERA_`。已有 `RIG_*` 环境变量不迁移，因为它们表达 rig CLI/daemon/BFF/mTLS 控制面身份、证书和连接配置。

边界：
- `EDERA_PI_BIN` 属于应用运行时配置。
- `RIG_CLIENT_CERT` / `RIG_CLIENT_KEY` / `RIG_CA_CERT` / `RIG_DAEMON_ADDR` / `RIG_IDENTITY` 保持控制面命名。
- daemon 默认 data dir 采用 `edera` 项目目录，但 mTLS 文件变量仍为 `RIG_*`。

### D4: 默认数据路径一次性改名

默认数据库、workspace、临时 gRPC 生成目录迁移到 `edera`：
- `data/edera.db`
- `/tmp/edera/runs`
- `${tempdir}/edera-rig-grpc`
- `/var/lib/edera` 或 `~/.local/share/edera`

不做旧路径查找或迁移脚本。开发阶段旧数据可手动删除或重跑生成。

### D5: README 名称来源必须写明

README SHALL 写明：
- `Edera` 源自 `Entity`、`DAG`、`Execution`、`Runtime`、`Architecture`。
- `edera` 在意大利语中有 ivy（常春藤）含义；项目借用连接、攀附、延展的隐喻。
- 项目定位为“以 Entity 为统一原语、以 DAG 为执行模型的通用编排内核”。

## Risks / Trade-offs

- [Risk] 全包名迁移会产生大量 import 和 monkeypatch 字符串改动 → Mitigation：使用全仓精确搜索，完成后运行 Python 测试、前端类型检查和 `rg stockimformation` 残留检查。
- [Risk] `rig` 与 `edera` 双名称可能混淆 → Mitigation：README 和 specs 明确 `Edera` 是项目，`rig` 是控制面 CLI。
- [Risk] `RIG_*` 保留会看起来没有彻底改名 → Mitigation：只保留控制面身份/证书/连接变量，项目配置变量全部改为 `EDERA_*`。
- [Risk] OpenSpec 仍有金融/股票规格 → Mitigation：本次只清理项目身份和名称；业务域规格另行决定是否删除或转为示例。

## Migration Plan

1. 移动包目录：`stockimformation_core` → `edera_core`，`stockimformation_types` → `edera_types`。
2. 更新所有 imports、测试 monkeypatch 字符串、pyproject workspace、console scripts 和 lockfile。
3. 更新默认 env prefix、数据库路径、workspace 路径、daemon data dir 和临时生成目录。
4. 更新 README、OpenSpec project metadata 和活规格中的项目身份术语。
5. 运行验证：后端测试、前端类型检查、OpenSpec validate、残留旧名搜索。

Rollback：开发阶段直接 revert change commit；不提供运行时数据回滚。
