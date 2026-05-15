## ADDED Requirements

### Requirement: Advice comparison API display
系统 SHALL 在结果浏览 API 中为建议记录展示基于本地价格历史计算的 comparison 字段，覆盖列表、结果摘要和建议详情。

#### Scenario: List advices with comparison
- **WHEN** 用户请求 `/api/advices` 或 `/api/results`
- **THEN** 系统 SHALL 在每条 advice payload 中包含 comparison verdict、horizon、baseline price、horizon price、price_change_percent 和 unknown reason

#### Scenario: Open advice detail with comparison
- **WHEN** 用户请求 `/api/advices/{id}`
- **THEN** 系统 SHALL 返回该建议的 comparison 字段，并保持既有 `Advice`、`AnalysisResult` 和 `RawItem` 证据链字段可用

### Requirement: Advice comparison WebUI display
系统 SHALL 在本机 Web 结果浏览界面展示建议价格对比 verdict，让用户能从建议列表和建议详情复盘历史建议与价格移动的关系。

#### Scenario: View comparison in results page
- **WHEN** 用户打开 `/results` 且建议存在
- **THEN** 系统 SHALL 在当前摘要和建议表格中显示每条建议的 comparison verdict，并用非纯颜色依赖的文本标签区分 `aligned`、`diverged` 和 `unknown`

#### Scenario: View comparison in advice detail page
- **WHEN** 用户打开 `/results/advices/{id}`
- **THEN** 系统 SHALL 展示该建议的 comparison verdict、baseline price、horizon price、price_change_percent、horizon 和 unknown reason

#### Scenario: Keep WebUI usable when comparison is unknown
- **WHEN** comparison verdict 为 `unknown`
- **THEN** 系统 SHALL 继续展示 advice 内容和证据链，并在 comparison 区域显示 unknown reason
