## 1. Actions

- [x] A1 将核心包目录和 import 从 `stockimformation_core` 迁移到 `edera_core`
- [x] A2 将共享 types 包目录和 import 从 `stockimformation_types` 迁移到 `edera_types`
- [x] A3 更新 workspace/package metadata：`edera-core`、`edera-types`、`edera` console script、package descriptions 和 lockfile
- [x] A4 更新应用入口、dev/Docker 脚本和测试 monkeypatch 字符串，移除 `stockimformation` console script
- [x] A5 将项目配置环境变量前缀从 `STOCKIMFORMATION_` 改为 `EDERA_`
- [x] A6 更新默认数据库、workspace、daemon data dir 和临时 gRPC 生成目录为 `edera` 命名
- [x] A7 保留并校准 `rig` 控制面命名：CLI 名、daemon/gRPC 术语、`RIG_*` 身份/证书/连接变量不迁移
- [x] A8 更新 README 标题、项目定位、启动命令，并写入 `Edera` 名称来源说明
- [x] A9 更新活 OpenSpec 项目元数据和规格术语，不修改 `openspec/changes/archive/**`
- [x] A10 更新前端/Web API 展示名和 FastAPI title 为 `Edera`

## 2. Checks

- [x] C1 验证 Python 包命名迁移完成
  - Covers: A1, A2, A3, A4
  - Command: `rg -n "stockimformation_core|stockimformation_types|stockimformation-core|stockimformation-types|stockimformation =" pyproject.toml packages extensions tests scripts dev.sh Dockerfile docker-compose.yaml`
  - Expect: 无匹配；如文件不存在则不计为失败

- [x] C2 验证旧项目名残留只存在于 archive 或明确历史引用
  - Covers: A1, A2, A3, A4, A5, A6, A8, A9, A10
  - Command: `rg -n "stockImformation|stockimformation|STOCKIMFORMATION" README.md docs openspec/project.opsx.yaml openspec/specs packages apps config scripts tests pyproject.toml uv.lock`
  - Expect: 无匹配；不得通过修改 `openspec/changes/archive/**` 达成

- [x] C3 验证项目入口和控制 CLI 边界
  - Covers: A3, A4, A7
  - Command: `uv run edera --help`
  - Expect: `edera` console script 可解析；`stockimformation` console script 不存在；`rig --help` 仍可用

- [x] C4 验证后端测试通过
  - Covers: A1, A2, A3, A4, A5, A6, A7
  - Command: `uv run pytest`
  - Expect: Python 测试通过

- [x] C5 验证前端类型检查通过
  - Covers: A10
  - Command: `cd apps/web-console && npx tsc --noEmit`
  - Expect: TypeScript 类型检查通过

- [x] C6 验证 README 名称来源和定位
  - Covers: A8
  - Evidence: `README.md`
  - Expect: 包含 `Edera` 来源于 `Entity`、`DAG`、`Execution`、`Runtime`、`Architecture` 的说明，并包含“以 Entity 为统一原语、以 DAG 为执行模型的通用编排内核”

- [x] C7 验证配置前缀和默认路径
  - Covers: A5, A6
  - Command: `rg -n "EDERA_|data/edera\\.db|/tmp/edera|/var/lib/edera|edera-rig-grpc" packages config tests`
  - Expect: 能找到新命名；旧 `STOCKIMFORMATION_`、`stockimformation.db`、`/tmp/stockimformation` 不再出现于活代码/配置

- [x] C8 验证 OpenSpec change 有效
  - Covers: A9
  - Command: `openspec validate rename-project-to-edera --type change --json`
  - Expect: validation 无 error

- [x] C9 验证 archive 未被修改
  - Covers: A9
  - Command: `git diff --name-only -- openspec/changes/archive`
  - Expect: 无输出
