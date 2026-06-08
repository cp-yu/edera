<!-- Design Summary used: 输入足够详细，跳过 explore，直接生成制品。 -->

## Why

现有的 DAG 输入机制（`inputs` + `input_binding`）在多 source 节点场景和 Sub-DAG 测试场景下过于复杂且不够灵活。当需要临时处理某个任务时，每次都需要修改配置文件，无法在运行时动态指定或覆盖节点输入。此外，三种运行入口（DAG run、Node trigger、Retry）缺乏统一的输入控制机制。

## What Changes

- **BREAKING** 移除 `DagConfig.inputs` 字段和 `NodeConfig.input_binding` 字段
- 新增运行时临时输入机制：`sourceSharedInputs`（所有 source 节点共享）、`nodeInputs`（节点独立）、`appendNodes`（追加模式声明）
- 新增核心 Entity Type：`input_mapping`，用于 Sub-DAG 的持久化输入映射配置
- 支持两种输入模式：覆盖（默认）和追加（显式）
- 统一 DAG run、Node trigger、Retry 三种运行入口的输入处理逻辑
- 修改 `DagNodeConfig.input_mapping` 支持 dict 或 entity 引用
- 更新 gRPC API、Web Console UI 和 CLI

## Capabilities

### New Capabilities

- `runtime-temporary-input`：运行时临时输入机制，覆盖节点输入的三种模式和优先级
- `input-mapping-entity`：InputMapping 核心 Entity Type 的定义和使用

### Modified Capabilities

- `dag-input-parameters`：移除 DAG.inputs 字段，改用 sourceSharedInputs 和 nodeInputs
- `sub-dag-execution`：Sub-DAG 的 input_mapping 支持 entity 引用
- `dag-control`：DagController 和 API 增加临时输入参数
- `multi-node-retry`：Retry 操作增加临时输入支持
- `manual-trigger-prefix`：Node trigger 内部转换为临时输入机制
- `edera-web-bff`：Web BFF API 增加临时输入参数
- `node-graph-dag-editor`：Web Console 增加临时输入配置 UI

## Impact

**后端**：
- `DagRunner`：新增 `_get_node_input()` 方法，移除 `_source_payload()` 和 `_input_binding()`
- `DagController`：`run_node_trigger()` 支持 append 参数
- gRPC services：`DagRunRequest`、`RetryRequest` 增加字段
- Entity schema：新增 `input_mapping` EntityType
- 数据库：新增 `entity_input_mapping` 表

**前端**：
- Web Console：新增 `TemporaryInputDialog` 组件
- API mutations：`useRunDag`、`useRetryDagNode` 增加参数

**迁移**：
- 现有 DAG 配置需要移除 `inputs` 字段
- 现有 Node 配置需要将 `input_binding` 移到 `config.default_*`
