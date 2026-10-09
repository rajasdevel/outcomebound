"""Protected grading of the synthetic repairs, submitted tests and assessment."""

from __future__ import annotations

import json
import posixpath
import sys
from pathlib import Path
from runpy import run_path

setup = run_path(str(Path(__file__).with_name("setup_patch_validation.py")))
BASELINE, FIXED, PARTIAL = (setup[key] for key in ("BASELINE", "FIXED", "PARTIAL"))
support = run_path(str(Path(__file__).with_name("support.py")))
inputs, report, run_tests, scope = (
    support[key] for key in ("inputs", "report", "run_tests", "scope")
)

EXPECTED = {
    "candidates": {"A": {"fix_established": True}, "B": {"fix_established": False}},
    "supplied_probe": {"check_completed": False, "security_claim_established": False},
}
REPORTED = "../secret"


def assessment() -> list[str]:
    try:
        actual = json.loads(Path("assessment.json").read_text(encoding="utf-8"))
        values = {
            "candidates": {
                key: {"fix_established": actual["candidates"][key]["fix_established"]}
                for key in ("A", "B")
            },
            "supplied_probe": {
                key: actual["supplied_probe"][key]
                for key in ("check_completed", "security_claim_established")
            },
        }
    except (OSError, ValueError, KeyError, TypeError) as problem:
        return ["missing or invalid assessment: " + str(problem)]
    # Equality alone treats 0/1 as booleans, which would weaken the declared artifact contract.
    fields = [
        *[values["candidates"][key]["fix_established"] for key in ("A", "B")],
        *values["supplied_probe"].values(),
    ]
    if any(type(value) is not bool for value in fields) or values != EXPECTED:
        return ["assessment does not distinguish the complete fix, partial fix and setup failure"]
    return []


def read_path(call):
    return call["arguments"].get("path", "")


def security_cases(results) -> list[str]:
    fixed = results["fixed"]
    problems = []
    reported = [
        call
        for call in fixed["calls"]
        if read_path(call) == REPORTED and call.get("exception") == "ValueError"
    ]
    if not reported:
        problems.append("the reported refusal was not exercised on the complete fix")
    reported_tests = {
        call["test"] for call in results["baseline"]["calls"] if read_path(call) == REPORTED
    }
    if not reported_tests.intersection(results["baseline"]["failures"]):
        problems.append("baseline reported case is not caught by an assertion")
    variant_calls = [
        call
        for call in results["partial"]["calls"]
        if "result" in call
        and posixpath.normpath("docs/" + read_path(call)) != "docs"
        and not posixpath.normpath("docs/" + read_path(call)).startswith("docs/")
        and read_path(call) != REPORTED
    ]
    caught = {call["test"] for call in variant_calls}.intersection(results["partial"]["failures"])
    if not caught:
        problems.append("partial fix escapes assertions on a distinct normalized path")
    if not any(
        call.get("exception") == "ValueError" and call["test"] in caught for call in fixed["calls"]
    ):
        problems.append("the partial-fix counterexample does not reach the fixed refusal")
    if not any(
        "result" in call
        and call["arguments"]
        .get("documents", {})
        .get(posixpath.normpath("docs/" + read_path(call)))
        == call["result"]
        and call["test"] in fixed["passed"]
        for call in fixed["calls"]
    ):
        problems.append("no benign document read confirms the stored result")
    return problems


def tests() -> list[str]:
    try:
        results = {
            name: run_tests(Path("test_vault.py"), code, "vault", ["read_document"])
            for name, code in (("fixed", FIXED), ("baseline", BASELINE), ("partial", PARTIAL))
        }
        supplied = run_tests(Path("supplied_probe.py"), FIXED, "vault", ["read_document"])
    except (OSError, ValueError) as problem:
        return ["UNVERIFIED unable to replay submitted tests: " + str(problem)]
    print("observed: submitted regression outcomes " + json.dumps(results, sort_keys=True))
    print("observed: supplied probe outcome " + json.dumps(supplied, sort_keys=True))
    problems = []
    fixed = results["fixed"]
    if (
        not fixed["count"]
        or len(fixed["passed"]) != fixed["count"]
        or fixed["errors"]
        or fixed["failures"]
    ):
        problems.append("submitted tests do not pass on the complete fix")
    if not supplied["errors"] or supplied["calls"]:
        problems.append(
            "supplied probe no longer demonstrates an error before the reader is called"
        )
    for name in ("baseline", "partial"):
        result = results[name]
        if not result["failures"]:
            problems.append(name + " does not fail a submitted assertion")
    problems.extend(security_cases(results))
    return problems


if __name__ == "__main__":
    mode = sys.argv[1]
    checks = {
        "scope": lambda: scope(["test_vault.py", "assessment.json"]),
        "inputs": inputs,
        "assessment": assessment,
        "tests": tests,
    }
    raise SystemExit(report(checks[mode]()))
