## ADDED Requirements

### Requirement: RawItem 数据模型
系统 SHALL 定义 RawItem 模型存储采集的原始条目，MUST 包含：url（唯一标识）、title、content、source_name、source_type、stock_codes（关联标的列表）、published_at、fetched_at。

#### Scenario: 创建 RawItem 记录
- **WHEN** 采集节点抓取到一条新信息
- **THEN** 系统创建 RawItem 记录，所有必填字段均有值，url 作为去重唯一标识

#### Scenario: URL 去重
- **WHEN** 采集节点尝试创建一条已存在 url 的 RawItem
- **THEN** 系统跳过该条目，不创建重复记录

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
