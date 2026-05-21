## Context

当前系统由多种独立概念组成：`NodeConfig`、`DagConfig`、`EntityConfig`、`SkillConfig`，各自有独立的加载路径、Pydantic schema 和管理接口。`DagRunner` 执行固定的拓扑并行策略，不支持条件分支或循环。Node 输出通过内存直接传递，输出型数据（RawItem、AnalysisResult 等）使用独立的 SQLModel 表存储。

系统定位为 Agent 的程序化缰绳——能观、能控、能力可复现。当前架构的多概念分离阻碍了这一目标：每新增一种能力都需要在多处添加加载/校验/CRUD 逻辑。

## Goals / Non-Goals

**Goals:**

- 统一系统原语为 Entity，通过 EntityType schema 字段声明能力
- 硬内核收敛为 4 个组件：Entity Store、Handler Loader、DAG Runner、Trigger Executor
- 支持条件分支、单节点循环、子 DAG 嵌套、fan_in stream 模式
- 引入 Trigger Entity 和事件组机制
- 配置文件夹 git 强制管理
- 保持 Agent 可通过纯文本操作扩展系统任何部分

**Non-Goals:**

- 不实现通用工作流引擎（不支持 DAG 级循环）
- 不实现 Agent 审批机制（git 是唯一安全网）
- 不实现 session resume（后续独立变更）
- 不实现 Web Console 重构（本次只适配 Entity CRUD 接口）
- 不实现 Agent 自我进化闭环（反思/skill 修正为后续变更）

## Decisions

### Decision 1: Entity 统一模型

**选择**：所有概念（Node、DAG、Trigger、Relation、Output）统一为 Entity，EntityType schema 字段即能力声明。

**替代方案**：保持多概念分离，通过 adapter 层统一接口。

**理由**：adapter 层只是表面统一，底层仍需维护多套逻辑。真正统一为 Entity 后，Entity Store 的 CRUD + schema 校验 + 权限检查自动覆盖所有概念，新增能力只需注册 EntityType。

**能力声明约定**：
- 有 `handler` 字段 → 可执行（Node）
- 有 `edges` + `nodes` 字段 → DAG
- 有 `wait_for` + `target` 字段 → Trigger
- 有 `from` + `to` + `relation_type` 字段 → Relation

### Decision 2: 三层存储

**选择**：Entity 按生命周期分三层存储。

| 层级 | 存储 | 内容 | 生命周期 |
|------|------|------|----------|
| 文件系统 | YAML in `config/` | 配置型 Entity（stock、node、dag、trigger、skill） | 持久，git 管理 |
| 数据库 | SQLite `node_outputs` 表 | 输出型 Entity（analysis、advice、briefing） | retention 策略清理 |
| 内存 | Python dict | 瞬态 Entity（run metadata、事件状态） | run 结束释放 |

**替代方案**：全部存文件系统 / 全部存数据库。

**理由**：配置型需要 git 版本管理和 Agent 文本操作；输出型量大需要数据库查询能力和 retention；瞬态型无需持久化。三层对应三种生命周期。

### Decision 3: DAG Runner 扩展

**选择**：在现有 `DagRunner` 基础上增量添加条件分支、单节点循环、子 DAG 调度。

**条件分支**：`DagEdge` 新增 `condition: str | None` 字段。执行时调用 condition evaluator handler 求值，为 true 则路由数据到该边。无 condition 的边始终执行。多条件都满足时全部走（并行分支）。

**单节点循环**：`DagNodeInstance` 新增 `loop` 配置：
```yaml
loop:
  mode: parallel | serial
  count: 3           # 固定次数
  until: "output.confidence > 0.8"  # 条件停止
```
- parallel：同输入启动 N 个实例并发
- serial：前一次输出作为下一次输入，迭代精炼

**子 DAG**：当 Node 的 EntityType 包含 `edges` 字段时，DAG Runner 递归调用自身执行子 DAG。input 传给子 DAG 的 source 节点，sink 节点的 output 作为该 Node 的 output 返回。递归深度由 `system.toml` 的 `max_dag_depth`（默认 3）控制。

**替代方案**：将执行策略做成可替换 handler。

**理由**：用户已确认拓扑并行是唯一执行模型（不需要事件驱动等替代策略），条件分支和循环是在此模型上的增量扩展，不需要可替换性。

### Decision 4: Trigger Executor 与事件组

**选择**：Trigger 是 Entity（EntityType 包含 `wait_for`、`target` 字段）。Trigger Executor 是内核组件，读取所有 Trigger Entity，维护事件组状态。

