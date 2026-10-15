"""What a test of the finish check asks of a run it did not start itself: the run record the
engine keeps in the Git directory, the end of a run a codex stop started in the background, and
`outcomebound finish-check --status`, which is what a person reads on claude-code."""

from __future__ import annotations

import json
import os
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


def _detached_runs(root: Path) -> list[str] | None:
    """The command lines of the detached runs a codex stop started on `root` that still run, or
    None where the process table cannot be read (Windows, or no `ps`). A codex stop starts its
    run before it exits, so the run is in the table as soon as the stop has ended."""

    ps = shutil.which("ps")
    if ps is None or os.name == "nt":
        return None
    listed = subprocess.run(
        [ps, "-A", "-ww", "-o", "stat=,command="], capture_output=True, text=True, check=False
    )
    if listed.returncode != 0:
        return None
    names = {str(root), str(root.resolve())}
    found = []
    for line in listed.stdout.splitlines():
        state, _, command = line.strip().partition(" ")
        if state.startswith("Z") or "--run" not in command.split():
            continue
        if finish_check.ID in command and any(name in command for name in names):
            found.append(command)
    return found


def settle(root: Path, since: datetime, seconds: float = 120) -> dict[str, Any] | None:
    """Wait for the run a codex stop may have started on `root` since `since`, and return its
    record, or None where it started none. Where the process table can be read, the wait is
    for every such run to be gone, which holds however loaded the machine is; elsewhere a run
    record is looked for during 3 s."""

    deadline = time.monotonic() + seconds
    while (left := _detached_runs(root)) is not None and left:
        assert time.monotonic() < deadline, f"a detached run did not end: {left}"
        time.sleep(0.05)
    if left is None:
        look = time.monotonic() + 3
        while time.monotonic() < look:
            record = run_record(root)
            when = started_at(record) if record else None
            if when is not None and when >= since:
                return wait_for_run(root, since, seconds=seconds)
            time.sleep(0.05)
        return None
    record = run_record(root)
    when = started_at(record) if record else None
    return record if when is not None and when >= since else None


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
