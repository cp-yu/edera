from __future__ import annotations

import os
import importlib.util
import sys
import time
from pathlib import Path

import pytest

from edera_testing.fixtures import create_mock_handler_context

_ADAPTER_PATH = Path(__file__).parents[1] / "adapter.py"
_SPEC = importlib.util.spec_from_file_location("test_uzi_skill_adapter", _ADAPTER_PATH)
assert _SPEC is not None and _SPEC.loader is not None
adapter = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(adapter)


@pytest.mark.asyncio
async def test_basic_call(tmp_path: Path) -> None:
    _write(tmp_path / "fetch_basic.py", "def main(ticker):\n    return {'ticker': ticker}\n")

    output = await adapter.run(_ctx(tmp_path, "fetch_basic", [{"source": "params.ticker"}], {"ticker": "00100.HK"}))

    assert output.ok is True
    assert output.payload == {"ticker": "00100.HK"}


@pytest.mark.asyncio
async def test_hk_prefixed_ticker_is_normalized_for_legacy_scripts(tmp_path: Path) -> None:
    _write(tmp_path / "fetch_basic.py", "def main(ticker):\n    return {'ticker': ticker}\n")

    output = await adapter.run(_ctx(tmp_path, "fetch_basic", [{"source": "params.ticker"}], {"ticker": "HK.00100"}))

    assert output.ok is True
    assert output.payload == {"ticker": "00100.HK"}


@pytest.mark.asyncio
async def test_exception_handling(tmp_path: Path) -> None:
    _write(tmp_path / "broken.py", "def main(ticker):\n    raise ValueError('bad ticker')\n")

    output = await adapter.run(_ctx(tmp_path, "broken", [{"source": "params.ticker"}], {"ticker": "00100.HK"}))

    assert output.ok is True
    assert output.payload["quality"] == "ERROR"
    assert "bad ticker" in output.payload["error"]


@pytest.mark.asyncio
async def test_args_from_params(tmp_path: Path) -> None:
    _write(tmp_path / "fetch_params.py", "def main(ticker):\n    return ticker\n")

    output = await adapter.run(_ctx(tmp_path, "fetch_params", [{"source": "params.ticker"}], {"ticker": "00020.HK"}))

    assert output.payload == "00020.HK"


@pytest.mark.asyncio
async def test_args_from_input(tmp_path: Path) -> None:
    _write(tmp_path / "fetch_industry.py", "def main(industry):\n    return industry\n")
    ctx = _ctx(
        tmp_path,
        "fetch_industry",
        [{"source": "input.0_basic.data.industry", "default": "综合"}],
        [{"data": {"industry": "软件服务"}}],
        metadata={"upstreams": ["0_basic"]},
    )

    output = await adapter.run(ctx)

    assert output.payload == "软件服务"


@pytest.mark.asyncio
async def test_path_isolation(tmp_path: Path) -> None:
    _write(tmp_path / "helper.py", "VALUE = 'ok'\n")
    _write(tmp_path / "path_fetcher.py", "from helper import VALUE\n\ndef main():\n    return VALUE\n")
    old_cwd = os.getcwd()
    old_path = list(sys.path)

    output = await adapter.run(_ctx(tmp_path, "path_fetcher", [], {}))

    assert output.payload == "ok"
    assert os.getcwd() == old_cwd
    assert sys.path == old_path


@pytest.mark.asyncio
async def test_env_isolation(tmp_path: Path) -> None:
    _write(tmp_path / "env_reader.py", "import os\n\ndef main():\n    return os.environ.get('UZI_CLI_ONLY')\n")
    old = os.environ.get("UZI_CLI_ONLY")
    ctx = _ctx(tmp_path, "env_reader", [], {})
    ctx.params["env"] = {"UZI_CLI_ONLY": "1"}

    output = await adapter.run(ctx)

    assert output.payload == "1"
    assert os.environ.get("UZI_CLI_ONLY") == old


