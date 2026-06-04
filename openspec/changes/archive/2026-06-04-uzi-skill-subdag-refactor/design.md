## Context

uzi-skill-analysis DAG 是 UZI-Skill extension 的核心分析管道，当前采用扁平化结构包含 53 个节点：
- 1 个 preflight 节点（数据预检）
- 22 个数据采集节点（基础信息、财务、新闻、市场等）
- 2 个 autofill 节点（定性补全）
- 1 个 score_dimensions 节点（维度评分，接收 25 个输入）
- 2 个生成节点（generate_panel、generate_synthesis）
- 21 个渲染节点（render_*）
- 1 个 assemble_report 节点（报告组装）

**现有问题**：
- 画布横向跨度超过 12000 像素，节点密集难以查看
- 逻辑分层不清晰，维护成本高
- 难以复用数据采集或渲染阶段

**技术约束**：
- 系统已实现 Sub DAG 执行能力（`cap.core.sub-dag-execution`）
- Entity 存储已迁移至 DB-backed 模式
- 所有节点均使用 optional 边和 resource 约束，需保持语义不变
- 用户期望运行时行为完全一致，无性能回退

## Goals / Non-Goals

**Goals:**
- 将 uzi-skill-analysis 主 DAG 节点数量从 53 降至 5
- 按功能阶段拆分为 3 个 Sub DAG：data-collection、scoring-synthesis、rendering
- 保持所有节点的 optional、fan-in/fan-out、resource 语义不变
- 保持运行时执行逻辑和性能特征完全一致
- 提升 DAG 画布可读性和可维护性

**Non-Goals:**
- 不改变任何节点的业务逻辑或配置参数
- 不优化执行性能或并行度（Sub DAG 只是组织形式）
- 不修改前端 UI 渲染逻辑（可选未来增强）
- 不改变 Entity 存储层或 Sub DAG 执行引擎

## Decisions

### 决策 1：三阶段拆分策略

**选择**：按执行阶段拆分为 3 个 Sub DAG（data-collection、scoring-synthesis、rendering）

**理由**：
- 各阶段职责清晰：采集 → 评分 → 渲染 → 组装
- 节点数量分布合理（25/3/21），避免单个 Sub DAG 过大或过小
- 数据流边界明确，便于定义输入输出契约

**备选方案**：
- 按数据类型拆分（财务、市场、新闻等）：会产生 10+ 个小 Sub DAG，增加复杂度
- 仅拆分 rendering 阶段：无法解决 data-collection 的 22 个节点聚集问题

### 决策 2：新增 aggregate-collection-results 节点

**选择**：在 data-collection Sub DAG 末尾新增聚合节点，作为唯一 sink

**理由**：
- 下游 score_dimensions 需要 25 个输入（basic + 22 fetch + 2 autofill），Sub DAG 必须返回包含所有字段的单一 payload
- 聚合节点作为数据采集阶段的输出契约，封装内部拓扑细节
- 便于未来扩展或替换数据采集逻辑

**备选方案**：
- 保持 score_dimensions 在主 DAG：破坏逻辑分层，主 DAG 仍需直接依赖 data-collection 内部节点
- 使用多 sink 模式：下游需手动处理 25 个输入，违背 Sub DAG 黑盒原则

**实现细节**：
- aggregate 节点类型：`function`，handler 为简单的字典构造逻辑
- 输入：fan-in from 所有 fetch 和 autofill 节点
- 输出：`{basic: {...}, financials: {...}, ..., autofill_mx: {...}}`
- optional 处理：缺失的 optional 输入对应字段为 null 或省略

### 决策 3：主 DAG 保留 preflight 和 assemble_report

**选择**：preflight 和 assemble_report 保留在主 DAG

**理由**：
- preflight 是全局预检逻辑，不属于数据采集阶段
- assemble_report 需要聚合 rendering 输出和 preflight 输出，是最终汇总点
- 保持主 DAG 清晰表达端到端流程：预检 → 采集 → 评分 → 渲染 → 组装

