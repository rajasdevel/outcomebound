"""The checkout engine invocation shared by launcher and package tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.portable import LAUNCH, ROOT


def engine(
    *arguments: str, cwd: Path, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """This checkout's engine, run as `scripts/outcomebound` runs it, through the running Python."""

    return subprocess.run(
        [sys.executable, "-I", "-X", "utf8", "-c", LAUNCH, str(ROOT), *arguments],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
