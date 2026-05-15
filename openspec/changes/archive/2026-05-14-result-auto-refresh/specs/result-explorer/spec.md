## ADDED Requirements

### Requirement: Result auto refresh
系统 SHALL 在结果浏览首页自动检测最新 `Briefing` 版本，并在新结果到达时刷新页面以展示新结果。

#### Scenario: Refresh when latest briefing changes
- **WHEN** 用户打开结果浏览首页且之后 `GET /api/briefings/latest` 返回的 `Briefing.id` 或 `created_at` 与页面初始版本不同
- **THEN** 系统 SHALL 自动刷新当前结果浏览页面，并保留当前 URL 查询参数

#### Scenario: Keep empty state while waiting for first briefing
- **WHEN** 用户打开结果浏览首页且数据库中没有任何 `Briefing`
- **THEN** 系统 SHALL 显示既有空状态，并继续检测直到新 `Briefing` 到达

#### Scenario: Tolerate refresh check failure
- **WHEN** 自动刷新检查请求失败或返回非 2xx 响应
- **THEN** 系统 MUST 保持当前页面内容可用，并在后续检查周期继续检测
