from __future__ import annotations

import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def config_write_lock(config_dir: Path, timeout_seconds: float = 30.0) -> Iterator[None]:
    lock = config_dir / ".config.lock"
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                lock.unlink(missing_ok=True)
                continue
            time.sleep(0.05)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def commit_config_changes(config_dir: Path, run_id: str, enabled: bool = True) -> bool:
    if not enabled or not (config_dir / ".git").exists():
        return False
    try:
        changed = _git(config_dir, "status", "--porcelain").stdout.strip()
        if not changed:
            return False
        _git(config_dir, "add", ".")
        summary = ", ".join(line[3:] for line in changed.splitlines()[:5])
        _git(config_dir, "commit", "-m", f"config run {run_id}: {summary}")
        return True
    except subprocess.CalledProcessError:
        return False


def _git(config_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=config_dir,
        check=True,
        text=True,
        capture_output=True,
    )
