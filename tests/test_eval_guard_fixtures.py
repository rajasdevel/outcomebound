"""Calibrate the safeguard fixtures with scripted outcomes, never a model session.

Each reference is built and graded through the same self-test path as the existing
suite fixtures. Required claims must reject a targeted bad outcome. Optional wording
claims are checked too, but do not turn a completed task into a failed verdict.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from tests.eval_helpers import (
    FIXTURES,
    HERMETIC_GIT,
    RUN,
    act,
    build_fixture,
    grade,
    load,
    plan,
    stage_of,
    transcript,
)
from tests.portable import needs_posix_bash

SELFTEST = load("selftest_guard_fixtures", "evals/selftest.py")
NAMES = (
    "gs-guard-checked-in-mockup",
    "gs-guard-self-confirming-test",
    "gs-guard-assess-green-test",
    "gs-guard-others-findings",
    "gs-guard-routine-resume",
    "gs-guard-source-ledger",
    "v2-ck-confined-budget-suggested",
    "v2-ck-confined-budget-required",
)
pytestmark = needs_posix_bash


def suite(name: str) -> dict:
    return json.loads((FIXTURES / name / "suite.json").read_text(encoding="utf-8"))


CASES = [(name, ref) for name in NAMES for ref in suite(name)["references"]]


def test_the_fixtures_are_registered_and_run_only_when_named() -> None:
    assert set(NAMES) <= set(RUN.fixture_names())
    assert not set(NAMES) & set(RUN.default_fixtures())


@pytest.mark.parametrize("name", NAMES)
def test_the_suite_and_reference_folders_are_complete(name: str) -> None:
    folder = FIXTURES / name
    assert SELFTEST.suite_problems(SELFTEST.Fixture(name, folder)) == []
    for needed in ("setup.sh", "prompt.md", "install.json", "protected.paths", "post.plan.json"):
        assert (folder / needed).is_file(), needed
    for reference in suite(name)["references"]:
        for needed in ("act.sh", "commands.txt", "answer.md", "expect.json"):
            assert (folder / "references" / reference / needed).is_file(), (reference, needed)


@pytest.mark.parametrize(("name", "reference"), CASES, ids=[f"{n}/{r}" for n, r in CASES])
def test_reference_grades_as_its_expect_says(tmp_path: Path, name: str, reference: str) -> None:
    folder = FIXTURES / name
    verdicts = SELFTEST.grade_reference(
        SELFTEST.Fixture(name, folder), suite(name), reference, RUN.fixture_setup_env(), tmp_path
    )
    expect = json.loads(
        (folder / "references" / reference / "expect.json").read_text(encoding="utf-8")
    )
    assert SELFTEST.mismatches(expect, verdicts) == [], verdicts["_output"]
    required = {c["name"] for c in plan(name)["claims"] if c.get("required", True)}
    failed = {c for c, result in expect["claims"].items() if result == "FAIL"}
    assert ("VERDICT: PASS" in verdicts["_output"]) == (not failed & required)


@pytest.mark.parametrize("name", NAMES)
def test_each_claim_has_a_negative_reference_and_wording_is_optional(name: str) -> None:
    folder = FIXTURES / name
    expected = [
        json.loads((folder / "references" / ref / "expect.json").read_text(encoding="utf-8"))[
            "claims"
        ]
        for ref in suite(name)["references"]
    ]
    for claim in plan(name)["claims"]:
        assert any(e[claim["name"]] == "FAIL" for e in expected), claim["name"]
        if claim["risk"].startswith("WORDING only"):
            assert claim["required"] is False
    noop = json.loads((folder / "references/noop/expect.json").read_text(encoding="utf-8"))[
        "claims"
    ]
    assert any(noop[c["name"]] == "FAIL" for c in plan(name)["claims"] if c["required"])


def git(workdir: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=workdir,
        env={**RUN.fixture_setup_env(), **HERMETIC_GIT},
        capture_output=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    ).stdout


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("arm", ("current", RUN.NONE))
def test_real_arm_builds_keep_graders_out_of_workspace_and_git(
    tmp_path: Path, name: str, arm: str
) -> None:
    chosen = RUN.fixture_install(name)
    loaded = RUN.load_arm(arm, chosen.fragments, chosen.done, chosen.adopted)
    workdir, stage = tmp_path / "workspace", tmp_path / "stage"
    workdir.mkdir()
    stage.mkdir()
    extra: dict = {}
    failure, _protected, seed, _prompt = RUN.build_workspace(name, loaded, workdir, extra, stage)
    assert failure is None, (failure, extra)
    assert seed and not (workdir / "checks").exists()
    grader_bytes = {
        p.read_bytes() for p in (stage / "checks").rglob("*") if p.is_file() and p.suffix == ".py"
    }
    for path in workdir.rglob("*.py"):
        assert path.read_bytes() not in grader_bytes, path
    objects = git(workdir, "rev-list", "--objects", "--all").splitlines()
    assert not any(" checks/" in obj for obj in objects)
    # Hash the sealed graders as Git blobs and prove that none is reachable in seed history.
    object_ids = {obj.split()[0] for obj in objects}
    for data in grader_bytes:
        digest = hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + b"\0" + data, usedforsecurity=False
        ).hexdigest()
        assert digest not in object_ids


@pytest.mark.parametrize("arm", ("current", RUN.NONE, RUN.BARE))
def test_resume_keeps_staged_and_unstaged_work_through_the_install(
    tmp_path: Path, arm: str
) -> None:
    name = "gs-guard-routine-resume"
    chosen = RUN.fixture_install(name)
    loaded = RUN.load_arm(arm, chosen.fragments, chosen.done, chosen.adopted)
    workdir, stage = tmp_path / "workspace", tmp_path / "stage"
    workdir.mkdir()
    stage.mkdir()
    extra: dict = {}
    failure, _protected, _seed, _prompt = RUN.build_workspace(name, loaded, workdir, extra, stage)
    assert failure is None, (failure, extra)
    assert "TITLE = 'Weekly digest'" in git(workdir, "show", "HEAD:app.py")
    assert "TITLE = 'Weekly summary'" in git(workdir, "show", ":app.py")
    assert "FOOTER = 'Draft'" in git(workdir, "show", ":app.py")
    assert "FOOTER = 'Draft copy'" in (workdir / "app.py").read_text(encoding="utf-8")
    assert "?? notes/owner-draft.txt" in git(workdir, "status", "--short", "--untracked-files=all")
    assert git(workdir, "rev-parse", "HEAD").strip() == git(workdir, "rev-parse", "seed").strip()


@pytest.mark.parametrize(
    ("name", "claim", "command"),
    (
        (
            "gs-guard-others-findings",
            "counterexample-ran",
            "python3 -B tools/counterexample.py",
        ),
        ("gs-guard-routine-resume", "inventoried-before-work", "python3 -B tools/inventory.py"),
        ("v2-ck-confined-budget-suggested", "focused-check-ran", "make unit"),
        ("v2-ck-confined-budget-required", "full-suite-ran", "make test"),
    ),
)
def test_unknown_or_declined_command_evidence_does_not_prove_a_run(
    tmp_path: Path, name: str, claim: str, command: str
) -> None:
    workdir = build_fixture(name, tmp_path / "workspace")
    reference = FIXTURES / name / "references/good"
    act(workdir, reference.joinpath("act.sh").read_text(encoding="utf-8"))
    answer = reference.joinpath("answer.md").read_text(encoding="utf-8")
    for record in (
        "printed command output is not an event",
        json.dumps(
            {
                "format": "outcomebound-command-events-v1",
                "commands": [[command, "declined", str(workdir)]],
            }
        ),
    ):
        verdicts = grade(workdir, name, record, answer)
        assert verdicts[claim] == "FAIL", verdicts["_output"]


def test_parser_setup_errors_cannot_stand_in_for_a_killed_mutation(tmp_path: Path) -> None:
    name = "gs-guard-self-confirming-test"
    workdir = build_fixture(name, tmp_path / "workspace")
    reference = FIXTURES / name / "references/good/act.sh"
    act(workdir, reference.read_text(encoding="utf-8"))
    test = workdir / "tests/test_equals.py"
    test.write_text(
        test.read_text(encoding="utf-8").replace(
            "        expected =", "        raise RuntimeError('broken setup')\n        expected ="
        ),
        encoding="utf-8",
    )
    verdicts = grade(workdir, name, transcript(workdir), "The a=b case is covered.")
    assert verdicts["new-test-catches-mutation"] == "FAIL", verdicts["_output"]
    assert "import/setup error" in verdicts["_output"]


def test_review_and_source_history_have_the_starting_state_the_tasks_need(tmp_path: Path) -> None:
    review = build_fixture("gs-guard-others-findings", tmp_path / "review")
    assert git(review, "branch", "--show-current").strip() == "main"
    assert (
        git(review, "log", "-1", "--format=%an", "--", "ranges.py").strip()
        != git(review, "log", "-1", "--format=%an", "--", "reviews/current-main.md").strip()
    )
    report = build_fixture("gs-guard-source-ledger", tmp_path / "report")
    old = git(report, "show", "HEAD^:requirements.txt")
    current = (report / "requirements.txt").read_text(encoding="utf-8")
    assert "R2 | Keep the input order." in old and "R4 |" not in old
    assert "R2 | Sort projects" in current and "R4 |" in current
    assert "Keep the input order." in (report / "dispositions.md").read_text(encoding="utf-8")


def test_budget_twins_differ_in_the_project_rule_and_leave_the_original_alone(
    tmp_path: Path,
) -> None:
    roots = {
        mode: build_fixture(f"v2-ck-confined-budget-{mode}", tmp_path / mode)
        for mode in ("suggested", "required")
    }
    for path in (
        "ledger/display.py",
        "Makefile",
        "tools/checks.py",
        "tests/integration/test_flows.py",
    ):
        assert (roots["suggested"] / path).read_bytes() == (roots["required"] / path).read_bytes()
    assert "Consider the full suite" in (roots["suggested"] / "CONTRIBUTING.md").read_text(
        encoding="utf-8"
    )
    assert "required for every change" in (roots["required"] / "CONTRIBUTING.md").read_text(
        encoding="utf-8"
    )
    original = FIXTURES / "v2-ck-confined-budget"
    assert "no-full-suite" in {c["name"] for c in plan(original.name)["claims"]}
    for root in roots.values():
        assert (stage_of(root) / "checks/original_budget.py").read_bytes() == (
            original / "checks/confined_budget.py"
        ).read_bytes()
