"""Run the named project checks and keep the completed result and input digest.

The receipt is local evidence, not an authenticated service record. The integration
suite's wait is simulated by this seed; its posting-flow assertions are unchanged.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def digest():
    paths = sorted(p for folder in ("ledger", "tests", "tools") for p in Path(folder).rglob("*.py"))
    paths.append(Path("Makefile"))
    result = hashlib.sha256()
    for path in paths:
        result.update(str(path).replace("\\", "/").encode("utf-8") + b"\0" + path.read_bytes())
    return result.hexdigest()


def record(kind, mode, before, result=None):
    folder = Path(".runs")
    folder.mkdir(exist_ok=True)
    row = {"kind": kind, "mode": mode, "before": before, "after": digest(), "exit": result}
    with (folder / "checks.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def main():
    mode = sys.argv[1]
    folders = {
        "unit": ("tests/unit",),
        "integration": ("tests/integration",),
        "full": ("tests/unit", "tests/integration"),
    }[mode]
    before = digest()
    record("start", mode, before)
    result = 0
    for folder in folders:
        done = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", folder, "-t", "."],
            check=False,
        )
        result = result or done.returncode
    record("end", mode, before, result)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
