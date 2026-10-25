#!/usr/bin/env python3
"""Check a suite-v2 fixture's graders against its reference outcomes, with no model call.

`python3 evals/selftest.py [FIXTURE ...] [--verbose]`. A FIXTURE is a name under
`evals/fixtures` or the path of a fixture folder; with none, every fixture that has a
`suite.json`. For each fixture this:

- checks `suite.json` itself: every claim of `post.plan.json` typed (`type` outcome, process,
  cost or safety; `oracle` completion, restraint or safety; `must_always` true or false) and no
  other; at least one completion oracle and one restraint or safety oracle; each report item a
  question with a reading sheet `reading/<item>.md`; the budget a positive input cap and timeout,
  each the tier's default unless the budget gives a `reason`; the stubs present under
  `evals/stubs`; the watched paths relative to the workspace; the required references named;
- for each reference under `references/<name>/`: builds the fixture in a temporary folder as the
  runner does (`setup.sh <workdir> <stage>`, with `run.fixture_setup_env()`), runs its `act.sh`
  there, makes the command-events transcript from `commands.txt` and the answer from
  `answer.md` (a line of `commands.txt` may start with a status in brackets, such as
  `[exited 1] `, instead of the default `succeeded`), supplies `OB_EVAL_WATCH_LOG`,
  `OB_EVAL_STUB_DIGESTS` and `OB_EVAL_BUDGET` from the reference's `watch.log`, `digests.json`
  and `budget.json` or, where it has none, the defaults the build contract states (an empty watch
  log, every stub's digest unchanged, a budget that did not stop with the fixture's reference
  usage), puts `evals/stubs` in `OB_EVAL_STUBS`, runs `post.plan.json` through
  `outcomebound_tools.validation` as `tests/eval_helpers.grade` does, and compares each claim's
  verdict with `expect.json`.

A suite.json with no `references` key is report-only: a fixture outside suite v2 that names its
tier and report items for the blind reading. Its keys, tier and report items with their sheets
are checked, and it is listed as `report-only, no references`. `guard` (true or false) marks a
guard fixture; `budget.reference` is the reference run's usage (`input`, `uncached`, `output`,
`seconds`, `commands`, as available), which the default budget record carries.

A suite.json with `references` and no `budget` is a default fixture's (the kernel and skill
fixtures a run takes when it names none): the runner gives its call no input cap and its own time
limit, so it has no cost claim and no budget record to check. Its `seed` is optional, and so is a
restraint or safety oracle; its references are `good`, `noop` and at least one more, a plausible
wrong outcome named for its defect. Every reference's expect.json names every claim of the plan.

It prints one line per fixture and reference, `PASS` or `FAIL` with each mismatch, and lists each
fixture's report items, which it does not grade: the lead reads them blind (`evals/reading.py`).
Exit 0 only when every suite file is sound and every reference matches; 1 otherwise; 2 where a
named fixture does not exist.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, NamedTuple

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "evals" / "fixtures"
STUBS = REPO / "evals" / "stubs"
RUN_SCRIPT = REPO / "evals" / "run.py"
HERMETIC_GIT = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
# The graders run as the runner runs them (`evals/run.py` GRADER_GIT): no replacement objects.
GRADER_GIT = {**HERMETIC_GIT, "GIT_NO_REPLACE_OBJECTS": "1", "GIT_GRAFT_FILE": os.devnull}
TIMEOUT = 900
CLAIM_LINE = re.compile(r"^(PASS|FAIL|UNVERIFIED) (\S+) \[", re.MULTILINE)

TIERS = ("XS", "S", "M", "L")
# The build contract: the input cap is 3 times the tier's input rate, and each tier's timeout.
INPUT_CAP = {"XS": 900_000, "S": 900_000, "M": 1_500_000, "L": 6_000_000}
TIMEOUT_SECONDS = {"XS": 600, "S": 900, "M": 2400, "L": 5400}
CLAIM_TYPES = ("outcome", "process", "cost", "safety")
ORACLES = ("completion", "restraint", "safety")
REQUIRED_REFERENCES = ("good", "noop", "empty", "incomplete", "overbuilt")
# A default fixture's suite (references and no budget): a good and a noop, and one more at least.
DEFAULT_REFERENCES = ("good", "noop")
SUITE_KEYS = frozenset(
    (
        "tier",
        "seed",
        "panel",
        "guard",
        "class",
        "claims",
        "report",
        "budget",
        "stubs",
        "watch",
        "references",
    )
)
# What a budget's reference usage may record: the reference run's spend.
USAGE_KEYS = ("input", "uncached", "output", "seconds", "commands")
VERDICTS = ("PASS", "FAIL")
ANSWERS = ("yes", "no")


class Fixture(NamedTuple):
    name: str
    folder: Path


def load_runner() -> ModuleType:
    """`evals/run.py` as a module, for the environment fixture setup runs under."""

    spec = importlib.util.spec_from_file_location("eval_run_for_selftest", RUN_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {RUN_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find(names: list[str]) -> list[Fixture]:
    """The fixtures named (a name under evals/fixtures or a folder path), or every fixture with
    a suite.json. ValueError names one that does not exist."""

    if not names:
        return [
            Fixture(path.name, path)
            for path in sorted(FIXTURES.iterdir())
            if (path / "suite.json").is_file()
        ]
    found = []
    for name in names:
        folder = FIXTURES / name if (FIXTURES / name).is_dir() else Path(name)
        if not (folder / "setup.sh").is_file():
            raise ValueError(f"no fixture {name} (no setup.sh in {folder})")
        found.append(Fixture(folder.resolve().name, folder.resolve()))
    return found


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def plan_claims(folder: Path) -> list[str]:
    return [claim["name"] for claim in _read_json(folder / "post.plan.json")["claims"]]


def _budget_problems(suite: dict[str, Any], tier: Any) -> list[str]:
    budget = suite.get("budget")
    if not isinstance(budget, dict):
        return ["budget is an object with input_cap and timeout_seconds"]
    problems = []
    for key, defaults in (("input_cap", INPUT_CAP), ("timeout_seconds", TIMEOUT_SECONDS)):
        value = budget.get(key)
        if type(value) is not int or value <= 0:
            problems.append(f"budget.{key} is a positive integer")
        elif tier in defaults and value != defaults[tier] and not budget.get("reason"):
            problems.append(
                f"budget.{key} {value} is not the {tier} default {defaults[tier]} "
                "and gives no reason"
            )
    reference = budget.get("reference", {})
    if not isinstance(reference, dict):
        return [*problems, "budget.reference is an object of the reference run's usage"]
    for key, value in reference.items():
        if key not in USAGE_KEYS:
            problems.append(f"budget.reference.{key} is not one of {', '.join(USAGE_KEYS)}")
        elif type(value) not in (int, float) or value < 0:
            problems.append(f"budget.reference.{key} is a number, zero or more")
    return problems


def default_fixture(suite: dict[str, Any]) -> bool:
    """Whether the suite.json is a default fixture's: references, and no budget."""

    return "references" in suite and "budget" not in suite


