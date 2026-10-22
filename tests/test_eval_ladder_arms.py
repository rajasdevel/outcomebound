"""The facts-only and bare arms, with no model call.

With `none` and `current` they form a ladder: `bare` has no instruction file at all, `none` the
fixture's own note, `facts-only` that note and adopt's facts-only install, `current` the full
install. Each is built on a fake fixture in a temporary folder, under each harness, as a run
builds it; every codex is a fake that records being started, and Claude Code is never started.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.eval_helpers import RUN, load
from tests.portable import needs_posix_bash

pytestmark = needs_posix_bash

NOTE = "# Team notes\n\nStack: Python. `make test` runs the unit tests (a few seconds).\n"
# A fixture with an instruction file in every place a harness reads one, a skill of its own, a
# nested repository with its own note (a task's subject), and a project file under
# `.outcomebound/` (a declared ticket store).
SETUP = """#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
target="${1:?}"; stage="${2:?}"
mkdir -p "$target" "$stage/checks"
cd "$target"
cat > AGENTS.md <<'NOTE'
@NOTE@
NOTE
printf 'test:\\n\\t@true\\ncheck:\\n\\t@true\\n' > Makefile
mkdir -p .claude/rules .claude/skills/own sub/.claude/rules nested .outcomebound
printf 'Claude notes\\n' > CLAUDE.md
printf 'Claude folder notes\\n' > .claude/CLAUDE.md
printf 'Rule\\n' > .claude/rules/style.md
printf -- '---\\nname: own\\ndescription: own\\n---\\nOwn\\n' > .claude/skills/own/SKILL.md
printf 'Override\\n' > sub/AGENTS.override.md
printf 'Rule\\n' > sub/.claude/rules/more.md
printf '{"version": 1, "store": "github"}' > .outcomebound/tickets.json
printf 'Local\\n' > CLAUDE.local.md
printf 'CLAUDE.local.md\\n' > .gitignore
(cd nested && git init -q && printf 'Subject\\n' > AGENTS.md && git add -A \\
  && git -c user.name=t -c user.email=t@example.invalid commit -q -m nested)
git init -q
git add -A 2>/dev/null
git -c user.name=t -c user.email=t@example.invalid commit -q -m seed
git tag seed
""".replace("@NOTE@", NOTE.rstrip("\n"))
PLAN = {
    "version": 1,
    "cwd": ".",
    "timeout_seconds": 60,
    "claims": [
        {"name": "always", "risk": "none", "kind": "static", "required": True, "command": ["true"]}
    ],
}
INSTALL = {"done": ["make check", "make test"], "fragments": ["commands"], "sandbox": "eval"}
REMOVED = [
    ".claude/CLAUDE.md",
    ".claude/rules",
    ".claude/skills",
    "AGENTS.md",
    "CLAUDE.local.md",
    "CLAUDE.md",
    "sub/.claude/rules",
    "sub/AGENTS.override.md",
]
SKILL_PATH = {RUN.HARNESS: ".agents/skills", RUN.CLAUDE: ".claude/skills"}


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """The fake fixture `ladder-fake`, a fake codex first on PATH, a clean Codex home and no
    skill folders outside it."""

    fixture = tmp_path / "evals" / "fixtures" / "ladder-fake"
    fixture.mkdir(parents=True)
    (fixture / "setup.sh").write_text(SETUP, encoding="utf-8")
    (fixture / "prompt.md").write_text("Record the release in the changelog.\n", "utf-8")
    (fixture / "protected.paths").write_text("Makefile\nAGENTS.md\n", encoding="utf-8")
    (fixture / "post.plan.json").write_text(json.dumps(PLAN), encoding="utf-8")
    (fixture / "install.json").write_text(json.dumps(INSTALL), encoding="utf-8")
    calls = tmp_path / "codex-calls.txt"
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    (bindir / "codex").write_text(f'#!/bin/sh\necho "$*" >> "{calls}"\nexit 9\n', "utf-8")
    (bindir / "codex").chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(bindir), os.environ["PATH"]]))
    home = tmp_path / "codex-home"
    (home / "skills" / ".system").mkdir(parents=True)
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setattr(RUN, "OUTSIDE_SKILLS", ())
    monkeypatch.setattr(RUN, "FIXTURES", fixture.parent)
    return {"calls": calls}


@pytest.fixture(params=[RUN.HARNESS, RUN.CLAUDE])
def harness(request: pytest.FixtureRequest) -> Iterator[str]:
    """Each harness the runner installs for, set back to codex after."""

    RUN.set_harness(request.param)
    yield request.param
    RUN.set_harness(RUN.HARNESS)


def _arm(kind: str) -> Any:
    return RUN.fixture_arms(RUN._parser(), kind, ["ladder-fake"])["ladder-fake"]


def _build(arm: Any, root: Path) -> tuple[Path, dict[str, str], str, dict[str, Any], Path]:
    """The fake fixture built under `arm` as a run builds it: its workspace, the protected
    digests, the prompt, the record and the grading stage."""

    workdir, stage = root / "workspace", root / "stage"
    workdir.mkdir(parents=True)
    stage.mkdir()
    extra: dict[str, Any] = {}
    failure, protected, _seed, prompt = RUN.build_workspace(
        "ladder-fake", arm, workdir, extra, stage
    )
    assert failure is None, (failure, extra)
    return workdir, protected, prompt, extra, stage


def _git(workdir: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=workdir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, **RUN.HERMETIC_GIT},
        check=True,
    ).stdout


def _clean(workdir: Path) -> None:
    """No change against the seed: what a grader reads as the model's change is empty."""

    assert _git(workdir, "status", "--porcelain", "--untracked-files=all") == ""
    assert _git(workdir, "rev-parse", "HEAD") == _git(workdir, "rev-parse", "seed^{commit}")


