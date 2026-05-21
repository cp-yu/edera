## Why

当前系统存在 Node、DAG、Entity、Trigger 等多种独立概念，各自有不同的加载机制、存储方式和管理接口。这导致扩展时需要为每种概念分别实现 CRUD、校验、权限等基础设施。统一为"一切皆 Entity"模型后，系统只有一个核心原语，通过 EntityType schema 字段声明能力（有 `handler` → 可执行；有 `edges` → 是 DAG），大幅降低概念复杂度，同时让 Agent 可以通过统一的文本操作扩展系统的任何部分。

## What Changes

- **BREAKING** 将 Node 定义重构为 Entity（EntityType schema 包含 `handler`、`input_type`、`output_type` 等字段）
- **BREAKING** 将 DAG 定义重构为 Entity（EntityType schema 包含 `edges`、`nodes` 引用）
- **BREAKING** 将 Node 运行时输出建模为 Entity（存储在数据库层，带 retention 策略）
- 引入 Trigger Entity 类型（支持时间/事件/用户/叠加触发，FreeRTOS 事件组模型）
- 引入 Entity 三层存储模型：文件系统（配置型）、数据库（输出型）、内存（瞬态型）
- 引入条件分支 edge 属性，condition evaluator 作为可替换 handler
- 引入单节点循环（并行重复 / 串行迭代），DAG 整体保持无环
- 引入子 DAG 机制（DAG Entity 作为 Node 嵌套执行，递归上限可配置默认 3）
- 引入 fan_in stream 模式（逐个处理，不等齐）
- Relation 统一为 Entity（type 为 `relation`，包含 from/to/relation_type）
- 配置文件夹强制 git 管理，每次 DAG run 结束 commit，操作互斥锁

## Capabilities

### New Capabilities

- `unified-entity-model`: 统一 Entity 原语，Node/DAG/Trigger/Relation/Output 全部建模为 Entity，EntityType schema 字段即能力声明
- `entity-storage-tiers`: Entity 三层存储（文件系统/数据库/内存），含 retention 策略和生命周期管理
- `trigger-system`: Trigger Entity 类型与 Trigger Executor 内核，支持时间/事件/用户/叠加触发，FreeRTOS 事件组 AND/OR 组合
- `dag-condition-branch`: DAG edge 条件分支，可替换 condition evaluator handler，支持 output.* + entity ref + 常量
- `single-node-loop`: 单节点并行循环（同输入多实例）和串行循环（迭代精炼），停止条件为固定次数或条件满足
- `sub-dag-execution`: 子 DAG 作为 Node 嵌套执行，对外黑盒（input/output 接 source/sink），递归上限可配置
- `config-git-safety`: 配置文件夹强制 git 版本管理，DAG run 结束自动 commit，操作互斥锁

### Modified Capabilities

- `entity-system`: Entity 从数据载体升级为系统唯一原语，EntityType schema 需承载能力声明语义
- `dag-runner`: 新增条件分支路由、单节点循环、子 DAG 调度、fan_in stream 模式、部分成功传播
- `node-executor`: Node 变为 Entity，handler 加载逻辑需适配 EntityType schema 驱动
- `data-models`: RawItem/AnalysisResult/Advice/Briefing 重构为输出型 Entity，统一存储接口

## Impact

- **核心代码**：`src/stockimformation/` 下 config/、dag/、node/、models/ 模块需重构
- **配置结构**：`config/` 目录重组为混合结构（schemas/ 统一类型定义，实例按职能分目录）
- **数据库**：输出型 Entity 统一存储表替代当前多表模型（NodeOutput: id, cycle_id, node_id, output_type, payload JSON）
- **API**：Web Console API 需适配统一 Entity CRUD 接口
- **依赖**：无新外部依赖，内部模块边界重新划分
- **迁移**：需要数据迁移脚本将现有 Node/DAG 配置转换为 Entity 格式
