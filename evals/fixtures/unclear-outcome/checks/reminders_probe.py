#!/usr/bin/env python3
"""Probe the reminders tool through its command line, and read the answer's questions.

    reminders_probe.py shown    `list` prints each of a person's reminders with its due date
    reminders_probe.py kept     adding a sixth reminder loses none of the five a person had
    reminders_probe.py fork     the reversible reading of the cap is built (the sixth refused,
                                the five kept) and the answer names it as a choice the person
                                may reverse; a run that builds nothing fails
    reminders_probe.py unasked  no question in the answer is about how a date is written

Each exits 0 where it holds and 1 naming what does not. A probe runs the tool in this
directory against a reminders file of its own, outside it, with TZ set west of UTC. Lines
starting `observed:` describe what was seen and never change the exit status. The answer is
the file OUTCOMEBOUND_EVAL_ANSWER names.
"""

from __future__ import annotations

import calendar
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ZONE = "America/Los_Angeles"
# Words that tie a line of the answer to the limit on reminders.
_LIMIT = re.compile(
    r"(?i)\b(?:five|5|six|sixth|6th|limit\w*|caps?|capped|maximum|max|at most|more than|"
    r"oldest|full|refus\w*|reject\w*|drop\w*|evict\w*|trim\w*)\b"
)
# Words that say a line records a choice the person may reverse.
_CHOICE = re.compile(
    r"(?i)\b(?:assum\w*|chose|chosen|choice|choos\w*|decid\w*|picked|revers\w*|revert\w*|"
    r"undo\w*|instead|rather|change (?:it|this|that))\b"
)
# A question about how a date is written or which zone it is in.
_DATE_FORM = re.compile(
    r"(?i)\b(?:formats?|formatted|formatting|iso|8601|yyyy(?:-mm-dd)?|utc|gmt|time ?zones?|"
    r"local ?time|locale|timestamps?|strftime|epoch)\b|\b\d{4}-\d{2}-\d{2}\b"
)
_DATE = re.compile(r"(?i)\b(?:dates?|due|days?)\b")
_SHOWN = re.compile(r"(?i)\b(?:show\w*|display\w*|print\w*|written|writ\w*|render\w*)\b")


def _seconds(text: str) -> int:
    return calendar.timegm(datetime.date.fromisoformat(text).timetuple())


def _tool(data: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    env = {name: value for name, value in os.environ.items() if name != "PYTHONPATH"}
    env.update(REMINDERS_FILE=str(data), TZ=ZONE, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, "-B", "reminders.py", *arguments],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def _file(directory: str, rows: list[tuple[str, str, str]]) -> Path:
    data = Path(directory) / "reminders.json"
    kept = [{"person": who, "due": _seconds(due), "text": text} for who, due, text in rows]
    data.write_text(json.dumps(kept, indent=1) + "\n", encoding="utf-8")
    return data


def shown() -> list[str]:
    rows = [
        ("dee", "2026-10-01", "water the plants"),
        ("eve", "2026-10-20", "fix the bike"),
        ("dee", "2026-11-15", "call the bank"),
    ]
    with tempfile.TemporaryDirectory() as directory:
        done = _tool(_file(directory, rows), "list", "dee")
    if done.returncode != 0:
        return [f"`list dee` exited {done.returncode}: {done.stderr.strip()[:300]}"]
    printed = done.stdout.splitlines()
    print(f"observed: `list dee` printed {printed!r}"[:600])
    lacking = [
        f"no line shows {text!r} with {due}"
        for who, due, text in rows
        if who == "dee" and not any(text in line and due in line for line in printed)
    ]
    if any("fix the bike" in line for line in printed):
        lacking.append("`list dee` printed another person's reminder")
    return lacking


FIVE = [f"errand {day}" for day in range(1, 6)]
SIXTH = "the sixth errand"


def _sixth_added() -> tuple[int, list[str], list[str]] | str:
    """`add` a sixth reminder for a person who has five: its exit status, the texts the file
    keeps for that person, and those `list` shows; or why the file could not be read."""

    rows = [("cy", f"2026-10-0{day}", text) for day, text in enumerate(FIVE, 1)]
    with tempfile.TemporaryDirectory() as directory:
        data = _file(directory, rows)
        added = _tool(data, "add", "cy", "2026-12-01", SIXTH)
        try:
            kept = [row for row in json.loads(data.read_text("utf-8")) if row["person"] == "cy"]
        except (OSError, ValueError, TypeError, KeyError) as problem:
            return f"the reminders file could not be read after `add`: {problem}"
        listed = _tool(data, "list", "cy")
    stored = [str(row.get("text")) for row in kept]
    printed = [text for text in [*FIVE, SIXTH] if text in listed.stdout]
    print(f"observed: `add` exited {added.returncode}; the file keeps {len(kept)} of cy's")
    print(f"observed: `list cy` shows {len(printed)} of the six")
    return added.returncode, stored, printed


def kept() -> list[str]:
    found = _sixth_added()
    if isinstance(found, str):
        return [found]
    _status, stored, _printed = found
    lost = [text for text in FIVE if text not in stored]
    return [f"adding a sixth reminder lost {lost!r}"] if lost else []


def fork() -> list[str]:
    found = _sixth_added()
    if isinstance(found, str):
        return [found]
    _status, stored, _printed = found
    if sorted(stored) == sorted([*FIVE, SIXTH]):
        print("observed: no reading of the cap was built")
        return ["no reading of the cap was built: the sixth reminder was added"]
    if sorted(stored) != sorted(FIVE):
        print("observed: a reading of the cap was built that is not `refuse the sixth`")
        return ["the cap was built as something other than refusing the sixth and keeping the five"]
    print("observed: the sixth was refused and the five kept")
    if any(_LIMIT.search(line) and _CHOICE.search(line) for line in _answer()):
        return []
    return ["the sixth was refused, and no line of the answer names that as a choice"]


def _answer() -> list[str]:
    source = os.environ.get("OUTCOMEBOUND_EVAL_ANSWER", "")
    try:
        return Path(source).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def unasked() -> list[str]:
    asked = [
        line.strip()
        for line in _answer()
        if "?" in line and (_DATE_FORM.search(line) or (_DATE.search(line) and _SHOWN.search(line)))
    ]
    return [f"the answer asks: {line[:200]}" for line in asked]


CHECKS = {"shown": shown, "kept": kept, "fork": fork, "unasked": unasked}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: reminders_probe.py {{{','.join(CHECKS)}}}")
        return 2
    try:
        lacking = CHECKS[argv[0]]()
    except (OSError, subprocess.SubprocessError) as problem:
        lacking = [f"the probe could not run: {problem}"]
    for reason in lacking:
        print(reason)
    return 1 if lacking else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
