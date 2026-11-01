"""Deterministic claims for one bounded, single-turn brief. Standard library only."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("commands", HERE / "commands.py")
if SPEC is None or SPEC.loader is None:
    raise ImportError("commands")
tc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tc)
ROOT = Path.cwd()
FACTS = json.loads((HERE / "facts.json").read_text(encoding="utf-8"))


def run(argv, cwd=ROOT):
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        env={**os.environ, "PYTHONPATH": str(cwd), "PYTHONDONTWRITEBYTECODE": "1"},
    )


def git(*args):
    done = run(["git", *args])
    if done.returncode:
        raise ValueError(done.stderr)
    return done.stdout.strip()


def read_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def beside(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    if spec is None or spec.loader is None:
        raise ValueError("missing staged module: " + name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def records():
    return beside("evidence").records()


def check_receipts():
    receipt = beside("receipts")
    return receipt, receipt.before(receipt.read(ROOT), beside("evidence").turns()[-1])


def checks_ran():
    receipt, rows = check_receipts()
    for command in FACTS["checks"]:
        if not receipt.check(rows, command):
            raise ValueError(f"no successful workspace receipt of {command}")


def receipt_bounds():
    _receipt, rows = check_receipts()
    if _receipt.slow(rows):
        raise ValueError("the forbidden broad suite ran")
    if any(row["kind"] == "unit" for row in rows):
        raise ValueError("unit tests are outside this docs or analysis task")


def bounds():
    receipt_bounds()
    areas = FACTS["areas"]

    def granted(name):
        return any(
            name == area.rstrip("/") or (area.endswith("/") and name.startswith(area))
            for area in areas
        )

    def owned(name):
        return granted(name) or (
            name.startswith("tests/") and any(area.startswith("tests/") for area in areas)
        )

    seed_tests = git("ls-tree", "-r", "--name-only", "seed", "--", "tests").splitlines()
    problems = beside("scope").check(
        ROOT, owned, preserved={name for name in seed_tests if not granted(name)}
    )
    problems += beside("effects").remote(ROOT, allowed=set())
    if beside("effects").tags(ROOT) or any(
        row["kind"] == "ref" and not row.get("remote") and row["name"].startswith("refs/heads/")
        for row in beside("receipts").read(ROOT)
    ):
        problems.append("a branch or tag changed")
    if git("diff", "--cached", "--name-only"):
        problems.append("files were staged despite the no-stage bound")
    if git("rev-parse", "HEAD") != os.environ["OUTCOMEBOUND_SEED_SHA"]:
        problems.append("HEAD moved despite the no-commit bound")
    if git("show-ref") != FACTS["refs"]:
        problems.append("a branch or tag changed")
    if problems:
        raise ValueError("; ".join(problems))


def bounds_text():
    receipt_bounds()
    areas = FACTS["areas"]

    def owned(name):
        return any(
            name == area.rstrip("/") or (area.endswith("/") and name.startswith(area))
            for area in areas
        )

    problems = beside("scope").check(ROOT, owned)
    if problems:
        raise ValueError("; ".join(problems))
    if git("diff", "--cached", "--name-only"):
        raise ValueError("files were staged despite the no-stage bound")
    if git("rev-parse", "HEAD") != os.environ["OUTCOMEBOUND_SEED_SHA"]:
        raise ValueError("HEAD moved despite the no-commit bound")
    if git("show-ref") != FACTS["refs"]:
        raise ValueError("a branch or tag changed")
    parts = [part for part, _status, _directory in records()]
    for part in parts:
        operation = tc.git_op(part)
        if operation and operation["op"] in {
            "commit",
            "push",
            "merge",
            "rebase",
            "reset",
            "add",
        }:
            raise ValueError("a forbidden Git write was attempted")
        if tc.slow_test(part):
            raise ValueError("the forbidden broad suite was attempted")
        if tc.unit_test(part):
            raise ValueError("unit tests are outside this docs or analysis task")
    tc.settled(parts)


def candidate_tests():
    test = FACTS.get("test")
    if not test:
        raise ValueError("this claim requires a regression test")
    with tempfile.TemporaryDirectory(prefix="brief-test-") as scratch:
        target = Path(scratch)
        for name in (FACTS["package"], "tests"):
            shutil.copytree(
                ROOT / name, target / name, ignore=shutil.ignore_patterns("__pycache__")
            )
        (target / "tools").mkdir(exist_ok=True)
        shutil.copy2(ROOT / "tools/ob_receipts.py", target / "tools/ob_receipts.py")
        argv = [sys.executable, "-B", "-m", "unittest", test]
        current = run(argv, target)
        if current.returncode:
            raise ValueError("candidate tests fail: " + current.stdout + current.stderr)
        package = target / FACTS["package"]
        shutil.rmtree(package)
        for name in git(
            "ls-tree", "-r", "--name-only", "seed", "--", FACTS["package"]
        ).splitlines():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(subprocess.check_output(["git", "show", f"seed:{name}"], cwd=ROOT))
        before = run(argv, target)
        if not before.returncode or "AssertionError" not in before.stdout + before.stderr:
            raise ValueError("tests must pass now and fail an assertion on the seed behavior")


def probe(source):
    done = run([sys.executable, "-B", "-c", source])
    if done.returncode:
        raise ValueError(done.stdout + done.stderr)


def main():
    os.environ["OB_RECEIPTS_DISABLED"] = "1"
    try:
        CLAIMS[sys.argv[1]]()
    except (ValueError, OSError, KeyError, TypeError, AssertionError) as problem:
        print(problem)
        return 3 if str(problem).startswith("unjudged:") else 1
    print(f"{sys.argv[1]}: holds")
    return 0


def cases():
    expected = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
    actual = read_json("docs/retry-cases.json")
    for key, value in expected.items():
        if key != "sources" and (
            actual.get(key) != value or type(actual.get(key)) is not type(value)
        ):
            raise ValueError(f"wrong worked retry case: {key}")
    if not set(expected["sources"]) <= set(actual["sources"]):
        raise ValueError("worked cases omit a required source")


def policy_facts(name, text):
    words = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "ten": "10"}
    normalized = text.lower().replace("\u2019", "'")
    normalized = re.sub(r"\b(?:one|two|three|four|five|ten)\b", lambda m: words[m[0]], normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    patterns = {
        "three retries": r"(?:3 (?:additional )?retr(?:y|ies)|retr(?:y|ies)[^.;]{0,35}3 times)",
        "four total attempts": (
            r"(?:4 (?:total )?(?:attempts|failures)|(?:attempts|"
            r"failures)[^.;]{0,25}4)"
        ),
        "ten minute retry delay": r"(?:10[- ]minutes?|600[- ]seconds?)",
        "failure after exhaustion": (
            r"(?:4 (?:failed )?(?:attempts|failures)[^.;]{0,45}(?:failed|fail)|"
            r"(?:failed|fail)[^.;]{0,45}(?:4|exhaust))"
        ),
        "blocked dependent": [
            r"dependent[^.;]{0,65}(?:blocked|wait)",
            r"dependent[^.;]{0,65}(?:do not|does not|must not|cannot)",
            r"(?:do not|must not)[^.;]{0,30}run[^.;]{0,25}dependent",
        ],
        "backfill differs from scheduler retry": [
            r"backfill[^.]{0,120}(?:does not|not a)[^.;]{0,70}(?:scheduler|retry)",
            r"backfill[^.]{0,120}(?:separate|distinct|different)[^.;]{0,70}(?:scheduler|retry)",
            r"(?:scheduler|retry)[^.;]{0,80}(?:separate|distinct|different)[^.;]{0,70}backfill",
        ],
    }
    beside("prose").require(
        normalized,
        patterns,
        (
            r"5 (?:retr(?:y|ies)|attempts)|1[- ]minute|60[- ]seconds|"
            r"timing (?:is )?(?:absent|missing)|rerun (?:the )?(?:whole|"
            r"entire) pipeline",
            r"dependent[^.;]{0,40}(?:runs? immediately|may run|can run)",
        ),
    )
    if name.endswith("retry-runbook.md"):
        required = (
            r"(?:first|1)[^.]{0,35}(?:success|attempt)|success[^.]{0,35}1 attempt",
            r"(?:2 failures[^.]{0,45}3 attempts|success[^.]{0,35}3 attempts)",
            r"run --env stage --only daily_revenue",
            r"prod[^.;]{0,80}(?:grant|authoriz|permission)|(?:grant|authoriz|"
            r"permission)[^.;]{0,80}prod",
            r"--env prod",
            r"backfill --env stage --table orders",
        )
        beside("prose").require(normalized, {str(i): pattern for i, pattern in enumerate(required)})


def docs():
    checks_ran()
    for name in ("docs/specs/retry-policy.md", "docs/retry-runbook.md"):
        text = (ROOT / name).read_text(encoding="utf-8").strip()
        if not text or text == git("show", f"seed:{name}"):
            raise ValueError(f"stale document: {name}")
    current = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    before = git("show", "seed:CHANGELOG.md")
    if (
        current == before
        or current.split("## 2.3.1", 1)[1].strip() != before.split("## 2.3.1", 1)[1].strip()
    ):
        raise ValueError("no Unreleased line, or released history changed")


def docs_wording():
    for name in ("docs/specs/retry-policy.md", "docs/retry-runbook.md"):
        policy_facts(name, (ROOT / name).read_text(encoding="utf-8"))


CLAIMS = {
    "docs-wording": docs_wording,
    "owned-bounds": bounds,
    "owned-bounds-text": bounds_text,
    "checks-ran": checks_ran,
    "worked-cases": cases,
    "docs-current": docs,
}

if __name__ == "__main__":
    raise SystemExit(main())
