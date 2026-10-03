# Package — #7, one step

This package adds to the ticket above and changes none of its decisions. It is one step, and
the step builds the whole ticket.

## Tests

The package's tests are in `tests/test_duration_forms.py`, committed on this branch. They are
fixed: make them pass, and do not change or remove any of them. You may add tests of your own
in other files under `tests/`. Each test fails now, for the reason in this table:

| Test | Fails now because |
| --- | --- |
| `test_hours_and_minutes_read_as_minutes` | `parse_duration` refuses `1h30m`: `invalid duration: '1h30m'` |
| `test_hours_alone_read_as_minutes` | `parse_duration` refuses `2h`: `invalid duration: '2h'` |
| `test_minutes_alone_read_in_any_number` | `parse_duration` refuses `45m`: `invalid duration: '45m'` |
| `test_whole_minutes_and_minutes_with_their_unit_agree` | `parse_duration` refuses `90m`: `invalid duration: '90m'` |
| `test_space_around_the_duration_is_ignored` | `parse_duration` refuses ` 1h30m `: `invalid duration: ' 1h30m '` |
| `test_minutes_after_hours_run_from_0_to_59` | `parse_duration` refuses `0h30m`: `invalid duration: '0h30m'` |
| `test_nothing_stands_between_or_after_the_parts` | `parse_duration` refuses `1h30m`: `invalid duration: '1h30m'` |
| `test_each_unit_needs_its_number` | `parse_duration` refuses `3h`: `invalid duration: '3h'` |
| `test_a_duration_of_no_time_is_refused` | `parse_duration` refuses `0h1m`: `invalid duration: '0h1m'` |
| `test_a_refusal_names_the_duration_as_written` | `parse_duration` refuses `1h`: `invalid duration: '1h'` |

Run the package's tests with `python3 -B -m unittest discover -s tests -p test_duration_forms.py`.

## Stubs

None. The step changes the body of one existing function and adds no symbol.

## Files you may write

- `durations.py`
- new test files under `tests/`

## Existing symbols

- `durations.parse_duration(text: str) -> int` returns the whole minutes `text` names. Today it
  reads only whole minutes, such as `90`. It raises `ValueError(f"invalid duration: {text!r}")`
  for any other text. Keep its name and its signature.
- `timelog.add` calls `parse_duration`. `timelog.main` turns its `ValueError` into exit status 2
  and prints `timelog: <message>` on standard error. Both already do what the ticket needs.

## Algorithm

1. Strip the text: `written = text.strip()`.
2. Where `written` fully matches `[0-9]+`, the result is `int(written)`.
3. Otherwise, fully match `written` against `(?:([0-9]+)h)?(?:([0-9]+)m)?`.
4. Refuse when there is no match, or when both groups are `None`.
5. Read the hours from group 1 and the minutes from group 2, each 0 where its group is `None`.
6. Refuse when group 1 is not `None` and the minutes are more than 59.
7. The result is `hours * 60 + minutes`.
8. Refuse when the result is 0.

To refuse is to raise `ValueError(f"invalid duration: {text!r}")`, with `text` exactly as passed
in. Compile both patterns once, at module level, with `re.compile`, and match them with
`fullmatch`. Use `[0-9]` in both patterns, so that only ASCII digits read.

## Text a person reads

The error message is `invalid duration: '<text>'`, as `f"invalid duration: {text!r}"` writes it.

## Edge cases

The tests cover: `1h30m`, `2h`, `10h`, `45m`, `90m`, `90`, space around a duration, minutes
from 0 to 59 after hours, `1h60m` and `1h75m`, `1h 30m`, `1H30M`, `1h30`, `30m1h`, `1hm`,
`1.5h`, `-1h`, `h`, `m`, `hm`, the empty text, `0h`, `0m`, `0h0m`, `0`, and the message of a
refusal.

The tests leave out: digits from scripts other than ASCII, which step 2's pattern refuses, and
the command line, which already turns a refusal into exit status 2.

## Shape to follow

Follow `durations.py` itself: a docstring on `parse_duration` that names the forms it reads.

## When to stop

Stop and report, without changing a package test, when a package test cannot pass with changes
to `durations.py` alone.
