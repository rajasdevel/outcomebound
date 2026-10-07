#!/usr/bin/env bash
# A business-day helper whose holiday list is never matched: the loader keeps each raw line of
# `holidays.txt`, trailing name included, and the function compares ISO dates. The one test
# passes its holidays in, so it never reaches the loader. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > bizdays.py <<'PY'
"""Business-day arithmetic for the company calendar."""

import datetime
from pathlib import Path

HOLIDAYS_FILE = Path(__file__).with_name("holidays.txt")


def load_holidays(path=HOLIDAYS_FILE):
    """The company holidays in `path`: one ISO date a line, then what the day is."""
    days = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            days.add(line)
    return days


def next_business_day(day, holidays=None):
    """The first day after `day` that is not a weekend day or a holiday."""
    if holidays is None:
        holidays = load_holidays()
    day += datetime.timedelta(days=1)
    while day.weekday() >= 5 or day.isoformat() in holidays:
        day += datetime.timedelta(days=1)
    return day
PY

cat > holidays.txt <<'TXT'
# Company holidays: an ISO date, then what the day is.
2026-07-03  Independence Day (observed)
2026-11-26  Thanksgiving
2026-12-25  Christmas Day
2027-01-01  New Year's Day
TXT

mkdir -p tests
cat > tests/test_bizdays.py <<'PY'
import datetime
import unittest

from bizdays import next_business_day

D = datetime.date


class NextBusinessDayTest(unittest.TestCase):
    def test_a_weekday_goes_to_the_next_one(self):
        self.assertEqual(next_business_day(D(2026, 3, 3), holidays=set()), D(2026, 3, 4))

    def test_friday_goes_to_monday(self):
        self.assertEqual(next_business_day(D(2026, 3, 6), holidays=set()), D(2026, 3, 9))

    def test_a_holiday_passed_in_is_skipped(self):
        self.assertEqual(
            next_business_day(D(2026, 3, 3), holidays={"2026-03-04"}), D(2026, 3, 5)
        )


if __name__ == "__main__":
    unittest.main()
PY

cat > AGENTS.md <<'NOTE'
# bizdays

`bizdays.py` holds the business-day arithmetic; `holidays.txt` is the company holiday list that
it reads.

Run the tests with `python3 -B -m unittest discover -s tests`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

. "$here/../skills-close/close.sh"
