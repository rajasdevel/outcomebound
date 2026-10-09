"""Protected property replay; no exact assertion wording is required."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from runpy import run_path

support = run_path(str(Path(__file__).resolve().parent.parent / "patch-validation/support.py"))
inputs, report, run_tests, scope = (
    support[key] for key in ("inputs", "report", "run_tests", "scope")
)
setup = run_path(str(Path(__file__).with_name("setup_property_oracles.py")))


def tests() -> list[str]:
    try:
        results = {
            name: run_tests(Path("test_codec.py"), code, "codec", ["encode", "decode", "normalize"])
            for name, code in (
                ("fixed", setup["FIXED"]),
                ("sign-loss", setup["LOSS"]),
                ("unstable-normalization", setup["ROTATION"]),
                ("coupled-reversal", setup["COUPLED"]),
            )
        }
    except (OSError, ValueError) as problem:
        return ["UNVERIFIED unable to replay submitted tests: " + str(problem)]
    print("observed: submitted property outcomes " + json.dumps(results, sort_keys=True))
    problems = []
    fixed = results["fixed"]
    if (
        not fixed["count"]
        or len(fixed["passed"]) != fixed["count"]
        or fixed["errors"]
        or fixed["failures"]
    ):
        problems.append("submitted tests do not pass on the fixed codec")
    for name in ("sign-loss", "unstable-normalization", "coupled-reversal"):
        result = results[name]
        if result["errors"] or not result["failures"]:
            problems.append(name + " is not caught by a submitted assertion")
    calls = fixed["calls"]
    roundtrip = False
    idempotence = False
    for call in calls:
        values = call["arguments"].get("values")
        if (
            call["function"] == "encode"
            and isinstance(values, list)
            and len(set(values)) >= 2
            and any(value < 0 for value in values)
            and values != sorted(values)
        ):
            roundtrip |= any(
                other["function"] == "decode"
                and other["test"] == call["test"]
                and other["arguments"].get("text") == call.get("result")
                and other.get("result") == values
                for other in calls
            )
        if call["function"] == "normalize" and isinstance(values, list) and len(set(values)) >= 2:
            idempotence |= any(
                other["function"] == "normalize"
                and other["test"] == call["test"]
                and other["arguments"].get("values") == call.get("result")
                and other.get("result") == call.get("result")
                for other in calls
                if other is not call
            )
    if not roundtrip:
        problems.append("no nontrivial signed, ordered encode/decode case was exercised")
    if not idempotence:
        problems.append("no nontrivial normalization result was normalized again")
    print("observed: independent oracles and generator coverage require source review")
    return problems


if __name__ == "__main__":
    checks = {
        "scope": lambda: scope(["test_codec.py"]),
        "inputs": inputs,
        "tests": tests,
    }
    raise SystemExit(report(checks[sys.argv[1]]()))
