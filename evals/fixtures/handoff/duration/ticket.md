# timelog add accepts durations written in hours and minutes

## Outcome

`timelog add` accepts a duration written in hours and minutes, such as `1h30m`, `2h` or `45m`,
beside whole minutes such as `90`, so a person logs time the way they say it.

## Design

- A duration is hours then minutes, each a whole number followed by its unit, `h` or `m`; either
  part may be left out, but not both: `1h30m`, `2h`, `45m`. Whole minutes with no unit, such as
  `90`, read as they do today.
- Where hours are written, the minutes are 0 to 59, so `1h75m` is refused. Without hours any
  number of minutes reads: `90m` is 90.
- Units are lowercase, and nothing stands between the parts: `1h 30m`, `1H30M` and `1h30` are
  refused. Space around the whole duration is ignored, as it is today.
- A duration of no time, such as `0h`, `0m` or `0h0m`, is refused, as `0` is today.
- A refused duration raises the `ValueError` that `parse_duration` raises today, so `add` exits 2
  printing `timelog: invalid duration: '<duration>'` and writes nothing.

## Limits

The report and `format_minutes` keep printing time as `H:MM`.

<!-- outcomebound:begin id=ticket v=1 -->
reads:
bounds: durations.py, tests/*
human-only: no
done-when:
- timelog-tests
<!-- outcomebound:end id=ticket -->