def _block(workdir: Path, block: str) -> str | None:
    from outcomebound_tools import adopt

    found = adopt.block_text((workdir / "AGENTS.md").read_text("utf-8"), block)
    return None if found is None else found.decode("utf-8")


# --- bare ---------------------------------------------------------------------------------------


def test_the_bare_arm_removes_every_instruction_file_into_the_seed(
    tmp_path: Path, fake: dict[str, Path], harness: str
) -> None:
    """Breaks if the bare arm leaves an instruction file, a rules folder or a skill a harness
    could load, removes a nested repository's own note or a project file, adds a kernel, a
    launcher or a file, records the removal other than it happened, or protects a path it
    removed."""

    arm = _arm(RUN.BARE)
    assert (arm.kernel, arm.files, arm.launcher, arm.adopted) == ("", {}, None, False)
    workdir, protected, prompt, extra, _stage = _build(arm, tmp_path / "b")
    assert extra["instructions_removed"] == REMOVED
    assert extra["instructions_kept"] == ["nested/AGENTS.md"]
    assert all(not (workdir / item).exists() for item in REMOVED)
    assert (workdir / "nested" / "AGENTS.md").is_file()
    assert (workdir / ".outcomebound" / "tickets.json").is_file()
    assert (workdir / "Makefile").is_file() and set(protected) == {"Makefile"}
    assert prompt == "Task:\nRecord the release in the changelog.\n"
    _clean(workdir)
    rows = {row[0]: row for row in RUN.isolation(arm, workdir, prompt, "", None)}
    assert rows["no-instruction-file"][1] == "PASS", rows
    assert rows["no-outcomebound-text"][1] == "PASS", rows
    (workdir / ".claude" / "rules").mkdir(parents=True)
    (workdir / ".claude" / "rules" / "late.md").write_text("x\n", encoding="utf-8")
    row = {row[0]: row for row in RUN.isolation(arm, workdir, prompt, "", None)}[
        "no-instruction-file"
    ]
    assert row[1] == "FAIL" and ".claude/rules" in row[2], row


