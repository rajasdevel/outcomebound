# Package — #7, design

This package adds to the ticket above and changes none of its decisions. You write the code and
the tests.

## Approach

Match the stripped text against two anchored patterns in turn, whole minutes and then hours and
minutes, and compute the minutes from the groups of the one that matches. Rejected: cutting the
text at `h` and `m` by hand, which reads `1h30`, `30m1h` and `1hm` unless each is caught on its
own.

## Signatures

- `durations.parse_duration(text: str) -> int`, changed body, same name and signature. It returns
  the whole minutes, always more than 0. For every refused form it raises
  `ValueError(f"invalid duration: {text!r}")`, with `text` as passed in, and it raises nothing
  else.
- Two module constants added to `durations.py`, private: the compiled patterns
  `[0-9]+` and `(?:([0-9]+)h)?(?:([0-9]+)m)?`, matched with `fullmatch`.

## Data and invariants

- The result is an `int` greater than 0; an hour is 60 minutes.
- `fullmatch` keeps anything from standing before, between or after the parts.
- `[0-9]`, not `\d`: `\d` also matches digits of other scripts.
- The empty text matches the hours-and-minutes pattern with both groups empty, so a match with
  no group is a refusal.
- Minutes after hours are 0 to 59; minutes alone have no upper limit.

## Edge cases

| Scenario | Expected | Test that proves it |
| --- | --- | --- |
| `90` | 90 | `tests/test_durations.py::test_whole_minutes` (exists) |
| `1h30m` | 90 | `tests/test_durations.py::test_hours_and_minutes` |
| `2h`, `10h` | 120, 600 | `tests/test_durations.py::test_hours_alone` |
| `45m`, `90m` | 45, 90 | `tests/test_durations.py::test_minutes_alone_in_any_number` |
| ` 1h30m ` | 90 | `tests/test_durations.py::test_space_around_hours_and_minutes` |
| `0h30m`, `1h0m`, `1h59m` | 30, 60, 119 | `tests/test_durations.py::test_minutes_after_hours_0_to_59` |
| `1h60m`, `1h75m` | `ValueError` | `tests/test_durations.py::test_minutes_after_hours_0_to_59` |
| `1h 30m`, `1H30M`, `1h30`, `30m1h`, `1hm`, `1.5h`, `-1h` | `ValueError` | `tests/test_durations.py::test_other_forms_are_refused` |
| `h`, `m`, the empty text | `ValueError` | `tests/test_durations.py::test_a_unit_needs_its_number` |
| `0h`, `0m`, `0h0m`, `0` | `ValueError` | `tests/test_durations.py::test_no_time_is_refused` (extend it) |
| ` 1h75m ` refused | message `invalid duration: ' 1h75m '` | `tests/test_durations.py::test_a_refusal_names_the_text_as_written` |
| `timelog add 2026-10-01 acme 1h30m` | the log line's minutes field is `90` | `tests/test_cli.py::test_add_reads_hours_and_minutes` |
| `timelog add 2026-10-01 acme 1h75m` | exit 2, `timelog: invalid duration: '1h75m'`, nothing written | `tests/test_cli.py::test_add_refuses_a_bad_duration` |

Every test named in the table is one the work adds, except those marked (exists). Each test
calls `parse_duration` or `timelog.main` itself; `tests/test_cli.py` already has a
`run(log, *argv)` helper for the command line.

## Milestones

1. The two patterns and the new body of `parse_duration`. Check:
   `python3 -B -m unittest discover -s tests -p test_durations.py` passes.
2. The tests in the table, in `tests/test_durations.py` and `tests/test_cli.py`. Check:
   `python3 -B -m unittest discover -s tests` passes.

## Keep, and stop

- Keep every existing test passing as it stands, and keep `format_minutes` as it is.
- Where a row above cannot hold together with the ticket, stop at that point and report it; do
  not work around it.
