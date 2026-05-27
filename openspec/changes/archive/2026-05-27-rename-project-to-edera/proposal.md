## Why

项目目标已从股票信息管道转为以 Entity 为统一原语、以 DAG 为执行模型的通用编排内核，`stockImformation` 名称和包命名已经误导项目定位。当前处于开发阶段，无需保留旧包名、命令名、环境变量前缀或默认数据路径的向后兼容。

## What Changes

- **BREAKING** 将项目 canonical name 改为 `Edera`，canonical slug 改为 `edera`。
- **BREAKING** 将 Python 包、分发包、默认启动命令、环境变量前缀、默认数据库/工作目录路径和 OpenSpec project id 统一迁移到 `edera` 命名。
- 保留 `rig` 作为控制面 CLI 名称和 daemon/gRPC 术语；`edera` 作为项目主入口命令，`rig` 作为操作控制命令。
- README MUST 解释 `Edera` 名称来源：它源自 `Entity`、`DAG`、`Execution`、`Runtime`、`Architecture` 的组合，并借用 ivy（常春藤）连接、攀附、延展的隐喻。
- 活 OpenSpec 术语同步到新定位：项目描述去除股票主线，保留金融/信息采集内容为示例或可配置应用域，而不是项目身份。
- 不修改 `openspec/changes/archive/**` 历史制品。

## Capabilities

### New Capabilities
- `project-identity`: 项目 canonical identity、包命名、命令名、环境变量前缀、默认路径、README 名称来源说明和 OpenSpec project 元数据。

### Modified Capabilities
- `core-bootstrap`: 核心启动入口和包命名从 `stockimformation_core` 迁移为 `edera_core`。
- `handler-context-protocol`: 共享 extension protocol 包从 `stockimformation-types` / `stockimformation_types` 迁移为 `edera-types` / `edera_types`。
- `rig-cli`: 保留 `rig` 控制 CLI，同时增加/确认 `edera` 项目主入口命令；证书和 daemon 相关 `RIG_*` 环境变量继续归属控制面。
- `daemon-data-directory`: daemon 默认数据目录从 `rig` 控制面目录语义收敛为 `edera` 项目数据目录；明确 `RIG_*` 控制面 env 与 `EDERA_*` 项目配置 env 的边界。
- `local-web-console`: Web API / FastAPI title / Web Console 展示名使用 `Edera`。

## Impact

- `pyproject.toml`, `uv.lock`, `packages/core/pyproject.toml`, `packages/core-types/pyproject.toml`: workspace 包名、分发包名、scripts、描述更新。
- `packages/core/src/stockimformation_core/**`, `packages/core-types/src/stockimformation_types/**`: 包目录、import、测试 monkeypatch 和动态模块名迁移到 `edera_core` / `edera_types`。
- `extensions/**`, `tests/**`, `scripts/**`, `dev.sh`, `Dockerfile`, `docker-compose.yaml`: import、命令、路径和服务名同步。
- `config/system.toml`, `packages/core/src/.../config/schema.py`, `grpc_runtime.py`: 默认数据库路径、workspace 路径、临时生成目录和 `STOCKIMFORMATION_` env prefix 迁移到 `edera` / `EDERA_`。
- `README.md`: 标题、启动命令、项目定位和 `Edera` 名称来源说明更新。
- `openspec/project.opsx.yaml`, `openspec/specs/**`: 活项目元数据和受影响规格更新；不修改 archive。
