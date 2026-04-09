# Temporary HOW Extraction Notes

## Purpose

This file temporarily stores implementation-oriented details extracted from `../planning-artifacts/prd.md` so the PRD can stay focused on WHAT, while preserving useful design context for later architecture and implementation work.

## PRD-to-Design Extraction Log

| PRD Area | Rewritten WHAT | Deferred HOW / Design Note |
|---|---|---|
| Executive Summary | 系统支持多类信息源采集、关联分析、建议输出、通知与 Web 呈现 | 原文中的多 Agent 管道、具体推送渠道、双循环调度、网页浏览型采集方式移出 PRD |
| What Makes This Special | 系统支持跨源归并、竞争性解释、可追溯建议 | 原文中的 ACH、事件引擎等实现机制移出 PRD |
| Success / Technical | 系统要求可追溯、可达、稳定 | 原文中的 `ntfy.sh`、具体存活机制表达移出 PRD |
| Innovation | 保留为能力与差异化结果 | 原文中的 SIR、弱信号共振、分级自愈机制细节移出 PRD |
| FR / NFR | 统一改为能力、边界、验收结果 | 原文中的 Skill/Agent/LLM prompt/Docker/PostgreSQL/provider names 等移出 PRD |

## Deferred Architecture / Design Notes

### Ingestion and Source Handling
- Original PRD assumed two acquisition modes:
  - browser-guided / workflow-driven extraction for harder sources
  - direct programmatic retrieval for structured/public sources
- Original PRD also distinguished RSS sources from non-RSS sources requiring source-specific logic.
- Later design needs to decide whether non-standard sources are modeled as `Skill`, adapter, connector, plugin, or another abstraction.

### Event Modeling and Analysis
- Original PRD referenced an event engine for:
  - cross-source merge
  - lifecycle state management
  - heat scoring
  - momentum/turning-point prediction
- Candidate mechanisms mentioned in the source PRD:
  - weighted source count
  - source credibility weighting
  - time decay
  - SIR-inspired turning point forecasting

### Recommendation Generation
- Original PRD referenced:
  - LLM-prompt-based direct recommendation generation in MVP
  - ACH-style multi-hypothesis reasoning in later phases
  - weak-signal resonance for high-confidence suggestions
- Recommendation inputs now explicitly include:
  - current collected/structured market information
  - user current investment situation snapshot
- Later design needs to define:
  - evidence schema
  - contradiction handling
  - recommendation confidence representation
  - trigger thresholds for stronger recommendations
  - schema for user investment situation snapshot (e.g. holdings, cost basis, target position, cash, risk preference if applicable)

### Notification and Delivery
- Original PRD named `ntfy.sh` and described:
  - priority levels: urgent/high/default/low
  - digest vs alert flows
  - cooldown behavior
  - deep links into dashboard views
- PRD now keeps channel requirements at WHAT level; provider choice remains deferred here.

### Runtime / Operations
- Original PRD referenced:
  - Docker deployment
  - restart policy
  - provider switching via base URL and API key
  - PostgreSQL
- These remain design choices, not PRD commitments.

## Open Design Questions
- How should non-standard source integrations be represented: adapter, connector, workflow, or skill?
- What is the canonical event schema across collection, analysis, recommendation, and dashboard display?
- What exact evidence model supports source traceability, contradiction marking, and auditability?
- How should cooldown, urgency scoring, and event significance interact?
- What minimum audit log is required for fintech-adjacent recommendation history?

## Measurability Assumptions Pending Confirmation
- Weekly simulated portfolio return will be compared against a同期基准指数.
- Current confirmed target: weekly excess return threshold `+3%`.
- Current confirmed scope: keep as hard success criterion.
- Current confirmed constraint: no additional drawdown/volatility requirement for now.
- Confirmed coverage metric:
  - compare against 同花顺 as the reference information stream
  - use independent time-entry count as the counting unit
  - weekly system coverage count should be greater than or equal to the reference count for the same comparison scope
- Confirmed alert timing:
  - urgent event alerts keep target `<=1 min`, hard limit `<=5 min`
  - urgent alerts are not constrained by the regular digest schedule
  - regular digests run every `15 min` during trading hours
  - outside trading hours, fixed digests are required at pre-open, auction stage, and post-close
- Confirmed notification summary measurability:
  - notifications must include a title
  - regular notification title length limit: `16` Chinese characters
  - summary content must include: symbol, direction, core reason, time, confidence
  - users should be able to make an initial judgment without opening the Web interface
- Confirmed dashboard value metrics:
  - users should use the Dashboard for historical review at least `2` times per week
  - time from opening the Dashboard to completing one initial judgment should be `<=5 min`
- Confirmed audit/compliance measurability:
  - recommendation records are retained long-term by default
  - system provides deletion capability triggered by time conditions
  - minimum audit fields: symbol, time, direction, core reason, confidence, source URL, source excerpt
  - event/recommendation state transitions must be recorded
  - recommendation audit must include the user's current investment situation snapshot
  - recommendation revisions must preserve before/after versions
  - audit records must support query by symbol, time range, recommendation direction, and confidence
  - deletion operations must themselves be logged
  - structured upstream information used by recommendation generation must be included in audit scope
- Confirmed abuse/misleading-risk handling:
  - low-confidence recommendations may still be output, but must be explicitly labeled as low confidence
  - when obvious contradictions exist across sources, the system may still generate a recommendation, but must show contradiction sources and conflict context
  - current user intent assumes contradiction handling depends on an upstream cross-validation stage that provides structured information to later analysis/recommendation stages
- Confirmed boundary display:
  - the non-investment-advice disclaimer must appear in the Web UI and README
  - do not add an explicit hard-boundary declaration for "no trading / no custody / no non-public data" at this stage
- Confirmed local investment-context boundary:
  - the user's current investment situation is stored locally only
  - it is used only as contextual input for recommendation generation
