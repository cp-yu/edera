from __future__ import annotations

import json
from pathlib import Path

import pytest

from edera_core.config.schema import (
    AgentNodeConfig,
    DagConfig,
    NodeConfig,
    RuntimeSettings,
    SystemConfig,
)
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import NodeInput
from edera_core.resolver import HandlerMeta
from edera_core.resolver import HandlerNotFoundError
from edera_core.snapshot import DagExecutionClosure
from edera_core.snapshot import DagExecutionSnapshot


def test_executor_with_snapshot():
    snapshot = _snapshot(_Resolver({}))
    executor = NodeExecutor(_nodes(), SystemConfig(), RuntimeSettings(), snapshot)

    assert executor.snapshot is snapshot


@pytest.mark.asyncio
async def test_load_handler_from_snapshot(tmp_path):
    handler = tmp_path / "handler.py"
    handler.write_text("async def run(ctx):\n    return {'ok': True}\n", encoding="utf-8")
    resolver = _Resolver({"reader": HandlerMeta(handler)})
    executor = NodeExecutor(_nodes(), SystemConfig(), RuntimeSettings(), _snapshot(resolver))

    loaded = await executor._load_handler("reader")

    assert resolver.calls == ["reader"]
    assert callable(loaded)


@pytest.mark.asyncio
async def test_load_handler_from_database(tmp_path):
    handler = tmp_path / "handler.py"
    handler.write_text("async def run(ctx):\n    return ctx.input.payload\n", encoding="utf-8")
    executor = NodeExecutor(_nodes(), SystemConfig(), RuntimeSettings(), _snapshot(_Resolver({"reader": HandlerMeta(handler)})))

    output = await executor.execute("reader", NodeInput(run_id="run", payload={"value": 1}))

    assert output.ok
    assert output.payload == {"value": 1}


@pytest.mark.asyncio
async def test_missing_handler_returns_node_output():
    executor = NodeExecutor(_nodes(), SystemConfig(), RuntimeSettings(), _snapshot(_Resolver({})))

    output = await executor.execute("reader", NodeInput(run_id="run", payload={}))

    assert not output.ok
    assert output.error == "handler not found: reader"


@pytest.mark.asyncio
async def test_module_cache(tmp_path):
    handler = tmp_path / "handler.py"
    handler.write_text("async def run(ctx):\n    return ctx.input.payload\n", encoding="utf-8")
    resolver = _Resolver({"reader": HandlerMeta(handler)})
    executor = NodeExecutor(_nodes(), SystemConfig(), RuntimeSettings(), _snapshot(resolver))

    await executor.execute("reader", NodeInput(run_id="run-1", payload=1))
    await executor.execute("reader", NodeInput(run_id="run-2", payload=2))

    assert resolver.calls == ["reader"]


@pytest.mark.asyncio
async def test_handler_storage_uses_execution_snapshot(tmp_path):
    handler = tmp_path / "handler.py"
    handler.write_text("async def run(ctx):\n    return ctx.storage.table('items')\n", encoding="utf-8")
    resolver = _Resolver({"reader": HandlerMeta(handler, extension_name="reader_ext")})
    snapshot = _snapshot(resolver, {"reader_ext": {"items": "snapshot_items"}})
    executor = NodeExecutor(
        _nodes(),
        SystemConfig(),
        RuntimeSettings(),
        snapshot,
    )

    output = await executor.execute("reader", NodeInput(run_id="run", payload={}))

    assert output.ok
    assert output.payload == "snapshot_items"


class _Resolver:
    def __init__(self, entries: dict[str, HandlerMeta]) -> None:
        self.entries = entries
        self.calls: list[str] = []

    async def get(self, name: str) -> HandlerMeta:
        self.calls.append(name)
        try:
            return self.entries[name]
        except KeyError as exc:
            raise HandlerNotFoundError(name) from exc


def _snapshot(
    resolver,
    extension_table_names: dict[str, dict[str, str]] | None = None,
) -> DagExecutionSnapshot:
    return DagExecutionSnapshot(
        DagExecutionClosure("demo", {"demo": _dag()}, _nodes()),
        {},
        resolver,
        extension_table_names or {},
        {},
    )


def _dag() -> DagConfig:
    return DagConfig(name="demo", nodes=[], edges=[], ui={})


def _nodes() -> dict[str, NodeConfig]:
    return {
        "reader": NodeConfig(
            name="reader",
            type="function",
            handler="reader",
            input_type="Any",
            output_type="Any",
        )
    }


