"""The facts-only, facts-only-noskills and bare arms, with no model call.

With `none` and `current` they form a ladder: `bare` has no instruction file at all, `none` the
fixture's own note, `facts-only` that note and adopt's facts-only install, `current` the full
install; `facts-only-noskills` is `facts-only` less its skills. Each is built on a fake fixture
in a temporary folder, under each harness, as a run builds it; every codex is a fake that records
being started, and Claude Code is never started.
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


def _arm(kind: str, kept: tuple[str, ...] = ()) -> Any:
    return RUN.fixture_arms(RUN._parser(), kind, ["ladder-fake"], kept=kept)["ladder-fake"]


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


def test_the_noskills_arm_is_the_facts_only_install_less_its_skills(
    tmp_path: Path, fake: dict[str, Path], harness: str
) -> None:
    """Breaks if the facts-only-noskills arm writes an AGENTS.md or a manifest other than the
    facts-only arm's, leaves a skill file adopt wrote, removes the fixture's own skill, leaves
    the removal outside the seed, or does not record what it removed."""

    only = _arm(RUN.FACTS_ONLY)
    arm = _arm(RUN.FACTS_ONLY_NOSKILLS)
    assert arm.adopted and arm.kernel == "" and arm.launcher == only.launcher
    assert arm.files == {} and (arm.selected, arm.done) == (only.selected, only.done)
    assert arm.kept_skills == () and "skills_kept" not in arm.record()
    with_skills, _protected, _prompt, _extra, _stage = _build(only, tmp_path / "f")
    workdir, _protected, prompt, extra, _stage = _build(arm, tmp_path / "n")
    for name in ("AGENTS.md", ".outcomebound/manifest.json", ".outcomebound/.gitignore"):
        assert (workdir / name).read_bytes() == (with_skills / name).read_bytes(), name
    assert extra["skills_removed"] == sorted(only.files)
    assert not any((workdir / path).exists() for path in only.files)
    skills = workdir / SKILL_PATH[harness]
    left = sorted(p.relative_to(workdir).as_posix() for p in skills.rglob("*") if p.is_file())
    own = [".claude/skills/own/SKILL.md"] if harness == RUN.CLAUDE else []
    assert left == own

    # Every other file is as the facts-only arm left it.
    def tree(root: Path) -> dict[str, bytes]:
        return {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(root).parts
        }

    assert tree(workdir) == {k: v for k, v in tree(with_skills).items() if k not in only.files}
    assert prompt == "Task:\nRecord the release in the changelog.\n"
    assert RUN.facts_only_problems(workdir) == [] and RUN.skill_problems(workdir) == []
    _clean(workdir)
    rows = {row[0]: row for row in RUN.isolation(arm, workdir, prompt, "", None)}
    assert rows["facts-only-install"][1] == "PASS" and rows["no-skill"][1] == "PASS", rows
    assert RUN.bare_record([{"fixture": "ladder-fake", **extra}]) == {
        "skills_removed": {"ladder-fake": sorted(only.files)}
    }
    assert RUN.bare_record([{"fixture": "ladder-fake"}]) == {}
    (workdir / sorted(only.files)[0]).parent.mkdir(parents=True, exist_ok=True)
    (workdir / sorted(only.files)[0]).write_text("x", "utf-8")
    assert RUN.skill_problems(workdir) == [f"skill file present: {sorted(only.files)[0]}"]


KEPT = ("diagnose", "decision-brief")


def test_the_noskills_arm_keeps_the_skills_it_is_told_to(
    tmp_path: Path, fake: dict[str, Path], harness: str
) -> None:
    """Breaks if `--keep-skills` removes a kept skill's file, leaves another skill's, changes a
    kept file's bytes, leaves the kept files unprotected or the removal outside the seed, does not
    record the kept list, or lets the dump rule pass a kept file that is missing, changed or
    another skill's file that is present."""

    only = _arm(RUN.FACTS_ONLY)
    arm = _arm(RUN.FACTS_ONLY_NOSKILLS, KEPT)
    keep = {p for p in only.files if p.split("/")[2] in KEPT}
    assert keep and keep < set(only.files)
    assert arm.kept_skills == KEPT and arm.files == {p: only.files[p] for p in keep}
    assert arm.record()["skills_kept"] == list(KEPT)
    with_skills, _protected, _prompt, _extra, _stage = _build(only, tmp_path / "f")
    workdir, protected, prompt, extra, _stage = _build(arm, tmp_path / "n")
    assert extra["skills_removed"] == sorted(set(only.files) - keep)
    assert all((workdir / p).read_bytes() == only.files[p] for p in keep)
    assert not any((workdir / p).exists() for p in set(only.files) - keep)
    assert keep <= set(protected) and not (set(only.files) - keep) & set(protected)
    for name in ("AGENTS.md", ".outcomebound/manifest.json"):
        assert (workdir / name).read_bytes() == (with_skills / name).read_bytes(), name
    _clean(workdir)
    assert RUN.skill_problems(workdir, KEPT) == [] and RUN.facts_only_problems(workdir) == []
    rows = {row[0]: row for row in RUN.isolation(arm, workdir, prompt, "", None)}
    assert rows["facts-only-install"][1] == "PASS" and rows["no-skill"][1] == "PASS", rows
    assert "diagnose" in rows["no-skill"][2]
    first, other = sorted(keep)[0], sorted(set(only.files) - keep)[0]
    (workdir / first).write_text("changed", "utf-8")
    (workdir / other).parent.mkdir(parents=True, exist_ok=True)
    (workdir / other).write_text("x", "utf-8")
    assert RUN.skill_problems(workdir, KEPT) == [
        f"kept skill file differs: {first}",
        f"skill file present: {other}",
    ]
    (workdir / first).unlink()
    assert f"kept skill file missing: {first}" in RUN.skill_problems(workdir, KEPT)
    assert RUN.skill_problems(workdir) != RUN.skill_problems(workdir, KEPT)


