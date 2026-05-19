# data-models Specification

## Purpose
此规约记录变更 project-mvp 引入的行为，请在后续同步或归档前补全正式 Purpose。
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
系统 SHALL 定义 Briefing 模型存储简报，MUST 包含：cycle_id、content（简报正文）、metadata（配置源列表/成功源列表/失败源列表/数据时间窗口）、created_at。

#### Scenario: 创建带元数据的 Briefing
- **WHEN** 简报生成节点完成简报
- **THEN** Briefing 记录的 metadata 包含本周期所有信息源的采集状态

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

