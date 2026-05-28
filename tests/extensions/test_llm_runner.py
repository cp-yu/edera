import importlib.util
import json
from pathlib import Path

import pytest

from edera_core.config.schema import NodeConfig, RuntimeSettings, SystemConfig
from edera_core.errors import NodeExecutionError
from edera_types import NodeInput


_LLM_PATH = Path(__file__).parents[2] / "extensions" / "_lib" / "llm.py"
_SPEC = importlib.util.spec_from_file_location("test_llm_module", _LLM_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_LLM = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_LLM)
resolve_session_dir = _LLM.resolve_session_dir
workspace_for_session = _LLM._workspace_for_session
run_pi = _LLM.run_pi
cleanup_sandboxes = _LLM.cleanup_sandboxes


def test_resolve_default_session_dir(tmp_path: Path) -> None:
    assert resolve_session_dir(None, tmp_path, "reader", "cycle-1") == tmp_path / "sandbox" / "reader" / "cycle-1" / "sessions"


def test_resolve_sandbox_cycle_session_dir(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox" / "reader" / "cycle-1"
    sandbox.mkdir(parents=True)

    assert resolve_session_dir("sandbox:reader:cycle-1", tmp_path, "other", "cycle-2") == sandbox / "sessions"


def test_workspace_for_sandbox_session_reuses_origin_workspace(tmp_path: Path) -> None:
    session_dir = tmp_path / "sandbox" / "reader" / "cycle-1" / "sessions"

    assert workspace_for_session(session_dir, tmp_path, "other", "cycle-2") == session_dir.parent


def test_resolve_missing_sandbox_fails(tmp_path: Path) -> None:
    with pytest.raises(NodeExecutionError, match="session sandbox not found"):
        resolve_session_dir("sandbox:reader:cycle-1", tmp_path, "other", "cycle-2")


def test_system_config_keeps_retention_fields() -> None:
    system = SystemConfig(retention_count=1, retention_hours=1)

    assert system.retention_count == 1
    assert system.retention_hours == 1


@pytest.mark.asyncio
async def test_run_pi_passes_tools_continue_and_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capture = tmp_path / "capture.json"
    fake_pi = tmp_path / "fake-pi"
    fake_pi.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps({\n"
        "    'args': sys.argv[1:],\n"
        "    'cwd': os.getcwd(),\n"
        "    'identity': os.environ.get('EDERA_IDENTITY'),\n"
        "    'home': os.environ.get('PI_CODING_AGENT_DIR'),\n"
        "}), encoding='utf-8')\n"
        "print('{\"ok\": true}')\n",
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    workspace_root = tmp_path / "runs"
    session_dir = workspace_root / "sandbox" / "reader" / "cycle-1" / "sessions"
    session_dir.mkdir(parents=True)
    (session_dir / "existing.jsonl").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CAPTURE", str(capture))

    payload, session_id = await run_pi(
        NodeConfig(
            name="reader",
            type="function",
            handler="run-pi",
            tools=["bash", "read"],
            input_type="Any",
            output_type="Any",
            parameters={"model": "hf-share/deepseek-v4-flash", "session_dir": "sandbox:reader:cycle-1"},
        ),
        [],
        NodeInput(cycle_id="cycle-2", payload={}),
        "cycle-2",
        "reader",
        SystemConfig(workspace_root=workspace_root),
        RuntimeSettings(pi_bin=str(fake_pi)),
    )

    captured = json.loads(capture.read_text(encoding="utf-8"))
    assert payload == {"ok": True}
    assert session_id == str(session_dir)
    assert captured["cwd"] == str(session_dir.parent)
    assert captured["identity"] == "node:reader"
    assert "--continue" in captured["args"]
    assert captured["args"][captured["args"].index("--tools") + 1] == "bash,read"
    assert json.loads((session_dir.parent / ".pi" / "settings.json").read_text(encoding="utf-8")) == {
        "defaultModel": "hf-share/deepseek-v4-flash"
    }


@pytest.mark.asyncio
async def test_run_pi_without_existing_session_does_not_continue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capture = tmp_path / "capture.json"
    fake_pi = tmp_path / "fake-pi"
    fake_pi.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n"
        "print('{\"ok\": true}')\n",
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    monkeypatch.setenv("CAPTURE", str(capture))

    await run_pi(
        NodeConfig(
            name="reader",
            type="function",
            handler="run-pi",
            input_type="Any",
            output_type="Any",
            parameters={"model": "hf-share/deepseek-v4-flash"},
        ),
        [],
        NodeInput(cycle_id="cycle-1", payload={}),
        "cycle-1",
        "reader",
        SystemConfig(workspace_root=tmp_path / "runs"),
        RuntimeSettings(pi_bin=str(fake_pi)),
    )

    assert "--continue" not in json.loads(capture.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_run_pi_uses_absolute_session_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capture = tmp_path / "capture.json"
    fake_pi = tmp_path / "fake-pi"
    fake_pi.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps({\n"
        "    'args': sys.argv[1:],\n"
        "    'cwd': os.getcwd(),\n"
        "}), encoding='utf-8')\n"
        "print('{\"ok\": true}')\n",
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    session_dir = tmp_path / "persistent-session"
    session_dir.mkdir()
    (session_dir / "existing.jsonl").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CAPTURE", str(capture))

    _payload, session_id = await run_pi(
        NodeConfig(
            name="advisor",
            type="function",
            handler="run-pi",
            input_type="Any",
            output_type="Any",
            parameters={"model": "hf-share/deepseek-v4-flash", "session_dir": str(session_dir)},
        ),
        [],
        NodeInput(cycle_id="cycle-1", payload={}),
        "cycle-1",
        "advisor",
        SystemConfig(workspace_root=tmp_path / "runs"),
        RuntimeSettings(pi_bin=str(fake_pi)),
    )

    captured = json.loads(capture.read_text(encoding="utf-8"))
    assert session_id == str(session_dir)
    assert captured["args"][captured["args"].index("--session-dir") + 1] == str(session_dir)
    assert "--continue" in captured["args"]
    assert captured["cwd"] == str(tmp_path / "runs" / "sandbox" / "advisor" / "cycle-1")


@pytest.mark.asyncio
async def test_run_pi_payload_resume_session_overrides_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capture = tmp_path / "capture.json"
    fake_pi = tmp_path / "fake-pi"
    fake_pi.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n"
        "print('{\"ok\": true}')\n",
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    workspace_root = tmp_path / "runs"
    configured = workspace_root / "sandbox" / "reader" / "configured"
    override = workspace_root / "sandbox" / "reader" / "override"
    (configured / "sessions").mkdir(parents=True)
    (override / "sessions").mkdir(parents=True)
    (override / "sessions" / "existing.jsonl").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CAPTURE", str(capture))

    _payload, session_id = await run_pi(
        NodeConfig(
            name="reader",
            type="function",
            handler="run-pi",
            input_type="Any",
            output_type="Any",
            parameters={"model": "hf-share/deepseek-v4-flash", "session_dir": "sandbox:reader:configured"},
        ),
        [],
        NodeInput(cycle_id="cycle-2", payload={"resume_session": "sandbox:reader:override"}),
        "cycle-2",
        "reader",
        SystemConfig(workspace_root=workspace_root),
        RuntimeSettings(pi_bin=str(fake_pi)),
    )

    args = json.loads(capture.read_text(encoding="utf-8"))
    assert session_id == str(override / "sessions")
    assert args[args.index("--session-dir") + 1] == str(override / "sessions")
    assert "--continue" in args


def test_cleanup_sandboxes_removes_expired_unreferenced(tmp_path: Path) -> None:
    first = tmp_path / "sandbox" / "reader" / "cycle-1"
    second = tmp_path / "sandbox" / "reader" / "cycle-2"
    first.mkdir(parents=True)
    second.mkdir(parents=True)

    cleanup_sandboxes(SystemConfig(workspace_root=tmp_path, retention_count=1, retention_hours=0))

    assert not first.exists()
    assert second.exists()


def test_cleanup_sandboxes_removes_oversized(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox" / "reader" / "cycle-1"
    sandbox.mkdir(parents=True)
    (sandbox / "large.txt").write_text("12345", encoding="utf-8")

    cleanup_sandboxes(SystemConfig(workspace_root=tmp_path, retention_count=0, retention_hours=0, sandbox_max_bytes=1))

    assert not sandbox.exists()
