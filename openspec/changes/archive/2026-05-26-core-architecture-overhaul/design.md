## Context

当前 core 层架构基于 `2026-05-18-node-type-instance-model` 和 `2026-05-24-core-extension-separation` 两次变更建立。NodeConfig 是扁平模型，所有节点类型共享同一组字段（handler、skills、tools、model 等），通过 `_uses_pi()` 函数判断是否为 LLM 节点。executor 统一走 handler registry 加载执行，无 type 级分发。

rig CLI 当前通过 HTTP 调用 FastAPI 后端，仅支持 entity get/list/update/query、node status/stop/resume、dag trigger。配置变更需要重启服务。agent 节点运行时无法实时观测内部状态。

项目处于开发阶段，无历史负担，可做 breaking change。未来计划 Rust 化 core 层。

## Goals / Non-Goals

**Goals:**
- 建立 Discriminated Union 节点类型模型（function/agent/dag），为 Rust 化铺路
- agent 节点独立执行分支，实现实时可观测和 stop/resume 生命周期
- 子 DAG 嵌套执行，DAG 可作为节点复用
- DAG 输入参数化，支持外部注入和 source 节点 binding
- 边级 + 节点级 optional 容错控制
- 全量配置热加载（config/handler/manifest）
- rig CLI 完整 CRUD + C/S 架构（gRPC + mTLS）
- BFF 网关支持 Web Console token 认证

**Non-Goals:**
- 数据库配置存储迁移（后续独立 change）
- Rust 化实现（本次仅确保设计兼容）
- cascade delete 原子性（降低承诺，等数据库迁移）
- pi CLI 改造（保持 pi 为纯 CLI 工具）
- 多用户/多租户权限体系

## Decisions

### D1: NodeConfig Discriminated Union

NodeConfig 重构为 Pydantic discriminated union，`type` 字段作为判别器：

```python
class NodeConfigBase(BaseModel):
    name: str
    role: Literal["source", "processor", "sink"]
    input_type: str
    output_type: str
    optional: bool = False
    timeout_seconds: float | None = None

class FunctionNodeConfig(NodeConfigBase):
    type: Literal["function"]
    handler: str
    parameters: dict = {}
    parameters_schema: dict = {}

class AgentNodeConfig(NodeConfigBase):
    type: Literal["agent"]
    model: str
    workdir: str | None = None
    tools: list[str] = []
    system_prompt_file: str | None = None

class DagNodeConfig(NodeConfigBase):
    type: Literal["dag"]
    dag_ref: str
    input_mapping: dict = {}

NodeConfig = FunctionNodeConfig | AgentNodeConfig | DagNodeConfig
```

替代方案：扁平模型 + 运行时校验 — 丢失类型安全，Rust 化时需要大量 `Option<T>`。

### D2: Executor Type 分发

executor 根据 NodeConfig 类型走不同执行分支：

- `FunctionNodeConfig` → handler registry 加载 + `HandlerContext` 调用（现有路径）
- `AgentNodeConfig` → subprocess 启动 pi CLI + stdout streaming
- `DagNodeConfig` → 递归调用 DagRunner，传入 input_mapping

替代方案：统一 handler 路径（agent 也走 handler registry）— 无法在 executor 层面管理 agent 生命周期。

### D3: Agent 执行 — Subprocess + Stdout Streaming

```
executor → subprocess(pi --session-dir {managed} --model {model} [--continue])
         → cwd = workdir
         → env: RIG_CLIENT_CERT, RIG_CLIENT_KEY, RIG_DAEMON_ADDR, RIG_IDENTITY
         → pipe stdout → event bus → SSE
```

- stop: SIGTERM → pi 保存 session 退出
- resume: 新进程 + `--continue` + session path + 可选新 prompt
- session 存储由 daemon 管理：`~/.rig/sessions/{dag_name}/{instance_id}/{cycle_id}/`
- workdir 由用户在 AgentNodeConfig 中配置

替代方案 B（pi 服务化）— pi 改造量大，收益不匹配当前阶段。
替代方案 C（控制文件）— 引入文件竞态，不如进程生命周期干净。

### D4: Sub-DAG 执行

- dag type 节点引用另一个 DAG（`dag_ref` 字段）
- 子 DAG 的 source 节点 = 外部输入接口，sink 节点 = 外部输出接口
- 子 DAG 生成独立 `cycle_id`，通过 `parent_cycle_id` + `parent_node` 关联父级
- 递归上限可配置（默认 3 层）
- 子 DAG 内部每个节点有独立执行记录，历史颗粒度到 node 级

替代方案：共享 cycle_id + 路径前缀 — 查询需解析路径，递归时路径过长。

### D5: DAG Input Parameters + Source Node Binding

DAG 声明 `inputs`（类似函数签名）：
```yaml
inputs:
  - name: ticker
    type: string
    required: false
```

