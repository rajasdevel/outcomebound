"""Protected acceptance for an ordinary repair with sufficient existing tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from runpy import run_path

support = run_path(str(Path(__file__).resolve().parent.parent / "patch-validation/support.py"))
inputs, report, run_tests, scope = (
    support[key] for key in ("inputs", "report", "run_tests", "scope")
)
setup = run_path(str(Path(__file__).with_name("setup_testing_no_work.py")))


def tests() -> list[str]:
    try:
        result = run_tests(
            Path("test_labels.py"),
            Path("labels.py").read_text(encoding="utf-8"),
            "labels",
            ["item_label"],
        )
    except (OSError, ValueError) as problem:
        return ["UNVERIFIED unable to replay label tests: " + str(problem)]
    print("observed: existing label test outcomes " + json.dumps(result, sort_keys=True))
    if result["count"] != 3 or len(result["passed"]) != 3 or result["errors"] or result["failures"]:
        return ["existing label regression does not pass"]
    return []


if __name__ == "__main__":
    checks = {
        "scope": lambda: scope(["labels.py"]),
        "inputs": inputs,
        "tests": tests,
    }
    raise SystemExit(report(checks[sys.argv[1]]()))
