#!/usr/bin/env python3
"""Run the shared deployment-state checks from this fixture's sealed copy."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_support = Path(__file__).resolve().parent / "deploy_probe.py"
if not _support.is_file():
    _support = Path(__file__).resolve().parents[3] / "graders" / "deploy_probe.py"
# run_path reads this protected source file without accepting candidate import caches.
_deploy_probe = runpy.run_path(str(_support), run_name="deploy_probe")


if __name__ == "__main__":
    raise SystemExit(_deploy_probe["_main"](sys.argv[1:], Path(__file__).name))
