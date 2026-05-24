## 1. Actions

- [x] A1 创建 uv workspace 根 `pyproject.toml`，声明 `packages/core` 和 `packages/core-types` 为 workspace members
- [x] A2 创建 `packages/core-types/` 包结构：`pyproject.toml` + `src/stockimformation_types/`，定义 `NodeInput`、`NodeOutput`、`HandlerContext`、`HandlerProtocol`、`EntityStoreProtocol`
- [x] A3 创建 `packages/core/` 包结构：`pyproject.toml` + `src/stockimformation_core/`，依赖 `stockimformation-types`
- [x] A4 迁移 `src/stockimformation/dag/` 到 `packages/core/src/stockimformation_core/dag/`（runner、loader、conditions、models）
- [x] A5 迁移 `src/stockimformation/config/` 到 `packages/core/src/stockimformation_core/config/`（schema、loader、entities、git）
- [x] A6 迁移 `src/stockimformation/trigger.py` 到 `packages/core/src/stockimformation_core/trigger.py`
- [x] A7 迁移 `src/stockimformation/models/` 到 `packages/core/src/stockimformation_core/storage/`（database、repository），移除 `RawItem` 专用表定义，保留 `PipelineRun`、`NodeRun`、`NodeOutputEntity`
- [x] A8 迁移 `src/stockimformation/errors.py` 到 `packages/core/src/stockimformation_core/errors.py`
- [x] A9 实现 `packages/core/src/stockimformation_core/manifest.py` — manifest 解析、校验、NodeTypeDescriptor 提取、fallback 逻辑
- [x] A10 实现 `packages/core/src/stockimformation_core/registry.py` — HandlerRegistry 和 EntityTypeRegistry
- [x] A11 实现 `packages/core/src/stockimformation_core/bootstrap.py` — 扫描扩展目录、解析 manifest、构建 registry、设置 sys.path、声明式建表
- [x] A12 重构 `packages/core/src/stockimformation_core/node/executor.py` — 移除 `_run_pi`/`_prepare_workspace`/LLM 分支，统一为 importlib 加载 + `HandlerContext` 单参数调用
- [x] A13 重构 `packages/core/src/stockimformation_core/pipeline.py` — 移除 `_build_executor` 硬编码 handler 字典，改为从 bootstrap registry 获取
- [x] A14 实现 `packages/core/src/stockimformation_core/engine.py` — 统一启动入口 `Engine(config_dir, extensions_dirs)`
- [x] A15 创建 `extensions/_lib/http_fetch.py` — 从 `services/collection.py` 提取 HTTP 抓取、recovery、去重逻辑
- [x] A16 创建 `extensions/_lib/llm.py` — 从 `node/executor.py` 提取 `_run_pi`、`_prepare_workspace` 逻辑
- [x] A17 创建 `extensions/rss-fetcher/` — `manifest.yaml` + `handler.py`，实现 `async def run(ctx: HandlerContext)`
- [x] A18 创建 `extensions/web-scraper/` — `manifest.yaml` + `handler.py`
- [x] A19 创建 `extensions/api-fetcher/` — `manifest.yaml` + `handler.py`
- [x] A20 创建 `extensions/reader/` — `manifest.yaml` + `handler.py`（内部调用 `_lib/llm.py`）
- [x] A21 创建 `extensions/advisor/` — `manifest.yaml` + `handler.py`
- [x] A22 创建 `extensions/briefing-generator/` — `manifest.yaml` + `handler.py`
- [x] A23 创建 `extensions/notifier/` — `manifest.yaml` + `handler.py`
- [x] A24 移动 `frontend/` 到 `apps/web-console/`，更新相关路径引用
- [x] A25 更新所有测试文件的 import 路径，重组为 `tests/core/` 和 `tests/extensions/`
- [x] A26 删除旧 `src/stockimformation/` 目录和旧 `handlers/`、`skill_handlers/`、`services/` 目录
- [x] A27 更新根 `pyproject.toml` 入口点 `stockimformation = "stockimformation_core.main:main"`

## 2. Checks

