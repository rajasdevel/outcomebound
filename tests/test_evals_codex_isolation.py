"""A codex call is isolated from the operator's own codex setup, and names its model.

A run sees its fixture and nothing of the operator's: a call ignores the operator's codex
config (whose writable roots and defaults are not the run's), rules and memories.
`workspace-write` keeps `.git` read-only, so a call in a git workspace adds that directory,
and the run can commit. The operator's configured default model need not be the one a run
chose, so every call names the model itself. No test here calls a model: it reads the argv
the runner builds.
"""

import subprocess
from pathlib import Path

from tests.eval_helpers import RUN as run


def _argv(tmp_path: Path, model: str = "gpt-6-sol", git: bool = True) -> tuple[list[str], Path]:
    workspace = tmp_path / model / "workspace"
    workspace.mkdir(parents=True)
    if git:
        subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    return run.codex_command(model, "medium", workspace, tmp_path / "last.md"), workspace


def test_every_call_names_its_model_and_ignores_the_operators_setup(tmp_path: Path) -> None:
    model = "gpt-6-sol"
    argv, _ = _argv(tmp_path, model)
    assert argv[:2] == ["codex", "exec"]
    assert argv[argv.index("-m") + 1] == model
    for flag in ("--ephemeral", "--ignore-user-config", "--ignore-rules"):
        assert flag in argv, flag
    assert argv[argv.index("features.memories=false") - 1] == "-c"


def test_a_call_in_a_git_workspace_may_write_its_git_directory(tmp_path: Path) -> None:
    argv, workspace = _argv(tmp_path)
    assert argv[argv.index("-s") + 1] == "workspace-write"
    assert argv[argv.index("--add-dir") + 1] == str(workspace / ".git")


def test_a_call_without_git_adds_only_the_task_note_directory(tmp_path: Path) -> None:
    argv, workspace = _argv(tmp_path, git=False)
    additions = [argv[i + 1] for i, arg in enumerate(argv) if arg == "--add-dir"]
    assert additions == [str(workspace / ".agents" / "work")]


def test_nested_adoption_writes_are_confined_to_upgrade_owned_roots(tmp_path):
    roots = run.fixture_write_roots("adopt-upgrade", tmp_path)
    assert tmp_path / "target/project/.git" in roots
    assert tmp_path / "target/project/.agents" not in roots
    assert tmp_path / "target/project/.codex" not in roots
    assert all(
        path == tmp_path / "target/project/.git"
        or path.parent == tmp_path / "target/project/.agents/skills"
        for path in roots
    )
    assert run.fixture_write_roots("adopt-inspect", tmp_path) == ()
    current = run.fixture_arm("adopt-upgrade", run.load_arm("current"))
    baseline = run.fixture_arm("adopt-upgrade", run.load_arm("none"))
    subject = ".agents/skills/adopt-outcomebound/SKILL.md"
    assert subject in current.files and subject in current.record()["arm_files"]
    assert subject not in baseline.files
