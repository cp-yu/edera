## ADDED Requirements

### Requirement: Bootstrap 逻辑可重入
核心 bootstrap 逻辑 SHALL 可重入，支持运行时重新执行扫描和 registry 构建。重新执行时 SHALL 原子替换 handler registry 和 entity type registry，不影响正在执行的 DAG。

#### Scenario: 热加载触发重新 bootstrap
- **WHEN** manifest 文件变更触发热加载
- **THEN** 核心 SHALL 重新执行扫描扩展、构建 registry 流程

#### Scenario: Registry 原子替换
- **WHEN** 重新 bootstrap 完成
- **THEN** 核心 SHALL 原子替换全局 handler registry 和 entity type registry，新 DAG run 使用新 registry

#### Scenario: 运行中 DAG 不受影响
- **WHEN** 重新 bootstrap 期间有 DAG 正在执行
- **THEN** 该 DAG SHALL 继续使用启动时的 registry 快照，不受新 registry 影响
