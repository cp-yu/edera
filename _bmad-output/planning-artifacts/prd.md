---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
inputDocuments: ['_bmad-output/brainstorming/brainstorming-session-2026-04-02-1442.md']
workflowType: 'prd'
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 1
  projectDocs: 0
classification:
  projectType: web_app
  domain: fintech
  complexity: high
  projectContext: greenfield
  notes: '个人工具，可能开源；需加免责声明（不构成投资建议）'
---

# Product Requirements Document - stockImformation

**Author:** Yunxin
**Date:** 2026-04-09

## Executive Summary

stockImformation 是一个面向港股/A股个人交易者的自动化信息分析系统。系统通过多Agent管道自动采集7类可配置信息源（公司官网、平台生态、财经RSS、交易所公告、社交舆情、技术社区、政策监管），经过交叉验证、深度研读、事件归并后，生成结构化的交易建议报告，并通过可插拔的推送渠道（初期 ntfy.sh）和 Web Dashboard 呈现。

核心目标：将交易者从分散的信息采集和人工分析中解放出来，直接获得可行动的决策建议。系统采用双循环调度（30分钟定时 + RSS/随机巡游实时），确保常规简报的稳定输出与突发事件的即时响应。

信息采集支持双模式：Agent Skill 浏览网页获取 + 程序化直接获取，按信息源特性灵活选择。

目标用户：个人交易者（初期自用，后续可能开源）。

免责声明：系统产出仅供参考，不构成投资建议。

### What Makes This Special

- **信息源可定制：** 用户自主配置标的与信息源映射，不被平台信息流锁定
- **跨源关联分析：** 通过事件引擎将多源信息归并为事件，识别看似独立信息之间的关联性
- **两层价值输出：** 表层 — 即时响应（"这个消息出来了，可以买/卖"）；深层 — 关联发现（"这几条信息之间有这样的联系，所以有这个判断"）
- **纯LLM研判 + ACH框架：** 对每个标的用竞争假设分析（涨/跌/横盘），逐事件验证/反驳，附带概率和因子归因，每条判断强制原文引用+URL溯源

## Project Classification

- **项目类型：** Web App（多Agent后端服务 + Web Dashboard）
- **领域：** Fintech（港股/A股交易信息分析与辅助）
- **复杂度：** 高（金融领域、多信息源采集、LLM分析链路、实时性要求）
- **项目状态：** Greenfield（全新项目）

## Success Criteria

### User Success

- **时间解放：** 用户从全时段盯盘转为仅关注通知推送，信息处理时间减少 95%
- **即时感知：** 重要公告/事件推送延迟目标 ≤1min，最迟不超过 5min
- **决策可行动：** 每条建议直接关联买/卖/持有动作，附带原因归因和原文溯源，用户无需二次查证

### Business Success

- **核心指标：** 使用系统后的交易收益率 vs 不使用时显著提升
- **3个月目标：** 系统稳定运行，覆盖主要持仓标的，日常简报和号外推送形成可靠节奏
- **开源指标（远期）：** GitHub Star、Fork、Issue 活跃度反映社区认可

### Technical Success

- **采集可靠性：** 每周期简报元数据明确标注成功/失败源，采集成功率 >85%
- **推送可达性：** ntfy.sh 推送到达率 >99%
- **系统存活性：** 每30min必推机制（有料高优先级/无料低优先级），用户可感知系统在线
- **LLM幻觉防护：** 每条判断强制原文引用 + URL溯源链，可验证率 100%

### Measurable Outcomes

- **信息覆盖准确性 >90%：** 相关重要信息不遗漏
- **建议方向参考价值：** 事后回溯建议方向与价格变动一致率，作为持续追踪优化指标（不预设硬目标）
- **推送延迟：** 号外事件 ≤1min（目标），≤5min（底线）；常规简报每30min一次

## User Journeys

### Journey 1: 日常简报 — "一切正常，无需行动"

**角色：** Yunxin，个人交易者，持有港股/A股若干标的

**Opening Scene：** 工作日下午，手机收到一条 ntfy 推送（default 优先级）。Yunxin 瞄一眼摘要 — 各标的无异常波动，信息与持仓预期一致。

**Resolution：** 手指划掉通知，继续手头的事。全程 <5秒。系统确认了"没有意外"，这本身就是价值。

### Journey 2: 日常简报 — "情况有变，需要评估"

**Opening Scene：** 同样场景，但摘要中某个标的出现利空信号，与持仓预期不符。

