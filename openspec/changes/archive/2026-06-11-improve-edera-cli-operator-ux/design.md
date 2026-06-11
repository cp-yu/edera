## Context

`edera` CLI 目前是单文件 argparse 实现，所有命令最终返回 Python 对象并由 `main()` 统一 JSON 打印。前两阶段已经补齐核心命令和控制面命令，当前缺口集中在展示、轮询和日志跟随。约束是继续保持纯 gRPC client，不新增 RPC、不改 server 读写语义。

## Goals / Non-Goals

**Goals:**

- 为现有命令增加统一输出格式，不让每个命令自行处理 JSON/YAML/table。
- 为运行观察命令增加 watch/tail，减少人工排障时的 shell 包装。
- 为列表查询补齐统一分页参数传递，避免不同命令命名漂移。
- 保持现有 JSON stdout 默认行为，避免破坏 agent 和脚本。

**Non-Goals:**

- 不新增 protobuf 字段或服务端分页能力；CLI 只传递现有 limit/offset 或在本地表格渲染已返回数据。
- 不做交互式 TUI、不引入第三方 CLI 框架。
- 不把 server 错误改写成业务含义不同的本地错误。

## Decisions

- 输出格式用一个顶层 `--output json|yaml|table` 处理。默认 `json` 保持现状；`yaml` 使用项目已有 PyYAML；`table` 只对 list/dict 做浅层表格渲染，复杂嵌套用 JSON 字符串放入单元格。
- watch/tail 由 CLI 层重复执行同一个 gRPC 查询。命令增加 `--watch`、`--interval` 和可选 `--watch-count`；默认持续到用户中断，测试和脚本可用 `--watch-count` 有界退出。
- tail 不维护 server-side cursor。CLI 通过已有 `limit` 拉取最近记录，按稳定 JSON 序列化去重后只打印新增项；这避免新增 RPC，也避免假设每个 payload 都有统一时间戳或 ID。
- 分页参数分两层处理：已有 server `limit` 的命令继续把 `limit` 传给 `GrpcClient`；`offset` 只作为 CLI 展示裁剪，作用于顶层 list 或单一 list 字段，不改变 server 请求契约。
- 错误输出统一为 JSON object 到 stderr，字段为 `error`、`type`、`detail`。默认人类可读错误虽然短，但机器处理困难；结构化 stderr 不改变退出码和 stdout 语义。

## Risks / Trade-offs

- [table 对嵌套 payload 信息密度有限] → 嵌套值保留 JSON 字符串，完整结构仍用默认 JSON 或 YAML。
- [watch 可能重复输出大对象] → watch 每轮输出完整结果，tail 只输出去重后的新增日志项。
- [offset 是本地展示裁剪] → 文档和测试明确它不改变 server 查询范围，只影响 CLI 输出对象。
- [结构化 stderr 改变错误文本断言] → 更新 CLI 单元测试为断言 JSON 字段，同时保留错误 detail。
