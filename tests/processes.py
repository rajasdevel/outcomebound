"""What a test asks of a process it started: whether it still runs."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def running(pid: int) -> bool:
    """Whether a process is running. A process killed whose parent is gone stays a zombie when
    no init reaps it, as in a container whose first process is not one: it runs nothing, and
    `os.kill(pid, 0)` still finds it. `os.kill` ends the process it names on Windows, so
    `tasklist` is asked there."""

    if os.name == "nt":
        listed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
            capture_output=True,
            text=True,
            check=False,
        )
        return f'"{pid}"' in listed.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        status = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return True
    return status.rsplit(")", 1)[-1].split()[0] != "Z"
