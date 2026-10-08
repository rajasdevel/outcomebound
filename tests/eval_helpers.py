"""Fixture construction and grading mechanics shared by no-model eval tests."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "evals" / "fixtures"
HERMETIC_GIT = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def load(name: str, relative: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None, relative
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN = load("eval_run", "evals/run.py")


def build_fixture(name: str, target: Path) -> Path:
    subprocess.run(
        ["bash", str(FIXTURES / name / "setup.sh"), str(target)],
        check=True,
        capture_output=True,
        env=RUN.fixture_setup_env(),
    )
    return target


def act(target: Path, script: str) -> None:
    subprocess.run(
        ["bash", "-c", script],
        cwd=str(target),
        check=True,
        capture_output=True,
        env={**os.environ, **HERMETIC_GIT},
    )


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
        env={**os.environ, **HERMETIC_GIT},
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
    env = {**os.environ, **HERMETIC_GIT, "PYTHONPATH": str(ROOT)}
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
    )
    verdicts = {
        found[2]: found[1]
        for found in re.finditer(r"(?m)^(PASS|FAIL|UNVERIFIED) (\S+) \[", done.stdout)
    }
    verdicts["_output"] = done.stdout + done.stderr
    verdicts["_grading_dir"] = str(grading)
    return verdicts
