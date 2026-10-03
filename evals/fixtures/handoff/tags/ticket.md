# Entries carry tags, and the report totals one tag

## Outcome

`timelog add` records tags on an entry, and `timelog report --tag T` totals only the entries
tagged `T`, so a person sees the time spent on one kind of work. A log written before keeps
reading as it does today.

## Design

- `add` takes `--tag T`, which may be given more than once. A tag is 1 to 20 characters, each a
  lowercase letter, a digit or `-`. Any other tag makes `add` exit 2 printing
  `timelog: invalid tag: '<tag>'`, and nothing is written.
- The log gains a fifth field after the note: the entry's tags joined by commas, in the order
  given, each tag once. An entry with no tags is written as four fields, exactly as today.
- A line of four fields reads as an entry with no tags, and a line of five reads its tags. Any
  other number of fields is the read error it is today.
- `report --tag T` totals only the entries tagged `T`, within `--from` and `--to` where they are
  given. With no such entries it prints `no entries`, as an empty report does today.
- `docs/log-format.md` describes the fifth field.

## Limits

`report` without `--tag` totals every entry, as it does today.

<!-- outcomebound:begin id=ticket v=1 -->
reads: docs/log-format.md#lines
bounds: entries.py, store.py, report.py, timelog.py, docs/log-format.md, README.md, tests/*
human-only: no
done-when:
- timelog-tests
<!-- outcomebound:end id=ticket -->
