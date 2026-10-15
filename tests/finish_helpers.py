"""What a test of the finish check asks of a run it did not start itself: the run record the
engine keeps in the Git directory, the end of a run a codex stop started in the background, and
`outcomebound finish-check --status`, which is what a person reads on claude-code."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from outcomebound_tools import finish_check
from tests.portable import engine


def git_dir(root: Path) -> Path:
    """The Git directory of a checkout: `.git` in a repository a test made with `git init`, and
    the folder Git names for a worktree, whose `.git` is a file."""

    if (root / ".git").is_dir():
        return root / ".git"
    found = subprocess.run(
        [shutil.which("git") or "git", "-C", str(root), "rev-parse", "--absolute-git-dir"],
        capture_output=True,
        text=True,
        check=False,
    )
    return Path(found.stdout.strip()) if found.returncode == 0 else root / ".git"


def run_record(root: Path) -> dict[str, Any] | None:
    """The run record, or None where there is none or it cannot be read."""

    try:
        document = json.loads((git_dir(root) / finish_check.RUN).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def started_at(record: dict[str, Any]) -> datetime | None:
    return finish_check.stamp(record.get("started"))


def wait_for_run(root: Path, since: datetime, ended: bool = True, seconds: float = 120) -> dict:
    """The record of the run that started at or after `since`, once it has ended where `ended`;
    a test fails where none does within `seconds`."""

    deadline = time.monotonic() + seconds
    while True:
        record = run_record(root)
        when = started_at(record) if record else None
        if record and when is not None and when >= since and (record.get("ended") or not ended):
            return record
        assert time.monotonic() < deadline, f"no run started since {since}: {record}"
        time.sleep(0.05)


def now() -> datetime:
    return datetime.now(timezone.utc)


def status(root: Path) -> str:
    """What `outcomebound finish-check --status` prints for `root`; it exits 0."""

    done = subprocess.run(
        engine("finish-check", "--status", str(root)),
        cwd=root,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr.decode()
    return done.stdout.decode("utf-8")
