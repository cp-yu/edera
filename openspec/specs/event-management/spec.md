# event-management Specification

## Purpose
此规约记录变更 event-situation-foundation 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 事件创建与更新（FR12）
系统 SHALL 基于跨源归并后的信息创建和更新事件记录，MUST 保留事件与 RawItem、AnalysisResult 的证据链接。

#### Scenario: 从新事件组创建事件
- **WHEN** 归并结果无法匹配既有活跃 EventRecord
- **THEN** 系统 SHALL 创建新的 EventRecord，status=discovered，并写入 stock_code、title、normalized_keywords、evidence_analysis_ids、evidence_raw_item_ids 和 source_names

#### Scenario: 用新增证据更新事件
- **WHEN** 归并结果匹配既有非 archived EventRecord
- **THEN** 系统 SHALL 更新该 EventRecord 的证据集合、source_names、last_seen_at、updated_at、contradiction 和 heat_score，而不是创建重复事件

#### Scenario: 不更新已归档事件
- **WHEN** 归并结果只匹配 archived EventRecord
- **THEN** 系统 SHALL 创建新的 EventRecord 或保持归档事件不变，MUST 不自动重开 archived 事件

### Requirement: 事件生命周期状态（FR13）
系统 SHALL 管理事件最小生命周期状态：discovered、verifying、monitoring、climax、fading、archived。

#### Scenario: 新事件处于发现状态
- **WHEN** 系统首次创建 EventRecord
- **THEN** 系统 SHALL 设置 status=discovered

#### Scenario: 多源或矛盾证据进入验证
- **WHEN** EventRecord 拥有多个独立 source_names 或 contradiction=true
- **THEN** 系统 SHALL 能将 status 更新为 verifying

#### Scenario: 持续新增证据进入监控
- **WHEN** EventRecord 在连续处理周期中新增本地证据且尚未达到 climax 条件
- **THEN** 系统 SHALL 能将 status 更新为 monitoring

#### Scenario: 高热度事件进入高潮
- **WHEN** EventRecord.heat_score 达到配置或默认 climax 阈值
- **THEN** 系统 SHALL 能将 status 更新为 climax

#### Scenario: 证据降温进入消退
- **WHEN** EventRecord 超过降温窗口没有新增证据或 heat_score 下降到 fading 阈值
- **THEN** 系统 SHALL 能将 status 更新为 fading

#### Scenario: 事件归档
- **WHEN** EventRecord 超过归档窗口或用户/系统显式归档事件
- **THEN** 系统 SHALL 将 status 更新为 archived

### Requirement: 确定性事件热度分数（FR14）
系统 SHALL 基于本地证据计算 EventRecord.heat_score，MUST 使用 evidence_count、source_diversity、recency 和 contradiction 作为输入，MUST 不访问实时外部市场数据。

#### Scenario: 计算可复现热度
- **WHEN** 相同 RawItem、AnalysisResult 和事件配置输入被重复处理
- **THEN** 系统 SHALL 生成相同 heat_score 和相同 heat_score_components

#### Scenario: 来源多样性提升热度
- **WHEN** 两个事件拥有相同 evidence_count 和 recency，但其中一个事件拥有更多独立 source_names
- **THEN** 多来源事件的 heat_score SHALL 不低于单来源事件

#### Scenario: 矛盾信息提升关注热度
- **WHEN** EventRecord.contradiction=true
- **THEN** heat_score SHALL 包含 contradiction component，且 WebUI/API SHALL 能展示该事件存在矛盾证据

#### Scenario: 不使用实时行情
- **WHEN** 系统计算 EventRecord.heat_score
- **THEN** 系统 MUST 只使用本地 RawItem、AnalysisResult、EventRecord 和配置输入，不访问实时行情、成交量、热搜或第三方服务

