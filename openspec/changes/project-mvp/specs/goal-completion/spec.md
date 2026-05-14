## ADDED Requirements

### Requirement: PRD 门禁
系统 MUST 在 MVP 完成前提供 PRD 门禁检查，确保 P1 范围可执行、可测试、无阶段冲突。

#### Scenario: P1 范围映射完整
- **WHEN** 执行完成门禁检查
- **THEN** PRD 中所有 P1 FR（FR1、FR2、FR3、FR4、FR7、FR11、FR15、FR18、FR19、FR20、FR21、FR22、FR26、FR27、FR29、FR30、FR31、FR32、FR46）均映射到 OpenSpec Requirement 和至少一个测试用例

#### Scenario: P2/P3 不阻塞 MVP
- **WHEN** 执行完成门禁检查
- **THEN** Dashboard、事件态势、多渠道推送、自动恢复、参数调优等 P2/P3 内容不得作为 MVP 完成条件

#### Scenario: Critical 校验未清除
- **WHEN** `_bmad-output/planning-artifacts/prd-validation-report.md` 的 `overallStatus` 仍为 `Critical`
- **THEN** 完成门禁失败，并输出阻塞原因

### Requirement: 测试金字塔门禁
系统 MUST 在 MVP 完成前通过单元测试、契约测试、集成测试和端到端验收测试。

#### Scenario: 单元测试覆盖确定性逻辑
- **WHEN** 执行 `pytest tests/unit`
- **THEN** 配置解析、URL 去重、RSS 解析、非标准源规则解析、通知摘要格式、建议结构校验、简报元数据校验均通过

#### Scenario: 契约测试阻断无证据输出
- **WHEN** 执行 `pytest tests/contract`
- **THEN** LLM Node 输出 schema、AnalysisResult 溯源字段、Advice 审计字段、凭据不入仓库检查均通过

#### Scenario: 集成测试覆盖主链路降级
- **WHEN** 执行 `pytest tests/integration`
- **THEN** 假 RSS 源、假 LLM、假通知通道可跑通默认 DAG；单个信息源失败不阻塞流程；重复 URL 不重复生成建议或通知

#### Scenario: E2E 验收测试生成完整产物
- **WHEN** 执行 `pytest tests/e2e`
- **THEN** 固定信息源 fixture、固定持仓配置、fake LLM 返回驱动一次 MVP pipeline，并生成结构化采集结果、分析摘要、买/卖/持有建议、证据 URL、原文引用、简报、通知 payload、审计记录

### Requirement: 性能与可靠性门禁
系统 MUST 在可控 fixture 环境中验证 MVP 关键性能与降级指标。

#### Scenario: 分析延迟达标
- **WHEN** 单条信息进入默认 DAG 的分析队列
- **THEN** 在 fake LLM 环境下 30s 内生成 AnalysisResult

#### Scenario: 周期流程达标
- **WHEN** 默认 30min 周期任务触发
- **THEN** 采集、分析、建议、简报、推送流程在一个周期内完成，并至少产生一次用户可感知输出

#### Scenario: 号外通知达标
- **WHEN** fixture 输入触发高优先级事件
- **THEN** priority=5 通知 payload 在 5min 内生成，且包含买/卖方向和核心原因

#### Scenario: 进程异常可恢复
- **WHEN** 单次节点执行异常
- **THEN** 系统记录降级状态，保留可审计错误信息，后续周期可继续执行

### Requirement: 完成判定入口
系统 MUST 提供单一完成判定入口，供 `/goal` 或人工验收使用。

#### Scenario: 完成命令全部通过
- **WHEN** 执行 `pytest tests/unit tests/contract tests/integration tests/e2e`、`ruff check .`、`mypy src`
- **THEN** 所有命令返回 0，且完成门禁报告列出 P1 FR 到测试用例的映射

#### Scenario: 任一门禁失败
- **WHEN** PRD 门禁、测试命令、P1 映射、E2E 产物断言任一失败
- **THEN** `/goal` 不得标记完成，并输出失败门禁名称与阻塞项
