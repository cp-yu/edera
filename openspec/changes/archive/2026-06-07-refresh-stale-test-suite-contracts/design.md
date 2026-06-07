## Context

当前实现已经完成多条契约迁移：`NodeExecutor` 接收 `DagExecutionSnapshot`，handler metadata 通过 snapshot 内的 resolver 查询；`RuntimeControlSnapshot` 是控制面状态快照，不再镜像完整 `AppConfig`；CLI 数据子命令是纯 gRPC client；extension manifest metadata 持久化到 DB，不再构建 `HandlerRegistry` 和 `EntityTypeRegistry`。

`docs/issues/stale-test-suite-contracts.md` 记录的失败来自测试仍绑定旧契约。Impact sweep 还发现 `core-bootstrap` 和 `node-executor` specs 中存在旧 registry 文本，与 `extension-manifest-system`、`dag-execution-snapshot` 和 OPSX intent 冲突。

## Goals / Non-Goals

**Goals:**

- 让 issue 点名的测试断言当前运行时、CLI 和 bootstrap 契约。
- 清理直接冲突的 OpenSpec registry 描述，防止测试维护引用旧语义。
- 保持 change 聚焦，验收命令覆盖 issue 原始命令和新增 collection failure。

**Non-Goals:**

- 不恢复 `edera_core.registry`。
- 不给 `NodeExecutor` 增加旧 `handlers=` 或缺省 `snapshot` 兼容。
- 不一次性修全仓所有旧 `NodeExecutor(...)` 调用点。
- 不改运行时行为或数据库 materialization 策略。

## Decisions

1. 测试跟随当前契约，而不是恢复旧 API。

   旧测试如果通过 `handlers=`、`RuntimeControlSnapshot.config` 或 registry fake 运行，就会把已经移除的架构重新固化。正确做法是使用 `DagExecutionSnapshot` fixture、当前 controller fake 和 gRPC client fake。

2. CLI running-server 测试拆成两类。

   一类验证 CLI 命令确实走 gRPC 查询路径，不断言旧启动 materialization 中的 `stock:TEST`。另一类通过显式 import/seed 创建实体，再验证实体可查和权限路径。这样不会把“启动自动拥有某个 YAML 实体”误认为 CLI 契约。

3. OpenSpec cleanup 只处理直接冲突文本。

   `core-bootstrap` 中 registry 构建、registry 原子替换等旧条款需要移除或改写；`node-executor` 中通过 handler registry 执行 Node Entity 的描述需要改写。其余较大的术语整理不放进本 change。

4. Bootstrap fallback 测试保留，但 fake controller 跟随当前 server 边界。

   bootstrap fallback 和 `bootstrap.json` 是 `edera-server-grpc` 的有效契约。测试不需要 registry 类型，只需要能让 `Server` 启动到 bootstrap 端口路径的当前 controller double。

## Risks / Trade-offs

- One change contains tests and specs → review 同时覆盖测试行为和 spec 文案；通过把 OpenSpec cleanup 限制为直接冲突条款降低范围。
- 不做旧 API 兼容 → 会暴露其他未纳入 issue 的旧测试；这些应作为后续测试债单独处理。
- CLI 测试拆分 → 测试结构比直接改断言多一点，但能清楚区分 gRPC 路径和实体数据准备。
