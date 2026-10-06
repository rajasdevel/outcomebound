"""scripts/canary.py runs `floor check` and `tickets check` where a synthetic project holds a
floor, drafts its claims plan names, or an export; it says why where it does not, keeps the
floor's caches out of the project, and fails a candidate that crashes or changes the tree."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from tests.portable import WINDOWS
from tests.test_canary import assert_no_path, canary, git, instructions, load_canary, project, stub

# The canary is maintainer tooling: it runs the installed release's sh launcher, and its tests
# stand in for interpreters and floor tools with sh scripts, which Windows cannot start.
pytestmark = pytest.mark.skipif(
    WINDOWS, reason="the canary and its sh stand-ins are POSIX maintainer tooling"
)

# A floor tool that keeps its cache as ruff does: in the folder its variable names, else in a
# folder of the tree that ignores itself, which `git status` alone does not show.
TOOL = """#!/bin/sh
[ "$1" = --version ] && { echo "floor-probe 1.0"; exit 0; }
cache="${RUFF_CACHE_DIR:-.ruff_cache}"
mkdir -p "$cache" && echo '*' > "$cache/.gitignore" && : > "$cache/entry"
exit 0
"""
DRAFT = """# Add a probe

## Outcome
The probe reports its version to the operator.

<!-- outcomebound:begin id=ticket v=1 -->
reads:
bounds: probe/
human-only: no
done-when:
- probe-runs
<!-- outcomebound:end id=ticket -->
"""
EXPORT = [
    {
        "data": {
            "repository": {
                "nameWithOwner": "owner/project",
                "issues": {"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}},
            }
        }
    }
]


def floored(path: Path, tool_folder: Path) -> Path:
    """A project with one floor claim, whose tool lives in `tool_folder` (on PATH)."""

    tool = tool_folder / "floor-probe"
    tool_folder.mkdir(exist_ok=True)
    tool.write_text(TOOL, encoding="utf-8")
    tool.chmod(0o755)
    root = project(path)
    claim = {
        "name": "project.probe",
        "mode": "gate",
        "tool": "floor-probe",
        "parser": "exit",
        "argv": ["floor-probe"],
    }
    floor = {"version": 1, "claims": [claim]}
    (root / ".outcomebound" / "floor.json").write_text(json.dumps(floor), encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "floor")
    return root


def ticketed(path: Path, drafts: bool, export: bool) -> Path:
    """A project that declares a ticket store; its claims plan names drafts where `drafts`."""

    root = project(path)
    declaration = {
        "version": 1,
        "store": "github",
        "repo": "owner/project",
        "label": "ob-ticket",
        "human_label": "human-only",
        "request_label": "human-requested",
        "claims": ".outcomebound/ticket-claims.json",
    }
    lint = ["outcomebound", "tickets", "check", ".", "--draft", "drafts/*.md"]
    claims = [{"name": "probe-runs", "risk": "the probe runs", "kind": "test", "command": ["true"]}]
    if drafts:
        claims.append({"name": "drafts-lint", "risk": "drafts", "kind": "static", "command": lint})
        (root / "drafts").mkdir()
        for name in ("add-probe", "add-probe-docs"):
            (root / "drafts" / f"{name}.md").write_text(DRAFT, encoding="utf-8")
    plan = {"version": 1, "cwd": "..", "claims": claims}
    outcomebound = root / ".outcomebound"
    (outcomebound / "tickets.json").write_text(json.dumps(declaration), encoding="utf-8")
    (outcomebound / "ticket-claims.json").write_text(json.dumps(plan), encoding="utf-8")
    if export:
        (root / "issues.json").write_text(json.dumps(EXPORT), encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "tickets")
    return root


def test_a_floor_claim_that_passes_on_both_engines_keeps_its_cache_out_of_the_tree(
    tmp_path: Path, monkeypatch
) -> None:
    tools = tmp_path / "tools"
    root = floored(tmp_path / "private-alpha", tools)
    monkeypatch.setenv("PATH", f"{tools}:{Path(sys.executable).parent}:/usr/bin:/bin")

    done = canary(tmp_path, [root], sys.executable)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "floor check" in next(line for line in done.stdout.splitlines() if "ran:" in line)
    assert "floor check, under python" in done.stdout
    assert re.search(r"floor check, under [^:]+: PASS, [0-9.]+ s \(installed: PASS, ", done.stdout)
    assert "  no change" in done.stdout
    assert not (root / ".ruff_cache").exists()
    assert_no_path(done.stdout + done.stderr, tmp_path)


def test_a_candidate_floor_check_that_crashes_fails(tmp_path: Path, monkeypatch) -> None:
    tools = tmp_path / "tools"
    root = floored(tmp_path / "private-alpha", tools)
    monkeypatch.setenv("PATH", f"{tools}:{Path(sys.executable).parent}:/usr/bin:/bin")
    crashing = stub(
        tmp_path,
        'if [ "$5" = floor ]; then\n'
        "  echo 'Traceback (most recent call last):' >&2\n"
        "  echo \"KeyError: '$7'\" >&2\n"
        "  exit 1\n"
        "fi\n"
        f'exec "{sys.executable}" "$@"',
    )

    done = canary(tmp_path, [root], crashing)

    assert done.returncode == 1, done.stdout + done.stderr
    assert "floor check, under python" in done.stdout
    assert "crash: traceback, KeyError" in done.stdout
    assert done.stdout.splitlines()[-1].startswith("FAIL canary: 1 of 1 project(s) failed")
    assert_no_path(done.stdout + done.stderr, tmp_path)


def test_a_candidate_that_makes_a_folder_git_ignores_in_a_project_fails(tmp_path: Path) -> None:
    """A cache folder that ignores itself, as ruff's does, is no change to `git status`."""

    root = project(tmp_path / "private-alpha")
    writing = stub(
        tmp_path,
        'if [ "$5" = adopt ]; then\n'
        '  mkdir -p "$6/.ruff_cache" && echo "*" > "$6/.ruff_cache/.gitignore"\n'
        "fi\n"
        f'exec "{sys.executable}" "$@"',
    )

    done = canary(tmp_path, [root], writing)

    assert done.returncode == 1, done.stdout + done.stderr
    assert "the project's tree changed during the run under python" in done.stdout
    assert "(the ignored entries changed)" in done.stdout, done.stdout
    assert_no_path(done.stdout + done.stderr, tmp_path)


