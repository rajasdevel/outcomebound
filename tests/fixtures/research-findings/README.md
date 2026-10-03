# Finding fixtures

One finding for each case, as the JSON file a project's inbox holds, with the verdict the finding
validation rules give it. OutcomeBound keeps a verbatim copy and runs the same cases through its
`research ingest` checks, so the two sides cannot drift apart: a change here is copied there.

- `<case>.json` is the finding, read with a JSON decoder (an escaped surrogate stays in the file as
  the escape, as a damaged file would hold it).
- `<case>.expect.json` is the expected result:
  - `verdict`: `accept` or `refuse`.
  - `today`: the date to judge `observed_on` by, so a date boundary does not move with the clock.
  - `rule`: the rule the case exercises; a label for the reader, not a message to match.
  - `scope`: `both` for a case about one finding's text, `consumer` for a case about the file's
    shape (keys, version, value types), which only the reader of an inbox file sees.

Each rule has its two sides at the boundary: the longest accepted value and the shortest refused
one. Accepted boundary values use ASCII text only, so a link of the finding stays within its
length limit. The rules are in `validate_finding`, in the research repository's collect script; the contract in
CONTRIBUTING.md names them.
