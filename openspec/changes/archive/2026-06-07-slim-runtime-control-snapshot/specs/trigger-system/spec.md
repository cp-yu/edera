## MODIFIED Requirements

### Requirement: 触发目标

系统 SHALL 支持触发 DAG、DAG-scoped Node 或 clear bit。触发目标 MUST 通过 `target` 字段指定，格式为 `dag:<name>` / `node:<dag_name>/<node_id>` / `clear:event:<name>`。系统 MUST NOT 支持通过 `node:<id>` 全局扫描所有 DAG 反查 Node。

#### Scenario: 触发 DAG 执行

- **WHEN** Trigger 的 `target` 为 `dag:default`
- **THEN** Trigger Executor 启动 `dag:default` 的一次完整执行

#### Scenario: 触发 DAG-scoped 单 Node 执行

- **WHEN** Trigger 的 `target` 为 `node:analysis/fetch-news`
- **THEN** Trigger Executor SHALL 在 DAG `analysis` 内解析 `fetch-news`
- **AND** DagController SHALL 为 DAG `analysis` 构建 execution closure 后执行该 Node

#### Scenario: 拒绝全局 Node target

- **WHEN** Trigger 的 `target` 为 `node:<id>`
- **THEN** 系统 SHALL 拒绝该 target 格式

#### Scenario: 触发 clear bit

- **WHEN** Trigger 的 `target` 为 `clear:event:market-open`
- **THEN** Trigger Executor 复位 `event:market-open` bit
