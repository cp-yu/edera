## 1. Actions

### Phase 1: 模型层

- [x] A1 重构 NodeConfig 为 Discriminated Union（FunctionNodeConfig | AgentNodeConfig | DagNodeConfig）
- [x] A2 在 Edge model 增加 `optional: bool` 字段
- [x] A3 在 NodeConfig 增加 `optional: bool` 字段（节点级语法糖）
- [x] A4 在 DAG config 增加 `inputs` 字段声明
- [x] A5 在 Source 节点 config 增加 `input_binding` 字段
- [x] A6 AgentNodeConfig 增加 `workdir` 字段，移除 `session_dir` 字段

### Phase 2: 运行时

- [x] A7 Executor 增加 type 分发逻辑（function/agent/dag 三分支）
- [x] A8 实现 agent 节点 subprocess 执行分支（pi CLI 调用）
- [x] A9 Agent 节点 subprocess 设置 cwd 为 workdir，session 路径由 daemon 管理
- [x] A10 Agent 节点 subprocess 注入环境变量（RIG_CLIENT_CERT、RIG_CLIENT_KEY、RIG_DAEMON_ADDR、RIG_IDENTITY）
- [x] A11 实现 agent 节点 stdout 实时 streaming 到 event bus
- [x] A12 实现 dag 节点递归执行分支（调用 DagRunner）
- [x] A13 子 DAG 生成独立 cycle_id，记录 parent_cycle_id 和 parent_node
- [x] A14 实现 DAG inputs 运行时注入和 source 节点 input_binding 逻辑
- [x] A15 Fan-in barrier 增加 edge optional 判定逻辑
- [x] A16 实现配置文件热加载（watchfiles 监听 config/ 和 extensions/）
- [x] A17 实现 handler 脚本热加载（清除模块缓存）
- [x] A18 实现 manifest 热加载（重新 bootstrap + 原子替换 registry）
- [x] A19 Bootstrap 逻辑改为可重入函数

### Phase 3: 接口层

- [x] A20 定义 gRPC proto（EntityService、DagService、NodeService、SystemService）
- [x] A21 实现 rig daemon gRPC server
- [x] A22 实现 daemon 内部 CA 和证书签发逻辑
- [x] A23 Daemon 启动 agent 节点前签发短期证书并注入环境变量
- [x] A24 Rig CLI 重写为 gRPC client
- [x] A25 Rig CLI 增加 entity create/delete 子命令
- [x] A26 Rig CLI 增加 dag status/edit 子命令（add-node/add-edge/remove-edge）
- [x] A27 Rig CLI 增加 node output 子命令
- [x] A28 Rig CLI 增加 client init 子命令（一键配置）
- [x] A29 BFF 重写为 gRPC client 连接 daemon
- [x] A30 BFF 实现 SSE endpoint 订阅 event bus
- [x] A31 BFF 实现 token 认证和 dev 模式
- [x] A32 Web Console 增加 DAG 触发界面的 inputs 表单渲染
- [x] A33 Web Console 增加 node 运行详情页实时展示 stdout

### 其他

- [x] A34 更新 entity-type-crud-api design 文档，降低 cascade delete 事务性承诺
- [x] A35 新增依赖：grpcio、grpcio-tools、watchfiles、cryptography

## 2. Checks

### Phase 1 验证

- [x] C1 验证 NodeConfig Discriminated Union 反序列化
  - Covers: A1
  - Command: `pytest tests/test_node_config.py::test_discriminated_union`
  - Expect: function/agent/dag 三种 type 正确反序列化为对应子类，无效 type 抛出 ValidationError

- [x] C2 验证 edge optional 字段加载
  - Covers: A2
  - Command: `pytest tests/test_dag_config.py::test_edge_optional`
  - Expect: edge 配置 `optional: true` 正确加载

- [x] C3 验证节点级 optional 语法糖
  - Covers: A3
  - Evidence: executor 代码中节点 optional 展开为所有出边 optional 的逻辑
  - Expect: 节点 `optional: true` 等价于所有出边 `optional: true`

- [x] C4 验证 DAG inputs 声明加载
  - Covers: A4
  - Command: `pytest tests/test_dag_config.py::test_dag_inputs`
  - Expect: DAG 配置 `inputs: [{name: ticker, type: string}]` 正确加载

- [x] C5 验证 source 节点 input_binding 加载
  - Covers: A5
  - Command: `pytest tests/test_node_config.py::test_input_binding`
  - Expect: source 节点配置 `input_binding: ticker` 正确加载

- [x] C6 验证 AgentNodeConfig workdir 字段
  - Covers: A6
  - Command: `pytest tests/test_node_config.py::test_agent_workdir`
  - Expect: AgentNodeConfig 包含 `workdir` 字段，不包含 `session_dir` 字段

### Phase 2 验证

- [x] C7 验证 executor type 分发
  - Covers: A7
  - Command: `pytest tests/test_executor.py::test_type_dispatch`
  - Expect: function 节点走 handler registry，agent 节点走 subprocess，dag 节点走递归

- [x] C8 验证 agent 节点 subprocess 启动
  - Covers: A8, A9
  - Command: `pytest tests/test_agent_executor.py::test_subprocess_launch`
  - Expect: agent 节点启动 pi subprocess，cwd 为 workdir，--session-dir 指向 daemon 管理路径

- [x] C9 验证 agent 节点环境变量注入
  - Covers: A10
  - Command: `pytest tests/test_agent_executor.py::test_env_injection`
  - Expect: subprocess 环境变量包含 RIG_CLIENT_CERT、RIG_CLIENT_KEY、RIG_DAEMON_ADDR、RIG_IDENTITY