def test_a_bare_workspace_with_no_agent_change_reads_as_no_change_to_the_graders(
    tmp_path: Path, fake: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a scope or diff check counts the bare arm's removal as the model's change: the
    shared engine graders' changed paths against the seed are empty, and a baseline the setup
    recorded loses the lines of the removed files."""

    workdir, _protected, _prompt, _extra, stage = _build(_arm(RUN.BARE), tmp_path / "b")
    (stage / "checks" / "baseline-files").write_text("./AGENTS.md\n./Makefile\n", "utf-8")
    (stage / "checks" / "baseline-hashes").write_text("aa  ./AGENTS.md\nbb  ./Makefile\n", "utf-8")
    RUN.refresh_baseline_hashes(workdir, stage, ("AGENTS.md",))
    assert (stage / "checks" / "baseline-files").read_text("utf-8") == "./Makefile\n"
    assert (stage / "checks" / "baseline-hashes").read_text("utf-8") == "bb  ./Makefile\n"
    seed_sha = RUN.seed_commit(workdir) or ""
    monkeypatch.chdir(workdir)
    monkeypatch.setenv(RUN.SEED_SHA_ENV, seed_sha)
    engine = load("ladder_enginecheck", "evals/fixtures/seeds/engine/checks/enginecheck.py")
    assert engine.changed_paths() == set()
    (workdir / "Makefile").write_text("changed\n", encoding="utf-8")
    assert engine.changed_paths() == {"Makefile"}, "the graders no longer see a change"


def test_a_bare_run_refuses_an_instruction_file_above_its_workspaces(tmp_path: Path) -> None:
    """Breaks if the codex pre-call check stops refusing an instruction file above the
    workspace for the bare arm on a fixture that is not a replica."""

    home, above = tmp_path / "home", tmp_path / "root"
    (home / "skills" / ".system").mkdir(parents=True)
    above.mkdir()
    (tmp_path / "AGENTS.md").write_text("Follow these rules.\n", encoding="utf-8")
    found = [str(tmp_path.resolve() / "AGENTS.md")]
    assert RUN.unclean_reach(["small-fix"], home, above) == []
    assert RUN.unclean_reach(["small-fix"], home, above, bare=True) == found


# --- facts-only ---------------------------------------------------------------------------------


def test_the_facts_only_arm_is_adopts_facts_only_install(
    tmp_path: Path, fake: dict[str, Path], harness: str
) -> None:
    """Breaks if the facts-only arm writes a kernel, a pointer or a fragment file, lacks the
    facts block the current arm writes, puts its skills anywhere but the harness's skill path,
    leaves the install outside the seed, or records other than what it installed."""

    from outcomebound_tools import adopt, facts

    arm = _arm(RUN.FACTS_ONLY)
    assert arm.adopted and arm.kernel == "" and arm.launcher == RUN.REPO / RUN.LAUNCHER
    assert arm.files and all(path.startswith(f"{SKILL_PATH[harness]}/") for path in arm.files)
    workdir, protected, prompt, _extra, _stage = _build(arm, tmp_path / "f")
    assert _block(workdir, adopt.KERNEL) is None and _block(workdir, facts.POINTERS) is None
    assert not (workdir / facts.FRAGMENT_DIR).exists()
    assert RUN.facts_only_problems(workdir) == []
    current, _protected, _prompt, _extra, _stage = _build(_arm("current"), tmp_path / "c")
    # The same facts as the current arm, save Precedence, which in a facts-only install names no
    # OutcomeBound guidance (docs/specs/install/design.md, Facts-only).
    only, full = _block(workdir, facts.FACTS), _block(current, facts.FACTS)
    assert only is not None and full is not None
    assert [line for line in only.splitlines() if not line.startswith("- Precedence:")] == [
        line for line in full.splitlines() if not line.startswith("- Precedence:")
    ]
    assert "OutcomeBound" not in only and "OutcomeBound's" in full
    assert (workdir / "AGENTS.md").read_text("utf-8").endswith(NOTE)
    manifest = json.loads((workdir / ".outcomebound" / "manifest.json").read_text("utf-8"))
    assert RUN.FACTS_ONLY in json.dumps(manifest)
    assert prompt == "Task:\nRecord the release in the changelog.\n"
    record = arm.record()
    assert record["arm_adopted"] and record["arm_done"] == INSTALL["done"]
    assert set(record["arm_files"]) == set(arm.files) <= set(protected)
    _clean(workdir)
    rows = {row[0]: row for row in RUN.isolation(arm, workdir, prompt, "", None)}
    assert rows["facts-only-install"][1] == "PASS", rows
    note = workdir / "AGENTS.md"
    note.write_text(note.read_text("utf-8").replace(NOTE, "- x: read y/SKILL.md\n"), "utf-8")
    assert RUN.facts_only_problems(workdir) == []
    kernel = RUN.kernel("current")
    note.write_text(kernel + "\n\n" + note.read_text("utf-8"), "utf-8")
    assert RUN.facts_only_problems(workdir) == [f"the {adopt.KERNEL} block present"]


# --- the dry run, the refusals and the loop -----------------------------------------------------


@pytest.mark.parametrize("kind", [RUN.FACTS_ONLY, RUN.BARE])
@pytest.mark.parametrize("tool", [RUN.HARNESS, RUN.CLAUDE])
def test_the_dump_builds_each_arm_on_each_harness_and_passes_its_rules(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fake: dict[str, Path], kind: str, tool: str
) -> None:
    arguments = ["--dump-arm", "ladder-fake", "--arm", kind, "--model", "m", "--harness", tool]
    try:
        code = RUN._main([*arguments, "--workspace-root", str(tmp_path / "dumps")])
    finally:
        RUN.set_harness(RUN.HARNESS)
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert f"fixture ladder-fake, arm {kind};" in printed
    rule = "facts-only-install" if kind == RUN.FACTS_ONLY else "no-instruction-file"
    isolation = printed.split("--- isolation ---\n", 1)[1]
    assert f"{rule} PASS" in isolation and " FAIL " not in isolation, printed
    assert not fake["calls"].exists(), "the dump started codex"


@pytest.mark.parametrize("kind", [RUN.FACTS_ONLY, RUN.BARE])
@pytest.mark.parametrize(
    "options",
    [["--drop", "kernel"], ["--add", "kernel"], ["--edits", "e.json", "--arm-label", "x"]],
)
def test_an_element_option_on_a_ladder_arm_is_refused(
    capsys: pytest.CaptureFixture[str], kind: str, options: list[str]
) -> None:
    arguments = ["--dump-arm", "small-fix", "--arm", kind, "--model", "m", *options]
    with pytest.raises(SystemExit) as stopped:
        RUN._main(arguments)
    assert stopped.value.code == 2
    assert f"--arm {kind} takes no --drop, --add or --edits" in capsys.readouterr().err


def test_a_loop_plan_runs_the_ladder_arms_and_refuses_their_edits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Breaks if a loop plan refuses the facts-only or bare arm, passes it to run.py other than
    as `--arm`, or accepts edits for it."""

    loop = load("ladder_loop", "evals/loop.py")
    runner = loop.load_runner()
    arms = [{"label": kind, "arm": kind} for kind in ("none", RUN.FACTS_ONLY, RUN.BARE, "current")]
    plan = {
        "name": "ladder",
        "model": "m",
        "effort": "medium",
        "harness": RUN.CLAUDE,
        "results": str(tmp_path / "results"),
        "workspaces": str(tmp_path / "workspaces"),
        "repetitions": [1],
        "fixtures": ["small-fix"],
        "arms": arms,
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    started: list[Any] = []
    assert loop.main([str(path), "--dry-run"], runner=started.append, module=runner) == 0
    printed = capsys.readouterr().out
    assert started == [] and "cells 4, done 0, to run 4" in printed
    for kind in (RUN.FACTS_ONLY, RUN.BARE):
        assert f"--arm {kind} --arm-label {kind}" in printed
    (tmp_path / "e.json").write_text("[]", encoding="utf-8")
    plan["arms"] = [{"label": "x", "arm": RUN.FACTS_ONLY, "edits": str(tmp_path / "e.json")}]
    path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(loop.PlanError, match="edits apply to the current arm"):
        loop.read_plan(path, runner)
