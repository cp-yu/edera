# Archived Specs

以下 spec 已被归档。它们描述的是旧架构或旧业务逻辑，已被当前架构取代。

## 归档理由分类

### 1. 旧架构概念（已不存在于代码中）
- **legacy-script-adapter** — UZI 旧脚本适配器模式，零代码引用
- **skill-registry** — 旧 YAML skill 定义 + `skill_handlers/` 目录，被 DB-backed Skill 取代
- **node-type-registry** — 全局 NodeType Registry 概念，被 DB-backed handler resolver 取代

### 2. 旧 YAML 配置模式（已被 DB-backed entity 取代）
- **config-management** — 旧 portfolio.yaml / entities.yaml 领域配置，FR29-32

### 3. 领域业务逻辑（handler 级，已移至 extensions 或废弃）
- **briefing-generation** — 旧简报生成，FR26-27, FR46
- **trade-advisory** — 旧交易建议，FR15, FR18
- **information-analysis** — 旧信息分析/情感分类，FR7-8, FR10-11
- **source-collection** — 旧 RSS/Web 采集，FR1-4
- **notification-delivery** — 旧 ntfy.sh 推送，FR19-22
- **source-health-monitoring** — 旧信息源健康监控
- **reflection-dag-pattern** — 旧反思 DAG 模式
- **data-models** — 旧 RawItem/AnalysisResult/Advice/Briefing 模型
- **minimax-retrieval-acceptance** — MiniMax 特定验收测试

### 4. 项目管理/验收（非系统 spec）
- **goal-completion** — MVP 完成门禁（P1 FR 映射、测试金字塔）

### 5. 旧 Web UI 功能（已被新 spec 取代）
- **result-explorer** — 旧结果浏览页面，被 dag-run-observability + dag-workbench-ui 取代

## 归档日期
2026-06-11
