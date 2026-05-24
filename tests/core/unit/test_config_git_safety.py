import threading
import time
from pathlib import Path

from stockimformation_core.config.git import commit_config_changes, config_write_lock


def test_config_git_safety(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    tmp_path.joinpath("system.toml").write_text("schedule_minutes = 30\n", encoding="utf-8")

    assert commit_config_changes(tmp_path, "cycle-1")
    first = _git(tmp_path, "log", "-1", "--pretty=%B")
    assert "cycle-1" in first
    assert not commit_config_changes(tmp_path, "cycle-2")
    tmp_path.joinpath("system.toml").write_text("schedule_minutes = 31\n", encoding="utf-8")
    assert not commit_config_changes(tmp_path, "cycle-3", enabled=False)


def test_config_write_lock_blocks_concurrent_writes(tmp_path: Path) -> None:
    order: list[str] = []

    def first() -> None:
        with config_write_lock(tmp_path):
            order.append("first-start")
            time.sleep(0.1)
            order.append("first-end")

    def second() -> None:
        time.sleep(0.02)
        with config_write_lock(tmp_path):
            order.append("second")

    left = threading.Thread(target=first)
    right = threading.Thread(target=second)
    left.start()
    right.start()
    left.join()
    right.join()

    assert order == ["first-start", "first-end", "second"]


def _git(path: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(["git", *args], cwd=path, check=True, text=True, capture_output=True).stdout
