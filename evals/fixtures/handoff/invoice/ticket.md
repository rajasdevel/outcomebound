# timelog report --json prints the report that invoice.py reads

## Outcome

`timelog report --json` prints the report as the JSON that `invoice.py` reads, so the month's
invoice is `python3 timelog.py report --json --from 2026-09-01 --to 2026-09-30 | python3
invoice.py --rate 90`.

## Design

- The JSON is the shape `docs/report-json.md` gives, and `invoice.py` is its reader.
- `--json` takes the same `--from` and `--to` as the text report and totals the same entries; a
  day not given is `null`.
- With `--json`, standard output is the JSON document and nothing else.
- A report with no entries is the same shape, with an empty `projects` and a `total_minutes` of 0.

## Limits

`report` without `--json` prints what it prints today. `invoice.py` and `docs/report-json.md`
stay as they are; where the shape cannot be printed as the document gives it, stop and ask.

<!-- outcomebound:begin id=ticket v=1 -->
reads: docs/report-json.md#shape
bounds: timelog.py, report.py, tests/*
human-only: no
done-when:
- timelog-tests
<!-- outcomebound:end id=ticket -->
