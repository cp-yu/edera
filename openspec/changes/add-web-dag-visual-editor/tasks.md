## 1. Actions

- [x] A1 创建 OpenSpec change 文档，覆盖 DAG 结构化编辑、保存校验和 YAML 兜底要求。
- [x] A2 在 Web 后端增加 DAG 视图模型和结构化 DAG payload 到 YAML 的保存路径，保存必须调用 `RuntimeConfigEditor.save("dag", ...)`。
- [x] A3 在 `config.html` 中为 `current.kind == "dag"` 增加结构化 DAG 编辑表单和 SVG 预览挂载点，并保持 YAML textarea 可用。
- [x] A4 新增最小 Vanilla JS，负责添加/删除边、整理 edges JSON hidden input、同步 SVG 预览，不实现 DAG 业务校验。
- [x] A5 扩展 `styles.css`，为 DAG 面板、预览、节点和边表格提供最小样式与移动端布局。
- [x] A6 增加单元和集成测试，覆盖结构化保存、非法 DAG 不写入、DAG 页面展示和非 DAG 页面隔离。

## 2. Checks

- [x] C1 验证 OpenSpec change 可用于实施
  - Covers: A1
  - Command: `openspec validate add-web-dag-visual-editor --strict`
  - Expect: validation passes

- [x] C2 验证结构化 DAG 保存和非法输入回滚
  - Covers: A2, A6
  - Command: `pytest tests/unit/test_config_editor.py tests/integration/test_web_api.py`
  - Expect: valid structured DAG writes YAML; cyclic, unknown-node, and I/O mismatch submissions return errors without modifying the file

- [x] C3 验证 DAG 编辑 UI 与 YAML 兜底
  - Covers: A3, A4, A5, A6
  - Command: `pytest tests/integration/test_web_api.py`
  - Expect: `/config?kind=dag&name=default` contains the DAG editor and raw YAML editor; `/config?kind=node&name=reader` does not contain the DAG editor

- [x] C4 验证静态质量门禁
  - Covers: A2, A3, A4, A5, A6
  - Command: `ruff check . && mypy src/stockimformation`
  - Expect: no lint or type errors
