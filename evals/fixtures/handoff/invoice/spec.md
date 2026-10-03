# Package — #8, one step

This package adds to the ticket above and changes none of its decisions. It is one step, and
the step builds the whole ticket.

## Tests

The package's tests are in `tests/test_report_json.py`, committed on this branch. They are
fixed: make them pass, and do not change or remove any of them. You may add tests of your own
in other files under `tests/`. Each test fails now, for the reason in this table:

| Test | Fails now because |
| --- | --- |
| `test_render_json_gives_the_shape` | the stub raises `NotImplementedError: ticket #8: render_json` |
| `test_render_json_writes_a_day_not_given_as_null` | the stub raises `NotImplementedError: ticket #8: render_json` |
| `test_render_json_of_no_entries_is_the_empty_shape` | the stub raises `NotImplementedError: ticket #8: render_json` |
| `test_report_json_prints_the_document_alone` | `report` has no `--json` option, so `timelog` exits 2: `unrecognized arguments: --json` |
| `test_invoice_reads_what_report_json_prints` | `report` has no `--json` option, so `timelog` exits 2: `unrecognized arguments: --json` |

Run the package's tests with `python3 -B -m unittest discover -s tests -p test_report_json.py`.

## Stubs

`report.py` holds this stub, committed on this branch. Replace its body, and keep its name, its
signature and its docstring:

```python
def render_json(found: dict[str, int], start: date | None = None, end: date | None = None) -> str:
    """The totals `found`, minutes per project, as the JSON document docs/report-json.md
    gives, for the days from `start` to `end`; None writes that side as null.

    Returns the document as text with no line end after it. Raises nothing.
    """
    raise NotImplementedError("ticket #8: render_json")
```

## Files you may write

- `report.py`
- `timelog.py`
- new test files under `tests/`

## Existing symbols

- `report.totals(entries, start=None, end=None) -> dict[str, int]` returns the minutes per
  project over the entries from `start` to `end`. `start` and `end` are `datetime.date` or
  `None`.
- `report.render(found: dict[str, int]) -> str` returns the text report. Do not change it.
- `timelog.parser()` builds the `argparse` parser. Its `report` sub-parser is the variable
  `shown`, with the options `--from` (stored as `start`) and `--to` (stored as `end`).
- `timelog.main(argv=None) -> int` prints `report.render(found)` for the `report` verb.
- `invoice.read_report(text: str) -> dict` checks a document against the shape and raises
  `ValueError` naming what is wrong. Do not change `invoice.py`.

## Algorithm

1. In `render_json`, build a `dict` with exactly the four keys `from`, `to`, `projects` and
   `total_minutes`, in that order.
2. `from` is `start.isoformat()`, or `None` where `start` is `None`. `to` is the same for `end`.
3. `projects` is a `list` with one `dict` for each item of `sorted(found.items())`. Each `dict`
   has exactly the keys `project`, the name, and `minutes`, the `int`.
4. `total_minutes` is `sum(found.values())`.
5. Return `json.dumps(document, indent=2)`. Add `import json` at the top of `report.py`.
6. In `timelog.parser()`, add to `shown` the option `--json` with `action="store_true"` and the
   help text `print the report as JSON`.
7. In `timelog.main()`, for the `report` verb, compute `found` as today. Then print
   `report.render_json(found, options.start, options.end)` where `options.json` is true, and
   `report.render(found)` where it is false.

Print nothing else on standard output when `--json` is given.

## Text a person reads

The help text of `--json` is `print the report as JSON`.

## Edge cases

The tests cover: a range with two projects, given unsorted; a report with neither `--from` nor
`--to`; a report with no entries; standard output holding the document alone; and `invoice.py`
reading the document `report --json` prints.

The tests leave out: the text report without `--json`, which the existing `tests/test_cli.py`
and `tests/test_report.py` already cover.

## Shape to follow

Follow `report.render` for how a function in `report.py` reads `found`, and the `--from` option
in `timelog.parser()` for how an option is added.

## When to stop

Stop and report, without changing a package test, when a package test cannot pass without a
change to `invoice.py` or `docs/report-json.md`.
