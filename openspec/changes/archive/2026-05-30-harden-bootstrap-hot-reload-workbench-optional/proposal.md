<!--
Smart routing:
- input length: Design Summary from exploration used
- detail score: 5/5
- multi-subsystem: true, already decomposed by openspec-explore
- decision: proceed using the explored Design Summary as primary input
-->

## Why

生产环境中 bootstrap 端口固定为 `127.0.0.1:9091`，端口冲突会直接阻断 `edera-server` 和同机 `edera-web` 的证书初始化链路。当前热重载组件已有但未接入 server 生命周期，workbench 也缺少 `optional` 的实例级和边级配置入口，导致已存在的 DAG optional 语义无法从 UI 稳定编辑和保存。

## What Changes

- `edera-server` bootstrap bind 仍固定为 `127.0.0.1`，端口从 `9091` 开始有界退避，并将实际端口写入 `EDERA_DATA_DIR/bootstrap.json`。
- `edera-web` 作为服务端本机 BFF，从 `bootstrap.json` 读取实际 bootstrap 端口，再请求 `bff:web-console` cert；该文件不作为远程 client 协议。
- `edera-server` 启动和停止时管理 `HotReloader.watch()` 后台任务；reload 成功才 emit `event:config-changed`，失败不杀死 watcher、不 emit。
- Workbench 支持编辑 `DagEdge.optional` 和当前 DAG 的 `DagNodeInstance.optional`。实际运行语义仍只有 effective edge optional；节点 optional 只是把该节点实例的所有出边视为 optional 的语法糖。
- GraphService 和 graph draft round-trip 保留 `DagEdge.optional` 与 `DagNodeInstance.optional`，避免保存响应或前端 draft 丢字段。
- 不在本 change 实现完整跨 registry 事务热加载；该能力后续单独立项。

## Capabilities

### New Capabilities

### Modified Capabilities
- `edera-server-grpc`: bootstrap port 保持 localhost-only，但从固定 `9091` 改为有界退避并记录本机发现状态。
- `edera-web-bff`: BFF cert bootstrap 从硬编码 `127.0.0.1:9091` 改为读取本机 `bootstrap.json`。
- `config-hot-reload`: `HotReloader.watch()` 接入 `edera-server` 生命周期，并定义 A+ 失败隔离语义。
- `edge-optional`: 明确 `DagEdge.optional` 是唯一执行语义入口，`DagNodeInstance.optional` 与 `NodeConfig.optional` 是不同作用域的语法糖。
- `dag-workbench-ui`: Inspector 提供 edge optional 和当前 DAG node instance optional 配置入口。
- `grpc-graph-service`: DAG graph GET/SAVE/response round-trip 保留 node instance optional 与 edge optional 字段。

## Impact

- 后端：`packages/core/src/edera_core/server.py`、`packages/core/src/edera_core/web/__main__.py`、`packages/core/src/edera_core/hot_reload.py`、`packages/core/src/edera_core/graph_service.py`、`packages/core/src/edera_core/service_common.py`。
- 前端：`apps/web-console/src/api/types.ts`、`apps/web-console/src/features/workbench/components/Inspector.tsx`、`apps/web-console/src/features/workbench/lib/graph.ts`、必要时覆盖 `Canvas.tsx` 的 edge hydration。
- 规格：更新 bootstrap、BFF、hot reload、optional、workbench 和 GraphService 行为文档。
- 测试：新增 bootstrap 端口冲突、BFF discovery、watcher 生命周期与失败隔离、optional round-trip 和 Inspector 保存覆盖。
