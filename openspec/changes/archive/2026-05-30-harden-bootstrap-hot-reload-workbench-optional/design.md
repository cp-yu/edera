## Context

当前系统已有 mTLS bootstrap、`HotReloader`、DAG optional 运行语义和 workbench graph 编辑能力，但三个生产可用性缺口仍存在：bootstrap 端口固定为 `127.0.0.1:9091`，生产端口冲突时无法自愈；`HotReloader.watch()` 没有接入 `edera-server` 生命周期；workbench 没有暴露 `DagEdge.optional` 与 `DagNodeInstance.optional`，且 GraphService 保存响应存在丢字段风险。

`edera-web` 是部署在服务端本机的 BFF。它通过本机 bootstrap 获取 `bff:web-console` cert 后，再用 mTLS 连接 `EDERA_SERVER_ADDR`。bootstrap 发现文件只服务本机进程间协作，不成为远程 client 协议。

## Goals / Non-Goals

**Goals:**
- bootstrap bind 继续固定 `127.0.0.1`，端口从 `9091` 起有界退避，并写入本机 `bootstrap.json`。
- `edera-web` 从 `EDERA_DATA_DIR/bootstrap.json` 读取实际 bootstrap port。
- `edera-server` 管理 `HotReloader.watch()` 后台任务，reload 失败不杀死 watcher，成功后才 emit `event:config-changed`。
- workbench 支持编辑 `DagEdge.optional` 和当前 DAG 的 `DagNodeInstance.optional`。
- GraphService 和前端 graph draft 保证 optional 字段 round-trip 不丢失。

**Non-Goals:**
- 不允许配置 bootstrap bind 地址，不把 bootstrap 暴露到外部网卡。
- 不实现远程 client 自动发现 fallback bootstrap port；远程仍按实际端口建立 SSH tunnel。
- 不实现完整跨 registry 事务热加载；后续单独 change 处理 runtime snapshot。
- 不在 DAG workbench 修改全局 `NodeConfig.optional`。

## Decisions

1. **bootstrap 使用 localhost-only 有界退避，而不是 env/flag 配置。**  
   这样解决生产端口冲突，同时保留现有安全边界。替代方案是继续固定 `9091` fail-fast，不能解决生产冲突；另一个替代方案是引入 `EDERA_BOOTSTRAP_PORT`，会把 bootstrap 安全边界变成运维配置问题。

2. **`bootstrap.json` 是本机状态文件，不是远程协议。**  
   文件内容保持极小：`host` 和 `port`。不写 token、cert、主服务地址或远程发现信息。`edera-web` 读取失败或连接失败时 fail fast，避免自动扫端口造成隐式协议。

3. **Hot reload 当前 change 采用 A+，完整事务热加载后续做。**  
   A+ 范围包括 watcher 生命周期、失败隔离和成功后 emit。失败 reload 不替换当前可用行为、不 emit `event:config-changed`、不终止 watcher。跨 registry runtime snapshot 需要重新收敛 handler registry、entity type registry、trigger index 和 cron emitter 所有权，单独立项更清晰。

4. **optional 的实际执行语义只有 effective edge optional。**  
   `DagEdge.optional` 是直接声明；`DagNodeInstance.optional` 是当前 DAG 当前节点实例所有出边 optional 的语法糖；`NodeConfig.optional` 是 node type 所有实例出边 optional 的语法糖。Workbench 只编辑边级和实例级入口。

5. **GraphService 保存响应必须保留 optional。**  
   GET 能看到但 SAVE response 丢字段会导致前端缓存或下一次保存污染配置。后端 response、前端 `toDagDraft()`、edge hydration 必须共同保证 round-trip。

## Risks / Trade-offs

- **过期 `bootstrap.json`** → `edera-web` SHALL fail fast 并报告 bootstrap 状态不可用；不要自动扫描端口。
- **fallback 端口被远程文档误用** → README 和 CLI spec SHALL 明确远程用户按实际端口手动建立 SSH tunnel。
- **A+ 热重载不是完整事务** → 当前 change 只保证失败隔离；完整跨 registry 原子替换另起 change。
- **实例 optional 与类型 optional 并存** → 文档和 UI 文案 SHALL 说明三者区别在作用域，不在执行语义。

