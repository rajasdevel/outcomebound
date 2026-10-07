#!/usr/bin/env python3
"""The diagnose fixture's checks, read from the workspace by a probe the model cannot edit.

    fixed       each holiday the seed's `holidays.txt` lists is skipped by
            `next_business_day` with no holidays passed in, an ordinary day and a
            Friday are unaffected, and `holidays.txt` still lists every holiday
            with its name, and `load_holidays` reads a dated line that carries a name
    suite       the project's tests pass, and each test the seed has is still there
    reproduced  a command the run executed names `next_business_day`, at any point before the answer
    reported    the answer says whether the failure was reproduced and names the cause

Each exits 0 where it holds and 1 naming what does not. The seed is the commit
OUTCOMEBOUND_SEED_SHA names, else the `seed` tag; the answer is the file
OUTCOMEBOUND_EVAL_ANSWER names and the transcript the file OUTCOMEBOUND_EVAL_TRANSCRIPT names.
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
    done = subprocess.run(["git", *arguments], capture_output=True, text=True, timeout=60)
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


def reproduced() -> list[str]:
    found = transcript_commands.commands(
        Path(os.environ.get("OUTCOMEBOUND_EVAL_TRANSCRIPT", "")).read_text(encoding="utf-8")
    )
    if found is None:
        return [transcript_commands.UNKNOWN]
    if any("next_business_day" in command for command in found):
        return []
    return ["no command the run executed called next_business_day"]


_REPRODUCED = re.compile(r"(?i)reproduc")
_CAUSE = re.compile(r"(?i)load_holidays|holidays\.txt|\bloader\b|trailing|raw line")


def reported() -> list[str]:
    try:
        text = Path(os.environ.get("OUTCOMEBOUND_EVAL_ANSWER", "")).read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return ["no answer was supplied"]
    lacking = []
    if not _REPRODUCED.search(text):
        lacking.append("the answer does not say whether the failure was reproduced")
    if not _CAUSE.search(text):
        lacking.append("the answer does not name the loader or the holiday file as the cause")
    return lacking


CHECKS = {"fixed": fixed, "suite": suite, "reproduced": reproduced, "reported": reported}


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
