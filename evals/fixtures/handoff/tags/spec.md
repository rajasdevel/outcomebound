# Package — #9, one step

This package adds to the ticket above and changes none of its decisions. It is one step, and
the step builds the whole ticket.

## Tests

The package's tests are in `tests/test_tags.py`, committed on this branch. They are fixed: make
them pass, and do not change or remove any of them. You may add tests of your own in other files
under `tests/`. Each test fails now, for the reason in this table:

| Test | Fails now because |
| --- | --- |
| `test_tags_make_a_fifth_field_and_no_tags_keep_four` | `store.format_line` writes no fifth field: `!= '2026-09-02\tacme\t60\tcall\tmeeting,billable'` |
| `test_five_fields_read_as_tags_four_as_none_and_six_as_an_error` | `store.parse_line` refuses five fields: `expected 4 fields, found 5` |
| `test_totals_count_only_the_entries_carrying_the_tag` | the stub raises `NotImplementedError: ticket #9: totals by tag` |
| `test_add_writes_tags_in_the_order_given_each_once` | `add` has no `--tag` option, so `timelog` exits 2: `unrecognized arguments: --tag` |
| `test_add_takes_a_tag_of_the_allowed_characters_and_refuses_any_other` | `add` has no `--tag` option, so `timelog` exits 2: `unrecognized arguments: --tag` |
| `test_a_log_written_before_tags_keeps_its_lines` | `add` has no `--tag` option, so `timelog` exits 2: `unrecognized arguments: --tag` |
| `test_report_totals_one_tag` | `report` has no `--tag` option, so `timelog` exits 2: `unrecognized arguments: --tag` |

Run the package's tests with `python3 -B -m unittest discover -s tests -p test_tags.py`.

## Stubs

Two stubs are committed on this branch. Keep each name, signature and docstring.

In `entries.py`, `Entry` has its last field, complete as it stands:

```python
    tags: tuple[str, ...] = ()
```

In `report.py`, `totals` has its new parameter. Replace the two lines that raise
`NotImplementedError`:

```python
def totals(entries, start=None, end=None, tag: str | None = None):
    """Minutes per project over the entries from `start` to `end`, both days included, that
    carry `tag`; None leaves that side open, or takes every entry."""
    if tag is not None:
        raise NotImplementedError("ticket #9: totals by tag")
```

## Files you may write

- `store.py`
- `report.py`
- `timelog.py`
- `docs/log-format.md`
- `README.md`
- new test files under `tests/`

## Existing symbols

- `entries.Entry(day: date, project: str, minutes: int, note: str = "", tags: tuple[str, ...] = ())`
  is a `NamedTuple`.
- `store.FIELDS` is `4`.
- `store.format_line(entry: Entry) -> str` returns one log line without its line end.
- `store.parse_line(line: str, number: int) -> Entry` reads one log line. It raises
  `store.LogError(f"line {number}: expected {FIELDS} fields, found {len(fields)}")` for a wrong
  number of fields.
- `timelog.parser()` builds the `argparse` parser. Its `add` sub-parser is the variable `add`, and
  its `report` sub-parser is the variable `shown`.
- `timelog.add(options)` validates the options, builds an `Entry` and calls `store.append`. A
  `ValueError` it raises becomes exit status 2 with `timelog: <message>` on standard error.
- `timelog.main(argv=None) -> int` calls `report.totals(store.load(log_path()), options.start,
  options.end)` for the `report` verb.

## Algorithm

1. In `store.format_line`, build the list of the four fields as today. Append
   `",".join(entry.tags)` as a fifth field only where `entry.tags` is not empty.
2. In `store.parse_line`, accept a line of `FIELDS` or `FIELDS + 1` fields. For any other count,
   raise the `LogError` it raises today, with the same message.
3. In `store.parse_line`, read the first four fields as today. Where there is a fifth field, the
   tags are the parts of it between its commas, an empty part left out, as a `tuple`. Where
   there is none, the tags are `()`. Pass the tags to `Entry` as its fifth argument.
4. In `report.totals`, skip an entry where `tag` is not `None` and `tag not in entry.tags`. Keep
   the `start` and `end` checks as they are.
5. In `timelog.parser()`, add to `add` the option `--tag` with `metavar="TAG"`. It may be given
   more than once, and `options.tags` is the list of its uses, empty where it is not given.
6. In `timelog.parser()`, add to `shown` the option `--tag` with `metavar="TAG"` and the help
   text `total only the entries tagged TAG`.
7. In `timelog.py`, add a module constant `TAG` that holds the compiled pattern of a tag: 1 to
   20 characters, each a lowercase ASCII letter, a digit or `-`.
8. In `timelog.add`, before anything is written, check each tag in `options.tags` against the
   whole of `TAG`. Raise `ValueError(f"invalid tag: {tag!r}")` for the first tag that does not
   match.
9. In `timelog.add`, pass the tags to `Entry` as `tags`, as a `tuple` in the order given with
   each repeated tag kept at its first place only.
10. In `timelog.main`, pass `options.tag` to `report.totals` as `tag`.
11. In `docs/log-format.md`, under `## Lines`, add one paragraph that describes the fifth field
    with the decisions the ticket gives for it.

## Text a person reads

- The error for a tag is `invalid tag: '<tag>'`, as `f"invalid tag: {tag!r}"` writes it.
- The help text of `report --tag` is `total only the entries tagged TAG`.

## Edge cases

The tests cover: a fifth field with two tags; four fields with no tags; a line of six fields; a
total for one tag, with and without `--from`; a tag no entry carries; a repeated tag; the tags
`x-1`, `Bad`, `a_b`, `a,b`, 21 characters, and the empty tag; a log written before tags; and
`report --tag` with no matching entries.

The tests leave out: `report` without `--tag`, which the existing `tests/test_cli.py` and
`tests/test_report.py` already cover, and the text of `docs/log-format.md`.

## Shape to follow

Follow the `--from` option in `timelog.parser()` for how an option is added, and the existing
checks at the top of `timelog.add` for how a refusal is raised.

## When to stop

Stop and report, without changing a package test, when a package test cannot pass with changes
to the files listed above.
