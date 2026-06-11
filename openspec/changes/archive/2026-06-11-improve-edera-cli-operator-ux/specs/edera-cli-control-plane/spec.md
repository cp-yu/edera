---
capabilities:
  - cap.core.edera-cli-control-plane
---
# edera-cli-control-plane Delta Specification

## ADDED Requirements

### Requirement: 控制面分页展示
`edera` 控制面 CLI SHALL 为列表型读命令提供统一 `--limit` 和 `--offset` 展示参数。`limit` SHALL 优先传递给已有 server 查询参数；`offset` SHALL 只影响 CLI 输出展示，不改变 server 查询范围。

#### Scenario: briefing 列表分页展示
- **WHEN** 用户执行 `edera query briefing list --limit 20 --offset 10`
- **THEN** CLI SHALL 将 `limit=20` 传递给 briefing list 查询
- **AND** CLI SHALL 从返回列表的第 11 项开始展示结果

#### Scenario: advice 列表分页展示
- **WHEN** 用户执行 `edera query advice list --limit 20 --offset 10`
- **THEN** CLI SHALL 将 `limit=20` 传递给 advice list 查询
- **AND** CLI SHALL 从返回列表的第 11 项开始展示结果

#### Scenario: node outputs 分页展示
- **WHEN** 用户执行 `edera query node-outputs --limit 50 --offset 25`
- **THEN** CLI SHALL 将 `limit=50` 传递给 node outputs 查询
- **AND** CLI SHALL 从返回列表的第 26 项开始展示结果

#### Scenario: source logs 分页展示
- **WHEN** 用户执行 `edera source logs --limit 50 --offset 25`
- **THEN** CLI SHALL 将 `limit=50` 传递给 source logs 查询
- **AND** CLI SHALL 从返回列表的第 26 项开始展示结果

#### Scenario: DAG 定义列表分页展示
- **WHEN** 用户执行 `edera dag list --limit 20 --offset 10`
- **THEN** CLI SHALL 对 DAG 定义列表输出应用分页展示

#### Scenario: handler 列表分页展示
- **WHEN** 用户执行 `edera handler list --limit 20 --offset 10`
- **THEN** CLI SHALL 对 handler 列表输出应用分页展示
