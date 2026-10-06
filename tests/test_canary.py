"""scripts/canary.py on synthetic projects that this checkout's adopt installed: the verdict,
what fails it, that no project path reaches the report, and the record keyed by tree."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.portable import WINDOWS

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "canary.py"
LAUNCHER = ROOT / "scripts" / "outcomebound"
IDENTITY = ("-c", "user.name=Canary", "-c", "user.email=canary@example.test")
# The canary is maintainer tooling: it runs the installed release's sh launcher, and its tests
# stand in for interpreters and floor tools with sh scripts, which Windows cannot start.
pytestmark = pytest.mark.skipif(
    WINDOWS, reason="the canary and its sh stand-ins are POSIX maintainer tooling"
)


def git(where: Path, *args: str) -> None:
    subprocess.run(["git", *IDENTITY, *args], cwd=where, check=True, capture_output=True)


def project(path: Path) -> Path:
    """A Git project with one commit, then OutcomeBound installed by this checkout and committed."""

    path.mkdir()
    git(path, "init", "-q")
    (path / "README.md").write_text("# a synthetic project\n", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "start")
    subprocess.run([str(LAUNCHER), "adopt", str(path)], check=True, capture_output=True)
    git(path, "add", "-A")
    git(path, "commit", "-qm", "adopt")
    return path


@pytest.fixture
def projects(tmp_path: Path) -> list[Path]:
    return [project(tmp_path / "private-alpha"), project(tmp_path / "private-beta")]


def stub(tmp_path: Path, body: str) -> Path:
    """An interpreter for the candidate that runs `body`; it is called as the canary calls a
    Python: `-I -c <code> <checkout> <verb> <project> ...`, so $5 is the verb, $6 the project."""

    path = tmp_path / "stub-python"
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def canary(tmp_path: Path, listed: list[Path], python: Path | str) -> subprocess.CompletedProcess:
    listing = tmp_path / "canary-projects.txt"
    listing.write_text("# private\n" + "".join(f"{p}\n" for p in listed), encoding="utf-8")
    env = {**os.environ, "OB_CANARY_LIST": str(listing)}
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--installed",
            str(LAUNCHER),
            "--python",
            str(python),
            "--records",
            str(tmp_path / "records"),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def assert_no_path(output: str, tmp_path: Path) -> None:
    assert str(tmp_path) not in output
    assert "private-alpha" not in output
    assert "private-beta" not in output


def test_the_same_engine_on_both_sides_passes_with_no_change(
    tmp_path: Path, projects: list[Path]
) -> None:
    done = canary(tmp_path, projects, sys.executable)

    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.count("  no change") == 2
    assert done.stdout.splitlines()[-1].startswith("PASS canary: 0 of 2 project(s) failed")
    assert_no_path(done.stdout + done.stderr, tmp_path)


def test_a_candidate_that_crashes_fails_and_names_no_path(
    tmp_path: Path, projects: list[Path]
) -> None:
    crashing = stub(
        tmp_path,
        "echo 'Traceback (most recent call last):' >&2\n"
        'echo "  File \\"$6/engine.py\\", line 1, in <module>" >&2\n'
        "echo \"PermissionError: [Errno 13] Permission denied: '$6/scratch'\" >&2\n"
        "exit 1",
    )

    done = canary(tmp_path, projects, crashing)

    assert done.returncode == 1, done.stdout + done.stderr
    assert "crash: traceback, PermissionError" in done.stdout
    assert "project 1: FAIL" in done.stdout
    assert "project 2: FAIL" in done.stdout
    assert done.stdout.splitlines()[-1].startswith("FAIL canary: 2 of 2 project(s) failed")
    assert_no_path(done.stdout + done.stderr, tmp_path)


def test_a_candidate_that_writes_into_a_project_fails(tmp_path: Path, projects: list[Path]) -> None:
    writing = stub(
        tmp_path, f'if [ "$5" = adopt ]; then : > "$6/stray.txt"; fi\nexec "{sys.executable}" "$@"'
    )

    done = canary(tmp_path, projects[:1], writing)

    assert done.returncode == 1, done.stdout + done.stderr
    assert "the project's tree changed during the run" in done.stdout
    assert done.stdout.splitlines()[-1].startswith("FAIL canary: 1 of 1 project(s) failed")
    assert_no_path(done.stdout + done.stderr, tmp_path)


def test_an_instructions_check_that_refuses_with_no_report_fails(
    tmp_path: Path, projects: list[Path]
) -> None:
    """The instruction CLI's refusal: exit 2, a reason on stderr, no JSON on stdout."""

    refusing = stub(
        tmp_path,
        'if [ "$5" = instructions ]; then\n'
        '  echo "outcomebound instructions: cannot read $6/.outcomebound/manifest.json" >&2\n'
        "  exit 2\n"
        "fi\n"
        f'exec "{sys.executable}" "$@"',
    )

    done = canary(tmp_path, projects[:1], refusing)

    assert done.returncode == 1, done.stdout + done.stderr
    assert "no report: exit 2, no JSON report" in done.stdout
    assert done.stdout.splitlines()[-1].startswith("FAIL canary: 1 of 1 project(s) failed")
    assert_no_path(done.stdout + done.stderr, tmp_path)


