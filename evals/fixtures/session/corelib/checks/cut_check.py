#!/usr/bin/env python3
"""Exit zero only when the third ticket disposition has a reachable commit."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def main():
    done = subprocess.run(
        ["git", "log", "--format=%s", "seed..HEAD"],
        cwd=Path(os.environ["OB_WORKSPACE"]),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    subjects = done.stdout.splitlines()
    return (
        0
        if done.returncode == 0
        and all(
            any(subject.startswith("ticket " + key + ":") for subject in subjects)
            for key in ("021", "022", "023")
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
