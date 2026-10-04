"""What the hidden acceptance tests share: the workspace's code, and its command line.

Each base's `accept.py` runs from the workspace after the model has acted, by `grade.py
accept`, and never sits in the workspace: the model cannot read or change it during the run.
It reads the workspace's modules and runs its `timelog.py` and `invoice.py` as a person
would, each with a log of its own outside the workspace. Standard library only.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType

WORKSPACE = Path.cwd()
# The workspace's modules come first, ahead of this directory, so an import reads the
# model's code and nothing beside the graders.
if str(WORKSPACE) not in sys.path[:1]:
    sys.path.insert(0, str(WORKSPACE))


def workspace_module(name: str) -> ModuleType:
    """The workspace's module `name`, as the model left it."""

    __import__(name)
    return sys.modules[name]


class Log:
    """A time log of its own, in a temporary directory outside the workspace."""

    def __init__(self, text: str = "") -> None:
        self._directory = tempfile.TemporaryDirectory(prefix="ob-accept-")
        self.path = Path(self._directory.name) / "timelog.tsv"
        if text:
            self.path.write_text(text, encoding="utf-8")

    def text(self) -> str:
        return self.path.read_text(encoding="utf-8") if self.path.exists() else ""

    def run(self, *argv: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
        """`python3 timelog.py <argv>` in the workspace, with this log as its log."""

        return command("timelog.py", *argv, stdin=stdin, log=self.path)

    def close(self) -> None:
        self._directory.cleanup()


def command(
    script: str, *argv: str, stdin: str = "", log: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """One of the workspace's scripts, run as a person runs it, never writing bytecode."""

    env = {key: value for key, value in os.environ.items() if key != "TIMELOG"}
    if log is not None:
        env["TIMELOG"] = str(log)
    return subprocess.run(
        [sys.executable, "-B", script, *argv],
        cwd=str(WORKSPACE),
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def rows(output: str) -> list[list[str]]:
    """A text report as its words, line by line: what it says, whatever its spacing."""

    return [line.split() for line in output.splitlines() if line.strip()]
