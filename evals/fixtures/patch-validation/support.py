"""Shared construction and mechanical checks for the three bounded research trials.

No function calls a model. Graders remain in the source checkout; submitted tests run
in disposable copies against source-controlled implementations.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent
ROOT = FIXTURES.parent.parent
ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "OutcomeBound eval",
    "GIT_COMMITTER_NAME": "OutcomeBound eval",
    "GIT_AUTHOR_EMAIL": "eval@example.invalid",
    "GIT_COMMITTER_EMAIL": "eval@example.invalid",
    "GIT_AUTHOR_DATE": "2026-10-09T12:00:00+0000",
    "GIT_COMMITTER_DATE": "2026-10-09T12:00:00+0000",
}


def git(target: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=target,
        env=ENV,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout


def build(target: Path, files: dict[str, str]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
    subprocess.run(
        ["bash", str(FIXTURES / "core-skill.sh"), str(ROOT), "AGENTS.md"],
        cwd=target,
        env=ENV,
        check=True,
        capture_output=True,
        timeout=30,
    )
    git(target, "init", "-q", ".")
    git(target, "config", "user.email", "eval@example.invalid")
    git(target, "config", "user.name", "OutcomeBound eval")
    git(target, "config", "commit.gpgsign", "false")
    for sample in (target / ".git/hooks").glob("*.sample"):
        sample.unlink()
    (target / ".git/info/exclude").write_text("__pycache__/\n", encoding="utf-8")
    git(target, "add", "-A")
    git(target, "commit", "-qm", "Seed bounded research trial")
    git(target, "tag", "seed")
    (target / ".git/COMMIT_EDITMSG").unlink(missing_ok=True)
    print("fixture ready: " + str(target))


def scope(allowed: list[str]) -> list[str]:
    target = Path.cwd()
    revision = (
        os.environ.get("OUTCOMEBOUND_SEED_SHA") or git(target, "rev-parse", "seed^{commit}").strip()
    )
    command = [
        sys.executable,
        "-B",
        str(ROOT / "evals/graders/scope_walk.py"),
        "--seed",
        revision,
        "--suppressed",
    ]
    for path in [*allowed, ".agents/work/*"]:
        command += ["--allow", path]
    done = subprocess.run(command, cwd=target, env=ENV, capture_output=True, text=True, timeout=60)
    if done.returncode:
        return ["UNVERIFIED content walk did not complete: " + done.stderr]
    problems = [line for line in done.stdout.splitlines() if line.startswith("PATH ")]
    if git(target, "rev-parse", "HEAD").strip() != revision:
        problems.append("HEAD changed")
    if git(target, "diff", "--cached", "--name-only").strip():
        problems.append("index changed")
    return problems


def inputs() -> list[str]:
    problems = []
    for key in ("OUTCOMEBOUND_EVAL_TRANSCRIPT", "OUTCOMEBOUND_EVAL_ANSWER"):
        path = Path(os.environ.get(key, ""))
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            problems.append("UNVERIFIED missing readable " + key)
    return problems


DRIVER = """
import copy, importlib, inspect, json, unittest
module = importlib.import_module(MODULE_NAME)
calls = []
active = []
for name in FUNCTION_NAMES:
    original = getattr(module, name)
    signature = inspect.signature(original)
    def observed(*args, _name=name, _original=original, _signature=signature, **kwargs):
        call = {"test": active[0] if active else None, "function": _name,
                "args": copy.deepcopy(args), "kwargs": copy.deepcopy(kwargs),
                "arguments": copy.deepcopy(dict(_signature.bind(*args, **kwargs).arguments))}
        try:
            result = _original(*args, **kwargs)
        except Exception as problem:
            call["exception"] = type(problem).__name__
            calls.append(call)
            raise
        call["result"] = copy.deepcopy(result)
        calls.append(call)
        return result
    setattr(module, name, observed)
class Result(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.passed = []
        self.failure_parents = []
        self.error_parents = []
    def startTest(self, test):
        active[:] = [test.id()]
        super().startTest(test)
    def addSuccess(self, test):
        self.passed.append(test.id())
        super().addSuccess(test)
    def addFailure(self, test, error):
        self.failure_parents.append(test.id())
        super().addFailure(test, error)
    def addError(self, test, error):
        self.error_parents.append(test.id())
        super().addError(test, error)
    def addSubTest(self, test, subtest, error):
        # Public unittest callback supplies the parent even for nested subtests.
        if error is not None:
            parents = (self.failure_parents if issubclass(error[0], test.failureException)
                       else self.error_parents)
            parents.append(test.id())
        super().addSubTest(test, subtest, error)
suite = unittest.defaultTestLoader.discover(".", pattern=TEST_FILE)
result = Result()
suite.run(result)
print("OB_TRIAL_OUTCOME=" + json.dumps({
    "count": result.testsRun, "passed": result.passed,
    "failures": result.failure_parents, "errors": result.error_parents,
    "failure_cases": [test.id() for test, trace in result.failures],
    "error_cases": [test.id() for test, trace in result.errors], "calls": calls,
}, sort_keys=True))
"""


def run_tests(test: Path, implementation: str, module: str, functions: list[str]) -> dict:
    with tempfile.TemporaryDirectory(prefix="ob-research-test-") as directory:
        target = Path(directory)
        shutil.copyfile(test, target / test.name)
        (target / (module + ".py")).write_text(implementation, encoding="utf-8")
        script = (
            "MODULE_NAME = " + repr(module) + "\n"
            "FUNCTION_NAMES = " + repr(functions) + "\n"
            "TEST_FILE = " + repr(test.name) + "\n" + DRIVER
        )
        done = subprocess.run(
            [sys.executable, "-B", "-c", script],
            cwd=target,
            env=ENV,
            capture_output=True,
            text=True,
            timeout=30,
        )
    lines = [line for line in done.stdout.splitlines() if line.startswith("OB_TRIAL_OUTCOME=")]
    if done.returncode or len(lines) != 1:
        raise ValueError("test driver did not return one outcome: " + done.stderr)
    return json.loads(lines[0].split("=", 1)[1])


def report(problems: list[str]) -> int:
    for problem in problems:
        print(problem)
    return int(bool(problems))
