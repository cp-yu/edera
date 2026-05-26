## Why

当前 core 层存在多个架构缺陷：节点类型模型扁平化（所有节点统一为 function type）、DAG 缺乏外部输入接口和边级容错控制、配置变更需要重启服务、CLI 功能不完整且与服务端耦合、agent 节点运行时不可观测。这些问题阻碍了 DAG 编排的表达力、agent 的自主操作能力和系统的可运维性。

## What Changes

- **BREAKING** NodeConfig 从扁平模型重构为 Discriminated Union：`FunctionNodeConfig | AgentNodeConfig | DagNodeConfig`，`type` 字段作为判别器
- **BREAKING** Agent 节点从 function type 中拆出，executor 对 agent type 走独立执行分支（subprocess + 实时 stdout streaming）
- 新增 `dag` node type，支持子 DAG 作为节点嵌套执行，子 DAG 生成独立 cycle_id 并通过 `parent_cycle_id` 关联父级
- DAG 新增 `inputs` 声明（类似函数签名），source 节点通过 `input_binding` 绑定 DAG input，运行时可接受外部注入
- Edge model 新增 `optional` 属性（边级），NodeConfig 新增 `optional` 属性（节点级，语法糖展开为所有出边 optional）
- 全量热加载：config YAML、handler 脚本、manifest 变更均可运行时生效，无需重启
- Rig CLI 补全：entity create/delete、dag status/edit（add-node/add-edge/remove-edge）、node output 查看
- C/S 架构：rig daemon（gRPC server）+ BFF（FastAPI HTTP/SSE for Web Console）+ rig CLI（gRPC client）
- 安全模型：mTLS（CLI/agent）+ token（Web Console），daemon 为 agent 节点签发短期证书
- Agent 节点 `session_dir` 语义拆分为 `workdir`（用户配置的 cwd）和 session 存储路径（daemon 自动管理）
- Agent 节点实时可观测：stdout streaming → event bus → SSE 推送到 Web Console
- Cascade delete 事务性：降低 design 承诺为顺序持久化，等数据库配置存储迁移后自然解决

## Capabilities

### New Capabilities
- `node-type-discriminated-union`: NodeConfig Discriminated Union 模型，覆盖 function/agent/dag 三种变体的字段定义、Pydantic 判别器和 YAML 反序列化
- `agent-executor`: Agent 节点独立执行分支，覆盖 subprocess 启动、stdout 实时 streaming、stop/resume 生命周期和 workdir/session 分离
- `sub-dag-execution`: 子 DAG 作为节点嵌套执行，覆盖独立 cycle_id、parent_cycle_id 关联、source/sink 接口映射和递归上限
- `dag-input-parameters`: DAG 输入参数声明，覆盖 inputs schema 定义、source 节点 input_binding、运行时参数注入和 CLI/API/Web 触发
- `edge-optional`: 边级和节点级 optional 属性，覆盖 fan-in barrier 容错判定、节点级语法糖展开和错误路径隔离
- `config-hot-reload`: 全量配置热加载，覆盖 file watch、增量重载、handler 模块缓存清除和 manifest 重新扫描
- `rig-daemon-grpc`: Rig daemon gRPC 服务，覆盖 service 定义、mTLS 传输、agent 短期证书签发和 dev 模式
- `rig-cli-full-crud`: Rig CLI 完整 CRUD，覆盖 entity create/delete、dag status/edit、node output 和 client init
- `bff-web-gateway`: BFF Web 网关，覆盖 gRPC client 转 HTTP/SSE、token 认证和 dev 模式免认证
- `agent-realtime-observability`: Agent 节点实时可观测，覆盖 stdout event bus、SSE 推送和 Web Console 展示

### Modified Capabilities
- `node-executor`: 执行分发逻辑从统一路径改为按 type 分支（function 走 handler registry，agent 走 subprocess，dag 走递归）
- `dag-event-driven-executor`: fan-in barrier 增加 edge optional 判定逻辑
- `core-bootstrap`: 增加热加载支持，bootstrap 逻辑可重入，registry 原子替换
- `rig-cli`: 从 HTTP client 改为 gRPC client，增加 daemon 连接管理和证书配置
- `pipeline-control`: DAG 运行 API 增加 inputs 参数传递
- `entity-type-crud-api`: cascade delete 降低事务性承诺为顺序持久化

## Impact

- `packages/core-types/`: NodeConfig 类型重构为 discriminated union
- `packages/core/src/stockimformation_core/node/executor.py`: 执行分支重构
- `packages/core/src/stockimformation_core/dag/runner.py`: sub-DAG 递归执行、edge optional 判定、inputs 注入
- `packages/core/src/stockimformation_core/dag/models.py`: edge optional 字段、DAG inputs 声明
- `packages/core/src/stockimformation_core/bootstrap.py`: 热加载可重入
- `packages/core/src/stockimformation_core/rig_cli.py`: gRPC client 重写 + 新增子命令
- `packages/core/src/stockimformation_core/`: 新增 daemon.py（gRPC server）、cert.py（证书管理）、hot_reload.py
- `apps/web-console/`: BFF 层从直接调用 core 改为 gRPC client
- `config/dags/*.yaml`: DAG 格式增加 inputs 和 edge optional 字段
- `config/nodes/*.yaml`: node type 字段语义变更
- 新增依赖：grpcio、grpcio-tools、watchfiles、cryptography