def test_without_a_list_it_reads_unverified(tmp_path: Path) -> None:
    env = {key: value for key, value in os.environ.items() if key != "OB_CANARY_LIST"}

    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--records", str(tmp_path / "records")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 2
    assert done.stdout.startswith("UNVERIFIED canary: no project list (OB_CANARY_LIST)")
    assert not (tmp_path / "records").exists()


def load_canary():
    spec = importlib.util.spec_from_file_location("canary", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Its dataclasses read their annotations through the module's entry in sys.modules.
    sys.modules["canary"] = module
    spec.loader.exec_module(module)
    return module


def test_the_record_is_keyed_by_tree_and_verify_reads_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_canary()
    repo = tmp_path / "candidate"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "engine.py").write_text("one\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "branch tip")
    folder = tmp_path / "records"

    assert module.verify(repo, folder) == 1
    assert "make canary" in capsys.readouterr().out

    (repo / "engine.py").write_text("changed\n", encoding="utf-8")
    module.write_record(repo, folder, "PASS", {})
    assert not folder.exists(), "a record was written for a tree with changes not committed"
    git(repo, "checkout", "--", "engine.py")

    module.write_record(repo, folder, "PASS", {})
    assert module.verify(repo, folder) == 0
    # A squash merge is a new commit with the same tree: the record still holds.
    git(repo, "commit", "-q", "--allow-empty", "-m", "squash merge of the branch")
    assert module.verify(repo, folder) == 0

    (repo / "engine.py").write_text("two\n", encoding="utf-8")
    git(repo, "commit", "-qam", "another tree")
    assert module.verify(repo, folder) == 1
    module.write_record(repo, folder, "FAIL", {})
    assert module.verify(repo, folder) == 1


def instructions(module):
    return next(c for c in module.COMMANDS if c.label == "instructions check")


def report_text(result: str = "UNVERIFIED", **changes: object) -> str:
    finding = {"check": "loading-ancestors", "verdict": "UNVERIFIED"}
    document: dict[str, object] = {"result": result, "findings": [finding], **changes}
    return json.dumps(document)


@pytest.mark.parametrize(
    ("exit", "out", "problem"),
    [
        (2, "", "exit 2, no JSON report"),
        (2, "[]", "not an object"),
        (2, report_text(result="SKIPPED"), "no result PASS, FAIL or UNVERIFIED"),
        (0, report_text(), "result UNVERIFIED disagrees with exit 0"),
        (2, report_text(findings="none"), "no list of findings"),
        (2, report_text(findings=[{"check": "x"}]), "a finding has no check or no verdict"),
    ],
)
def test_an_instructions_report_that_is_missing_or_malformed_fails(
    exit: int, out: str, problem: str
) -> None:
    module = load_canary()
    outcome = module.read(instructions(module), exit, out, "")

    assert outcome.failed() is not None
    assert outcome.failed().startswith("no report: ")
    assert problem in outcome.failed()


def test_a_valid_unverified_report_is_a_verdict_and_no_report_is_a_failure() -> None:
    module = load_canary()
    valid = module.read(instructions(module), 2, report_text(), "")
    missing = module.read(instructions(module), 2, "", "refused\n")

    assert valid.failed() is None
    assert valid.verdict == "UNVERIFIED"
    assert valid.kinds == {"loading-ancestors UNVERIFIED": 1}

    # The installed release with no report and a candidate with a valid one is no failure.
    result = module.Result(1)
    module._compare(result, instructions(module), missing, valid, "python 3")
    assert not result.failures
    # The reverse is a failure of the candidate.
    result = module.Result(1)
    module._compare(result, instructions(module), valid, missing, "python 3")
    assert result.failures == {"no report": 1}
