## Why

uzi-skill-analysis DAG 当前包含 53 个节点，在画布中横向分布超过 12000 像素，导致用户难以查看和维护整体结构。将其按功能阶段拆分为 3 个 Sub DAG，可以显著提升可读性和可维护性。

## What Changes

- 创建 3 个新的 Sub DAG Entity：
  - `uzi-data-collection`：数据采集阶段（22个fetch + 2个autofill + 1个aggregate节点）
  - `uzi-scoring-synthesis`：评分与综合阶段（3个串联节点）
  - `uzi-rendering`：渲染阶段（21个render节点）
- 重构 `uzi-skill-analysis` 主 DAG：
  - 保留 `preflight` 和 `assemble_report` 节点
  - 将原有 51 个节点替换为 3 个 Sub DAG 引用节点（type: dag）
  - 主 DAG 节点数量从 53 降至 5
- 新增 `aggregate-collection-results` 节点：
  - 作为 `uzi-data-collection` 的 sink 节点
  - 聚合所有数据采集结果为单一输出字典
- 更新 uzi-skill extension manifest：
  - 添加 3 个新 Sub DAG Entity 的导入声明
  - 添加 aggregate 节点的导入声明

## Capabilities

### New Capabilities
- `uzi-subdag-structure`：UZI-Skill 分层 Sub DAG 结构，定义数据采集、评分综合、渲染三阶段的子图组织和数据流契约

### Modified Capabilities
- `uzi-skill-dag-instance`：UZI-Skill DAG 实例配置从扁平化 53 节点结构改为 3 层 Sub DAG 嵌套结构，保持原有数据采集、评分、渲染逻辑不变

## Impact

**后端（Python）**：
- `extensions/uzi-skill/entities/dags/uzi-skill-analysis.yaml`：主 DAG 配置重构
- `extensions/uzi-skill/entities/dags/`：新增 3 个 Sub DAG Entity 文件
- `extensions/uzi-skill/entities/nodes/`：新增 aggregate 节点配置
- `extensions/uzi-skill/manifest.yaml`：更新 imports.entities 列表

**前端（TypeScript）**：
- 无代码修改，主 DAG 画布节点从 53 → 5，显著提升可读性
- （可选增强）未来可为 Sub DAG 节点添加特殊样式和钻取功能

**运行时**：
- 无性能影响，Sub DAG 只是组织形式，执行逻辑完全相同
- 所有节点的 optional 语义、fan-in/fan-out 模式、resource 约束保持不变

**依赖**：
- 依赖现有 `cap.core.sub-dag-execution` 能力（已实现）
- 依赖 DB-backed Entity 存储（已实现）
