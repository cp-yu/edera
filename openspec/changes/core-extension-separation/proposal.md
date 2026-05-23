## Why

当前系统核心引擎（DAG runner、Node executor、Entity Store、Trigger）与业务扩展（RSS 抓取、建议生成、通知推送）混合在同一个 Python 包内，`pipeline.py` 硬编码 handler 注册，`node/executor.py` 内嵌 LLM 执行逻辑。这导致：
1. 添加新 handler/skill 必须修改核心代码
2. 核心无法独立编译优化（未来 Rust 重写目标）
3. 业务逻辑与引擎逻辑耦合，职责边界模糊

## What Changes

- **BREAKING**: 重组项目为 uv workspace monorepo，拆分为 `packages/core/`、`packages/core-types/`、`extensions/` 三层
- **BREAKING**: 统一所有节点为 function node，移除 `type: "llm"` 区分，LLM 调用降级为 handler 内部实现
- **BREAKING**: Handler 签名统一为 `async def run(ctx: HandlerContext) -> Any`，废弃当前多签名 inspect 机制
- 核心引擎领域无关化：移除所有 `rss-source`、`fetch-rss`、`advice` 等领域硬编码
- 引入 Manifest 声明式扩展注册，核心内置 bootstrap 扫描机制
- 扩展可声明 entity types 和数据库表，核心自动合并注册
- 当前 `services/` 拆解为独立扩展目录，共享逻辑移入 `extensions/_lib/`
- Web Console 移至 `apps/web-console/` 作为独立子项目

## Capabilities

### New Capabilities
- `extension-manifest-system`: 扩展 manifest 声明、解析、校验和 fallback 机制
- `core-bootstrap`: 核心启动时扫描扩展目录、解析 manifest、构建 handler registry 和 entity type registry
- `handler-context-protocol`: 统一 HandlerContext 单参数调用协议和 HandlerProtocol 接口定义
- `extension-declarative-storage`: 扩展通过 manifest 声明自定义数据库表，核心自动建表管理

### Modified Capabilities
- `node-executor`: 移除 LLM executor 分支和 `_run_pi` 逻辑，统一为 function-only 执行路径，handler 通过 importlib 加载
- `unified-entity-model`: Entity type 注册来源扩展为 manifest 声明 + 用户配置覆盖的双层优先级
- `pipeline-control`: 移除 `_build_executor` 硬编码 handler 注册，改为从 bootstrap registry 获取

## Impact

- **目录结构**: 全面重组为 `packages/core/`、`packages/core-types/`、`extensions/`、`apps/web-console/`
- **Python 包**: 从单包 `stockimformation` 拆为 `stockimformation-core` + `stockimformation-types` workspace
- **所有 import 路径**: 核心代码 import 从 `stockimformation.*` 变为 `stockimformation_core.*`，扩展 import 接口从 `stockimformation_types.*`
- **测试**: 需要重组测试目录，核心测试与扩展测试分离
- **配置加载**: `config/` 目录位置不变，但加载逻辑移入核心 bootstrap
- **前端 API**: Web Console API 路由不变，但实现从 `src/stockimformation/web/` 移至 `apps/web-console/`
- **CI/构建**: 需要适配 uv workspace 构建流程
