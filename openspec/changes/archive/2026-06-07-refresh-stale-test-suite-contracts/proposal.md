## Why

部分单元测试仍断言旧的运行时和 CLI 契约，例如 `NodeExecutor` 无 `snapshot` 构造、`RuntimeControlSnapshot.config`、本地 YAML import 路径和已移除的 registry 类型。这些过期断言让广泛回归运行产生噪音，并掩盖真实失败。

同时，少量 OpenSpec 文本仍保留旧 registry 语义，和当前 OPSX intent、实现、较新的 specs 冲突；如果不清理，后续测试维护会继续被旧契约带偏。

## What Changes

- 更新 issue 点名的 stale tests，使其断言当前 `DagExecutionSnapshot`、gRPC service、CLI import 和 bootstrap 契约。
- 将 CLI running-server 测试拆成纯 gRPC 查询路径验证，以及显式 import/seed 后实体可查验证。
- 清理 `core-bootstrap` 和 `node-executor` 中直接冲突的 registry 描述，保留当前 DB-backed manifest 与 `DatabaseHandlerResolver` 语义。
- 保留 `test_web_bootstrap_discovery.py` 和 `packages/core/tests/test_bootstrap_with_existing_cert.py` 在验收命令中，防止 bootstrap/BFF 边界回归。
- 不修改应用运行时行为，不恢复 `edera_core.registry`，不为旧 `NodeExecutor(..., handlers=...)` 增加兼容 shim。

## Capabilities

### New Capabilities

### Modified Capabilities
- `core-bootstrap`: 将 bootstrap 行为从构建内存 registry 改为扫描 manifest、持久化 metadata、维护 module path，并去除 registry 原子替换契约。
- `node-executor`: 将旧的 handler registry 执行描述改为基于 `DagExecutionSnapshot.handler_resolver` 的 Node Entity 执行契约。
- `edera-cli`: 明确 CLI entity import 通过 `GrpcClient.entity_import` 提交完整 Entity YAML，并区分 gRPC 查询路径和显式导入后的实体可查行为。
- `edera-server-grpc`: 明确 bootstrap 端口 fallback 和 `bootstrap.json` 可作为独立 server bootstrap 契约验证，不依赖 registry fake。

## Impact

- Tests:
  - `tests/core/unit/test_core_architecture_overhaul.py`
  - `tests/core/unit/test_cli.py`
  - `tests/core/unit/test_bootstrap_fallback.py`
  - `tests/core/unit/test_web_bootstrap_discovery.py`
  - `packages/core/tests/test_bootstrap_with_existing_cert.py`
- Specs:
  - `openspec/specs/core-bootstrap/spec.md`
  - `openspec/specs/node-executor/spec.md`
  - `openspec/specs/edera-cli/spec.md`
  - `openspec/specs/edera-server-grpc/spec.md`
- No new dependencies.
- No application-code compatibility layer.