Source 节点实例声明 `input_binding`：
```yaml
config:
  input_binding: ticker
  source_names: [default-watchlist]  # fallback
```

运行时：有 input → 绑定的 source 跳过拉取，直接使用传入值；无 input → 正常拉取。

与 sub-DAG 衔接：DAG 的 inputs 声明即为其作为 dag type 节点时的输入接口。

### D6: Edge Optional + Node Optional

Edge model 新增 `optional: bool = False`。Node 的 `optional: bool` 是语法糖，等价于所有出边 optional。

executor fan-in barrier 判定逻辑：
- 收集入边状态
- optional 边的上游失败 → 不阻塞，该边数据视为缺失
- required 边的上游失败 → 阻塞，当前节点标记失败

### D7: 全量热加载

监听机制：`watchfiles` 库监听 `config/` 和 `extensions/` 目录。

变更处理：
- config YAML 变更 → 重新解析受影响配置，更新内存状态
- handler 脚本变更 → 清除 `_modules` 缓存，下次执行重新加载
- manifest 变更 → 重新执行 bootstrap 扫描，原子替换 registry

对运行中 DAG 的策略：变更只影响新的 run，不影响正在执行的 run。

### D8: C/S 架构 — Daemon + BFF

```
rig daemon (gRPC server, tonic-compatible proto)
  ├── EntityService: CRUD + query
  ├── DagService: trigger/status/edit/history
  ├── NodeService: status/stop/resume/output
  └── SystemService: health/reload/config

BFF (FastAPI, gRPC client)
  ├── HTTP REST API (现有路由保持兼容)
  ├── SSE endpoint (实时推送 DAG/node 状态)
  └── 静态文件服务 (Web Console)

rig CLI (gRPC client)
  ├── entity create/get/list/update/delete/query
  ├── dag trigger/status/edit(add-node/add-edge/remove-edge)
  ├── node status/stop/resume/output
  └── client init/auth
```

### D9: 安全模型 — mTLS + Token

gRPC 层（CLI/agent）：
- 自签 CA，daemon 持有 server cert
- CLI: 长期 client cert，CN=`human:{username}`
- Agent: 短期 client cert，CN=`node:{instance_id}`，TTL 对齐 timeout
- daemon 从 cert CN 提取身份，查找 entity_permissions

BFF 层（Web Console）：
- BFF 持有自己的 client cert（CN=`bff:web-console`）连接 daemon
- 浏览器通过 token 认证到 BFF
- dev 模式（`RIG_ENV=dev`）：BFF 免 token，支持 WSL→Windows 本地开发

Agent 证书签发：
- daemon 启动 agent 节点前签发短期证书
- 通过环境变量注入：`RIG_CLIENT_CERT`、`RIG_CLIENT_KEY`、`RIG_DAEMON_ADDR`
- rig CLI 自动读取环境变量完成 mTLS 握手

### D10: CLI 一键部署

Server 部署后，Client 通过 `rig client init --server=<addr>` 一键完成：
- 连接 server，验证可达性
- 请求签发 client cert（需 server 端确认）
- 保存 cert + config 到 `~/.rig/`
- 后续 rig 命令自动使用保存的配置

## Risks / Trade-offs

- [Scope 过大] 单次 change 涉及模型层、运行时、接口层三个层面 → 按 Phase 1/2/3 顺序实现，每个 phase 可独立验证
- [gRPC 引入复杂度] 新增 proto 定义和代码生成步骤 → 项目开发阶段可接受，且为 Rust 化铺路（tonic 原生 proto）
- [mTLS 证书管理] 自签 CA 需要安全存储 → daemon 数据目录权限控制，CA key 仅 daemon 进程可读
- [热加载竞态] 配置变更和 DAG 执行并发 → 变更只影响新 run，不影响进行中的 run
- [subprocess 开销] 每次 agent 执行 spawn 新进程 → 本机场景可接受，pi 启动时间远小于 LLM 推理时间
- [两套认证并存] mTLS + token 增加维护面 → 各自场景明确（CLI vs 浏览器），不会混用

## Migration Plan

1. Phase 1（模型层）：重构 NodeConfig 为 discriminated union → edge optional → DAG inputs
2. Phase 2（运行时）：sub-DAG 执行 → 热加载 → agent executor 分支 + stdout streaming
3. Phase 3（接口层）：CLI 补全 → daemon gRPC → BFF 网关 → mTLS/token 认证

回滚策略：git revert 整个 change 分支。每个 Phase 完成后可独立验证。

## Open Questions

- proto 文件组织：单一 `rig.proto` 还是按 service 拆分？
- agent 证书签发的确认机制：CLI `rig client init` 时 server 端如何验证请求合法性？（首次信任 / 预共享 token）
- 热加载的 debounce 策略：文件快速连续变更时的合并窗口？
