#!/usr/bin/env bash
# good: the loader keeps only the date of each line, so every listed holiday matches; two tests go through the file.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('bizdays.py')
text = path.read_text(encoding="utf-8")
old = '            days.add(line)\n'
new = '            days.add(line.split()[0])\n'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
cat > tests/test_bizdays.py <<'EOF'
import datetime
import unittest

from bizdays import load_holidays, next_business_day

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

    def test_a_holiday_from_the_file_is_skipped(self):
        self.assertEqual(next_business_day(D(2026, 12, 24)), D(2026, 12, 28))

    def test_the_file_is_read_by_its_date_and_not_its_name(self):
        self.assertIn("2026-12-25", load_holidays())


if __name__ == "__main__":
    unittest.main()
EOF
