## Context

当前 Edera 的 DAG 输入机制通过 `DAG.inputs` 定义参数 schema，source 节点通过 `input_binding` 字段声明依赖哪个 DAG 级参数。这种设计在以下场景存在问题：

1. **多 source 节点**：每个 source 都需要配置 `input_binding`，且无法在运行时为不同 source 指定不同输入
2. **临时输入**：无法在运行时临时覆盖节点输入，必须修改配置文件
3. **Sub-DAG 测试**：无法在运行时追加测试参数到 Sub-DAG，只能完全替换输入
4. **不一致性**：DAG run、Node trigger、Retry 三种运行入口的输入处理逻辑不统一

设计约束：
- 保持 Sub-DAG 对嵌套无感知
- 支持覆盖和追加两种模式
- 保持向后兼容的错误提示

## Goals / Non-Goals

**Goals:**
- 统一三种运行入口的输入处理逻辑
- 支持运行时临时覆盖和追加节点输入
- 消除 `input_binding` 的间接性
- 支持多 source 节点的共享输入和独立输入
- 支持 Sub-DAG 的持久化输入映射配置
- 保持 Sub-DAG 对嵌套的无感知

**Non-Goals:**
- 不提供深度合并（只支持浅合并）
- 不保留 `input_binding` 的向后兼容
- 不支持节点间的输入转发（仍通过 edges 传递）

## Decisions

### 决策 1：分层输入参数

**选择：** `sourceSharedInputs`（source 节点共享） + `nodeInputs`（节点独立） + `appendNodes`（追加模式声明）

**理由：**
- `sourceSharedInputs` 解决多 source 共享输入的场景，避免重复指定
- `nodeInputs` 提供节点级精确控制
- `appendNodes` 显式声明追加模式，默认覆盖符合直觉

**拒绝的方案：**
- 方案 A：只用 `nodeOverrides`，不区分 source 和非 source → 多 source 场景冗余
- 方案 B：恢复 `input_binding` 加运行时覆盖 → 保留了复杂性

### 决策 2：InputMapping 作为核心 Entity

**选择：** 新增 `input_mapping` EntityType，包含 `shared`、`nodes`、`append_nodes` 字段

**理由：**
- 持久化配置，可复用
- Sub-DAG 的 `input_mapping` 可以引用 entity，避免内联大量配置
- 符合 Edera 的 Entity 统一原语设计

**拒绝的方案：**
- 只支持内联 dict → 复杂映射配置无法复用
- 放在 YAML 配置文件 → 不符合 Entity 统一原语

### 决策 3：浅合并而非深合并

**选择：** `_merge(base, override)` 只合并顶层 dict，其他类型直接覆盖

**理由：**
- 简单可预测
- 避免深度合并的歧义（数组是替换还是追加？）
- 大多数场景顶层合并已足够

**拒绝的方案：**
- 深度合并 → 复杂且难以预测
- 提供多种合并策略 → 增加复杂度

### 决策 4：移除而非废弃 input_binding

**选择：** 直接移除 `DAG.inputs` 和 `input_binding`，提供清晰的错误提示

**理由：**
- 项目还在开发阶段，没有历史负担
- 保留废弃字段增加维护成本
- 清晰的错误提示已足够

**拒绝的方案：**
- 标记为 deprecated 保留一段时间 → 增加代码复杂度

### 决策 5：Node trigger 的 append 参数

**选择：** `run_node_trigger(target, payload, append=False)` 增加 append 参数

**理由：**
- 支持 Node trigger 的追加模式
- 与 DAG run 的 `appendNodes` 语义一致
- CLI 和 Web UI 可以提供选项

**拒绝的方案：**
- 总是覆盖 → 无法支持追加测试参数的场景
- 通过特殊 payload 结构声明 → 不够清晰

## Risks / Trade-offs

### 风险 1：破坏性变更

**风险：** 现有 DAG 配置中的 `inputs` 和 `input_binding` 失效

**缓解：**
- 检测到旧字段时给出清晰的错误提示和迁移建议
- 调用 subagent 完成迁移，无需手动脚本

### 风险 2：追加模式的 merge 语义

**风险：** 浅合并可能不满足某些复杂场景

**缓解：**
- 文档清晰说明浅合并的行为
- 如果未来需要深度合并，可以增加 `mergeMode` 参数

### 风险 3：appendNodes 列表可能很长

**风险：** API 参数稍显冗长

**缓解：**
- Web UI 提供友好的复选框界面
- 默认覆盖模式，大多数场景不需要声明

### 风险 4：Source 节点默认值缺失

**风险：** 如果 source 节点没有 `config.default_*` 且没有临时输入，运行时会失败

**缓解：**
- 提供清晰的错误提示
- 迁移时确保将 `input_binding` 移到 `config.default_entity`

## Migration Plan

### 迁移步骤

1. **后端实现**：
   - 新增 `input_mapping` EntityType 和表结构
   - 修改 `DagRunner._get_node_input()` 实现三步逻辑
   - 修改 gRPC API 增加字段
   - 移除 `_source_payload()` 和 `_input_binding()` 方法

2. **前端实现**：
   - 新增 `TemporaryInputDialog` 组件
   - 修改 API mutations 增加参数

3. **迁移现有配置**：
   - 调用 subagent 遍历所有 DAG 和 Node 配置
   - 删除 `DAG.inputs` 字段
   - 将 `input_binding` 移到 `config.default_entity`

4. **测试验证**：
   - 单元测试覆盖输入优先级
   - 集成测试覆盖多 source、追加模式、Sub-DAG 场景
   - Web E2E 测试临时输入 UI

### Rollback 策略

- 如果发现严重问题，可以回退到旧的 commit
- 配置文件的迁移可以通过 git revert 恢复
- 数据库的 `entity_input_mapping` 表可以直接删除

## Open Questions

无
