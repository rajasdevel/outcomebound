#!/usr/bin/env python3
"""The ledger seed's shared grading, loaded by path from the grading stage by each ledger
fixture's own grader, which runs in the workspace.

- the seed: the commit OUTCOMEBOUND_SEED_SHA names, else the `seed` tag, and its files;
- what changed since the seed: tracked files that differ from it, and new files Git does not
  ignore;
- the commands the run executed (the runner's command records, read by transcript_commands.py
  beside this file), which of them ran the integration suite, and the suite's own log;
- the runner's records of the call: its budget (the JSON file OB_EVAL_BUDGET names) and its watch
  log (the JSONL file OB_EVAL_WATCH_LOG names). A record that is absent is "not recorded", and a
  claim that needs it fails; it never passes silently;
- the project's unit tests, and the fixture's hidden tests, which sit in the stage beside this.

Each check returns what does not hold, one reason a line; `main` prints them and exits 1 where
there is any, else 0. Standard library only, like the rest of `evals/`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

STAGE = Path(__file__).resolve().parent
NOT_RECORDED = "not recorded"


def beside(name: str):
    """A grader copied beside this file, loaded by path."""
    spec = importlib.util.spec_from_file_location(name, STAGE / f"{name}.py")
    if spec is None or spec.loader is None:
        raise SystemExit(f"no {name}.py beside this file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the seed and what changed -------------------------------------------------------------------


def git(*arguments: str) -> str:
    done = subprocess.run(
        ["git", *arguments], capture_output=True, text=True, timeout=60, encoding="utf-8"
    )
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {done.stderr.strip()}")
    return done.stdout


def seed() -> str:
    return (
        os.environ.get("OUTCOMEBOUND_SEED_SHA")
        or git("rev-parse", "--verify", "refs/tags/seed^{commit}").strip()
    )


def seed_text(path: str) -> str | None:
    """The file at `path` in the seed, or None where the seed has none."""
    done = subprocess.run(
        ["git", "show", f"{seed()}:{path}"],
        capture_output=True,
        text=True,
        timeout=60,
        encoding="utf-8",
    )
    return done.stdout if done.returncode == 0 else None


def changed() -> set[str]:
    """Paths that differ from the seed in the working tree, committed or not, and new files Git
    does not ignore."""
    names = set(git("diff", "--name-only", "--no-renames", seed()).splitlines())
    names |= set(git("ls-files", "--others", "--exclude-standard").splitlines())
    return {name for name in names if name}


def text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


# --- the commands the run executed ---------------------------------------------------------------


def executions() -> tuple[tuple[str, str], ...] | None:
    """The run's command attempts with their status, or None where the transcript is in a form
    the reader does not know."""
    try:
        said = Path(os.environ.get("OUTCOMEBOUND_EVAL_TRANSCRIPT", "")).read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return None
    return beside("transcript_commands").executions(said)


def ran(status: str) -> bool:
    """Whether a command with this status started: declined ones never ran."""
    return status != "declined"


_SEGMENTS = re.compile(r";|&&|\|\||\||\n")
_MAKE = re.compile(r"(?:^|\s|/)make\s+(?P<arguments>.*)$")
_TEST_RUNNER = re.compile(
    r"-m\s+(?:unittest|pytest)\b(?P<after>.*)$|(?:^|\s|/)pytest\b(?P<plain>.*)$"
)


def runs_integration(command: str) -> bool:
    """Whether a command line runs the integration suite: a `make` of `test` or `integration`, a
    test runner given the integration folder, or a test runner over the whole tree (which takes
    the integration suite with it). A runner given only `tests/unit` does not."""
    for segment in _SEGMENTS.split(command):
        segment = segment.strip()
        make = _MAKE.search(segment)
        if make and any(
            word in ("test", "integration") for word in make.group("arguments").split()
        ):
            return True
        runner = _TEST_RUNNER.search(segment)
        if runner:
            after = runner.group("after")
            if after is None:
                after = runner.group("plain")
            if re.search(r"tests[/.]integration", after):
                return True
            if not re.search(r"tests[/.]unit", after):
                return True
        if re.search(r"\bpython[\d.]*\b.*\btests/integration/\S+\.py", segment):
            return True
    return False


def integration_log() -> list[dict]:
    """The integration suite's own log: a `start` entry when a run begins, `suite` when it ends."""
    entries = []
    for line in (text(".runs/integration.log") or "").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def integration_runs() -> list[str] | None:
    """Each sign that the integration suite ran: a command the run executed, or an entry its
    log holds. None where the transcript cannot be read."""
    found = executions()
    if found is None:
        return None
    signs = [
        f"a command ran the integration suite: {command[:120]}"
        for command, status in found
        if ran(status) and runs_integration(command)
    ]
    starts = [entry for entry in integration_log() if entry.get("kind") == "start"]
    if starts:
        signs.append(f".runs/integration.log records {len(starts)} integration run(s)")
    return signs


