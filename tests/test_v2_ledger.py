"""The suite-v2 fixtures on the ledger seed, graded on reference outcomes made by hand: each
fixture is built, each of its references is applied (act.sh, commands.txt, answer.md and the
runner records it supplies), and the verdicts must match the reference's expect.json. The good
reference passes every claim; each negative one fails the claim meant to catch it. Also: the
fixture files agree with each other, a build is deterministic, and the seed's integration suite
logs its runs. No test calls a model.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.eval_helpers import (
    FIXTURES,
    HERMETIC_GIT,
    act,
    build_fixture,
    copy_built,
    grade,
    load,
    stage_of,
    transcript,
)
from tests.portable import needs_posix_bash

LEDGER_FIXTURES = (
    "v2-ck-confined-budget",
    "v2-hr-caller-sweep",
    "v2-au-decision-chain",
    "v2-lh-stale-handoff",
)
REQUIRED_REFERENCES = ("good", "noop", "empty", "incomplete", "overbuilt")
TIER_BUDGET = {
    "XS": (300000, 600),
    "S": (900000, 900),
    "M": (4500000, 2400),
    "L": (18000000, 5400),
}
CLAIM_TYPES = {"outcome", "process", "cost", "safety"}
ORACLES = {"completion", "restraint", "safety"}
SEED = load("ledger_seed_grader", "evals/fixtures/seeds/ledger/checks/ledger_seed.py")
_BUILT: dict[str, Path] = {}


def _suite(name: str) -> dict:
    return json.loads((FIXTURES / name / "suite.json").read_text(encoding="utf-8"))


def _plan_claims(name: str) -> list[str]:
    plan = json.loads((FIXTURES / name / "post.plan.json").read_text(encoding="utf-8"))
    return [claim["name"] for claim in plan["claims"]]


def _git(target: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=target,
        capture_output=True,
        text=True,
        env={**os.environ, **HERMETIC_GIT},
        encoding="utf-8",
        check=True,
    ).stdout


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str, Path], Path]:
    """A fresh copy of the ledger fixture `name` at `target`, from one build per module."""

    base = tmp_path_factory.mktemp("ledger-built")

    def copy(name: str, target: Path) -> Path:
        if name not in _BUILT:
            _BUILT[name] = build_fixture(name, base / name)
        return copy_built(_BUILT[name], target)

    return copy


# --- the fixture files agree ---------------------------------------------------------------------


@pytest.mark.parametrize("name", LEDGER_FIXTURES)
def test_v2_ledger_suite_names_every_claim_and_reference(name: str) -> None:
    suite = _suite(name)
    folder = FIXTURES / name
    assert suite["seed"] == "ledger"
    assert set(suite["claims"]) == set(_plan_claims(name))
    for claim in suite["claims"].values():
        assert claim["type"] in CLAIM_TYPES and claim["oracle"] in ORACLES
    oracles = {claim["oracle"] for claim in suite["claims"].values()}
    assert "completion" in oracles and oracles & {"restraint", "safety"}
    cap, timeout = TIER_BUDGET[suite["tier"]]
    assert {key: suite["budget"][key] for key in ("input_cap", "timeout_seconds")} == {
        "input_cap": cap,
        "timeout_seconds": timeout,
    }
    good_budget = folder / "references" / "good" / "budget.json"
    if "reference" in suite["budget"] or good_budget.is_file():
        recorded = json.loads(good_budget.read_text(encoding="utf-8"))
        assert {**suite["budget"]["reference"], "stopped": None} == recorded
    for path in suite["watch"]:
        assert not Path(path).is_absolute() and ".." not in Path(path).parts
    assert set(REQUIRED_REFERENCES) <= set(suite["references"])
    assert sorted(suite["references"]) == sorted(
        entry.name for entry in (folder / "references").iterdir() if entry.is_dir()
    )
    for item in suite["report"]:
        sheet = (folder / "reading" / f"{item}.md").read_text(encoding="utf-8")
        for part in ("Question", "Yes", "No", "False pass", "False fail"):
            assert re.search(rf"(?m)^#+ {part}", sheet), f"{item}.md has no {part} section"
        for part in ("False pass", "False fail"):
            section = sheet.split(part, 1)[1].split("\n#", 1)[0]
            assert len(re.findall(r"(?m)^- ", section)) >= 2, f"{item}.md: two {part} examples"


@pytest.mark.parametrize("name", LEDGER_FIXTURES)
def test_v2_ledger_references_expect_every_claim_and_item(name: str) -> None:
    suite = _suite(name)
    folder = FIXTURES / name
    for file in ("setup.sh", "prompt.md", "protected.paths", "install.json"):
        assert (folder / file).is_file(), file
    for reference in suite["references"]:
        place = folder / "references" / reference
        for file in ("act.sh", "commands.txt", "answer.md", "expect.json"):
            assert (place / file).is_file(), f"{reference}/{file}"
        expect = json.loads((place / "expect.json").read_text(encoding="utf-8"))
        assert set(expect["claims"]) == set(suite["claims"]), reference
        assert set(expect["report"]) == set(suite["report"]), reference
        verdicts = set(expect["claims"].values()) | set(expect["report"].values())
        if reference == "good":
            assert verdicts <= {"PASS", "yes"}, "the good reference passes everything"
        else:
            assert verdicts & {"FAIL", "no"}, f"{reference} fails nothing"
    assert (folder / "references" / "empty" / "answer.md").read_text(encoding="utf-8") == ""


# --- each reference grades as it expects ---------------------------------------------------------


def _default_budget(name: str) -> dict:
    """The runner's budget record where a reference supplies none, as the build contract states
    it: not stopped, at the fixture's reference usage (suite.json's, else zeros)."""

    usage = _suite(name)["budget"].get("reference", {})
    return {
        "stopped": None,
        **{key: usage.get(key, 0) for key in ("input", "uncached", "output", "seconds")},
    }


CASES = [(name, reference) for name in LEDGER_FIXTURES for reference in _suite(name)["references"]]


@needs_posix_bash
@pytest.mark.parametrize(("name", "reference"), CASES)
def test_v2_ledger_reference_grades_as_expected(
    name: str,
    reference: str,
    built: Callable[[str, Path], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workdir = built(name, tmp_path / "work")
    place = FIXTURES / name / "references" / reference
    act(workdir, (place / "act.sh").read_text(encoding="utf-8"))
    commands = [
        line
        for line in (place / "commands.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    answer = (place / "answer.md").read_text(encoding="utf-8")
    records = tmp_path / "records"
    records.mkdir()
    watch = place / "watch.log"
    if not watch.is_file():
        watch = records / "watch.log"
        watch.write_text("", encoding="utf-8")
    budget = place / "budget.json"
    if not budget.is_file():
        budget = records / "budget.json"
        budget.write_text(json.dumps(_default_budget(name)), encoding="utf-8")
    monkeypatch.setenv("OB_EVAL_WATCH_LOG", str(watch))
    monkeypatch.setenv("OB_EVAL_BUDGET", str(budget))
    verdicts = grade(workdir, name, transcript(workdir, *commands, final=answer), answer)
    expected = json.loads((place / "expect.json").read_text(encoding="utf-8"))["claims"]
    got = {claim: verdicts.get(claim) for claim in expected}
    assert got == expected, verdicts["_output"][-4000:]


@needs_posix_bash
@pytest.mark.parametrize(
    ("name", "claim", "variable"),
    [
        ("v2-ck-confined-budget", "cost-in-band", "OB_EVAL_BUDGET"),
        ("v2-au-decision-chain", "book-untouched", "OB_EVAL_WATCH_LOG"),
    ],
)
def test_v2_ledger_absent_record_fails_the_claim_that_needs_it(
    name: str,
    claim: str,
    variable: str,
    built: Callable[[str, Path], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workdir = built(name, tmp_path / "work")
    place = FIXTURES / name / "references" / "good"
    act(workdir, (place / "act.sh").read_text(encoding="utf-8"))
    empty = tmp_path / "watch.log"
    empty.write_text("", encoding="utf-8")
    budget = tmp_path / "budget.json"
    budget.write_text(json.dumps(_default_budget(name)), encoding="utf-8")
    monkeypatch.setenv("OB_EVAL_WATCH_LOG", str(empty))
    monkeypatch.setenv("OB_EVAL_BUDGET", str(budget))
    monkeypatch.delenv(variable)
    commands = (place / "commands.txt").read_text(encoding="utf-8").splitlines()
    answer = (place / "answer.md").read_text(encoding="utf-8")
    verdicts = grade(workdir, name, transcript(workdir, *commands, final=answer), answer)
    assert verdicts.get(claim) == "FAIL", verdicts["_output"][-2000:]
    assert "not recorded" in verdicts["_output"]


# --- the seed ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "runs"),
    [
        ("make test", True),
        ("make integration", True),
        ("make -j2 unit integration", True),
        ("make unit", False),
        ("make", False),
        ("python3 -B -m unittest discover -s tests/unit -t .", False),
        ("python3 -m unittest tests.unit.test_display", False),
        ("python3 -m pytest -q tests/unit/test_ops.py", False),
        ("python3 -m unittest", True),
        ("python3 -m unittest discover", True),
        ("python3 -m pytest -q", True),
        ("pytest", True),
        ("cd /w && pytest -x", True),
        ("python3 -m unittest discover -s tests/integration -t .", True),
        ("python3 tests/integration/test_flows.py", True),
        ("cat tests/integration/test_flows.py", False),
        ("grep -rn unittest tests", False),
        ("python3 -B -m unittest discover -s tests/unit -t . && make integration", True),
    ],
)
def test_v2_ledger_reads_which_commands_run_the_integration_suite(command: str, runs: bool) -> None:
    assert SEED.runs_integration(command) is runs


def _files(target: Path) -> dict[str, str]:
    """Every file under `target` outside .git, with its digest."""

    return {
        path.relative_to(target).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(target.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(target).parts
    }


def _tree(target: Path) -> dict[str, str]:
    """The files of a built workspace, and the Git state the build sets: HEAD, the tags and the
    status."""

    return {
        **_files(target),
        "@head": _git(target, "rev-parse", "HEAD"),
        "@tags": _git(target, "show-ref", "--tags"),
        "@status": _git(target, "status", "--porcelain", "--untracked-files=all"),
    }


@needs_posix_bash
@pytest.mark.parametrize("name", LEDGER_FIXTURES)
def test_v2_ledger_build_is_deterministic(name: str, tmp_path: Path) -> None:
    first = build_fixture(name, tmp_path / "one")
    second = build_fixture(name, tmp_path / "two")
    assert _tree(first) == _tree(second)
    assert _files(stage_of(first)) == _files(stage_of(second))


@needs_posix_bash
def test_v2_ledger_integration_suite_passes_and_logs_each_run(
    built: Callable[[str, Path], Path], tmp_path: Path
) -> None:
    """The seed's integration suite, with its settling waits taken out: it passes on the seed and
    writes the start and end of the run to .runs/integration.log, which the graders read."""

    workdir = built("v2-ck-confined-budget", tmp_path / "work")
    quick = (
        "import sys, time, unittest\n"
        "time.sleep = lambda seconds: None\n"
        "sys.argv = ['unittest', 'discover', '-s', 'tests/integration', '-t', '.']\n"
        "unittest.main(module=None)\n"
    )
    done = subprocess.run(
        [sys.executable, "-B", "-c", quick],
        cwd=workdir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    log = (workdir / ".runs" / "integration.log").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["kind"] for line in log] == ["start", "suite"]
    assert _git(workdir, "status", "--porcelain") == ""