- [x] C1 验证 uv workspace 结构可解析
  - Covers: A1, A2, A3
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && uv sync`
  - Expect: 依赖解析成功，`packages/core` 和 `packages/core-types` 均可安装

- [x] C2 验证 core-types 包可独立导入
  - Covers: A2
  - Command: `python -c "from stockimformation_types import HandlerContext, HandlerProtocol, EntityStoreProtocol, NodeInput, NodeOutput"`
  - Expect: 导入成功，无 ImportError

- [x] C3 验证核心 DAG 模块迁移后可导入
  - Covers: A4, A5, A8
  - Command: `python -c "from stockimformation_core.dag.runner import DagRunner; from stockimformation_core.dag.loader import load_graph; from stockimformation_core.config.schema import DagConfig"`
  - Expect: 导入成功

- [x] C4 验证 trigger 模块迁移
  - Covers: A6
  - Command: `python -c "from stockimformation_core.trigger import TriggerExecutor, EventGroup"`
  - Expect: 导入成功

- [x] C5 验证 storage 模块迁移且无 RawItem 表
  - Covers: A7
  - Command: `python -c "from stockimformation_core.storage.repository import create_pipeline_run, store_node_output_entities" && grep -rL "RawItem" packages/core/src/`
  - Expect: 导入成功，核心代码中无 `RawItem` 引用

- [x] C6 验证 manifest 解析 — 完整 manifest
  - Covers: A9
  - Command: `python -c "from stockimformation_core.manifest import parse_manifest; from pathlib import Path; m = parse_manifest(Path('extensions/rss-fetcher/manifest.yaml')); assert m.name == 'rss-fetcher'; assert len(m.handlers) >= 1"`
  - Expect: 解析成功，handler 描述符包含 name、role、input_type、output_type

- [x] C7 验证 manifest 解析 — 缺少必填字段时报错
  - Covers: A9
  - Command: `python -c "from stockimformation_core.manifest import parse_manifest; from pathlib import Path; import tempfile, yaml; f = tempfile.NamedTemporaryFile(suffix='.yaml', mode='w', delete=False); yaml.dump({'description': 'no name'}, f); f.close(); parse_manifest(Path(f.name))" 2>&1 | grep -i "error\|missing\|validation"`
  - Expect: 抛出校验错误，提示缺少 `name` 或 `version`

- [x] C8 验证 handler registry 构建和冲突检测
  - Covers: A10
  - Command: `python -c "from stockimformation_core.registry import HandlerRegistry; r = HandlerRegistry(); r.register('fetch-rss', '/tmp/a.py'); r.register('fetch-rss', '/tmp/b.py')" 2>&1 | grep -i "conflict\|duplicate\|error"`
  - Expect: 第二次注册同名 handler 时抛出冲突错误

- [x] C9 验证 bootstrap 扫描扩展目录
  - Covers: A11
  - Command: `python -c "from stockimformation_core.bootstrap import scan_extensions; from pathlib import Path; result = scan_extensions([Path('extensions')]); assert 'fetch-rss' in result.handler_registry"`
  - Expect: 扫描成功，rss-fetcher 扩展的 handler 已注册

- [x] C10 验证 node executor 统一调用协议
  - Covers: A12
  - Command: `grep -c "_run_pi\|_prepare_workspace\|type.*llm" packages/core/src/stockimformation_core/node/executor.py`
  - Expect: 输出 `0`，核心 executor 中无 LLM 相关代码

- [x] C11 验证 pipeline controller 无硬编码 handler
  - Covers: A13
  - Command: `grep -c "make_fetch_handler\|make_advice_handler\|make_briefing_handler\|make_notify_handler" packages/core/src/stockimformation_core/pipeline.py`
  - Expect: 输出 `0`，无业务 handler 工厂引用

- [x] C12 验证 Engine 启动入口
  - Covers: A14
  - Command: `python -c "from stockimformation_core.engine import Engine; from pathlib import Path; e = Engine(config_dir=Path('config'), extensions_dirs=[Path('extensions')]); print(type(e))"`
  - Expect: Engine 实例化成功

- [x] C13 验证 _lib/http_fetch 共享模块
  - Covers: A15
  - Command: `python -c "import sys; sys.path.insert(0, 'extensions'); from _lib.http_fetch import fetch_with_recovery, dedupe_raw_items"`
  - Expect: 导入成功

- [x] C14 验证 _lib/llm 共享模块
  - Covers: A16
  - Command: `python -c "import sys; sys.path.insert(0, 'extensions'); from _lib.llm import prepare_workspace, run_pi"`
  - Expect: 导入成功

- [x] C15 验证扩展 handler 符合 HandlerContext 协议
  - Covers: A17, A18, A19, A20, A21, A22, A23
  - Command: `for ext in rss-fetcher web-scraper api-fetcher reader advisor briefing-generator notifier; do python -c "import sys, importlib.util; sys.path.insert(0, 'extensions'); spec = importlib.util.spec_from_file_location('handler', f'extensions/$ext/handler.py'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); import inspect; sig = inspect.signature(mod.run); params = list(sig.parameters); assert len(params) == 1, f'$ext: expected 1 param, got {len(params)}'" && echo "$ext: OK"; done`
  - Expect: 所有扩展 handler 均为单参数签名

- [x] C16 验证前端目录移动
  - Covers: A24
  - Command: `test -d apps/web-console/src && test -f apps/web-console/package.json && echo "OK"`
  - Expect: 输出 `OK`

- [x] C17 验证旧目录已清理
  - Covers: A26
  - Command: `test ! -d src/stockimformation && test ! -d handlers && test ! -d skill_handlers && echo "CLEAN"`
  - Expect: 输出 `CLEAN`

- [x] C18 验证核心测试通过
  - Covers: A4, A5, A6, A7, A8, A9, A10, A11, A12, A13, A14, A25
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && uv run pytest tests/core/ -x`
  - Expect: 所有核心测试通过

- [x] C19 验证扩展测试通过
  - Covers: A15, A16, A17, A18, A19, A20, A21, A22, A23, A25
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && uv run pytest tests/extensions/ -x`
  - Expect: 所有扩展测试通过

- [x] C20 验证 entity type 双层优先级
  - Covers: A9, A11
  - Command: `python -c "from stockimformation_core.bootstrap import scan_extensions; from stockimformation_core.config.loader import load_entity_types; from pathlib import Path; ext_types = scan_extensions([Path('extensions')]).entity_type_registry; user_types = load_entity_types(Path('config')); merged = {**ext_types, **user_types}; assert 'rss-source' in merged"`
  - Expect: 合并成功，用户配置覆盖扩展声明

- [x] C21 验证入口点可启动
  - Covers: A27
  - Command: `timeout 3 uv run stockimformation 2>&1 || true`
  - Expect: 进程启动（可能因端口占用退出），无 ImportError 或 ModuleNotFoundError
