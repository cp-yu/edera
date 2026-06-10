## Context

`packages/core/src/edera_core/cli.py` 已集中注册 `entity`、`relation`、`entity-type`、`skill`、`dag`、`event`、`system`、`extension` 等命令，`GrpcClient` 已封装部分本次需要的服务端能力。本阶段聚焦运行控制命令入口和 workflow extension export 包结构。

## Goals / Non-Goals

**Goals:**
- 用最小改动提供本阶段运行控制 CLI 行为，不新增第二阶段的完整 control-plane 命令族。
- 复用现有 gRPC client 和服务端 RPC，不改 proto schema。
- 保持 CLI 的 JSON stdout 和错误 stderr 约定。
- 用单元测试覆盖新增 CLI 参数、文件输出和 extension package 内容。

**Non-Goals:**
- 不新增 `edera config`、`edera query`、`edera handler`、`edera node-type`、`edera dag list/show/create/save/import/export` 等完整控制面命令。
- 不改变 `NodeService.Output` 的业务输出语义。
- 不重构 CLI 框架或拆分文件。

## Decisions

- 在现有 argparse CLI 内扩展命令，不引入新 CLI 框架。当前 CLI 已经是单文件集中调度，局部扩展能避免无关迁移风险。
- `edera node output export` 走已有业务输出查询路径，并只负责将 payload 写入用户指定文件；日志仍由 `edera node logs` 查询，避免把 execution logs 混入业务输出。
- `edera dag retry` 复用 `GrpcClient.dag_retry` 已有的 `source_shared_inputs`、`node_inputs`、`append_nodes` 参数，只扩展 parser 和 dispatch 传参。
- source repair task 挂在 `edera system repair-source <source_name>`，因为底层能力属于 `SystemService.CreateRepairTask`，且 source health CLI 的完整查询面属于第二阶段。
- workflow extension export 以已有 `extension export` 为入口收紧打包内容：providers 放入 `_providers/`，libraries 放入 `_lib/`，缺失代码继续通过 warnings 返回。

## Risks / Trade-offs

- `node output export` 的输出选择可能遇到多条 output。→ 明确导出服务端返回的业务输出 payload 集合，后续如需单条选择再单独扩展过滤参数。
- `repair-source` 缺少配套 source health 查询命令。→ 本 change 只暴露已有 repair task mutation；source 查询和日志归入第二阶段。
- workflow extension provider manifest 生成依赖 manifest snapshot 的可用信息。→ 实现时优先使用 snapshot/imports 信息，缺失时 warning，不静默伪造不可验证内容。
- CLI 继续集中在 `cli.py` 会让文件变长。→ 本次范围是还债，重构 CLI 模块化不属于本 change。
