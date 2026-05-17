## 1. Actions

- [x] A1 在 `routes.py` 新增 `GET /api/config/portfolio` 端点，读取 `config/portfolio.yaml` 并返回 `{ "content": "<yaml text>" }`
- [x] A2 在 `routes.py` 新增 `GET /api/config/system` 端点，读取 `config/system.toml` 并返回 `{ "content": "<toml text>" }`
- [x] A3 在 `routes.py` 新增 `POST /api/graph/dag/{name}/nodes` 端点，创建节点 YAML 文件并追加到 DAG nodes 列表
- [x] A4 为 `useRunDag`、`useStopDag`、`useCreateNode` mutation 添加 `onError` 回调，使用 `window.alert` 展示错误信息
- [x] A5 在 `SourcesPage.tsx` 添加 error state 分支，API 失败时展示错误提示和重试按钮

## 2. Checks

- [x] C1 验证 `GET /api/config/portfolio` 返回配置内容
  - Covers: A1
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && python -m pytest tests/integration/test_web_api.py -k "config_portfolio_read" -x 2>/dev/null || curl -s http://127.0.0.1:8000/api/config/portfolio | python -m json.tool`
  - Expect: 响应包含 `content` 字段，值为 portfolio.yaml 的原始文本

- [x] C2 验证 `GET /api/config/system` 返回配置内容
  - Covers: A2
  - Command: `curl -s http://127.0.0.1:8000/api/config/system | python -m json.tool`
  - Expect: 响应包含 `content` 字段，值为 system.toml 的原始文本

- [x] C3 验证 `POST /api/graph/dag/{name}/nodes` 创建节点成功
  - Covers: A3
  - Command: `curl -s -X POST http://127.0.0.1:8000/api/graph/dag/default/nodes -H 'Content-Type: application/json' -d '{"name":"test_node","type":"rss_fetcher","input_type":"rss_feed","output_type":"raw_item"}' | python -m json.tool`
  - Expect: 响应包含创建后的节点数据，`config/nodes/test_node.yaml` 文件存在，DAG nodes 列表包含 `test_node`

- [x] C4 验证节点名冲突时返回 409
  - Covers: A3
  - Command: `curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/api/graph/dag/default/nodes -H 'Content-Type: application/json' -d '{"name":"existing_node","type":"function","input_type":"any","output_type":"any"}'`
  - Expect: 对已存在的节点名返回 HTTP 409

- [x] C5 验证 mutation 错误时用户收到反馈
  - Covers: A4
  - Evidence: 代码审查 `frontend/src/api/mutations.ts` 中 `useRunDag`、`useStopDag`、`useCreateNode` 的 `onError` 回调
  - Expect: 每个 mutation 包含 `onError` 回调，调用 `window.alert` 展示 `error.message`

- [x] C6 验证信息源页面 API 失败时展示错误状态
  - Covers: A5
  - Evidence: 代码审查 `frontend/src/features/sources/SourcesPage.tsx` 中 `isError` 分支
  - Expect: 存在 error 条件分支，展示错误文案和重试按钮
