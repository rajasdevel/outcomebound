# Package — #9, design

This package adds to the ticket above and changes none of its decisions. You write the code and
the tests.

## Approach

Carry the tags on `Entry` as a tuple, write them as an optional fifth field in `store`, filter
them in `report.totals`, and validate them in `timelog.add` before anything is written.
Rejected: a tags field written on every line, empty where there are none, which would change
every line a log without tags gets and break the ticket's byte-for-byte rule.

## Signatures

- `entries.Entry`, changed: gains its last field, `tags: tuple[str, ...] = ()`.
- `store.format_line(entry: Entry) -> str`, changed: four fields where `entry.tags` is empty, five
  where it is not. It raises nothing.
- `store.parse_line(line: str, number: int) -> Entry`, changed: reads four or five fields. For any
  other count it raises `store.LogError(f"line {number}: expected 4 fields, found {n}")`, the
  error and message it raises today.
- `report.totals(entries, start=None, end=None, tag: str | None = None) -> dict[str, int]`,
  changed: with `tag`, only the entries carrying it count. It raises nothing.
- `timelog.parser()`, changed: `add` gains `--tag`, which may be given more than once and is read
  as `options.tags`, a list that is empty where the option is not used; `report` gains `--tag`
  (one value, read as `options.tag`).
- `timelog.add(options)`, changed: raises `ValueError(f"invalid tag: {tag!r}")` for the first
  tag that is not 1 to 20 characters of `a-z`, `0-9` and `-`, before anything is written.

## Data and invariants

- `Entry.tags` is a tuple in the order given, each tag once: a repeated tag keeps its first place.
- Every tag in a log matches `[a-z0-9-]{1,20}`, so no tag holds a comma, a tab or a line end, and
  joining by commas can be split back.
- A log written with no tags is byte for byte what the code writes today.
- A four-field line reads as `tags == ()`; a five-field line splits its fifth field on commas.

## Edge cases

| Scenario | Expected | Test that proves it |
| --- | --- | --- |
| `Entry` with tags `("meeting", "billable")` | line ends `\tmeeting,billable` | `tests/test_store.py::test_tags_are_a_fifth_field` |
| `Entry` with no tags | four fields, as today | `tests/test_store.py::test_entries_read_back_as_written` (exists) |
| a five-field line | its tags, in order | `tests/test_store.py::test_a_fifth_field_reads_as_tags` |
| a four-field line | `tags == ()` | `tests/test_store.py::test_a_fifth_field_reads_as_tags` |
| a six-field line | `LogError`, `line N: expected 4 fields, found 6` | `tests/test_store.py::test_six_fields_are_a_read_error` |
| totals with `tag`, with and without `start` | only entries carrying the tag | `tests/test_report.py::test_totals_of_one_tag` |
| `add … --tag b --tag a --tag b` | fifth field `b,a` | `tests/test_cli.py::test_add_writes_tags_in_order_each_once` |
| `add … --tag x-1`, and a 20-character tag | recorded | `tests/test_cli.py::test_add_takes_allowed_tags` |
| `add … --tag Bad`, `a_b`, `a,b`, 21 characters, the empty tag | exit 2, `timelog: invalid tag: '<tag>'`, log unchanged | `tests/test_cli.py::test_add_refuses_other_tags` |
| a log written before tags, then `add … --tag billable` | old lines unchanged; both read | `tests/test_cli.py::test_a_log_written_before_tags_keeps_its_lines` |
| `report --tag billable` | totals of the tagged entries only | `tests/test_cli.py::test_report_totals_one_tag` |
| `report --tag meeting --from <a later day>` with no match | `no entries` | `tests/test_cli.py::test_report_totals_one_tag` |
| `report` without `--tag` | every entry, as today | `tests/test_cli.py::test_add_then_report` (exists) |

Every test named in the table is one the work adds, except those marked (exists). Each test
calls `store`, `report.totals` or `timelog.main` itself; `tests/test_cli.py` already has
a `run(log, *argv)` helper for the command line.

## Milestones

1. `Entry.tags`, and the fifth field in `format_line` and `parse_line`, with their tests. Check:
   `python3 -B -m unittest discover -s tests -p test_store.py` passes.
2. `report.totals` with `tag`, and its test. Check:
   `python3 -B -m unittest discover -s tests -p test_report.py` passes.
3. `--tag` on `add` and on `report`, the validation, and their command-line tests. Check:
   `python3 -B -m unittest discover -s tests` passes.
4. The fifth field described under `## Lines` in `docs/log-format.md`. Check: the paragraph names
   the field's place, the comma, the order, the one-each rule and the four-field case.

## Keep, and stop

- Keep a log without tags byte for byte as today, the read error's message as today, and every
  existing test passing as it stands.
- Where a row above cannot hold together with the ticket, stop at that point and report it; do
  not work around it.
