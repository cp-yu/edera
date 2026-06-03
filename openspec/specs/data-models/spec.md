---
capabilities:
  - cap.data.data-models
---
# data-models Specification

## Purpose
定义 RawItem 数据模型、AnalysisResult 数据模型、Advice 数据模型、Briefing 数据模型等能力。
## Requirements
### Requirement: RawItem 数据模型

系统 SHALL 定义 RawItem 模型存储采集的原始条目，MUST 包含：url（唯一标识）、title、content、source_name、source_type、tags（关联实体引用列表）、published_at、fetched_at。

#### Scenario: 创建 RawItem 记录

- **WHEN** 采集节点抓取到一条新信息
- **THEN** 系统创建 RawItem 记录，所有必填字段均有值，url 作为去重唯一标识

#### Scenario: URL 去重

- **WHEN** 采集节点尝试创建一条已存在 url 的 RawItem
- **THEN** 系统跳过该条目，不创建重复记录

#### Scenario: Store entity tags

- **WHEN** 系统保存 RawItem 到数据库
- **THEN** 系统 SHALL 将关联的实体引用存储在 `tags` 字段（如 `["stock:00700.HK", "city:北京"]`）

#### Scenario: Query by entity tag

- **WHEN** 系统查询特定实体的 RawItem
- **THEN** 系统 SHALL 通过 `tags` 字段过滤（如 `WHERE "stock:00700.HK" = ANY(tags)`）

#### Scenario: Migrate from stock_codes

- **WHEN** 系统从旧数据库迁移
- **THEN** 系统 SHALL 将 `stock_codes` 中的值转换为 `tags`（如 `["00700.HK"]` → `["stock:00700.HK"]`）

### Requirement: AnalysisResult 数据模型
系统 SHALL 定义 AnalysisResult 模型存储分析结果，MUST 包含：raw_item_id（关联原始条目）、summary、keywords、sentiment（bullish/bearish/neutral）、confidence、source_quote（原文引用片段）、source_url（原始 URL）。

#### Scenario: 创建 AnalysisResult 记录
- **WHEN** 分析节点完成一条 RawItem 的分析
- **THEN** 系统创建 AnalysisResult 记录，关联到原始 RawItem，包含原文引用和 URL 溯源

### Requirement: Advice 数据模型
系统 SHALL 定义 Advice 模型存储交易建议，MUST 包含：stock_code、stock_name、direction（buy/sell/hold）、confidence、reason（核心原因）、evidence（分析结果引用列表）、source_quotes（原文引用片段列表）、source_urls（原始 URL 列表）、portfolio_snapshot（生成时的投资情况快照）、created_at、data_window_start、data_window_end。

#### Scenario: 创建完整审计字段的 Advice
- **WHEN** 建议节点生成一条交易建议
- **THEN** Advice 记录包含所有审计字段，缺失任一必填字段时系统拒绝创建

#### Scenario: 建议版本化
- **WHEN** 同一标的因新信息更新建议
- **THEN** 系统创建新版本 Advice 记录，保留旧版本，两者通过 version 字段关联

### Requirement: Briefing 数据模型
系统 SHALL 定义 Briefing 模型存储简报，MUST 包含：run_id、content（简报正文）、metadata（配置源列表/成功源列表/失败源列表/数据时间窗口）、created_at。

#### Scenario: 创建带元数据的 Briefing
- **WHEN** 简报生成节点完成简报
- **THEN** Briefing 记录的 metadata 包含本周期所有信息源的采集状态
- **AND** Briefing 记录的 `run_id` 字段关联到对应的 DAG run

#### Scenario: 通过 run_id 查询 Briefing
- **WHEN** 用户查询特定 run 的简报
- **THEN** 系统 SHALL 通过 `run_id` 字段过滤（如 `WHERE run_id = 'abc123'`）

### Requirement: 数据库引擎与 Migration
系统 SHALL 使用 SQLite（WAL 模式）+ aiosqlite 异步驱动，MUST 使用 Alembic 管理所有 schema 变更。

#### Scenario: 初始 Migration
- **WHEN** 首次运行 Alembic migration
- **THEN** 创建所有表结构（raw_items、analysis_results、advices、briefings）

