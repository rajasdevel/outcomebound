# The spec package's executable part for ticket #7, written into the workspace from its root
# before the seed commit: the package's fixed tests, each failing on the seed for the reason
# the package names. The step adds no symbol, so it has no stub.
cat > tests/test_duration_forms.py <<'PY'
"""Ticket #7: durations written in hours and minutes.

These tests are the hand-off package's, and they are fixed: make them pass, and change or
remove none of them.
"""

import unittest

from durations import parse_duration


class DurationFormsTest(unittest.TestCase):
    def assert_refused(self, text):
        with self.assertRaisesRegex(ValueError, r"^invalid duration: "):
            parse_duration(text)

    def test_hours_and_minutes_read_as_minutes(self):
        self.assertEqual(parse_duration("1h30m"), 90)

    def test_hours_alone_read_as_minutes(self):
        self.assertEqual(parse_duration("2h"), 120)
        self.assertEqual(parse_duration("10h"), 600)

    def test_minutes_alone_read_in_any_number(self):
        self.assertEqual(parse_duration("45m"), 45)
        self.assertEqual(parse_duration("90m"), 90)

    def test_whole_minutes_and_minutes_with_their_unit_agree(self):
        self.assertEqual(parse_duration("90m"), parse_duration("90"))

    def test_space_around_the_duration_is_ignored(self):
        self.assertEqual(parse_duration(" 1h30m "), 90)
        self.assertEqual(parse_duration("\t2h\n"), 120)

    def test_minutes_after_hours_run_from_0_to_59(self):
        self.assertEqual(parse_duration("0h30m"), 30)
        self.assertEqual(parse_duration("1h0m"), 60)
        self.assertEqual(parse_duration("1h59m"), 119)
        self.assert_refused("1h60m")
        self.assert_refused("1h75m")

    def test_nothing_stands_between_or_after_the_parts(self):
        self.assertEqual(parse_duration("1h30m"), 90)
        for text in ("1h 30m", "1H30M", "1h30", "30m1h", "1hm", "1.5h", "-1h"):
            with self.subTest(text=text):
                self.assert_refused(text)

    def test_each_unit_needs_its_number(self):
        self.assertEqual(parse_duration("3h"), 180)
        for text in ("h", "m", "hm", ""):
            with self.subTest(text=text):
                self.assert_refused(text)

    def test_a_duration_of_no_time_is_refused(self):
        self.assertEqual(parse_duration("0h1m"), 1)
        for text in ("0h", "0m", "0h0m", "0"):
            with self.subTest(text=text):
                self.assert_refused(text)

    def test_a_refusal_names_the_duration_as_written(self):
        self.assertEqual(parse_duration("1h"), 60)
        with self.assertRaisesRegex(ValueError, r"^invalid duration: ' 1h75m '$"):
            parse_duration(" 1h75m ")


if __name__ == "__main__":
    unittest.main()
PY
