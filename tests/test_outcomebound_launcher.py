"""`scripts/outcomebound`: one launcher that runs this checkout's engine from anywhere.

It resolves its own checkout through a symlink, runs each verb's module by path, and
cannot be shadowed by an `outcomebound_tools` package in the caller's directory or on
the caller's PYTHONPATH.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "scripts" / "outcomebound"
VERBS = (
    "adopt",
    "tickets",
    "brief",
    "floor",
    "validation",
    "fragments",
    "discovery",
    "instructions",
    "finish-check",
)


def launch(
    *arguments: str, cwd: Path, launcher: Path = LAUNCHER, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(launcher), *arguments],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_launcher_is_an_executable_posix_script() -> None:
    assert os.access(LAUNCHER, os.X_OK)
    assert LAUNCHER.read_text(encoding="utf-8").startswith("#!/bin/sh\n")


def test_a_symlink_on_another_directory_runs_this_checkout(tmp_path: Path) -> None:
    bin_dir, elsewhere = tmp_path / "bin", tmp_path / "elsewhere"
    bin_dir.mkdir()
    elsewhere.mkdir()
    link = bin_dir / "outcomebound"
    link.symlink_to(LAUNCHER)
    subprocess.run(["git", "init", "-q", str(elsewhere)], check=True)

    home = launch("home", cwd=elsewhere, launcher=link)
    detected = launch("adopt", str(elsewhere), "--detect", cwd=elsewhere, launcher=link)

    assert home.returncode == 0 and Path(home.stdout.strip()) == ROOT
    assert detected.returncode == 0, detected.stderr
    assert detected.stdout.split()[:2] == ["outcomebound", "adopt"]
    assert [path.name for path in elsewhere.iterdir()] == [".git"]


def test_an_engine_in_the_callers_directory_or_path_is_never_run(tmp_path: Path) -> None:
    decoy = tmp_path / "outcomebound_tools"
    decoy.mkdir()
    (decoy / "__init__.py").write_text("", encoding="utf-8")
    for name in ("__main__", "home", "adopt", "fileplan", "fragments", "identity"):
        (decoy / f"{name}.py").write_text("raise SystemExit(99)\n", encoding="utf-8")
    environment = {**os.environ, "PYTHONPATH": str(tmp_path)}
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)

    result = launch("adopt", str(tmp_path), "--detect", cwd=tmp_path, environment=environment)

    assert result.returncode == 0, result.stderr
    assert result.stdout.split()[:2] == ["outcomebound", "adopt"]


# Each verb's own verbs, whose `--help` a reader reaches as `outcomebound <verb> <sub> --help`.
SUBVERBS = {
    "tickets": ("check", "brief"),
    "floor": ("propose", "apply", "check", "baseline", "ratchet", "provision", "remove"),
    "fragments": ("compose", "detect"),
}
HELPS = [(verb,) for verb in VERBS] + [
    (verb, sub) for verb, subs in SUBVERBS.items() for sub in subs
]


@pytest.mark.parametrize("words", HELPS, ids=" ".join)
def test_every_verb_runs_its_module_by_path_and_its_help_names_the_launcher(
    tmp_path: Path, words: tuple[str, ...]
) -> None:
    """A usage line an agent copies runs from any directory: it names `outcomebound <verb>`,
    never `python3 -m outcomebound_tools.<module>`, which fails outside this checkout."""

    result = launch(*words, "--help", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(f"usage: outcomebound {' '.join(words)}"), result.stdout
    assert "outcomebound_tools" not in result.stdout


@pytest.mark.parametrize("arguments", [(), ("frobnicate",), ("-m",)])
def test_an_unknown_verb_lists_the_verbs_and_exits_2(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    result = launch(*arguments, cwd=tmp_path)

    assert result.returncode == 2
    assert all(verb in result.stderr.split() for verb in ("home", *VERBS))


def test_a_command_the_engine_runs_inherits_the_callers_environment(tmp_path: Path) -> None:
    """The engine runs isolated without exporting anything, so a project's own check keeps
    its working directory on `sys.path` and sees the caller's PYTHONPATH."""

    probe = (
        "import os, sys; "
        "sys.exit(0 if not os.environ.get('PYTHONSAFEPATH') "
        "and os.environ.get('PYTHONPATH') == 'callers' and sys.path[0] == '' else 1)"
    )
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "version": 1,
                "cwd": ".",
                "timeout_seconds": 60,
                "claims": [
                    {
                        "name": "environment",
                        "risk": "the launcher leaks its interpreter settings into a check",
                        "kind": "test",
                        "required": True,
                        "command": ["python3", "-c", probe],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONSAFEPATH"} | {
        "PYTHONPATH": "callers"
    }

    result = launch("validation", str(plan), cwd=tmp_path, environment=environment)

    assert result.returncode == 0, result.stdout + result.stderr


RUNNER = ROOT / ".agents" / "tools" / "runner"


def test_the_runner_puts_this_checkouts_engine_first_from_anywhere(tmp_path: Path) -> None:
    """In a worktree, `outcomebound` on PATH may run another checkout: the runner makes every
    command it starts name this one, through OUTCOMEBOUND_HOME and the launcher first on PATH."""

    other = tmp_path / "other-bin"
    other.mkdir()
    (other / "outcomebound").write_text("#!/bin/sh\necho elsewhere\n", encoding="utf-8")
    (other / "outcomebound").chmod(0o755)
    environment = {**os.environ, "PATH": f"{other}{os.pathsep}{os.environ['PATH']}"}

    done = subprocess.run(
        [str(RUNNER), "sh", "-c", 'echo "$OUTCOMEBOUND_HOME"; outcomebound home'],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    bare = subprocess.run([str(RUNNER)], capture_output=True, text=True, check=False)

    assert done.returncode == 0, done.stderr
    assert [Path(line) for line in done.stdout.split()] == [ROOT, ROOT]
    assert bare.returncode == 2 and "usage:" in bare.stderr