def _claim_problems(suite: dict[str, Any], claims: list[str]) -> list[str]:
    typed = suite.get("claims")
    if not isinstance(typed, dict):
        return ["claims is an object naming every claim of post.plan.json"]
    problems = [f"claim {name} has no type" for name in claims if name not in typed]
    problems += [f"claim {name} is not in post.plan.json" for name in typed if name not in claims]
    for name, entry in typed.items():
        if not isinstance(entry, dict):
            problems.append(f"claim {name} is an object")
            continue
        if entry.get("type") not in CLAIM_TYPES:
            problems.append(f"claim {name}: type is one of {', '.join(CLAIM_TYPES)}")
        if entry.get("oracle") not in ORACLES:
            problems.append(f"claim {name}: oracle is one of {', '.join(ORACLES)}")
        if type(entry.get("must_always", False)) is not bool:
            problems.append(f"claim {name}: must_always is true or false")
    oracles = {entry.get("oracle") for entry in typed.values() if isinstance(entry, dict)}
    if "completion" not in oracles:
        problems.append("no completion oracle")
    if default_fixture(suite):
        problems += [
            f"claim {name} is a cost claim, and a suite with no budget has no budget record"
            for name, entry in typed.items()
            if isinstance(entry, dict) and entry.get("type") == "cost"
        ]
    elif not oracles & {"restraint", "safety"}:
        problems.append("no restraint or safety oracle")
    return problems


def _report_problems(suite: dict[str, Any], folder: Path) -> list[str]:
    report = suite.get("report", {})
    if not isinstance(report, dict):
        return ["report is an object of report items"]
    problems = []
    for item, entry in report.items():
        if not isinstance(entry, dict) or not str(entry.get("question", "")).strip():
            problems.append(f"report item {item} has no question")
        elif type(entry.get("must_always", False)) is not bool:
            problems.append(f"report item {item}: must_always is true or false")
        if not (folder / "reading" / f"{item}.md").is_file():
            problems.append(f"report item {item} has no reading/{item}.md")
    return problems


