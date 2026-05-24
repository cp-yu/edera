## ADDED Requirements

### Requirement: Manifest 文件解析

核心 SHALL 解析扩展目录下的 `manifest.yaml` 文件，提取 handler 声明、entity type 声明和依赖信息。Manifest MUST 遵循固定 schema：顶层字段 `name`（必填）、`version`（必填）、`description`（可选）、`depends`（可选）、`handlers`（可选）、`entity_types`（可选）、`storage`（可选）。

#### Scenario: 解析完整 manifest

- **WHEN** 核心扫描到包含 `manifest.yaml` 的扩展目录，manifest 包含 `name`、`version`、`handlers`、`entity_types` 字段
- **THEN** 核心 SHALL 解析出所有 handler 描述符和 entity type 定义，注册到全局 registry

#### Scenario: Manifest 缺少必填字段

- **WHEN** 核心扫描到 `manifest.yaml` 缺少 `name` 或 `version` 字段
- **THEN** 核心 SHALL 拒绝加载该扩展并记录错误日志，包含文件路径和缺失字段名

#### Scenario: Manifest schema 校验失败

- **WHEN** `manifest.yaml` 中 `handlers` 条目缺少 `entry`、`role` 或 `input_type` 字段
- **THEN** 核心 SHALL 拒绝该 handler 注册并记录校验错误

### Requirement: 文件名 Fallback 机制

当扩展目录不包含 `manifest.yaml` 时，核心 SHALL 退化为文件名即 handler 名模式：目录内每个 `.py` 文件视为一个 handler，文件名（去 `.py` 后缀）即 handler 名。

#### Scenario: 无 manifest 的简单扩展

- **WHEN** 核心扫描到扩展目录仅包含 `handler.py`，无 `manifest.yaml`
- **THEN** 核心 SHALL 将该文件注册为 handler，handler 名为目录名

#### Scenario: 无 manifest 时 DAG 校验跳过类型检查

- **WHEN** DAG 引用了通过 fallback 注册的 handler（无 role/I/O type 信息）
- **THEN** 核心 SHALL 跳过该节点的 I/O 类型匹配校验，仅执行拓扑合法性检查

### Requirement: Handler 描述符提取

核心 SHALL 从 manifest 的 `handlers` 段提取 `NodeTypeDescriptor`，包含 `name`、`role`、`input_type`、`output_type`，用于 DAG 拓扑校验。

#### Scenario: 提取 NodeTypeDescriptor

- **WHEN** manifest 声明 handler `name: fetch-rss, role: source, input_type: Any, output_type: "list[RawItem]"`
- **THEN** 核心 SHALL 构建 `NodeTypeDescriptor(name="fetch-rss", role="source", input_type="Any", output_type="list[RawItem]")` 并注册到 node type registry

#### Scenario: 同一扩展提供多个 handler

- **WHEN** manifest 的 `handlers` 段包含多个条目
- **THEN** 核心 SHALL 为每个条目分别构建并注册 `NodeTypeDescriptor`

### Requirement: 扩展依赖声明

Manifest MAY 包含 `depends` 字段声明对其他扩展或 `_lib/` 模块的依赖。核心 SHALL 在 bootstrap 时校验依赖是否存在。

#### Scenario: 依赖存在

- **WHEN** manifest 声明 `depends: [_lib/http_fetch]` 且 `extensions/_lib/http_fetch.py` 存在
- **THEN** 核心 SHALL 正常加载该扩展

#### Scenario: 依赖缺失

- **WHEN** manifest 声明 `depends: [_lib/missing_module]` 且该模块不存在
- **THEN** 核心 SHALL 拒绝加载该扩展并记录依赖缺失错误
