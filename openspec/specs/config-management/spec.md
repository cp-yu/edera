---
capabilities:
  - cap.config.runtime-config-editing
---
# config-management Specification

## Purpose
此规约记录变更 project-mvp 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 标的与投资情况配置（FR29）
系统 SHALL 支持用户通过 YAML 文件配置持仓/关注标的列表与当前投资情况（持仓量、成本价等）。

#### Scenario: 配置持仓标的
- **WHEN** 用户在 portfolio.yaml 中配置一个标的及其持仓信息
- **THEN** 系统在下一周期使用该配置生成建议时纳入投资情况

#### Scenario: 配置关注标的
- **WHEN** 用户在 portfolio.yaml 中配置一个仅关注（无持仓）的标的
- **THEN** 系统在采集和分析中包含该标的，建议中标注为非持仓标的

### Requirement: 信息源关联配置（FR30）
系统 SHALL 支持用户为标的配置关联的信息源列表。

#### Scenario: 标的关联信息源
- **WHEN** 用户为某标的配置 3 个信息源
- **THEN** 系统在采集阶段仅从这 3 个源获取该标的相关信息

### Requirement: 标准 RSS 信息源配置（FR31）
系统 SHALL 支持用户直接添加标准 RSS 信息源，仅需提供 RSS URL。

#### Scenario: 添加 RSS 源
- **WHEN** 用户在配置中添加一个 RSS URL
- **THEN** 系统在下一周期使用 fetch-rss Skill 从该 URL 采集信息

### Requirement: 非标准源接入规则配置（FR32）
系统 SHALL 支持用户配置非标准信息源的接入规则（目标 URL + 抓取规则/选择器/正则）。

#### Scenario: 配置网页抓取规则
- **WHEN** 用户为某交易所公告页配置 URL 和 CSS 选择器规则
- **THEN** 系统在下一周期使用 fetch-web Skill 按规则抓取信息

### Requirement: 分层配置体系
系统 SHALL 支持分层配置：TOML（系统配置：调度频率、日志级别）、YAML（业务配置：标的、信息源、Node、DAG）、env（凭据：API key）。

#### Scenario: 配置优先级
- **WHEN** 系统加载配置
- **THEN** env 凭据 > YAML 业务配置 > TOML 系统配置，高优先级覆盖低优先级同名配置

#### Scenario: 凭据不入仓库
- **WHEN** 凭据通过 .env 文件配置
- **THEN** .env 文件在 .gitignore 中，仓库中仅保留 .env.example 模板