def _list_problems(suite: dict[str, Any], folder: Path) -> list[str]:
    problems = []
    stubs, watch = suite.get("stubs", []), suite.get("watch", [])
    if not isinstance(stubs, list) or not all(isinstance(item, str) for item in stubs):
        problems.append("stubs is a list of stub names")
    else:
        problems += [f"stub {name} is not in evals/stubs" for name in stubs if not stub(name)]
    if not isinstance(watch, list) or not all(isinstance(item, str) for item in watch):
        problems.append("watch is a list of workspace-relative paths")
    else:
        problems += [
            f"watched path {path} is not relative to the workspace"
            for path in watch
            if not path or Path(path).is_absolute() or ".." in Path(path).parts
        ]
    references = suite.get("references")
    if not isinstance(references, list) or not all(isinstance(item, str) for item in references):
        return [*problems, "references is a list of reference names"]
    required = DEFAULT_REFERENCES if default_fixture(suite) else REQUIRED_REFERENCES
    problems += [f"reference {name} is required" for name in required
                 if name not in references]  # fmt: skip
    if default_fixture(suite) and not set(references) - set(required):
        problems.append("a wrong reference is required beside good and noop")
    for name in references:
        here = folder / "references" / name
        for needed in ("act.sh", "expect.json"):
            if not (here / needed).is_file():
                problems.append(f"reference {name} has no {needed}")
    empty = folder / "references" / "empty" / "answer.md"
    if empty.is_file() and empty.read_text(encoding="utf-8").strip():
        problems.append("reference empty has a non-empty answer")
    return problems


def report_only(suite: dict[str, Any]) -> bool:
    """Whether the suite.json is a report-only one: a fixture outside suite v2 that names its
    tier and report items for the blind reading, and no references."""

    return "references" not in suite


def suite_problems(fixture: Fixture) -> list[str]:
    """What is wrong with the fixture's suite.json, against its plan and its folder. A
    report-only suite.json is checked for its keys, tier and report items only."""

    path = fixture.folder / "suite.json"
    try:
        suite = _read_json(path)
        claims = plan_claims(fixture.folder)
    except (OSError, ValueError, KeyError, TypeError) as problem:
        return [f"cannot read suite.json or post.plan.json: {problem}"]
    if not isinstance(suite, dict):
        return ["suite.json is an object"]
    problems = [f"unknown key {key}" for key in sorted(set(suite) - SUITE_KEYS)]
    tier = suite.get("tier")
    if tier not in TIERS:
        problems.append(f"tier is one of {', '.join(TIERS)}")
    problems += [
        f"{key} is true or false"
        for key in ("panel", "guard")
        if type(suite.get(key, False)) is not bool
    ]
    if report_only(suite):
        return problems + _report_problems(suite, fixture.folder)
    default = default_fixture(suite)
    if not default and (not isinstance(suite.get("seed"), str) or not suite.get("seed")):
        problems.append("seed names the seed project")
    problems += _claim_problems(suite, claims)
    problems += _report_problems(suite, fixture.folder)
    if not default:
        problems += _budget_problems(suite, tier)
    problems += _list_problems(suite, fixture.folder)
    return problems + expect_problems(fixture, suite, claims)


def expect_problems(fixture: Fixture, suite: dict[str, Any], claims: list[str]) -> list[str]:
    """Each reference's expect.json: known claims and items with a PASS/FAIL or yes/no; `good`
    passes every claim and says yes to every item; every other reference fails at least one."""

    items = list(suite.get("report", {}) or {})
    problems = []
    for name in suite.get("references", []) if isinstance(suite.get("references"), list) else []:
        path = fixture.folder / "references" / name / "expect.json"
        if not path.is_file():
            continue
        try:
            expect = _read_json(path)
        except (OSError, ValueError) as problem:
            problems.append(f"reference {name}: expect.json unreadable: {problem}")
            continue
        verdicts, answers = expect.get("claims", {}), expect.get("report", {})
        if not isinstance(verdicts, dict) or not isinstance(answers, dict):
            problems.append(f"reference {name}: expect.json has claims and report objects")
            continue
        problems += [
            f"reference {name}: claim {claim} is not in post.plan.json"
            for claim in verdicts
            if claim not in claims
        ]
        problems += [
            f"reference {name}: expect.json names no verdict for claim {claim}"
            for claim in claims
            if claim not in verdicts
        ]
        problems += [
            f"reference {name}: claim {claim} expects {value!r}, not PASS or FAIL"
            for claim, value in verdicts.items()
            if value not in VERDICTS
        ]
        problems += [
            f"reference {name}: report item {item} is not in suite.json"
            for item in answers
            if item not in items
        ]
        problems += [
            f"reference {name}: report item {item} expects {value!r}, not yes or no"
            for item, value in answers.items()
            if value not in ANSWERS
        ]
        if name == "good":
            if any(verdicts.get(claim) != "PASS" for claim in claims):
                problems.append("reference good does not expect PASS on every claim")
            if any(answers.get(item) != "yes" for item in items):
                problems.append("reference good does not expect yes on every report item")
        elif "FAIL" not in verdicts.values() and "no" not in answers.values():
            problems.append(f"reference {name} names no claim it fails and no item it misses")
    return problems


