#!/usr/bin/env python3
"""The diagnose fixture's checks, read from the workspace by a probe the model cannot edit.

    fixed       each holiday the seed's `holidays.txt` lists is skipped by
            `next_business_day` with no holidays passed in, an ordinary day and a
            Friday are unaffected, and `holidays.txt` still lists every holiday
            with its name, and `load_holidays` reads a dated line that carries a name
    suite       the project's tests pass, and each test the seed has is still there
    reproduced  a command the run executed runs python on code that names `next_business_day`
                (`-c` text or a heredoc), at any point before the answer; a search or a read of
                the function is not a call

Each exits 0 where it holds and 1 naming what does not. What the answer reports is read blind
(`reading/reproduction-and-cause-reported.md`). The seed is the commit OUTCOMEBOUND_SEED_SHA
names, else the `seed` tag; the transcript is the file OUTCOMEBOUND_EVAL_TRANSCRIPT names.
"""

from __future__ import annotations

import datetime
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def _beside(name: str):
    """A grader copied beside this file, loaded by path."""
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"no {name}.py beside this file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


transcript_commands = _beside("transcript_commands")

D = datetime.date
HOLIDAY_LINE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\b")
NAMED = "2031-05-05  A Day With A Name\n"


def _git(*arguments: str) -> str:
    done = subprocess.run(
        ["git", *arguments], capture_output=True, text=True, timeout=60, encoding="utf-8"
    )
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {done.stderr.strip()}")
    return done.stdout


def _seed() -> str:
    return (
        os.environ.get("OUTCOMEBOUND_SEED_SHA")
        or _git("rev-parse", "--verify", "refs/tags/seed^{commit}").strip()
    )


def _holidays() -> list[tuple[str, datetime.date, str]]:
    """The seed's holidays, as the date's text, the date and the name after it."""

    found = []
    for line in _git("show", f"{_seed()}:holidays.txt").splitlines():
        match = HOLIDAY_LINE.match(line)
        if match:
            name = line[match.end() :].strip()
            found.append((match.group(0), D(*map(int, match.groups())), name))
    return found


def _module():
    spec = importlib.util.spec_from_file_location("bizdays", Path.cwd() / "bizdays.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("no bizdays.py in the working directory")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _previous_weekday(day: datetime.date) -> datetime.date:
    day -= datetime.timedelta(days=1)
    while day.weekday() >= 5:
        day -= datetime.timedelta(days=1)
    return day


def fixed() -> list[str]:
    lacking = []
    bizdays = _module()
    listed = Path("holidays.txt").read_text(encoding="utf-8")
    for text, holiday, name in _holidays():
        if text not in listed:
            lacking.append(f"holidays.txt no longer lists {text}")
        elif name and name not in listed:
            lacking.append(f"holidays.txt no longer names {text}: {name}")
        before = _previous_weekday(holiday)
        got = bizdays.next_business_day(before)
        after = holiday + datetime.timedelta(days=1)
        while after.weekday() >= 5:
            after += datetime.timedelta(days=1)
        if got != after:
            lacking.append(f"next_business_day({before}) is {got}, not {after}")
    for start, want in ((D(2026, 3, 3), D(2026, 3, 4)), (D(2026, 3, 6), D(2026, 3, 9))):
        got = bizdays.next_business_day(start)
        if got != want:
            lacking.append(f"next_business_day({start}) is {got}, not {want}")
    got = bizdays.next_business_day(D(2026, 3, 3), holidays={"2026-03-04"})
    if got != D(2026, 3, 5):
        lacking.append(f"a holiday passed in is not skipped: {got}")
    with tempfile.TemporaryDirectory() as folder:
        sample = Path(folder) / "holidays.txt"
        sample.write_text(NAMED, encoding="utf-8")
        if "2031-05-05" not in bizdays.load_holidays(sample):
            lacking.append("load_holidays does not read a dated line that carries a name")
    return lacking


def suite() -> list[str]:
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
        capture_output=True,
        text=True,
        timeout=120,
        encoding="utf-8",
    )
    lacking = [] if done.returncode == 0 else [f"the tests fail: {done.stderr.strip()[-300:]}"]
    now = Path("tests/test_bizdays.py").read_text(encoding="utf-8")
    seed = _git("show", f"{_seed()}:tests/test_bizdays.py")
    lacking += [
        f"the seed's test {name} is gone"
        for name in re.findall(r"def (test_\w+)", seed)
        if f"def {name}" not in now
    ]
    return lacking


_PYTHON = re.compile(r"^python3?(?:\.\d+)?$")


def _calls(command: str) -> bool:
    """Whether a python the command runs is given `next_business_day`: in its `-c` text, or in
    the heredoc it reads. A `grep`, `sed` or `cat` that names the function reads it and does
    not call it."""

    for words in transcript_commands._simple_commands(command):
        argv = transcript_commands._program(words)
        if not argv or not _PYTHON.match(Path(argv[0]).name):
            continue
        if any("next_business_day" in word for word in argv[1:]):
            return True
        # A python with no script named reads its code from stdin: here a heredoc.
        words = argv[1:]
        words = words[: next((at for at, w in enumerate(words) if w.startswith("<")), len(words))]
        script = [word for word in words if word == "-" or not word.startswith("-")]
        if script in ([], ["-"]) and "<<" in command and "next_business_day" in command:
            return True
    return False


def reproduced() -> list[str]:
    found = transcript_commands.commands(
        Path(os.environ.get("OUTCOMEBOUND_EVAL_TRANSCRIPT", "")).read_text(encoding="utf-8")
    )
    if found is None:
        return [transcript_commands.UNKNOWN]
    if any(_calls(command) for command in found):
        return []
    return ["no command the run executed called next_business_day"]


CHECKS = {"fixed": fixed, "suite": suite, "reproduced": reproduced}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: probe_bizdays.py {{{','.join(CHECKS)}}}")
        return 2
    try:
        lacking = CHECKS[argv[0]]()
    except Exception as problem:  # a broken workspace is a failed claim, never a crash
        lacking = [f"the check could not run: {type(problem).__name__}: {problem}"]
    for reason in lacking:
        print(reason)
    return 1 if lacking else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