### 决策 4：rendering Sub DAG 采用多 source 多 sink 模式

**选择**：21 个 render 节点作为独立的 source 和 sink，无内部依赖

**理由**：
- 所有 render 节点接收相同输入（generate_synthesis 输出），无 fan-out 或依赖关系
- 保持并行执行语义，与原 DAG 一致
- 下游 assemble_report 通过 fan-in 收集所有 render 输出

**数据流**：
- Sub DAG 输入：通过 initial_payload 传递给所有 source 节点
- Sub DAG 输出：所有 sink 节点输出组成的数组

### 决策 5：使用 DB-backed Entity 存储

**选择**：所有新 Entity（Sub DAG、aggregate 节点）通过 EntityStore 持久化到数据库

**理由**：
- 项目已完成 YAML → DB 迁移，新 Entity 必须遵循统一存储方式
- extension manifest 的 `imports.entities` 声明触发自动导入（`cap.core.extension-entity-imports`）
- 便于运行时查询和热重载

**实现路径**：
- 在 `extensions/uzi-skill/entities/dags/` 创建 YAML 文件（作为导入模板）
- 在 manifest.yaml 的 `imports.entities` 添加路径
- 系统启动时通过 importer 自动导入到数据库

## Risks / Trade-offs

### 风险 1：aggregate 节点增加复杂度
- **风险**：新增节点需要额外的配置、测试和维护
- **缓解**：aggregate 逻辑极简（字典构造），可通过 function 节点实现，无外部依赖

### 风险 2：嵌套层级增加调试难度
- **风险**：Sub DAG 内部错误需要通过 parent_run_id 关联查询，调试路径变长
- **缓解**：现有 `cap.web.dag-run-observability` 已支持 sub_dag_run_id 追踪，Web Console 可展示父子关系

### 风险 3：UI 无 Sub DAG 特殊样式
- **风险**：用户无法直观识别哪些节点是 Sub DAG，也无法"钻取"查看内部结构
- **缓解**：当前可通过节点 type 字段判断，未来可增强 UI（非本次变更范围）

### 权衡 1：主 DAG 节点数量 vs 嵌套深度
- **权衡**：从扁平化 53 节点变为 2 层嵌套（主 DAG 5 节点，Sub DAG 3-25 节点）
- **影响**：增加 1 层嵌套，但在 max_dag_depth=3 限制内，且可读性显著提升

### 权衡 2：黑盒封装 vs 可观测性
- **权衡**：Sub DAG 作为黑盒隐藏内部拓扑，调试时需额外查询子运行记录
- **影响**：现有 runtime facts 表已记录所有节点执行状态，通过 run_id 可完整追溯

## Migration Plan

### 阶段 1：创建新 Entity（无影响）
1. 创建 3 个 Sub DAG YAML 文件
2. 创建 aggregate 节点 YAML 文件
3. 更新 manifest.yaml 的 imports.entities
4. 重启 edera-server，触发自动导入

### 阶段 2：重构主 DAG（替换）
1. 备份当前 uzi-skill-analysis Entity（通过 DB export）
2. 修改主 DAG 配置：
   - 保留 preflight、assemble_report
   - 删除 51 个中间节点
   - 新增 3 个 Sub DAG 引用节点（type: dag）
3. 调整边配置：
   - preflight → data-collection
   - data-collection → scoring-synthesis
   - scoring-synthesis → rendering
   - rendering → assemble_report
   - preflight → assemble_report（直接边，保持原逻辑）
4. 更新数据库中的 uzi-skill-analysis Entity

### 阶段 3：验证（集成测试）
1. 手动触发 uzi-skill-analysis DAG 运行
2. 验证所有 Sub DAG 正常执行
3. 检查 aggregate 节点输出包含所有必需字段
4. 确认最终报告与重构前一致

### 回滚策略
- 保留备份的原 DAG 配置（数据库快照）
- 如验证失败，通过 EntityStore 恢复原 Entity
- Sub DAG Entity 可保留（不影响其他 DAG）

## Open Questions

无。所有技术决策已确定。