def test_the_drafts_the_claims_plan_names_and_the_export_are_checked(tmp_path: Path) -> None:
    root = ticketed(tmp_path / "private-alpha", drafts=True, export=True)

    done = canary(tmp_path, [root], sys.executable)

    assert done.returncode == 0, done.stdout + done.stderr
    ran = next(line for line in done.stdout.splitlines() if "ran:" in line)
    assert "tickets check --draft (set 1, 2 file(s))" in ran
    assert "tickets check --input" in ran
    assert "no report" not in done.stdout
    assert "refusal" not in done.stdout
    assert_no_path(done.stdout + done.stderr, tmp_path)


def test_a_candidate_tickets_check_with_no_valid_report_fails(tmp_path: Path) -> None:
    root = ticketed(tmp_path / "private-alpha", drafts=True, export=False)
    refusing = stub(
        tmp_path,
        f'if [ "$5" = tickets ]; then echo "{{}}"; exit 0; fi\nexec "{sys.executable}" "$@"',
    )

    done = canary(tmp_path, [root], refusing)

    assert done.returncode == 1, done.stdout + done.stderr
    assert "tickets check --draft (set 1, 2 file(s)), under python" in done.stdout
    assert "no report: the report has no result PASS, FAIL or UNVERIFIED" in done.stdout


def test_a_project_with_no_floor_and_no_drafts_says_why_each_was_not_run(tmp_path: Path) -> None:
    bare = project(tmp_path / "private-alpha")
    declared = ticketed(tmp_path / "private-beta", drafts=False, export=False)

    done = canary(tmp_path, [bare, declared], sys.executable)

    assert done.returncode == 0, done.stdout + done.stderr
    first, second = done.stdout.split("project 2:")
    assert "floor check: not run, the project has no .outcomebound/floor.json" in first
    assert "tickets check: not run, the project has no .outcomebound/tickets.json" in first
    assert "tickets check --draft: not run, the claims plan names no" in second
    assert "tickets check --input: UNVERIFIED, no readable issues.json" in second
    assert "command(s) not run, each named with why" in done.stdout.splitlines()[-1]
    assert_no_path(done.stdout + done.stderr, tmp_path)


def test_an_installed_engine_that_failed_gives_no_baseline_and_no_comparison() -> None:
    module = load_canary()
    command = instructions(module)
    crashed = module.Outcome(1, crash="traceback, KeyError")
    valid = module.Outcome(0, verdict="PASS", kinds=module.Counter({"x FAIL": 1}))
    result = module.Result(1)

    module._compare(result, command, crashed, valid, "python 3")

    shown = result.shown()
    assert not result.failures
    assert any("no baseline: installed engine failed (crash: traceback" in s for s in shown)
    assert not any("'x FAIL'" in s for s in shown), "a kind was compared with no baseline"
    assert not result.added