- [x] C10 验证 agent 节点 stdout streaming
  - Covers: A11
  - Command: `pytest tests/test_agent_executor.py::test_stdout_streaming`
  - Expect: pi subprocess 输出逐行发送到 event bus

- [x] C11 验证 dag 节点递归执行
  - Covers: A12, A13
  - Command: `pytest tests/test_dag_executor.py::test_sub_dag_execution`
  - Expect: dag 节点触发子 DAG 执行，子 DAG 生成独立 cycle_id，记录 parent_cycle_id

- [x] C12 验证 DAG inputs 注入和 source binding
  - Covers: A14
  - Command: `pytest tests/test_dag_runner.py::test_inputs_injection`
  - Expect: DAG 运行时传入 inputs，绑定的 source 节点跳过拉取使用传入值

- [x] C13 验证 edge optional fan-in barrier
  - Covers: A15
  - Command: `pytest tests/test_dag_runner.py::test_edge_optional_barrier`
  - Expect: optional 边上游失败不阻塞下游，required 边上游失败阻塞下游

- [x] C14 验证配置文件热加载
  - Covers: A16
  - Command: `pytest tests/test_hot_reload.py::test_config_hot_reload`
  - Expect: 修改 config YAML 后，新 DAG run 使用更新后配置

- [x] C15 验证 handler 脚本热加载
  - Covers: A17
  - Command: `pytest tests/test_hot_reload.py::test_handler_hot_reload`
  - Expect: 修改 handler 脚本后，下次执行重新加载

- [x] C16 验证 manifest 热加载
  - Covers: A18, A19
  - Command: `pytest tests/test_hot_reload.py::test_manifest_hot_reload`
  - Expect: 修改 manifest 后，registry 原子替换，新 DAG run 使用新 registry

### Phase 3 验证

- [x] C17 验证 gRPC proto 定义
  - Covers: A20
  - Command: `python -m grpc_tools.protoc --python_out=. --grpc_python_out=. rig.proto`
  - Expect: proto 编译成功，生成 Python stub

- [x] C18 验证 daemon gRPC server 启动
  - Covers: A21
  - Command: `pytest tests/test_daemon.py::test_grpc_server_start`
  - Expect: daemon 启动 gRPC server，监听配置端口

- [x] C19 验证 daemon 证书签发
  - Covers: A22, A23
  - Command: `pytest tests/test_daemon.py::test_cert_issuance`
  - Expect: daemon 为 agent 节点签发短期证书，CN 为 node:{instance_id}

- [x] C20 验证 rig CLI gRPC 连接
  - Covers: A24
  - Command: `rig --help`
  - Expect: CLI 通过 gRPC 连接 daemon，输出子命令列表

- [x] C21 验证 rig entity create/delete
  - Covers: A25
  - Command: `rig entity create --type test --id test-1 && rig entity delete test:test-1`
  - Expect: entity 创建和删除成功

- [x] C22 验证 rig dag status/edit
  - Covers: A26
  - Command: `rig dag status my-dag && rig dag edit my-dag add-node --type fetch`
  - Expect: 返回 DAG 状态和编辑成功

- [x] C23 验证 rig node output
  - Covers: A27
  - Command: `rig node output llm-analyzer --cycle-id <cycle_id>`
  - Expect: 返回节点输出内容

- [x] C24 验证 rig client init
  - Covers: A28
  - Command: `rig client init --server localhost:9090`
  - Expect: 连接 server，保存证书和配置到 ~/.rig/

- [x] C25 验证 BFF gRPC client
  - Covers: A29
  - Command: `curl http://localhost:8000/api/pipeline/dag/my-dag/run -d '{"inputs":{}}'`
  - Expect: BFF 通过 gRPC 转发请求到 daemon，返回 cycle_id

- [x] C26 验证 BFF SSE 推送
  - Covers: A30
  - Command: `curl -N http://localhost:8000/api/events/node/<node_id>`
  - Expect: SSE 连接建立，实时接收 node 输出事件

- [x] C27 验证 BFF token 认证
  - Covers: A31
  - Command: `curl http://localhost:8000/api/pipeline/dag/my-dag/run -H "Authorization: Bearer <token>"`
  - Expect: 有效 token 允许访问，无效 token 返回 401

- [x] C28 验证 Web Console inputs 表单
  - Covers: A32
  - Evidence: 浏览器打开 DAG 触发页面，检查 inputs 表单渲染
  - Expect: 根据 DAG inputs 声明动态渲染输入字段

- [x] C29 验证 Web Console 实时 stdout 展示
  - Covers: A33
  - Evidence: 浏览器打开 agent 节点运行详情页，观察 stdout 实时更新
  - Expect: 页面实时展示 agent 节点 stdout 输出

### 其他验证

- [x] C30 验证 cascade delete design 更新
  - Covers: A34
  - Evidence: 阅读 entity-type-crud-api design 文档
  - Expect: 文档明确说明 cascade delete 为顺序持久化，不保证原子性

- [x] C31 验证依赖安装
  - Covers: A35
  - Command: `pip install grpcio grpcio-tools watchfiles cryptography`
  - Expect: 依赖安装成功，无冲突

## Remediation

- [x] [code_fix] Implement daemon gRPC mTLS, client certificate rejection, and CN identity extraction.
- [x] [code_fix] Enforce gRPC EntityService permissions from certificate identity.
- [x] [code_fix] Make `rig client init` obtain and persist client certificate material.
- [x] [code_fix] Make BFF connect with its own `bff:web-console` client certificate.