#### Scenario: WAL 模式
- **WHEN** 数据库引擎初始化
- **THEN** SQLite 启用 WAL 模式

### Requirement: EventRecord 数据模型
系统 SHALL 定义 EventRecord 模型存储事件态势记录，MUST 包含 stock_code、title、normalized_keywords、status、heat_score、contradiction、evidence_analysis_ids、evidence_raw_item_ids、source_names、first_seen_at、last_seen_at、created_at 和 updated_at。

#### Scenario: 创建事件记录
- **WHEN** 事件管理能力从归并后的 AnalysisResult 创建新事件
- **THEN** 系统 SHALL 创建 EventRecord，且 evidence_analysis_ids、evidence_raw_item_ids、source_names 和 normalized_keywords 均来自本地 RawItem/AnalysisResult 证据

#### Scenario: 更新事件记录
- **WHEN** 新 AnalysisResult 被归入既有事件
- **THEN** 系统 SHALL 更新 EventRecord 的证据 ID、source_names、last_seen_at、updated_at、contradiction 和 heat_score

### Requirement: EventRecord 状态约束
系统 SHALL 将 EventRecord.status 限定为 discovered、verifying、monitoring、climax、fading 或 archived，MUST 拒绝其他状态值。

#### Scenario: 接受合法状态
- **WHEN** 事件记录状态为 discovered、verifying、monitoring、climax、fading 或 archived 之一
- **THEN** 系统 SHALL 保存该事件记录

#### Scenario: 拒绝非法状态
- **WHEN** 事件记录状态不是 discovered、verifying、monitoring、climax、fading 或 archived
- **THEN** 系统 MUST 拒绝保存该事件记录

### Requirement: EventRecord 证据可追溯性
系统 SHALL 保证 EventRecord 可追溯到关联 RawItem 和 AnalysisResult，MUST 不保存没有本地证据 ID 的正式事件记录。

#### Scenario: 查询事件证据
- **WHEN** 系统查询一条 EventRecord 的证据
- **THEN** 系统 SHALL 返回关联 AnalysisResult 的 summary、sentiment、source_quote、source_url 和关联 RawItem 的 title、url、source_name、published_at

#### Scenario: 阻断无证据事件
- **WHEN** 事件记录缺少 evidence_analysis_ids 或 evidence_raw_item_ids
- **THEN** 系统 MUST 不将其作为正式事件记录保存

### Requirement: 统一输出 Entity 存储

系统 SHALL 将所有 Node 输出统一存储为输出型 Entity，使用统一的 `node_outputs` 表替代当前的多表模型（RawItem、AnalysisResult、Advice、Briefing）。

#### Scenario: 存储 RawItem 为输出 Entity

- **WHEN** 采集节点抓取到原始条目
- **THEN** 系统存储为 `type: raw-item` 的 Entity，`attributes` 包含 url、title、content、source_name、tags、published_at、fetched_at

#### Scenario: 存储 AnalysisResult 为输出 Entity

- **WHEN** 分析节点完成分析
- **THEN** 系统存储为 `type: analysis` 的 Entity，`attributes` 包含 raw_item_id、summary、keywords、sentiment、confidence、source_quote、source_url

#### Scenario: 存储 Advice 为输出 Entity

- **WHEN** 建议节点生成交易建议
- **THEN** 系统存储为 `type: advice` 的 Entity，`attributes` 包含 action、reasoning、evidence、confidence

#### Scenario: 存储 Briefing 为输出 Entity

- **WHEN** 简报节点生成简报
- **THEN** 系统存储为 `type: briefing` 的 Entity，`attributes` 包含 content、summary、generated_at

### Requirement: 统一查询接口

系统 SHALL 通过 Entity Store 统一查询所有输出型 Entity，支持按 type、run_id、node_id、tags 过滤。

#### Scenario: 按 type 查询

- **WHEN** 用户查询所有 `type: analysis` 的 Entity
- **THEN** 系统从 `node_outputs` 表返回所有分析结果

#### Scenario: 按 run_id 查询

- **WHEN** 用户查询某次 run 的所有输出
- **THEN** 系统返回该 run_id 下所有输出 Entity

#### Scenario: 按 tags 查询

