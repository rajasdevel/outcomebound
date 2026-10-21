"""A codex call is isolated from the operator's own codex setup, and names its model.

A run sees its fixture and nothing of the operator's: a call ignores the operator's codex
config (whose writable roots and defaults are not the run's), rules and memories, and the
account's remote plugins, whose sync made the skill catalog differ between calls.
`workspace-write` keeps `.git` read-only, so a call in a git workspace adds that directory,
and the run can commit. The operator's configured default model need not be the one a run
chose, so every call names the model itself. A call keeps its session, since the model, effort
and working directory it counts for are read from that record. No test here calls a model: it
reads the argv the harness builds.
"""

import subprocess
from pathlib import Path

from tests.eval_helpers import RUN as run


def _argv(
    tmp_path: Path, model: str = "gpt-6-sol", git: bool = True, local_listener: bool = False
) -> tuple[list[str], Path]:
    workspace = tmp_path / model / "workspace"
    workspace.mkdir(parents=True)
    if git:
        subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    argv = run.make_harness().command(
        model, "medium", workspace, tmp_path / "last.md", local_listener=local_listener
    )
    return argv, workspace


def test_every_call_names_its_model_and_ignores_the_operators_setup(tmp_path: Path) -> None:
    model = "gpt-6-sol"
    argv, _ = _argv(tmp_path, model)
    assert argv[:2] == ["codex", "exec"]
    assert argv[argv.index("-m") + 1] == model
    for flag in ("--ignore-user-config", "--ignore-rules"):
        assert flag in argv, flag
    assert "--ephemeral" not in argv, "the call keeps its session: its identity is read from it"
    assert argv[argv.index("features.memories=false") - 1] == "-c"
    assert argv[argv.index("memories.generate_memories=false") - 1] == "-c"
    assert argv[argv.index("memories.use_memories=false") - 1] == "-c"
    assert argv[argv.index("features.remote_plugin=false") - 1] == "-c", "remote plugins vary"


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


def test_a_call_may_bind_a_port_only_where_its_fixture_needs_a_listener(tmp_path: Path) -> None:
    setting = "sandbox_workspace_write.network_access=true"
    default, _ = _argv(tmp_path / "default")
    assert not [arg for arg in default if "network" in arg], "the default sandbox is kept"
    granted, _ = _argv(tmp_path / "granted", local_listener=True)
    assert granted.count(setting) == 1 and granted[granted.index(setting) - 1] == "-c"
    assert granted[granted.index("-s") + 1] == "workspace-write"
    assert len(granted) == len(default) + 2, "the grant adds the one setting and nothing else"
