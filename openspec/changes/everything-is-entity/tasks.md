## 1. Actions

- [ ] A1 定义核心 EntityType schema 文件（node.yaml、dag.yaml、trigger.yaml、relation.yaml、run-metadata.yaml）到 `config/schemas/`
- [ ] A2 重构 EntityTypeConfig 模型，新增 `storage_tier` 字段和能力字段检测逻辑
- [ ] A3 实现三层 Entity Store（文件系统层、数据库层、内存层），统一 CRUD 接口
- [ ] A4 实现数据库层 `node_outputs` 统一表和 ORM 模型
- [ ] A5 重构 Node 配置加载：从 Entity Store 读取 Node Entity 替代直接 NodeConfig 加载
- [ ] A6 重构 DAG 配置加载：从 Entity Store 读取 DAG Entity 替代直接 DagConfig 加载
- [ ] A7 实现 DagEdge 条件分支：新增 `condition` 字段，集成 condition evaluator
- [ ] A8 实现默认 condition evaluator handler（受限 DSL：比较运算 + entity ref + 逻辑组合）
- [ ] A9 实现 evaluator 可替换机制（从 `config/evaluators/` 加载自定义 evaluator）
- [ ] A10 实现单节点并行循环（同输入多实例并发）
- [ ] A11 实现单节点串行循环（迭代精炼，前次输出作为下次输入）
- [ ] A12 实现子 DAG 嵌套执行（DAG Entity 作为 Node，递归调用 DagRunner）
- [ ] A13 实现递归深度限制和循环嵌套检测
- [ ] A14 实现 fan_in stream 模式（上游逐个完成即触发下游）
- [ ] A15 实现 optional 节点标记和 LLM fallback 策略（切换模型 / 跳过）
- [ ] A16 实现 Trigger Entity 加载和 Trigger Executor 内核
- [ ] A17 实现事件组机制（AND/OR 组合等待、事件消费后清除）
- [ ] A18 实现事件源注册（Entity 变更、config 文件变更、时间调度、Node 输出条件）
- [ ] A19 实现配置文件夹 git 自动 commit（DAG run 结束后检查变更并 commit）
- [ ] A20 实现配置文件操作互斥锁
- [ ] A21 实现 Handler 每次 run 重新加载机制
- [ ] A22 实现 Node 输出存储为 Entity（含 session_id 记录）
- [ ] A23 编写数据迁移脚本（现有多表 → 统一 node_outputs 表）
- [ ] A24 编写配置迁移脚本（现有 nodes/dags YAML → Entity 格式）
- [ ] A25 适配 Web Console API 到统一 Entity CRUD 接口
- [ ] A26 实现 handler 校验工具（独立 CLI 命令，校验 handler 签名和语法）

## 2. Checks

- [ ] C1 验证 EntityType schema 文件正确加载且能力字段检测生效
  - Covers: A1, A2
  - Command: `python -m pytest tests/ -k "test_entity_type_capability_detection"`
  - Expect: node EntityType 被识别为可执行，dag EntityType 被识别为 DAG，trigger EntityType 被识别为 Trigger

- [ ] C2 验证三层 Entity Store 统一 CRUD 接口
  - Covers: A3, A4
  - Command: `python -m pytest tests/ -k "test_entity_store_three_tiers"`
  - Expect: 配置型 Entity 存储到文件系统，输出型存储到数据库，瞬态型存储到内存，统一查询接口跨层透明

- [ ] C3 验证 Node Entity 加载和执行
  - Covers: A5, A21
  - Command: `python -m pytest tests/ -k "test_node_entity_execution"`
  - Expect: Node 从 Entity Store 加载，handler 每次 run 重新加载，修改 handler 文件后下次 run 使用新版本

- [ ] C4 验证 DAG Entity 加载和拓扑执行
  - Covers: A6
  - Command: `python -m pytest tests/ -k "test_dag_entity_loading"`
  - Expect: DAG 从 Entity Store 加载，拓扑排序正确，并发执行同层节点

- [ ] C5 验证条件分支路由
  - Covers: A7, A8, A9
  - Command: `python -m pytest tests/ -k "test_condition_branch"`
  - Expect: 条件为 true 时路由数据，为 false 时不路由，无条件边始终路由，多条件满足时并行分支，自定义 evaluator 可替换默认

- [ ] C6 验证单节点循环
  - Covers: A10, A11
  - Command: `python -m pytest tests/ -k "test_single_node_loop"`
  - Expect: 并行循环启动 N 个实例同输入，串行循环迭代精炼，条件停止和固定次数停止均生效

- [ ] C7 验证子 DAG 嵌套执行
  - Covers: A12, A13
  - Command: `python -m pytest tests/ -k "test_sub_dag_execution"`
  - Expect: 子 DAG 对外黑盒，input/output 正确映射，递归深度超限报错，循环嵌套检测拒绝加载

- [ ] C8 验证 fan_in stream 模式
  - Covers: A14
  - Command: `python -m pytest tests/ -k "test_fan_in_stream"`
  - Expect: stream 模式下上游每完成一个立即触发下游，不等其他上游

- [ ] C9 验证 optional 节点和 LLM fallback
  - Covers: A15
  - Command: `python -m pytest tests/ -k "test_optional_node_and_fallback"`
  - Expect: optional 节点失败不阻塞下游，LLM fallback 切换模型重试或跳过

- [ ] C10 验证 Trigger 系统
  - Covers: A16, A17, A18
  - Command: `python -m pytest tests/ -k "test_trigger_system"`
  - Expect: Trigger Entity 正确加载，AND/OR 事件组等待生效，事件消费后清除，多种事件源正确触发

- [ ] C11 验证配置文件夹 git 管理
  - Covers: A19, A20
  - Command: `python -m pytest tests/ -k "test_config_git_safety"`
  - Expect: DAG run 结束后自动 commit 变更，互斥锁阻止并发写入，无变更时不 commit

- [ ] C12 验证 Node 输出存储为 Entity
  - Covers: A22
  - Command: `python -m pytest tests/ -k "test_node_output_entity"`
  - Expect: 输出存储到 node_outputs 表，包含 cycle_id/node_id/payload/session_id，可通过 Entity Store 查询

- [ ] C13 验证数据迁移脚本
  - Covers: A23, A24
  - Command: `python -m pytest tests/ -k "test_migration_scripts"`
  - Expect: 现有 RawItem/AnalysisResult/Advice/Briefing 数据正确迁移到 node_outputs 表，现有 Node/DAG YAML 正确转换为 Entity 格式

- [ ] C14 验证 Web Console API 适配
  - Covers: A25
  - Command: `python -m pytest tests/ -k "test_web_api_entity_crud"`
  - Expect: Web API 通过统一 Entity CRUD 接口操作所有类型 Entity

- [ ] C15 验证 handler 校验工具
  - Covers: A26
  - Command: `python -m pytest tests/ -k "test_handler_validator"`
  - Expect: 校验工具检测语法错误和签名不匹配，正确 handler 通过校验

- [ ] C16 验证条件死路径检测
  - Covers: A7
  - Command: `python -m pytest tests/ -k "test_dead_path_detection"`
  - Expect: 所有条件边都不满足时记录 warning 到 run metadata，不视为执行错误

- [ ] C17 验证 retention 策略清理输出型 Entity
  - Covers: A3, A4
  - Command: `python -m pytest tests/ -k "test_retention_cleanup"`
  - Expect: 超过 retention_count 或 retention_hours 的输出 Entity 被正确清理