**Rising Action：** Yunxin 打开股票交易网站查看实时行情，同时打开 Dashboard 查看该条信息的详细分析 — 信息来源、利空分类依据、关联事件。

**Climax：** 综合股价走势和系统分析，决定是否调整仓位。

**Resolution：** 做出决策（持有/减仓/清仓），整个评估过程 5-10 分钟。

### Journey 3: 号外事件 — "立即行动"

**Opening Scene：** 手机收到 urgent 推送，某标的出现重大政策变动。

**Rising Action：** 看到摘要，判断需要立即操作。直接打开交易软件完成买入/卖出。

**Climax：** 操作完成后，打开 Dashboard 查看完整简报和分析链，验证决策依据。

**Resolution：** 确认系统判断合理，或发现补充信息需要后续关注。

### Journey 4: 信息源适配 — "接入新信息源"

**Opening Scene：** Yunxin 想接入一个新的信息源（如某公司官网IR页面），或买入新股票需要关联信息源。

**Rising Action：**
- **RSS类：** 直接在配置界面添加 RSS URL，绑定标的，即时生效
- **非RSS类：** 需要为该信息源开发对应的采集 Skill（定义抓取目标、解析规则等）。Skill 产出后绑定到对应标的

**Climax：** 采集 Agent 通过 Skill 完成首次抓取验证。

**Resolution：** 信息源正式上线，下一个采集周期纳入。也包括反向操作：剔除低质量信息源、删除不再关注的标的。

### Journey 5: 复盘与Agent调优 — "系统越用越准"

**Opening Scene：** 周末，Yunxin 回顾本周交易，想验证系统建议的准确性。

**Rising Action：** 打开 Dashboard 历史页面，对比历史建议方向与实际股价变动。

**Climax：** 发现某类信息源权重偏高/偏低，或某个 Agent 的判断逻辑有优化空间。

**Resolution：** 调整 Agent 参数或 prompt，提升后续分析质量。

### Journey 6: 采集故障 — "Skill 执行异常"

**Opening Scene：** 采集 Agent 使用某个 Skill 时遇到问题（目标页面改版、反爬策略变化等）。

**Rising Action：**
- **小问题 → 自动修复：** Agent 自行尝试修复（调整选择器、重试策略），修复成功后记录日志
- **大问题 → 上报：** Agent 无法自行解决，推送通知给用户。用户可选择：手动修复 Skill，或交由更强模型的 Agent 辅助修复

**Resolution：** Skill 恢复正常；或该信息源临时标记为不可用，简报元数据体现降级状态。

### Journey Requirements Summary

| 能力域 | 来源旅程 | 优先级 |
|--------|---------|--------|
| 推送摘要（通知栏级信息密度） | J1, J2, J3 | MVP |
| urgent 推送行动方向一句话 | J3 | MVP |
| Skill 开发/配置工作流（非RSS源适配） | J4 | MVP |
| RSS 源直接配置（无需 Skill） | J4 | MVP |
| Dashboard 三级信息架构（摘要→简报→分析链） | J2, J3 | Growth |
| 推送到 Dashboard 的深链跳转 | J2, J3 | Growth |
| 标的/信息源配置界面 | J4 | Growth |
| 历史建议 vs 股价对比视图 | J5 | Growth |
| 简报归档检索 | J5 | Growth |
| Agent 参数/prompt 调优入口 | J5 | Growth |
| Skill 执行异常自动修复（小问题） | J6 | Growth |
| 异常上报 + 用户/强模型协助修复（大问题） | J6 | Growth |
| Skill 执行日志与健康监控 | J4, J6 | Growth |
| 信息源健康状态监控 | J4, J6 | Growth |

## Domain-Specific Requirements

### 合规与监管

- **定位：** 学习/研究用途的个人工具，不涉及资金托管、交易执行或用户数据收集
- **免责声明：** 系统产出不构成投资建议，仅供学习参考
- **不适用项：** KYC/AML、PCI DSS、金融牌照等传统 fintech 合规要求均不适用

### 技术约束

- **数据获取：** 不区分商用/个人使用，按学习用途获取公开信息
- **LLM幻觉防护：** 每条判断强制原文引用 + URL溯源链（已纳入技术成功指标）
- **数据时效性：** 简报元数据强制标注数据时间窗口，避免基于过时信息的建议

### 开源策略

- **License：** 采用限制性开源协议（如 AGPL-3.0 或 BSL），限制商业使用
- **免责条款：** README 和系统界面均需包含"不构成投资建议"声明