@pytest.mark.asyncio
async def test_nested_lib_import_path(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    (scripts / "lib" / "pipeline").mkdir(parents=True)
    _write(scripts / "lib" / "__init__.py", "")
    _write(scripts / "lib" / "helper.py", "VALUE = 'ok'\n")
    _write(
        scripts / "lib" / "pipeline" / "preflight_helpers.py",
        "from lib.helper import VALUE\n\ndef main():\n    return VALUE\n",
    )

    output = await adapter.run(_ctx(scripts / "lib" / "pipeline", "preflight_helpers", [], {}))

    assert output.payload == "ok"


@pytest.mark.asyncio
async def test_nested_package_relative_import(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    renderer = scripts / "lib" / "pipeline" / "renderer"
    renderer.mkdir(parents=True)
    for path in (scripts / "lib", scripts / "lib" / "pipeline", renderer):
        _write(path / "__init__.py", "")
    _write(renderer / "base.py", "VALUE = 'ok'\n")
    _write(renderer / "section.py", "from .base import VALUE\n\ndef main():\n    return VALUE\n")

    output = await adapter.run(_ctx(renderer, "section", [], {}))

    assert output.payload == "ok"


@pytest.mark.asyncio
async def test_subprocess_call_preserves_nested_package_import(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    renderer = scripts / "lib" / "pipeline" / "renderer"
    renderer.mkdir(parents=True)
    for path in (scripts / "lib", scripts / "lib" / "pipeline", renderer):
        _write(path / "__init__.py", "")
    _write(renderer / "base.py", "VALUE = 'ok'\n")
    _write(renderer / "section.py", "from .base import VALUE\n\ndef main():\n    return VALUE\n")
    ctx = _ctx(renderer, "section", [], {})
    ctx.params["timeout_seconds"] = 5.0

    output = await adapter.run(ctx)

    assert output.payload == "ok"


@pytest.mark.asyncio
async def test_subprocess_call_times_out(tmp_path: Path) -> None:
    _write(tmp_path / "slow.py", "import time\n\ndef main():\n    time.sleep(5)\n")
    ctx = _ctx(tmp_path, "slow", [], {})
    ctx.params["timeout_seconds"] = 0.2

    started = time.monotonic()
    output = await adapter.run(ctx)

    assert time.monotonic() - started < 2
    assert output.ok is True
    assert output.payload["quality"] == "ERROR"
    assert "legacy script timeout" in output.payload["error"]


@pytest.mark.asyncio
async def test_renderer_class_fallback(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    renderer = scripts / "lib" / "pipeline" / "renderer"
    renderer.mkdir(parents=True)
    for path in (scripts / "lib", scripts / "lib" / "pipeline", renderer):
        _write(path / "__init__.py", "")
    _write(
        renderer / "base.py",
        "from dataclasses import dataclass, field\n"
        "@dataclass\n"
        "class RenderContext:\n"
        "    ticker: str\n"
        "    name: str\n"
        "    market: str = 'A'\n"
        "    data: dict = field(default_factory=dict)\n"
        "    meta: dict = field(default_factory=dict)\n"
        "    quality: str = 'full'\n"
        "class SectionRenderer:\n"
        "    section_id = ''\n"
        "    def render(self, ctx):\n"
        "        return self.render_full(ctx)\n",
    )
    _write(
        renderer / "basic_header.py",
        "from .base import SectionRenderer\n"
        "class BasicHeaderRenderer(SectionRenderer):\n"
        "    section_id = 'basic_header'\n"
        "    def render_full(self, ctx):\n"
        "        return f\"<h1>{ctx.name}:{ctx.data['name']}</h1>\"\n",
    )
    payload = {
        "raw": {"ticker": "00100.HK", "dimensions": {"0_basic": {"data": {"name": "X"}}}},
        "synthesis": {"ticker": "00100.HK", "name": "Y"},
    }
    ctx = _ctx(renderer, "basic_header", [{"source": "input"}], payload)
    ctx.params["function"] = "render"

    output = await adapter.run(ctx)

    assert output.payload == {"section_id": "basic_header", "html": "<h1>Y:X</h1>"}


@pytest.mark.asyncio
async def test_json_safe_payload(tmp_path: Path) -> None:
    _write(
        tmp_path / "dataclass_output.py",
        "from dataclasses import dataclass\n"
        "from datetime import date\n"
        "from pathlib import Path\n"
        "@dataclass\n"
        "class Item:\n"
        "    path: Path\n"
        "def main():\n"
        "    return {'item': Item(Path('report.html')), 'date': date(2026, 6, 4)}\n",
    )

    output = await adapter.run(_ctx(tmp_path, "dataclass_output", [], {}))

    assert output.payload == {"item": {"path": "report.html"}, "date": "2026-06-04"}


def test_score_dimensions_wrapper_normalizes_collection_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_call(name, raw):
        seen["name"] = name
        seen["raw"] = raw
        return {"fundamental_score": 60}

    monkeypatch.setattr(adapter, "_call_run_real_test", fake_call)

    output = adapter.score_dimensions_from_raw({
        "0_basic": {"data": {"ticker": "300470.SZ", "market": "A"}},
        "4_market": {"data": {"stage": "Stage 2"}},
        "15_competitors": {"data": {"peer_table": []}},
    })

    assert output["dims_scored"] == {"fundamental_score": 60}
    assert seen["name"] == "score_dimensions"
    assert seen["raw"]["ticker"] == "300470.SZ"
    assert "dimensions" in seen["raw"]
    assert seen["raw"]["dimensions"]["2_kline"] == {"data": {"stage": "Stage 2"}}
    assert seen["raw"]["dimensions"]["4_peers"] == {"data": {"peer_table": []}}


def test_basic_header_name_falls_back_to_intro() -> None:
    data = adapter._section_data(
        {"dimensions": {"0_basic": {"data": {"intro": "MiniMax Group Inc.是全球领先的通用人工智能科技公司。"}}}},
        "basic_header",
    )

    assert data["name"] == "MiniMax Group Inc."


def test_generate_panel_wrapper_adds_agent_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_call(name, dims_scored, raw):
        assert name == "generate_panel"
        assert dims_scored == {"score": 80}
        assert raw == {"ticker": "300470.SZ"}
        return {"investors": []}

    monkeypatch.setattr(adapter, "_call_run_real_test", fake_call)

    output = adapter.generate_panel_from_scored({
        "raw": {"ticker": "300470.SZ"},
        "dims_scored": {"score": 80},
    })

    assert "analyst_<investor_id>" in output["prompt"]
    assert output["panel"] == {"investors": []}


def test_generate_synthesis_wrapper_merges_agent_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_call(name, raw, dims_scored, panel):
        seen["name"] = name
        seen["raw"] = raw
        seen["dims_scored"] = dims_scored
        seen["panel"] = panel
        return {"verdict": "ok"}

    monkeypatch.setattr(adapter, "_call_run_real_test", fake_call)

    output = adapter.generate_synthesis_from_panel([
        {"raw": {"ticker": "300470.SZ"}, "dims_scored": {"score": 80}, "panel": {"investors": []}},
        {"stdout": "{\"investor_id\":\"buffett\",\"signal\":\"bullish\",\"score\":90}"},
    ])

    assert output["synthesis"] == {"verdict": "ok"}
    assert seen["name"] == "generate_synthesis"
    assert seen["panel"]["agent_evaluations"] == [{"investor_id": "buffett", "signal": "bullish", "score": 90}]


def test_generate_synthesis_wrapper_accepts_named_upstreams(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_call(name, raw, dims_scored, panel):
        seen["name"] = name
        seen["raw"] = raw
        seen["dims_scored"] = dims_scored
        seen["panel"] = panel
        return {"verdict": "ok"}

    monkeypatch.setattr(adapter, "_call_run_real_test", fake_call)

    output = adapter.generate_synthesis_from_panel({
        "generate_panel": {"raw": {"ticker": "300470.SZ"}, "dims_scored": {"score": 80}, "panel": {"investors": []}},
        "analyst_buffett": {"stdout": "{\"investor_id\":\"buffett\",\"signal\":\"bullish\",\"score\":90}"},
    })

    assert output["synthesis"] == {"verdict": "ok"}
    assert seen["name"] == "generate_synthesis"
    assert seen["raw"] == {"ticker": "300470.SZ"}
    assert seen["dims_scored"] == {"score": 80}
    assert seen["panel"]["agent_evaluations"] == [{"investor_id": "buffett", "signal": "bullish", "score": 90}]


def test_generate_synthesis_wrapper_accepts_fenced_agent_json(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_call(name, raw, dims_scored, panel):
        seen["panel"] = panel
        return {"verdict": "ok"}

    monkeypatch.setattr(adapter, "_call_run_real_test", fake_call)

    adapter.generate_synthesis_from_panel({
        "generate_panel": {"raw": {"ticker": "300470.SZ"}, "dims_scored": {"score": 80}, "panel": {"investors": []}},
        "analyst_buffett": {"stdout": "```json\n{\"investor_id\":\"buffett\",\"signal\":\"bullish\",\"score\":90}\n```"},
    })

    assert seen["panel"]["agent_evaluations"] == [{"investor_id": "buffett", "signal": "bullish", "score": 90}]


def test_generate_synthesis_wrapper_falls_back_for_empty_agent_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_call(name, raw, dims_scored, panel):
        seen["panel"] = panel
        return {"verdict": "ok"}

    monkeypatch.setattr(adapter, "_call_run_real_test", fake_call)

    adapter.generate_synthesis_from_panel([
        {
            "raw": {"ticker": "00100.HK"},
            "dims_scored": {"score": 20},
            "panel": {
                "investors": [
                    {"investor_id": "buffett", "name": "巴菲特", "signal": "bearish", "score": 20, "headline": "看空核心"},
                    {"investor_id": "graham", "name": "格雷厄姆", "signal": "neutral", "score": 40, "headline": "等待折价"},
                ]
            },
        },
        {"stdout": "", "session_id": "/tmp/sessions/analyst_buffett/run-1"},
    ])

    assert seen["panel"]["agent_evaluations"] == [
        {
            "investor_id": "buffett",
            "name": "巴菲特",
            "signal": "bearish",
            "score": 20,
            "headline": "看空核心",
            "agent_node_id": "analyst_buffett",
            "source": "rule_engine_fallback",
        }
    ]


def test_analyst_panel_html_renders_agent_evaluations() -> None:
    html = adapter._analyst_panel_html({
        "panel": {
            "agent_evaluations": [
                {
                    "investor_id": "buffett",
                    "name": "巴菲特",
                    "signal": "bearish",
                    "score": 20,
                    "verdict": "回避",
                    "headline": "看空核心：自由现金流不达标",
                    "source": "rule_engine_fallback",
                }
            ]
        }
    })

    assert "投资评审团明细" in html
    assert "巴菲特" in html
    assert "规则回退" in html


def test_analyst_panel_html_labels_panel_investors() -> None:
    html = adapter._analyst_panel_html({
        "panel": {
            "investors": [
                {"investor_id": "graham", "name": "格雷厄姆", "signal": "bearish", "score": 0, "headline": "估值不满足"}
            ]
        }
    })

    assert "格雷厄姆" in html
    assert "规则面板" in html


def test_assemble_rendered_report_writes_single_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "__file__", str(tmp_path / "extensions" / "uzi-skill" / "adapter.py"))
    payload = {
        "render_b": {"section_id": "b", "html": "<section>B</section>"},
        "render_a": {"section_id": "a", "html": "<section>A</section>"},
    }
    edge_inputs = [
        {"from_node_id": "render_a", "status": "available", "has_payload": True},
        {"from_node_id": "render_b", "status": "available", "has_payload": True},
    ]

    output = adapter.assemble_rendered_report(payload, "run-1", edge_inputs)

    report_path = Path(output["report_path"])
    assert output["section_count"] == 2
    assert report_path.exists()
    assert "<!doctype html>" in output["html"]
    text = report_path.read_text(encoding="utf-8")
    assert text.index("<section>A</section>") < text.index("<section>B</section>")


def _ctx(
    root: Path,
    module: str,
    args_map: list[dict[str, str]],
    payload: object,
    metadata: dict[str, object] | None = None,
) -> HandlerContext:
    return create_mock_handler_context(
        input_payload=payload,
        input_metadata=metadata or {},
        params={"module_path": str(root / f"{module}.py"), "function": "main", "args_map": args_map},
        node_name="node",
        node_type="legacy-script-adapter",
        run_id="run",
    )


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