def test_the_kept_list_survives_a_rebuild_from_the_meta(fake: dict[str, Path]) -> None:
    """Breaks if `--rescore` or `--regrade` rebuilds the arm of a run that kept skills without
    its kept list, or gives the list to another arm."""

    meta = {"arm": "x", "arm_kind": RUN.FACTS_ONLY_NOSKILLS, "skills_kept": list(KEPT)}
    arm, why = RUN.rebuilt_arm("ladder-fake", meta)
    assert why == "" and arm is not None and arm.kept_skills == KEPT
    assert RUN.rebuilt_arm("ladder-fake", {**meta, "arm_kind": RUN.FACTS_ONLY})[0].kept_skills == ()


# --- the dry run, the refusals and the loop -----------------------------------------------------


@pytest.mark.parametrize("kind", [RUN.FACTS_ONLY, RUN.FACTS_ONLY_NOSKILLS, RUN.BARE])
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
    rules = {
        RUN.FACTS_ONLY: ["facts-only-install"],
        RUN.FACTS_ONLY_NOSKILLS: ["facts-only-install", "no-skill"],
        RUN.BARE: ["no-instruction-file"],
    }[kind]
    isolation = printed.split("--- isolation ---\n", 1)[1]
    assert all(f"{rule} PASS" in isolation for rule in rules), printed
    assert " FAIL " not in isolation, printed
    assert not fake["calls"].exists(), "the dump started codex"


@pytest.mark.parametrize("kind", [RUN.FACTS_ONLY, RUN.FACTS_ONLY_NOSKILLS, RUN.BARE])
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
    kinds = ("none", RUN.FACTS_ONLY, RUN.FACTS_ONLY_NOSKILLS, RUN.BARE, "current")
    arms = [{"label": kind, "arm": kind} for kind in kinds]
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
    assert started == [] and "cells 5, done 0, to run 5" in printed
    for kind in (RUN.FACTS_ONLY, RUN.FACTS_ONLY_NOSKILLS, RUN.BARE):
        assert f"--arm {kind} --arm-label {kind}" in printed
    (tmp_path / "e.json").write_text("[]", encoding="utf-8")
    plan["arms"] = [{"label": "x", "arm": RUN.FACTS_ONLY, "edits": str(tmp_path / "e.json")}]
    path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(loop.PlanError, match="edits apply to the current arm"):
        loop.read_plan(path, runner)


@pytest.mark.parametrize("tool", [RUN.HARNESS, RUN.CLAUDE])
def test_the_dump_with_kept_skills_passes_its_rules(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fake: dict[str, Path], tool: str
) -> None:
    arguments = ["--dump-arm", "ladder-fake", "--arm", RUN.FACTS_ONLY_NOSKILLS, "--model", "m"]
    arguments += ["--harness", tool, "--keep-skills", ",".join(KEPT)]
    try:
        code = RUN._main([*arguments, "--workspace-root", str(tmp_path / "dumps")])
    finally:
        RUN.set_harness(RUN.HARNESS)
    printed = capsys.readouterr().out
    assert code == 0, printed
    isolation = printed.split("--- isolation ---\n", 1)[1]
    assert "no-skill PASS" in isolation and " FAIL " not in isolation, printed
    assert f"{SKILL_PATH[tool]}/diagnose/SKILL.md" in printed
    assert f"{SKILL_PATH[tool]}/tests-worth-keeping/SKILL.md" not in printed
    assert not fake["calls"].exists(), "the dump started codex"


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (["--arm", RUN.FACTS_ONLY_NOSKILLS, "--keep-skills", "diagnose,nope"], "no skill 'nope'"),
        (["--arm", RUN.FACTS_ONLY_NOSKILLS, "--keep-skills", ""], "no skill ''"),
        (["--arm", RUN.FACTS_ONLY_NOSKILLS, "--keep-skills", "diagnose,diagnose"], "once"),
        (["--arm", RUN.FACTS_ONLY, "--keep-skills", "diagnose"], "keeps skills in the facts-only-"),
        (["--arm", "current", "--keep-skills", "diagnose"], "keeps skills in the facts-only-"),
        (["--arm", RUN.BARE, "--keep-skills", "diagnose"], "keeps skills in the facts-only-"),
    ],
)
def test_a_bad_keep_skills_option_is_refused_before_anything_is_built(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], options: list[str], message: str
) -> None:
    arguments = ["--dump-arm", "small-fix", "--model", "m", *options]
    arguments += ["--workspace-root", str(tmp_path / "dumps")]
    with pytest.raises(SystemExit) as stopped:
        RUN._main(arguments)
    assert stopped.value.code == 2
    assert message in capsys.readouterr().err
    assert not (tmp_path / "dumps").exists()