### 风险缓解

| 风险 | 缓解措施 |
|------|---------|
| LLM幻觉产生错误建议 | 强制原文引用 + URL溯源 |
| 信息源数据过时 | 简报标注时间窗口 + 采集失败可见 |
| 用户误信建议造成损失 | 免责声明 + 建议附带置信度 |

## Innovation & Novel Patterns

### Detected Innovation Areas

- **跨源事件关联引擎：** 不同于传统信息聚合平台的"信息展示"模式，系统通过事件引擎将多个独立信息源的数据归并为事件，自动识别看似无关信息之间的关联性。从"信息搬运"到"信息理解"的质变
- **ACH情报分析框架引入交易决策：** 将CIA的竞争假设分析方法论应用于个人股票研判 — 对每个标的建立涨/跌/横盘多假设，用活跃事件逐一验证/反驳，输出概率化结论。跨域方法论迁移
- **采集 Skill 自适应修复：** Agent 在 Skill 执行异常时具备分级自愈能力（自动修复 → 上报用户 → 强模型辅助），系统在信息源环境变化时具备韧性
- **双循环调度架构：** 借鉴地震P波/S波概念，30min定时常规循环（S波）+ RSS/随机巡游实时循环（P波），兼顾全面性和时效性
- **SIR传染病曲线热度拐点预测：** 借鉴传染病传播模型（SIR曲线）量化事件热度演变，预测热度拐点（扩散高峰 → 消退），为事件生命周期状态机提供量化决策依据
- **弱信号叠加触发高置信建议（Alpha信号合成）：** 借鉴量化交易中弱Alpha信号合成思路，单条信息可能不足以触发建议，但多源弱信号共振（多个独立信息源同时出现同方向信号）时触发高置信度建议

### Market Context & Competitive Landscape

- 现有工具（东方财富、雪球、Wind）侧重信息展示和社区讨论，不做自动化跨源关联分析
- 量化交易平台（聚宽、RiceQuant）侧重数值型因子和回测，不处理非结构化文本信息
- 本系统填补了"非结构化公开信息 → 结构化事件分析 → 可行动建议"这一链路的空白

### Validation Approach

- **事件关联准确性：** 事后回溯验证事件归并是否正确（误关联率追踪）
- **建议有效性：** 建议方向与实际股价变动的一致率持续追踪
- **自愈机制有效性：** Skill 自动修复成功率 vs 上报率
- **热度拐点预测准确性：** SIR模型预测的拐点时间 vs 实际事件消退时间的偏差

### Risk Mitigation

| 创新风险 | 缓解策略 |
|---------|---------|
| 事件关联可能过度 / 误关联 | 验证Agent加轻量语义判断 + 事件级去重 |
| ACH框架在金融领域有效性未验证 | 持续追踪建议准确性，迭代prompt |
| 自愈机制可能掩盖根本问题 | 所有自动修复记录日志，定期review |
| SIR模型参数需校准 | 初期使用保守参数，根据实际事件数据逐步校准 |
| 弱信号共振可能误触发 | 设置最低共振阈值 + 冷却窗口 |

## Web App Specific Requirements

### Project-Type Overview

本系统为 SPA 架构的 Web Dashboard + 多Agent后端服务。Dashboard 用于信息消费、配置管理和历史回溯；后端负责信息采集、分析管道和推送。

### Technical Architecture Considerations

**前端：**
- **架构：** SPA（Single Page Application）
- **浏览器支持：** 现代浏览器（Chrome/Firefox/Edge 最新两个主版本）
- **SEO：** 不需要
- **无障碍：** 无特殊要求
- **实时更新：** Dashboard 在新推送到达时自动刷新（WebSocket / SSE）

**响应式设计：**
- Desktop 为主要使用场景
- Mobile 端主要依赖 ntfy 推送摘要，Dashboard 移动端适配为低优先级

### Performance Targets

- Dashboard 首屏加载 <2s
- 信息列表/简报页面切换 <500ms
- 实时推送到 Dashboard 刷新延迟 <1s

### Implementation Considerations

- 前后端分离，后端提供 REST API
- WebSocket/SSE 用于推送事件驱动的 Dashboard 实时刷新
- 前端状态管理需支持三级信息架构的渐进展开（摘要→简报→分析链）
- 深链支持：ntfy 推送中包含 Dashboard URL，点击直达对应信息详情

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach：** Problem-Solving MVP — 验证核心价值链"采集→分析→推送"能否产出有用的交易建议
**开发资源：** 个人开发 + Agent 辅助
**目标周期：** 1 周

