"""Fixture construction and grading mechanics shared by no-model eval tests."""

from __future__ import annotations

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
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "evals" / "fixtures"
HERMETIC_GIT = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
GRADER_GIT = {**HERMETIC_GIT, "GIT_NO_REPLACE_OBJECTS": "1", "GIT_GRAFT_FILE": os.devnull}


def load(name: str, relative: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None, relative
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN = load("eval_run", "evals/run.py")


def copy_fixture_sources(base: Path, *, history: bool = False) -> Path:
    """Copy fixture sources and setup inputs, with no links to the checkout."""

    base = base.resolve()
    if history:
        _run_checked(
            ["git", "clone", "--quiet", "--no-hardlinks", "--no-checkout", str(ROOT), str(base)]
        )
    ignore = shutil.ignore_patterns("__pycache__")
    for name in ("fixtures", "graders", "stubs"):
        shutil.copytree(ROOT / "evals" / name, base / "evals" / name, ignore=ignore)
    shutil.copy2(ROOT / "evals/session_protocol.py", base / "evals/session_protocol.py")
    for name in (
        "skills",
        "templates",
        "scripts",
        "outcomebound_tools",
        "schemas",
        "adapters",
        "fragments",
        "kits",
    ):
        shutil.copytree(ROOT / name, base / name, ignore=ignore)
    for name in ("VERSION", "OutcomeBound.md"):
        shutil.copy2(ROOT / name, base / name)
    return base / "evals/fixtures"


TIMEOUT = 120


def _run_checked(command: list[str], **options: Any) -> None:
    """A command that must succeed, within `TIMEOUT` seconds, so a hung setup fails the test
    instead of the job. A failure raises `CalledProcessError` as `check=True` does, after it
    prints the command's own output, which pytest shows with the failure."""

    done = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=TIMEOUT,
        **options,
    )
    if done.returncode != 0:
        print(f"{command} exited {done.returncode}:\n{done.stdout}{done.stderr}", file=sys.stderr)
        raise subprocess.CalledProcessError(done.returncode, command, done.stdout, done.stderr)


def stage_of(target: Path) -> Path:
    """The grading stage of the workspace `target`: a folder beside it, as the runner makes one
    outside the workspace, that the fixture's setup writes its graders to."""

    return target.with_name(target.name + ".stage")


def run_setup(name: str, target: Path, env: dict[str, str]) -> Path:
    """The fixture's `setup.sh` run in `target` under `env`, with its graders in
    `stage_of(target)`, as the runner runs it."""

    stage_of(target).mkdir(parents=True, exist_ok=True)
    _run_checked(
        ["bash", str(FIXTURES / name / "setup.sh"), str(target), str(stage_of(target))], env=env
    )
    return target


def build_fixture(name: str, target: Path, arm: str | None = None) -> Path:
    """The fixture as its setup builds it in `target`, with its graders in `stage_of(target)`."""

    return run_setup(
        name, target, {**RUN.fixture_setup_env(), **({"OB_EVAL_ARM": arm} if arm else {})}
    )


def copy_built(source: Path, target: Path) -> Path:
    """A copy of a built workspace and of its grading stage."""

    shutil.copytree(source, target, symlinks=True)
    shutil.copytree(stage_of(source), stage_of(target), symlinks=True)
    return target


def act(target: Path, script: str) -> None:
    _run_checked(["bash", "-c", script], cwd=str(target), env={**os.environ, **HERMETIC_GIT})


def transcript(workdir: Path, *commands: str, final: str = "Done.") -> str:
    """Synthetic records at the same structured boundary the real runners produce."""
    return json.dumps(
        {
            "format": "outcomebound-command-events-v1",
            "commands": [[command, "succeeded", str(workdir)] for command in commands],
            "answer": final,
        }
    )


def plan(name: str) -> dict:
    return json.loads((FIXTURES / name / "post.plan.json").read_text(encoding="utf-8"))


def seed(target: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "refs/tags/seed^{commit}"],
        cwd=str(target),
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        env={**os.environ, **HERMETIC_GIT},
        encoding="utf-8",
    ).stdout.strip()


def grade(
    target: Path, name: str, said: str, answer: str, *, eval_dir: Path | None = None
) -> dict[str, str]:
    """Grade one fixture in a fresh directory without changing the caller's environment."""
    grading = Path(tempfile.mkdtemp(prefix="grading-", dir=target.parent))
    copied_plan = grading / "post.plan.json"
    copied_plan.write_bytes((FIXTURES / name / "post.plan.json").read_bytes())
    (grading / "transcript.txt").write_text(said, encoding="utf-8")
    (grading / "answer.md").write_text(answer, encoding="utf-8")
    revision = seed(target)
    env = {**os.environ, **GRADER_GIT, "PYTHONPATH": str(ROOT)}
    # As the runner runs a plan: the graders are in the grading stage, outside the workspace.
    env["OUTCOMEBOUND_GRADER_DIR"] = str(stage_of(target))
    env.pop("OUTCOMEBOUND_EVAL_DIR", None)
    env.pop("OUTCOMEBOUND_SEED_SHA", None)
    if eval_dir is not None:
        env["OUTCOMEBOUND_EVAL_DIR"] = str(eval_dir)
    if revision:
        env["OUTCOMEBOUND_SEED_SHA"] = revision
    env.update(
        OUTCOMEBOUND_EVAL_TRANSCRIPT=str(grading / "transcript.txt"),
        OUTCOMEBOUND_EVAL_ANSWER=str(grading / "answer.md"),
    )
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "outcomebound_tools.validation",
            str(copied_plan),
            "--cwd",
            str(target),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        timeout=TIMEOUT,
        encoding="utf-8",
    )
    verdicts = {
        found[2]: found[1]
        for found in re.finditer(r"(?m)^(PASS|FAIL|UNVERIFIED) (\S+) \[", done.stdout)
    }
    verdicts["_output"] = done.stdout + done.stderr
    verdicts["_grading_dir"] = str(grading)
    return verdicts
