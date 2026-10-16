"""What a test asks of a process it started: whether it still runs."""

from __future__ import annotations

import os
import subprocess

from tests.portable import process_alive


def running(pid: int) -> bool:
    """Whether a process is running. A process killed whose parent is gone stays a zombie when
    no init reaps it, as in a container whose first process is not one: it runs nothing, and
    `os.kill(pid, 0)` still finds it, so a POSIX process is asked through `process_alive`, which
    reads a zombie as gone. `os.kill` ends the process it names on Windows, so `tasklist` is
    asked there."""

    if os.name != "nt":
        return process_alive(pid)
    listed = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )
    return f'"{pid}"' in listed.stdout
