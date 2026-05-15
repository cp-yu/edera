## 1. Recovery Recording

- [x] 1.1 增加源级恢复配置读取，包含启用开关、最大尝试次数和 repair task 输出目录默认值
- [x] 1.2 在 source 节点执行路径识别限定可恢复异常，并按配置执行有限恢复尝试
- [x] 1.3 将恢复结果写入 `Briefing.metadata_`，保持旧 `failed_sources` 兼容
- [x] 1.4 确保 `NodeRun` 只记录最终节点状态，并保留失败 error 供日志追溯

## 2. Health And Escalation Surface

- [x] 2.1 扩展 `source_health_summary()` 返回 recovery_status、attempt_count、升级状态和最近 repair task 摘要
- [x] 2.2 扩展 `/api/sources/health` 与 `/sources` 页面展示恢复、升级和 handoff 状态
- [x] 2.3 保持 `/api/sources/logs` cycle_id、node error 和 pipeline status 输出兼容

## 3. Repair Task Handoff

- [x] 3.1 增加最小 handoff API，为已升级 source 生成 repair task 文件
- [x] 3.2 repair task 文件只写入 source 配置片段、最近失败上下文、恢复尝试摘要和期望修复目标
- [x] 3.3 拒绝未升级 source 的 handoff 请求，并返回统一 JSON error

## 4. Verification

- [x] 4.1 增加 source recovery 成功、恢复耗尽升级、不可恢复直接升级的单元测试
- [x] 4.2 增加 source health API 和 handoff API 集成测试
- [x] 4.3 运行相关测试与 `openspec validate source-recovery-escalation --type change --json`
