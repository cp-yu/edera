## ADDED Requirements

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

系统 SHALL 通过 Entity Store 统一查询所有输出型 Entity，支持按 type、cycle_id、node_id、tags 过滤。

#### Scenario: 按 type 查询

- **WHEN** 用户查询所有 `type: analysis` 的 Entity
- **THEN** 系统从 `node_outputs` 表返回所有分析结果

#### Scenario: 按 cycle_id 查询

- **WHEN** 用户查询某次 run 的所有输出
- **THEN** 系统返回该 cycle_id 下所有输出 Entity

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