def test_a_run_that_keeps_skills_needs_a_label_to_tell_it_apart(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = ["--arm", RUN.FACTS_ONLY_NOSKILLS, "--keep-skills", "diagnose", "--model", "m"]
    arguments += ["--fixtures", "small-fix", "--out", str(tmp_path / "out")]
    with pytest.raises(SystemExit) as stopped:
        RUN._main(arguments)
    assert stopped.value.code == 2
    assert "--keep-skills needs --arm-label" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_a_loop_plan_passes_keep_skills_and_refuses_what_run_py_would(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Breaks if a plan's `keep_skills` does not reach run.py as `--keep-skills` with the arm's
    own label, is accepted for another arm or an unknown or repeated skill, is lost from
    LOOP.json, or a plan name can be reused under another list; and if two labelled arms of one
    kind do not get separate result folders."""

    loop = load("ladder_keep_loop", "evals/loop.py")
    runner = loop.load_runner()
    kind = RUN.FACTS_ONLY_NOSKILLS
    arms = [
        {"label": "all-out", "arm": kind},
        {"label": "keep-dd", "arm": kind, "keep_skills": ["diagnose", "decision-brief"]},
        {"label": "keep-rf", "arm": kind, "keep_skills": ["review-findings"]},
    ]
    plan = {
        "name": "keeps",
        "model": "m",
        "results": str(tmp_path / "results"),
        "workspaces": str(tmp_path / "workspaces"),
        "repetitions": [1],
        "fixtures": ["small-fix"],
        "arms": arms,
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    read = loop.read_plan(path, runner)
    words = {cell.arm.label: list(cell.argv) for cell in loop.cells(read)}
    assert "--keep-skills" not in words["all-out"]
    assert (
        words["keep-dd"][words["keep-dd"].index("--keep-skills") + 1] == "diagnose,decision-brief"
    )
    assert words["keep-rf"][words["keep-rf"].index("--keep-skills") + 1] == "review-findings"
    outs = {Path(w[w.index("--out") + 1]) for w in words.values()}
    assert outs == {tmp_path / "results" / "keeps" / f"{n}-r1-small-fix" for n in words}
    labels = {w[w.index("--arm-label") + 1] for w in words.values()}
    assert labels == set(words) and all(w[w.index("--arm") + 1] == kind for w in words.values())
    # run.py accepts each call's options.
    parser = RUN._parser()
    for call in words.values():
        parsed = parser.parse_args(call[2:])
        assert RUN.keep_skills_option(parser, parsed) == tuple(
            parsed.keep_skills.split(",") if parsed.keep_skills else ()
        )
    loop.record(read)
    saved = json.loads((tmp_path / "results" / "keeps" / "LOOP.json").read_text("utf-8"))
    assert [a.get("keep_skills") for a in saved["arms"]] == [
        None, ["diagnose", "decision-brief"], ["review-findings"]
    ]  # fmt: skip
    arms[1]["keep_skills"] = ["diagnose"]
    path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(loop.PlanError, match="records keep_skills"):
        loop.record(loop.read_plan(path, runner))
    for entry, message in (
        ({"label": "x", "arm": "current", "keep_skills": ["diagnose"]}, "applies to the facts"),
        ({"label": "x", "arm": kind, "keep_skills": ["nope"]}, "does not carry"),
        ({"label": "x", "arm": kind, "keep_skills": ["diagnose", "diagnose"]}, "twice"),
    ):
        plan["arms"] = [entry]
        path.write_text(json.dumps(plan), encoding="utf-8")
        with pytest.raises(loop.PlanError, match=message):
            loop.read_plan(path, runner)


# --- the runner's own commits -------------------------------------------------------------------


@pytest.mark.parametrize("kind", [RUN.BARE, RUN.FACTS_ONLY_NOSKILLS])
def test_a_fold_into_the_seed_commits_as_the_eval_on_a_machine_with_no_git_identity(
    tmp_path: Path, fake: dict[str, Path], monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Breaks if a commit the runner makes to fold an install or a removal into the seed takes
    its committer from the machine: here Git may not guess one from the user and host names, as
    on a CI runner or as a container's root, so such a fold fails. The seed keeps its author."""

    for name in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "user.useConfigOnly")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    workdir, _protected, _prompt, _extra, _stage = _build(_arm(kind), tmp_path / "b")
    who = _git(workdir, "log", "-1", "--format=%an <%ae>|%cn <%ce>", "seed")
    assert who == "t <t@example.invalid>|OutcomeBound eval <eval@example.invalid>\n"
