# The export

`records export` writes CSV with three columns:

- `day`: the record's day, `YYYY-MM-DD`;
- `kind`: `call`, `note` or `visit`;
- `title`: free text.

`--since` and `--until` take a day and keep the records on or after, and on or before, that day.
`--kind` keeps one kind. `--data` reads another records file.
