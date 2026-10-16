"""A test waits on a condition, never on the speed of the machine it was written on.

A fixed sleep, a timer that fires after a fixed delay, or today's date in place of a condition
passes on a fast machine and fails first on the hosted Windows runner, which runs this suite
several times more slowly, or on the day a date in the repository passes. Each such call in
`tests/` names why the real time or date is the behaviour under test, with a `real time:` or
`real date:` comment on its line or the line above; any other is a finding.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# A sleep shorter than this is a poll interval inside a loop that waits on a condition.
POLL_SECONDS = 0.5
WAITS = {"time.sleep", "sleep"}
TIMERS = {"threading.Timer", "Timer"}
DATES = {"date.today", "datetime.date.today"}


def findings(path: Path) -> list[str]:
    """Each fixed wait, delayed timer or real-date read in `path` with no reason beside it."""

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    found = []
    calls = [node for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Call)]
    for node in sorted(calls, key=lambda call: call.lineno):
        name = ast.unparse(node.func)
        first = node.args[0] if node.args else None
        if name in WAITS:
            seconds = first.value if isinstance(first, ast.Constant) else None
            if not isinstance(seconds, (int, float)) or seconds < POLL_SECONDS:
                continue
            kind, reason = "a fixed sleep", "real time:"
        elif name in TIMERS:
            kind, reason = "a delayed timer", "real time:"
        elif name in DATES:
            kind, reason = "today's date", "real date:"
        else:
            continue
        nearby = lines[max(node.lineno - 2, 0) : node.lineno]
        if not any(reason in line for line in nearby):
            found.append(f"{path.relative_to(path.parents[1]).as_posix()}:{node.lineno}: {kind}")
    return found


def test_every_fixed_wait_and_real_date_in_the_tests_names_why() -> None:
    found = [line for path in sorted((ROOT / "tests").glob("*.py")) for line in findings(path)]
    assert found == [], "wait on a condition, or say why with `real time:`/`real date:`"


def test_NEGATIVE_CONTROL_a_fixed_sleep_a_timer_and_a_date_read_are_found(tmp_path: Path) -> None:
    folder = tmp_path / "tests"
    folder.mkdir()
    sample = folder / "test_sample.py"
    sample.write_text(
        "import threading, time, datetime\n"
        "time.sleep(2)\n"
        "threading.Timer(0.1, print)\n"
        "datetime.date.today()\n"
        "time.sleep(0.05)\n"
        "# real time: the delay is the behaviour under test\n"
        "time.sleep(1)\n",
        encoding="utf-8",
    )
    assert findings(sample) == [
        "tests/test_sample.py:2: a fixed sleep",
        "tests/test_sample.py:3: a delayed timer",
        "tests/test_sample.py:4: today's date",
    ]
