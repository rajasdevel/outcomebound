# The reference solution for ticket #7, written over a built workspace from its root: what
# the validity test applies to show the post-checks pass on work that meets the ticket. Kept
# beside the fixture, never in the workspace.
cat > durations.py <<'PY'
"""Durations as the command line writes them."""

import re

_MINUTES = re.compile(r"[0-9]+")
_HOURS_AND_MINUTES = re.compile(r"(?:([0-9]+)h)?(?:([0-9]+)m)?")


def parse_duration(text):
    """The whole minutes `text` names: whole minutes, `90`, or hours and minutes, `1h30m`,
    `2h` or `45m`, where minutes after hours run 0 to 59.

    Space around the text is ignored. Raises ValueError naming the text as written where it
    names no positive duration in one of those forms.
    """
    written = text.strip()
    minutes = 0
    if _MINUTES.fullmatch(written):
        minutes = int(written)
    else:
        found = _HOURS_AND_MINUTES.fullmatch(written)
        if found and any(found.groups()):
            hours, rest = (int(part) if part else 0 for part in found.groups())
            if found.group(1) is None or rest < 60:
                minutes = hours * 60 + rest
    if minutes == 0:
        raise ValueError(f"invalid duration: {text!r}")
    return minutes


def format_minutes(minutes):
    """`minutes` as hours and minutes: 90 is `1:30`."""
    hours, rest = divmod(minutes, 60)
    return f"{hours}:{rest:02d}"
PY
cat > tests/test_duration_hours.py <<'PY'
import unittest

from durations import parse_duration


class HoursAndMinutesTest(unittest.TestCase):
    def test_hours_and_minutes(self):
        self.assertEqual(parse_duration("1h30m"), 90)

    def test_minutes_after_hours_stop_at_59(self):
        with self.assertRaises(ValueError):
            parse_duration("1h60m")


if __name__ == "__main__":
    unittest.main()
PY
