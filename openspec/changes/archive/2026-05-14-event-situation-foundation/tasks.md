## 1. Data Model

- [x] 1.1 新增 EventRecord SQLModel，字段覆盖 stock_code、title、normalized_keywords、status、heat_score、heat_score_components、contradiction、evidence_analysis_ids、evidence_raw_item_ids、source_names、first_seen_at、last_seen_at、created_at、updated_at
- [x] 1.2 为 EventRecord 添加状态校验和证据非空校验
- [x] 1.3 新增 Alembic migration 创建事件记录表，不修改现有 RawItem、AnalysisResult、Advice、Briefing 字段语义
- [x] 1.4 在 repository 中增加事件创建、更新、列表、详情和按 analysis ids 查询相关事件的方法

## 2. Event Analysis Foundation

- [x] 2.1 实现关键词、标题、摘要和正文 token 的规范化工具，覆盖大小写、空白、标点和去重
- [x] 2.2 实现 stock_code + token overlap + 时间窗口的事件归并服务
- [x] 2.3 实现跨源矛盾检测，要求不同 source_name 或 source_url 才能标记多源矛盾
- [x] 2.4 复用 AnalysisResult.contradiction 标记属于矛盾证据的分析结果，并保持 source_quote/source_url 可查询
- [x] 2.5 实现 create/update EventRecord 规则，避免更新 archived 事件

## 3. Lifecycle And Heat

- [x] 3.1 实现 discovered、verifying、monitoring、climax、fading、archived 最小状态流转规则
- [x] 3.2 实现只基于本地 evidence_count、source_diversity、recency、contradiction 的确定性 heat_score
- [x] 3.3 返回 heat_score_components，供测试和 WebUI 解释热度来源
- [x] 3.4 确保热度计算不访问实时行情、成交量、热搜或任何新第三方服务

## 4. Result Explorer API And WebUI

- [x] 4.1 扩展 `/api/results` 返回 events 列表，并支持沿用 stock_code 过滤
- [x] 4.2 扩展 `/api/advices/{id}` 返回 Advice 证据相关事件，缺少事件时保持既有 payload 可用
- [x] 4.3 在 `/results` 页面增加事件组表格或列表，展示 status、heat_score、contradiction、source count、evidence count 和 evidence links
- [x] 4.4 在 `/results/advices/{id}` 页面增加相关事件上下文，保持 textual/table/badge 展示，不引入图或图表
- [x] 4.5 增加事件空状态，确保无事件数据时结果页和建议详情页不报错

## 5. Tests And Verification

- [x] 5.1 添加 data model 和 migration 测试，覆盖合法/非法 status 与无证据阻断
- [x] 5.2 添加事件归并测试，覆盖同标的同事件、不同标的相似关键词、超出时间窗口不归并
- [x] 5.3 添加跨源矛盾检测测试，覆盖不同来源矛盾、同源重复不算多源矛盾
- [x] 5.4 添加 heat_score fixture 测试，确认相同输入得到相同输出
- [x] 5.5 添加 Result Explorer API/WebUI 测试，覆盖事件展示、矛盾 badge、建议详情相关事件和无事件空状态
- [x] 5.6 运行 `openspec validate event-situation-foundation --type change --json`
- [x] 5.7 运行项目现有相关测试，例如 `pytest`
