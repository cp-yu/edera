## Context

当前 `edera-web` BFF 的 `deps.py` 将 `controller()`、`config_dir()`、`handler_registry()` 三个依赖替换为 501 stub，导致 ~85% 的 HTTP route 不可用。已接通的 route（dag trigger/status、node stop/resume/status、SSE events）证明 gRPC 通路可行。

`edera-server` 已持有 `PipelineController` 和 `session_factory`，具备承载全部业务逻辑的条件。`routes.py` 中 ~1700 行代码混合了 HTTP 适配、schema 验证、文件操作和 DB 查询，需要按职责拆分到 server 端。

## Goals / Non-Goals

**Goals:**
- 所有前端活跃调用的 HTTP route 通过 gRPC 恢复可用
- BFF 进程不再持有任何业务逻辑（验证、文件操作、DB 查询）
- 新增 4 个 gRPC service 按职责内聚：GraphService、ConfigService、QueryService、PipelineService
- CLI (`edera`) 可直接复用同一套 gRPC service，无需重复验证逻辑

**Non-Goals:**
- 不拆分 `edera_core` 为多个 Python 包（server/client 仍共享一个包）
- 不为 proto message 做完整 typed 建模——复杂 payload 使用 JSON string field
- 不实现 BFF 层缓存或聚合优化
- 不改变 mTLS/bootstrap/dev-mode 行为

## Decisions

### D1: 4 个新 service 而非扩展现有 service

**选择**：新增 `GraphService`、`ConfigService`、`QueryService`、`PipelineService`

**替代方案**：把所有新 RPC 塞进现有 4 个 service（EntityService/DagService/NodeService/SystemService）

**理由**：现有 service 按 entity/dag/node/system 划分，新增的操作（graph CRUD、config 编辑、DB 查询、pipeline 控制）跨越这些边界。例如 GraphService 同时操作 dag + node + skill + handler，塞进 DagService 或 NodeService 都不合适。独立 service 保持内聚，也便于未来按 service 做权限隔离。

### D2: JSON string field 作为 payload 载体

**选择**：RPC 签名使用 typed message（含 operation 标识字段），请求/响应 body 使用 `string json` field

**替代方案**：为每个操作定义完整 protobuf message（DagNode、DagEdge、SkillConfig 等）

**理由**：
- 复杂结构（DagConfig 含 nodes/edges/ui/inspector_schema）已由 Pydantic model 定义和验证
- 在 proto 重复建模维护成本高，且 inspector_schema 是动态结构无法静态建模
- JSON string 允许 server 端直接使用现有 Pydantic 验证链，无需 proto↔domain 转换层
- 缺点是失去 proto schema 的跨语言 codegen 优势，但当前只有 Python client

### D3: 验证逻辑完整下沉到 server

**选择**：所有 config schema 验证、EntityStore 级联操作、DB 查询逻辑在 server servicer 中执行

**替代方案 A**：验证留在 BFF（thin proxy）
**替代方案 C**：读 thin + 写 thick 混合

**理由**：
- BFF spec 已声明"配置无知契约"——BFF MUST NOT 读 config 目录
- CLI 需要复用同一套验证逻辑，server 是唯一合理位置
- 混合方案在 `/api/graph/dag/{name}` 等需要组装多文件数据的 GET 上不够用

### D4: BFF routes.py 重写策略

**选择**：保留现有 route path 和 HTTP method 不变，handler 内部替换为 gRPC 调用

**理由**：前端不需要任何改动。每个 handler 变为 ~5-10 行：解析 HTTP 参数 → 调用 grpc_client.xxx() → 返回 JSON response。

### D5: server.py 代码组织

**选择**：每个新 service 一个独立 Python 文件（`graph_service.py`、`config_service.py`、`query_service.py`、`pipeline_service.py`），在 `server.py` 中 import 并注册

**理由**：当前 `server.py` 已有 ~300 行 servicer 代码。新增 4 个 service 预计 ~1500 行逻辑（从 routes.py 迁移），放在一个文件中不可维护。按 service 拆文件，每个文件 ~300-400 行。

## Risks / Trade-offs

**[Risk] 单次改动面过大** → 按 Phase 分批实现（P0 QueryService → P1 PipelineService → P2 GraphService → P3 ConfigService），每个 phase 可独立验证

**[Risk] JSON string 失去类型安全** → server 端使用 Pydantic model_validate 保证运行时类型安全；未来如需跨语言 client 可逐步将高频 RPC 的 payload typed 化

**[Risk] routes.py 重写期间前端可能出现回归** → 保持 HTTP API 契约（path/method/response shape）不变，前端零改动；通过集成测试覆盖

**[Risk] server.py 启动时需要 DB session** → QueryService 需要 session_factory，当前 server 已在 start() 中 init_db，无额外风险

## Open Questions

无——所有关键决策已在 explore 阶段确认。
