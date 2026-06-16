## Why

「哪些能力该不该暴露 Web」目前只以一次性 Decision 的形式埋在已 archive 的 change design 里（`2026-06-15-extension-overwrite-and-delete-controls` Decision 6：delete 与 import-entities 仅 CLI+gRPC）。这条分层暴露准则无法被后续 change 复用与引用，导致新 agent 表述"CLI 和 gRPC"时易产生歧义。需将其提升为 Web BFF 的通用准入准则。

## What Changes

- 在 `edera-web-bff` spec 新增一条 Requirement，确立「运行态管理 vs 运维操作」的分类准则：运维操作（如 daemon 端源目录删除、批量数据导入）SHALL 仅经 CLI+gRPC 暴露，MUST NOT 注册 HTTP route。
- 仅写通用判断准则，不列具体操作清单（避免准则腐化）。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `cap.web.edera-web-bff`: 新增「运维操作不暴露 Web」Requirement，确立 Web BFF 的能力准入边界。

## Impact

- 仅影响 spec 文档 `openspec/specs/edera-web-bff/spec.md`。
- 不改代码、不新增/移除 HTTP route、不动 gRPC service。
- 该准则的执行依赖 propose/review 阶段套用判断，无运行时行为变化。