- **WHEN** 用户查询 `tags` 包含 `"stock:00700.HK"` 的所有 Entity
- **THEN** 系统返回所有关联该 stock 的输出 Entity（跨类型）

### Requirement: URL 去重保持

系统 SHALL 对 `type: raw-item` 的输出 Entity 保持 URL 去重逻辑。

#### Scenario: URL 去重

- **WHEN** 采集节点尝试存储一条已存在 url 的 raw-item Entity
- **THEN** 系统跳过该条目，不创建重复记录

### Requirement: 数据迁移

系统 SHALL 提供迁移脚本将现有多表数据迁移到统一 `node_outputs` 表。

#### Scenario: 迁移 RawItem 表

- **WHEN** 执行迁移脚本
- **THEN** 系统将 `raw_items` 表的每条记录转换为 `type: raw-item` 的 Entity 存入 `node_outputs` 表

#### Scenario: 迁移后旧表保留

- **WHEN** 迁移完成
- **THEN** 系统保留旧表作为备份，不自动删除

### Requirement: DagRun 数据模型
系统 SHALL 定义 DagRun 模型存储 DAG 执行记录，MUST 包含：run_id（唯一标识）、dag_name、source（发起来源）、status、started_at、ended_at、error、retry_of，表名为 `dag_runs`。

#### Scenario: 创建 DagRun 记录
- **WHEN** DAG 开始执行
- **THEN** 系统创建 DagRun 记录，`run_id` 为 UUID，`source` 标注发起方式

#### Scenario: source 字段合法值
- **WHEN** 系统创建 DagRun 记录
- **THEN** `source` 字段 SHALL 为以下值之一：`manual`、`retry`、`trigger:<trigger_name>`

#### Scenario: startup source rejected
- **WHEN** 系统尝试创建 `source = "startup"` 的 DagRun
- **THEN** 系统 MUST 拒绝该记录

#### Scenario: Trigger Entity fire 时记录 source
- **WHEN** Trigger Entity `morning-cron` fire 启动 DAG
- **THEN** DagRun 记录的 `source` 字段 SHALL 为 `trigger:morning-cron`

#### Scenario: 手动运行记录 source
- **WHEN** 用户通过 CLI 或 UI 手动运行 DAG
- **THEN** DagRun 记录的 `source` 字段 SHALL 为 `manual`

#### Scenario: 重试记录 source
- **WHEN** 用户重试失败的 run
- **THEN** DagRun 记录的 `source` 字段 SHALL 为 `retry`

### Requirement: NodeRun 数据模型使用 run_id
系统 SHALL 定义 NodeRun 模型存储节点执行记录，MUST 包含：run_id（外键关联 dag_runs.run_id）、node_id（DAG 节点实例 UUID）、status、started_at、ended_at、error、failure_kind。人类可读 alias/type 由投影层补齐，不写入 runtime 表。

#### Scenario: 创建 NodeRun 记录
- **WHEN** 节点开始执行
- **THEN** 系统创建 NodeRun 记录，`run_id` 关联到父 DagRun

#### Scenario: Sub-DAG 记录 parent_run_id
- **WHEN** 子 DAG 作为节点执行
- **THEN** 子 DAG 的 NodeRun 记录的 `metadata.parent_run_id` 字段 SHALL 关联到父 run_id
- **AND** 子 DAG 的 DagRun 有独立的 `run_id`

### Requirement: NodeOutput 数据模型使用 run_id
系统 SHALL 定义 NodeOutput 模型存储节点输出，MUST 包含：run_id（外键关联 dag_runs.run_id）、node_id、payload、ok、created_at。

#### Scenario: 创建 NodeOutput 记录
- **WHEN** 节点执行完成
- **THEN** 系统创建 NodeOutput 记录，`run_id` 关联到对应的 DAG run

### Requirement: EdgeInput 数据模型使用 run_id
系统 SHALL 定义 EdgeInput 模型存储边输入事实，MUST 包含：run_id（外键关联 dag_runs.run_id）、from_node_id、to_node_id、payload、created_at。

#### Scenario: 记录 edge input fact
- **WHEN** DAG dispatcher 在节点调度决策点生成边输入事实
- **THEN** 系统创建 EdgeInput 记录，`run_id` 关联到对应的 DAG run