### MVP Feature Set (Phase 1)

**Core User Journeys Supported：** J1（日常简报）、J3（号外事件）

**Must-Have Capabilities：**
- 数据采集层：至少3类信息源（财经RSS、交易所公告、社交舆情），RSS直接配置 + 非RSS采集Skill
- 研读Agent：信息摘要、关键词提取、利好/利空分类
- 建议Agent（简化版）：LLM prompt + 当前采集信息直接研判，输出买/卖/持有 + 核心原因
- 推送Agent：ntfy.sh 分级推送（urgent/high/default/low），摘要在通知栏级别可完成判断
- 30min定时调度（常规循环）
- 事件去重（URL为唯一ID）
- 持仓/关注列表配置（配置文件级别，无UI）
- 简报元数据：标注配置信息源/采集成功源/失败源/数据时间窗口

**MVP 不包含：**
- Web Dashboard（P2）
- 交叉验证Agent、事件引擎（P2）
- 建议Agent ACH深度研判（P2）
- RSS哨兵实时监听（P2）
- Skill 自动修复机制（P2）

### Post-MVP Features

**Phase 2 (Growth)：**
- Web Dashboard：三级信息架构（摘要→简报→分析链）+ 推送深链跳转
- 交叉验证Agent：关键词事件归并、信源加权、矛盾检测
- 建议Agent：ACH多假设研判框架 + 弱信号叠加共振触发
- 事件引擎：生命周期状态机 + 热度量化 + SIR曲线拐点预测
- RSS哨兵Agent：实时监听
- 全部7类信息源接入
- 标的/信息源配置界面
- Skill 执行异常自动修复 + 上报机制
- 历史建议 vs 股价对比视图
- Agent 参数/prompt 调优入口

**Phase 3 (Expansion)：**
- 随机巡游Agent
- 号外冷却机制 + 号外回流简报
- 概率化归因输出
- 推送渠道模块化扩展（Telegram/Email 等）
- 开源发布 + 社区化运营

### Risk Mitigation Strategy

| 风险类型 | 具体风险 | 缓解策略 |
|---------|---------|---------|
| 技术风险 | 非RSS信息源的 Skill 适配成本不可预测 | MVP 优先接入 RSS 源 + 交易所结构化数据，复杂源逐步接入 |
| 技术风险 | LLM 分析质量不稳定 | 强制原文引用+溯源链，持续迭代 prompt |
| 市场风险 | 建议对交易决策的实际帮助程度未知 | MVP 快速验证，1周出结果，根据实际使用调整 |
| 资源风险 | 个人开发精力有限 | Agent辅助开发；MVP极简（无Dashboard、无复杂Agent链路） |

## Functional Requirements

### 信息采集

- FR1: 系统可通过 RSS 订阅自动拉取财经新闻流 [P1]
- FR2: 系统可通过采集 Skill 从非RSS信息源抓取结构化信息 [P1]
- FR3: 系统可按30min周期定时触发采集任务 [P1]
- FR4: 系统可基于 URL 对采集到的信息进行去重 [P1]
- FR5: 系统可实时监听 RSS 源并在新条目到达时触发处理（RSS哨兵） [P2]
- FR6: 系统可随机间隔访问信息源池抓取热点（随机巡游） [P3]

### 信息分析

- FR7: 研读Agent可对每条信息生成摘要、提取关键词、标注利好/利空分类 [P1]
- FR8: 交叉验证Agent可对多源信息进行关键词事件归并，识别同一事件 [P2]
- FR9: 交叉验证Agent可对信息进行信源加权评估置信度 [P2]
- FR10: 交叉验证Agent可检测多源信息间的矛盾 [P2]
- FR11: 每条分析结果强制关联原文引用和原始 URL 溯源 [P1]

### 事件管理

- FR12: 事件引擎可基于归并后的信息创建和更新事件 [P2]
- FR13: 事件引擎可管理事件生命周期状态（发现→验证→扩散监控→高潮标记→消退确认→归档） [P2]
- FR14: 事件引擎可计算事件热度分数（信息源提及数 × 信源权重 × 时间衰减因子） [P2]
- FR47: 事件引擎可基于 SIR 传染病曲线模型预测事件热度拐点 [P2]

### 交易建议

