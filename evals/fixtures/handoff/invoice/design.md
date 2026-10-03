# Package — #8, design

This package adds to the ticket above and changes none of its decisions. You write the code and
the tests.

## Approach

Add `report.render_json`, which turns the totals `report.totals` already computes into the
document, and a `--json` flag on `report` that prints it in place of the text report. Rejected:
building the document in `timelog.py`, which would put a second copy of the report's logic
beside `report.render`.

## Signatures

- `report.render_json(found: dict[str, int], start: date | None = None, end: date | None = None)
  -> str`, added. It returns the document as JSON text, with no line end after it;
  it raises nothing for any `found` that `report.totals` returns.
- `timelog.parser()`, changed: the `report` sub-parser gains `--json`, `action="store_true"`.
- `timelog.main()`, changed: for `report`, it prints `render_json(found, options.start,
  options.end)` where `--json` is given, and `render(found)` where it is not.

## Data and invariants

- The document is a `dict` with exactly the keys `from`, `to`, `projects`, `total_minutes`.
- `from` and `to` are `date.isoformat()` strings, or `None` for a day not given.
- `projects` is a list of `{"project": name, "minutes": int}`, sorted by name, one per project,
  no other keys.
- `total_minutes` equals the sum of the projects' minutes, 0 for no project.
- With `--json`, standard output holds the document and nothing else.
- `invoice.read_report` is the judge of the shape; `invoice.py` and `docs/report-json.md` stay as
  they are.

## Edge cases

| Scenario | Expected | Test that proves it |
| --- | --- | --- |
| two projects given unsorted, with `--from` and `--to` | sorted `projects`, both days as strings, the sum | `tests/test_report.py::test_render_json_gives_the_shape` |
| no `--from` and no `--to` | `from` and `to` are `null` | `tests/test_report.py::test_render_json_writes_open_days_as_null` |
| only `--to` | `from` is `null`, `to` is the day | `tests/test_report.py::test_render_json_writes_open_days_as_null` |
| no entries in the range | `projects` is `[]`, `total_minutes` is 0 | `tests/test_report.py::test_render_json_of_no_entries` |
| `timelog report --json --from … --to …` | exit 0; `json.loads` of the whole standard output is the document | `tests/test_cli.py::test_report_json_prints_the_document_alone` |
| `report --json` piped into `invoice.read_report` and `invoice.invoice` | read without error; the invoice's lines are the projects and the total | `tests/test_cli.py::test_invoice_reads_report_json` |
| `timelog report` without `--json` | the text report, as today | `tests/test_cli.py::test_add_then_report` (exists) |

Every test named in the table is one the work adds, except those marked (exists). Each test
calls `report.render_json`, `timelog.main` or `invoice` itself; `tests/test_cli.py`
already has a `run(log, *argv)` helper for the command line.

## Milestones

1. `report.render_json` and its three tests. Check:
   `python3 -B -m unittest discover -s tests -p test_report.py` passes.
2. The `--json` flag and its two command-line tests. Check:
   `python3 -B -m unittest discover -s tests` passes.

## Keep, and stop

- Keep the text report byte for byte as it is, and every existing test passing as it stands.
- Where the document cannot be printed in the shape `docs/report-json.md` gives, stop at that
  point and report it; do not change `invoice.py` or the document to get past it.