def stub(name: str) -> Path | None:
    path = STUBS / name
    return path if path.is_file() else None


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def default_digests(stubs: list[str]) -> dict[str, dict[str, str]]:
    """The stub digest record of a call that changed no stub: each stub's before and after
    digest, equal."""

    found = {name: stub(name) for name in stubs}
    return {name: {"before": _digest(p), "after": _digest(p)} for name, p in found.items() if p}


def default_budget(suite: dict[str, Any]) -> dict[str, Any]:
    """The budget record of a call that did not stop: the fixture's reference usage, from
    `budget.reference` where suite.json gives one, else zeros."""

    usage = (suite.get("budget") or {}).get("reference") or {}
    return {
        "stopped": None,
        **{key: usage.get(key, 0) for key in ("input", "uncached", "output", "seconds")},
        **{key: usage[key] for key in USAGE_KEYS if key in usage},
    }


STATUS_PREFIX = re.compile(r"^\[(succeeded|exited -?\d+|declined|failed|unverified)\] ")


def transcript(workdir: Path, commands: list[str], answer: str) -> str:
    """The command-events transcript of the reference, as `tests/eval_helpers.transcript`
    writes one: each command succeeded, in the workspace, unless its line of `commands.txt`
    starts with a status in brackets (`[exited 1] git restore f; false`), which is its status."""

    records = []
    for line in commands:
        found = STATUS_PREFIX.match(line)
        records.append(
            [line[found.end() :], found.group(1), str(workdir)]
            if found
            else [line, "succeeded", str(workdir)]
        )
    return json.dumps(
        {"format": "outcomebound-command-events-v1", "commands": records, "answer": answer}
    )


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _checked(command: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
    done = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT, **options
    )
    if done.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} exited {done.returncode}:\n{done.stdout}{done.stderr}"
        )
    return done


def _seed(workdir: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "refs/tags/seed^{commit}"],
        cwd=workdir,
        capture_output=True,
        text=True,
        env={**os.environ, **HERMETIC_GIT},
        encoding="utf-8",
        timeout=TIMEOUT,
    ).stdout.strip()


def _stub_path(env: dict[str, str]) -> dict[str, str]:
    if not STUBS.is_dir():
        return env
    return {**env, "OB_EVAL_STUBS": str(STUBS), "PATH": f"{STUBS}{os.pathsep}{env.get('PATH', '')}"}


def grade_reference(
    fixture: Fixture,
    suite: dict[str, Any],
    name: str,
    setup_env: dict[str, str],
    scratch: Path,
    folder: Path | None = None,
) -> dict[str, str]:
    """Build the fixture, apply the reference and grade it; each claim's verdict, with the
    validation output under `_output`. `folder` names a reference outside `references/` (a
    control that a test grades, such as a good outcome in another form)."""

    reference = folder or fixture.folder / "references" / name
    workdir, stage, grading = scratch / "ws", scratch / "ws.stage", scratch / "grading"
    for folder in (workdir, stage, grading):
        folder.mkdir(parents=True)
    _checked(["bash", str(fixture.folder / "setup.sh"), str(workdir), str(stage)], env=setup_env)
    _checked(
        ["bash", str(reference / "act.sh")],
        cwd=workdir,
        env=_stub_path({**os.environ, **HERMETIC_GIT, "OB_EVAL_REFERENCE_DIR": str(reference)}),
    )
    commands = [line for line in _text(reference / "commands.txt").splitlines() if line.strip()]
    answer = _text(reference / "answer.md")
    (grading / "post.plan.json").write_bytes((fixture.folder / "post.plan.json").read_bytes())
    (grading / "transcript.txt").write_text(transcript(workdir, commands, answer), "utf-8")
    (grading / "answer.md").write_text(answer, encoding="utf-8")
    records = {
        "OB_EVAL_WATCH_LOG": ("watch.log", ""),
        "OB_EVAL_STUB_DIGESTS": ("digests.json", json.dumps(default_digests(suite["stubs"]))),
        "OB_EVAL_BUDGET": ("budget.json", json.dumps(default_budget(suite))),
    }
    env = {**os.environ, **GRADER_GIT, "PYTHONPATH": str(REPO)}
    for variable in ("OUTCOMEBOUND_EVAL_DIR", "OUTCOMEBOUND_SEED_SHA", *records):
        env.pop(variable, None)
    for variable, (filename, default) in records.items():
        target = grading / filename
        if (reference / filename).is_file():
            shutil.copyfile(reference / filename, target)
        else:
            target.write_text(default, encoding="utf-8")
        env[variable] = str(target)
    revision = _seed(workdir)
    if revision:
        env["OUTCOMEBOUND_SEED_SHA"] = revision
    env.update(
        OUTCOMEBOUND_GRADER_DIR=str(stage),
        OUTCOMEBOUND_EVAL_TRANSCRIPT=str(grading / "transcript.txt"),
        OUTCOMEBOUND_EVAL_ANSWER=str(grading / "answer.md"),
    )
    done = subprocess.run(
        [sys.executable, "-m", "outcomebound_tools.validation", str(grading / "post.plan.json"),
         "--cwd", str(workdir)],
        capture_output=True, text=True, cwd=str(REPO), env=_stub_path(env), timeout=TIMEOUT,
        encoding="utf-8",
    )  # fmt: skip
    verdicts = {found[2]: found[1] for found in CLAIM_LINE.finditer(done.stdout)}
    verdicts["_output"] = done.stdout + done.stderr
    return verdicts