- FR15: 建议Agent可基于当前采集信息通过 LLM prompt 生成简单交易建议（买/卖/持有 + 核心原因） [P1]
- FR16: 建议Agent可基于标的全部活跃事件态势使用 ACH 框架对涨/跌/横盘多假设逐事件验证/反驳 [P2]
- FR17: 每条建议附带概率化表达和因子归因 [P3]
- FR18: 每条建议强制附带原文引用和原始 URL 溯源 [P1]
- FR48: 建议Agent可在多个独立信息源出现同方向弱信号时触发高置信度建议（弱信号共振） [P2]

### 推送与通知

- FR19: 系统可通过 ntfy.sh 按优先级分级推送消息（urgent/high/default/low） [P1]
- FR20: 推送摘要可在手机通知栏级别完成信息判断（无需打开App） [P1]
- FR21: urgent 推送摘要包含明确的行动方向（买/卖 + 核心原因） [P1]
- FR22: 每30min必推一次（有料高优先级/无料低优先级确认系统存活） [P1]
- FR23: 号外推送后自动归入下一周期简报 [P3]
- FR24: 号外推送设置冷却窗口，避免推送风暴 [P3]
- FR25: 推送渠道可模块化扩展（Telegram/Email 等） [P3]

### 简报生成

- FR26: 系统可生成结构化简报，包含所有标的的分析汇总 [P1]
- FR27: 简报固定包含元数据区：配置信息源/本次采集源/失败源/数据时间窗口 [P1]
- FR28: 系统可归档历史简报支持回溯查询 [P2]

### 配置管理

- FR29: 用户可配置持仓/关注标的列表 [P1]
- FR30: 用户可为标的配置关联的信息源 [P1]
- FR31: 用户可直接添加 RSS 信息源（无需 Skill 适配） [P1]
- FR32: 用户可开发/配置非RSS信息源的采集 Skill [P1]
- FR33: 用户可通过 Web 界面管理标的和信息源配置 [P2]
- FR34: 用户可查看信息源健康状态（成功率、最近失败原因） [P2]

### Skill 运维

- FR35: 采集Agent在 Skill 执行异常时可自动尝试修复小问题 [P2]
- FR36: 采集Agent在无法自行修复时可上报用户 [P2]
- FR37: 用户可将 Skill 修复任务交由更强模型的Agent辅助完成 [P2]
- FR38: 系统可记录 Skill 执行日志 [P2]

### Dashboard（Web UI）

- FR39: 用户可在 Dashboard 查看当前周期简报摘要 [P2]
- FR40: 用户可从摘要渐进展开到简报详情再到完整分析链 [P2]
- FR41: 用户可通过 ntfy 推送中的深链直达 Dashboard 对应信息 [P2]
- FR42: Dashboard 在新推送到达时自动刷新 [P2]
- FR43: 用户可查看历史建议并与实际股价变动对比 [P2]
- FR44: 用户可检索历史简报（按标的、按时间） [P2]
- FR45: 用户可调整 Agent 参数和 prompt [P2]

### 合规与免责

- FR46: 系统界面和 README 展示免责声明（不构成投资建议） [P1]

## Non-Functional Requirements

### Performance

- **号外推送延迟：** 从信息源更新到用户收到 ntfy 推送 ≤1min（目标），≤5min（底线）
- **常规采集周期：** 30min 内完成全部信息源采集 + 分析 + 推送
- **LLM 调用延迟：** 单次研读/建议生成 ≤30s（受 LLM provider 限制）

### Security

- **LLM API Key：** 通过环境变量注入，不硬编码，不进版本控制
- **数据库凭据：** 同上，环境变量管理
- **网络暴露：** Dashboard（P2）仅内网访问或通过反向代理 + 认证暴露

### Reliability

- **部署方式：** Docker 容器，个人服务器
- **自动恢复：** Docker restart policy = always，进程异常自动重启
- **系统存活性：** 每30min必推机制本身作为存活探针，无推送 = 系统异常
- **采集降级：** 单个信息源采集失败不阻塞整体流程，简报元数据标注失败源

### Integration

- **LLM Provider：** 支持 OpenAI 格式兼容的任意提供商（OpenAI / DeepSeek / Groq 等），通过 base_url + api_key 配置切换
- **推送渠道：** ntfy.sh HTTP API
- **信息源：** RSS（标准协议）+ 自定义采集 Skill（按源适配）
- **数据存储：** PostgreSQL，预留备份接口（暂不实现备份策略）