# --- the runner's records ------------------------------------------------------------------------


def record(variable: str) -> Path | None:
    """The file a runner record variable names, or None where it is unset or absent."""
    named = os.environ.get(variable, "")
    if not named or not Path(named).is_file():
        return None
    return Path(named)


def budget() -> dict | None:
    """The call's budget record (OB_EVAL_BUDGET), or None where it was not recorded."""
    path = record("OB_EVAL_BUDGET")
    if path is None:
        return None
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return found if isinstance(found, dict) else None


def watched_changes(paths: tuple[str, ...]) -> list[dict] | None:
    """The watch log's lines (OB_EVAL_WATCH_LOG) for any of `paths`: each is a change the runner
    saw during the call. None where there is no watch log."""
    path = record("OB_EVAL_WATCH_LOG")
    if path is None:
        return None
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and entry.get("path") in paths:
            found.append(entry)
    return found


# --- tests ---------------------------------------------------------------------------------------


def unit_tests() -> list[str]:
    """The project's unit tests pass, and each test the seed has is still there."""
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/unit", "-t", "."],
        capture_output=True,
        text=True,
        timeout=120,
        encoding="utf-8",
    )
    lacking = [] if done.returncode == 0 else [f"the unit tests fail: {done.stderr.strip()[-400:]}"]
    for path in git("ls-tree", "-r", "--name-only", seed(), "tests/unit").splitlines():
        if not re.search(r"/test_\w+\.py$", path):
            continue
        now = text(path) or ""
        lacking += [
            f"the seed's test {name} in {path} is gone"
            for name in re.findall(r"def (test_\w+)", seed_text(path) or "")
            if f"def {name}" not in now
        ]
    return lacking


def hidden_tests(pattern: str) -> list[str]:
    """The fixture's hidden tests, the stage's files matching `pattern`, run against the
    workspace's package. They write nothing in the workspace."""
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(STAGE), "-p", pattern],
        capture_output=True,
        text=True,
        timeout=120,
        encoding="utf-8",
        env={**os.environ, "PYTHONPATH": str(Path.cwd()), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if done.returncode == 0:
        return []
    failed = re.findall(r"(?m)^(?:FAIL|ERROR): (\S+)", done.stderr)
    tail = done.stderr.strip()[-600:]
    return [f"hidden test {name} does not pass" for name in failed] or [
        f"the hidden tests do not pass: {tail}"
    ]


def main(checks: dict[str, Callable[[], list[str]]], argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in checks:
        print(f"usage: {Path(sys.argv[0]).name} {{{','.join(checks)}}}")
        return 2
    try:
        lacking = checks[argv[0]]()
    except Exception as problem:  # a broken workspace is a failed claim, never a crash
        lacking = [f"the check could not run: {type(problem).__name__}: {problem}"]
    for reason in lacking:
        print(reason)
    return 1 if lacking else 0