**事件组模型**（参考 FreeRTOS `xEventGroupWaitBits`）：
```yaml
# triggers/morning-analysis.yaml
type: trigger
attributes:
  wait_for:
    mode: AND
    events:
      - "schedule:09:00"
      - "event:market-open"
  target: "dag:morning-analysis"
```

- 事件源：任何可观测事件（Entity 变更、config/ 文件变更、Node 输出满足条件、外部 webhook、时间）
- 事件瞬态，不持久化为 Entity，消费后清除
- 事件发生记录到 run metadata（内存层 Entity）

**替代方案**：保持 APScheduler 简单定时。

**理由**：用户需要事件触发、叠加触发等复杂场景，简单定时无法覆盖。

### Decision 5: Condition Evaluator 可替换

**选择**：默认 evaluator 支持受限 DSL（`==`、`!=`、`>`、`<`、`>=`、`<=`、`in`、`and`、`or`、`not`），操作数支持 `output.*`、`entity:{ref}.{field}`、常量。用户可在 `config/evaluators/` 注册自定义 evaluator handler 替换。

**替代方案**：Python `eval` / 固定不可替换。

**理由**：`eval` 有安全隐患；固定不可替换限制未来扩展。可替换 handler 兼顾安全和扩展性。

### Decision 6: 配置文件夹 git 管理

**选择**：`config/` 目录作为独立 git 仓库（或 submodule），DAG run 结束后自动 commit。配置文件操作加互斥锁。

**commit 策略**：每次 DAG run 结束时，检查 `config/` 是否有变更，有则自动 commit（message 包含 cycle_id 和变更摘要）。策略本身可通过 `system.toml` 配置。

**替代方案**：每次文件修改立即 commit / 由 Agent 决定。

**理由**：DAG run 是系统的完整执行单元，以此为 commit 粒度语义清晰，回滚时回滚一次完整执行的副作用。

### Decision 7: fan_in stream 模式

**选择**：`DagEdge` 新增 `fan_in_mode: collect | stream` 字段（默认 `collect`）。

- `collect`：等所有上游完成，收齐后一次性传给下游
- `stream`：上游每完成一个，立即传给下游执行一次

**实现**：stream 模式下，下游节点注册为上游的 callback，上游每产出一个结果即触发下游执行。

### Decision 8: 配置目录结构

```
config/
├── system.toml
├── schemas/           # EntityType schema 定义
├── nodes/             # Node Entity 实例
├── dags/              # DAG Entity 实例
├── entities/          # 数据型 Entity 实例
├── triggers/          # Trigger Entity 实例
├── skills/            # Skill 定义
├── handlers/          # Handler 代码文件
├── evaluators/        # Condition evaluator handler
└── relations.yaml     # Relation Entity 实例
```

## Risks / Trade-offs

- **[迁移复杂度]** 现有 Node/DAG 配置格式需要迁移为 Entity 格式 → 提供自动迁移脚本，保留旧格式兼容加载作为过渡期
- **[性能]** 三层存储增加 Entity Store 查询复杂度 → 内存层和文件层在启动时全量加载到内存缓存，数据库层按需查询
- **[条件分支死路径]** 所有条件都不满足时数据无处可去 → DAG Runner 检测并记录 warning 到 run metadata，不视为错误
- **[子 DAG 递归]** 配置错误可能导致深度递归 → 硬限制递归深度，超限时立即报错
- **[git 冲突]** 并发 DAG run 的互斥锁可能成为瓶颈 → 当前系统同一 DAG 默认排队，实际并发写配置的场景极少
- **[stream 模式复杂度]** callback 机制增加 DAG Runner 复杂度 → 作为最后实现的特性，先确保 collect 模式稳定

## Migration Plan

1. 定义新 EntityType schema 文件（node、dag、trigger、relation）
2. 编写迁移脚本：将现有 `config/nodes/*.yaml`、`config/dags/*.yaml` 转换为 Entity 格式
3. 重构 Entity Store：支持三层存储，统一 CRUD 接口
4. 重构 DAG Runner：增量添加条件分支 → 单节点循环 → 子 DAG → stream 模式
5. 实现 Trigger Executor
6. 实现 config/ git 管理
7. 适配 Web Console API
8. 回归测试全部现有功能

**回滚策略**：每个阶段独立可回滚。迁移脚本保留旧格式文件备份。Entity Store 新旧接口并存直到迁移完成。

## Open Questions

- Trigger Executor 的事件源注册机制具体 API 设计（如何注册"Entity 变更"作为事件源）
- stream 模式下的背压处理（下游处理速度跟不上上游产出时的策略）
- 输出型 Entity 的 `output_type` schema 注册流程（是否需要 CLI 工具辅助）
