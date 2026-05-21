# config-git-safety Specification

## Purpose
此规约记录变更 everything-is-entity 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 配置文件夹 git 强制管理

系统 SHALL 将 `config/` 目录作为 git 仓库管理。每次 DAG run 结束后，系统 MUST 检查配置文件变更并自动 commit。

#### Scenario: DAG run 结束后自动 commit

- **WHEN** DAG run 结束，且 `config/` 目录有文件变更
- **THEN** 系统自动执行 git add + commit，commit message 包含 cycle_id 和变更摘要

#### Scenario: DAG run 结束无变更

- **WHEN** DAG run 结束，且 `config/` 目录无文件变更
- **THEN** 系统不执行 commit

#### Scenario: commit 策略可配置

- **WHEN** `system.toml` 配置 `config_git_commit: false`
- **THEN** 系统不自动 commit，但仍保持 git 仓库状态

### Requirement: 配置文件操作互斥锁

系统 SHALL 对 `config/` 目录的写操作加互斥锁，同一时刻 MUST 只有一个 DAG run 或 agent session 能写配置文件。

#### Scenario: 并发写入被阻塞

- **WHEN** DAG run A 正在写配置文件，DAG run B 也尝试写配置文件
- **THEN** DAG run B 等待 DAG run A 释放锁后再执行写操作

#### Scenario: 锁超时释放

- **WHEN** 持有锁的进程异常退出未释放锁
- **THEN** 系统在锁超时后自动释放，允许其他进程获取锁

#### Scenario: 读操作不受锁限制

- **WHEN** 一个进程持有写锁
- **THEN** 其他进程仍可读取配置文件

### Requirement: git 回滚支持

系统 SHALL 支持通过 git 回滚配置文件到任意历史版本。

#### Scenario: 回滚到指定 commit

- **WHEN** 用户指定一个 commit hash 执行回滚
- **THEN** 系统将 `config/` 目录恢复到该 commit 的状态，并重新加载所有 Entity

#### Scenario: 回滚后系统重新加载

- **WHEN** 配置文件被回滚
- **THEN** 系统重新加载所有 Entity，校验 schema，跳过有问题的 Entity 继续运行