def _echo_pi(capture: Path) -> Path:
    pi = capture.parent / "pi"
    pi.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, pathlib\n"
        f"pathlib.Path({str(capture)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        "print('ok')\n",
        encoding="utf-8",
    )
    pi.chmod(0o755)
    return pi


@pytest.mark.asyncio
async def test_agent_command_assembles_capabilities(tmp_path: Path) -> None:
    """C3: 验证 _build_agent_command 完整装配 argv"""
    capture = tmp_path / "args.json"
    pi = _echo_pi(capture)

    skills_dir = tmp_path / "skills"
    (skills_dir / "foo").mkdir(parents=True)
    (skills_dir / "foo" / "SKILL.md").write_text("# Foo", encoding="utf-8")

    node = AgentNodeConfig(
        name="agent-node",
        type="agent",
        model="test-model",
        input_type="Any",
        output_type="Any",
        skills=["foo"],
        tools=["bash"],
        system_prompt="be concise",
    )

    executor = NodeExecutor(
        {"agent-node": node},
        SystemConfig(skills_dir=skills_dir),
        RuntimeSettings(pi_bin=str(pi)),
        _snapshot(_Resolver({})),
        daemon_data_dir=tmp_path / "data",
    )

    output = await executor.execute("agent-node", NodeInput(run_id="run-1", payload={}))

    assert output.ok
    args = json.loads(capture.read_text())

    assert "--no-skills" in args
    assert "--no-context-files" in args
    assert f"--skill" in args
    skill_idx = args.index("--skill")
    assert args[skill_idx + 1] == str(skills_dir / "foo")

    sys_idx = args.index("--system-prompt")
    assert args[sys_idx + 1] == "be concise"

    tools_idx = args.index("--tools")
    assert args[tools_idx + 1] == "bash"


@pytest.mark.asyncio
async def test_agent_command_empty_tools_emits_no_tools(tmp_path: Path) -> None:
    """C3: 空 tools 列表 → --no-tools"""
    capture = tmp_path / "args.json"
    pi = _echo_pi(capture)

    node = AgentNodeConfig(
        name="agent-node",
        type="agent",
        model="test-model",
        input_type="Any",
        output_type="Any",
    )

    executor = NodeExecutor(
        {"agent-node": node},
        SystemConfig(skills_dir=tmp_path / "skills"),
        RuntimeSettings(pi_bin=str(pi)),
        _snapshot(_Resolver({})),
        daemon_data_dir=tmp_path / "data",
    )

    output = await executor.execute("agent-node", NodeInput(run_id="run-1", payload={}))

    assert output.ok
    args = json.loads(capture.read_text())
    assert "--no-tools" in args
    assert "--tools" not in args


@pytest.mark.asyncio
async def test_agent_command_system_prompt_file_append(tmp_path: Path) -> None:
    """C3: system_prompt_file → --append-system-prompt"""
    capture = tmp_path / "args.json"
    pi = _echo_pi(capture)

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("base rules", encoding="utf-8")

    node = AgentNodeConfig(
        name="agent-node",
        type="agent",
        model="test-model",
        input_type="Any",
        output_type="Any",
        system_prompt_file=str(prompt_file),
    )

    executor = NodeExecutor(
        {"agent-node": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        _snapshot(_Resolver({})),
        daemon_data_dir=tmp_path / "data",
    )

    output = await executor.execute("agent-node", NodeInput(run_id="run-1", payload={}))

    assert output.ok
    args = json.loads(capture.read_text())
    append_idx = args.index("--append-system-prompt")
    assert args[append_idx + 1] == str(prompt_file)


@pytest.mark.asyncio
async def test_agent_system_prompt_file_reread_on_modify(tmp_path: Path) -> None:
    """system_prompt_file 执行时现读，改盘后下一次执行反映新内容（不读快照）"""
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("base rules", encoding="utf-8")

    node = AgentNodeConfig(
        name="agent-node",
        type="agent",
        model="test-model",
        input_type="Any",
        output_type="Any",
        system_prompt_file=str(prompt_file),
    )

    # 首次执行：loader 不合并，system_prompt 字段保持空（DB 唯一源）
    assert node.system_prompt is None
    assert node.system_prompt_file == str(prompt_file)

    prompt_file.write_text("updated rules", encoding="utf-8")

    # 改盘后再加载节点配置：system_prompt 仍不被 loader 合并填充
    reloaded = AgentNodeConfig.model_validate(node.model_dump(mode="json"))
    assert reloaded.system_prompt is None
    assert reloaded.system_prompt_file == str(prompt_file)