def mismatches(expect: dict[str, Any], verdicts: dict[str, str]) -> list[str]:
    """Each claim whose verdict differs from the one expect.json names."""

    return [
        f"{claim} expected {wanted}, got {verdicts.get(claim, 'no verdict')}"
        for claim, wanted in (expect.get("claims") or {}).items()
        if verdicts.get(claim) != wanted
    ]


def check_fixture(fixture: Fixture, setup_env: dict[str, str], verbose: bool) -> bool:
    """Print the fixture's lines; whether its suite file is sound and every reference matched."""

    problems = suite_problems(fixture)
    try:
        suite = _read_json(fixture.folder / "suite.json")
    except (OSError, ValueError):
        suite = None
    only = isinstance(suite, dict) and report_only(suite)
    shown = ": report-only, no references" if only else ""
    if problems:
        print(f"FAIL {fixture.name}/suite.json{shown}: " + "; ".join(problems))
    else:
        print(f"PASS {fixture.name}/suite.json{shown}")
    if not isinstance(suite, dict):
        return False
    sound = not problems
    listed = suite.get("references")
    references: list[str] = listed if isinstance(listed, list) else []
    suite.setdefault("stubs", [])
    for name in references:
        path = fixture.folder / "references" / name / "expect.json"
        if not path.is_file() or not (path.parent / "act.sh").is_file():
            print(f"FAIL {fixture.name}/{name}: no act.sh or expect.json")
            sound = False
            continue
        with tempfile.TemporaryDirectory(prefix="selftest-") as scratch:
            try:
                verdicts = grade_reference(fixture, suite, name, setup_env, Path(scratch))
            except (OSError, RuntimeError, subprocess.SubprocessError) as problem:
                print(f"FAIL {fixture.name}/{name}: could not build or act: {problem}")
                sound = False
                continue
        found = mismatches(_read_json(path), verdicts)
        sound = sound and not found
        print(f"{'FAIL' if found else 'PASS'} {fixture.name}/{name}" + (
            ": " + "; ".join(found) if found else ""))  # fmt: skip
        if found and verbose:
            print(verdicts["_output"])
    items = list(suite.get("report") or {})
    if items:
        print(f"     {fixture.name} report items, read blind, not graded here: {', '.join(items)}")
    return sound


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evals/selftest.py",
        description="Grade each suite-v2 fixture's reference outcomes; no model call.",
    )
    parser.add_argument("fixtures", nargs="*", metavar="FIXTURE")
    parser.add_argument(
        "--verbose", action="store_true", help="print the validation output of a mismatch"
    )
    args = parser.parse_args(argv)
    try:
        chosen = find(args.fixtures)
    except ValueError as problem:
        sys.stderr.write(f"selftest: {problem}\n")
        return 2
    if not chosen:
        print("selftest: no fixture has a suite.json")
        return 1
    setup_env = load_runner().fixture_setup_env()
    results = [check_fixture(fixture, setup_env, args.verbose) for fixture in chosen]
    print(f"selftest: {sum(results)} of {len(results)} fixtures sound")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
