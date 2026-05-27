from __future__ import annotations

import os
import importlib.util
import sys
from pathlib import Path

import pytest

from edera_types import HandlerContext, NodeInput

_ADAPTER_PATH = Path(__file__).parents[2] / "extensions" / "uzi-skill" / "adapter.py"
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
async def test_json_safe_payload(tmp_path: Path) -> None:
    _write(
        tmp_path / "dataclass_output.py",
        "from dataclasses import dataclass\n"
        "from pathlib import Path\n"
        "@dataclass\n"
        "class Item:\n"
        "    path: Path\n"
        "def main():\n"
        "    return {'item': Item(Path('report.html'))}\n",
    )

    output = await adapter.run(_ctx(tmp_path, "dataclass_output", [], {}))

    assert output.payload == {"item": {"path": "report.html"}}


def _ctx(
    root: Path,
    module: str,
    args_map: list[dict[str, str]],
    payload: object,
    metadata: dict[str, object] | None = None,
) -> HandlerContext:
    return HandlerContext(
        input=NodeInput(cycle_id="cycle", payload=payload, metadata=metadata or {}),
        params={"module_path": str(root / f"{module}.py"), "function": "main", "args_map": args_map},
        node_name="node",
        node_type="legacy-script-adapter",
        cycle_id="cycle",
        entity_store=_EmptyStore(),
    )


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


class _EmptyStore:
    def query(self, type: str | None = None) -> list[object]:
        return []

    def resolve(self, ref: str) -> object:
        raise KeyError(ref)

    def related_refs(self, ref: str) -> list[str]:
        return []
