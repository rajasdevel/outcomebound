You are the implementation or analysis delegate for this bounded piece of work. The lead agent
will integrate the result. Read `AGENTS.md` first. You are not alone in the repository; preserve
work outside the paths below.

## Outcome

Build portable time-entry bundles that can be verified and compared offline.

## Context and files to read

Read `tally/model.py`, `tally/readers.py`, `tally/aggregate.py`, `tally/merge.py`,
`tally/errors.py`, `tally/report.py`, `tally/bundles/__main__.py`, `tests/helpers.py`,
`tests/test_merge.py`, `tests/test_readers.py`, `docs/bundles.md` and the output decisions.
Use the existing entry model, canonical CSV writer and grouping rather than copying them.

## Work

Implement a separate `python3 -m tally.bundles` CLI. Split IO, integrity checks and command
handling where useful. Keep the existing `python3 -m tally` CLI unchanged.

1. `build FILE... --out DIR [--by project|person|week|day] [--since YYYY-MM-DD]
   [--until YYYY-MM-DD]` reads CSV or JSONL through the existing readers. Remove exact duplicate
   entries, sort by the model order, then select an inclusive calendar window. Count duplicate
   removals before filtering. Refuse a reversed window with E104, even on empty input.
2. Publish a new directory with exactly `entries.csv`, `summary.json`, and `manifest.json`.
   Summary and build stdout are the same object: `entry_count`, `duplicate_count`,
   `total_minutes`, `by`, and `rows` (sorted by key; each has `key`, `entry_count`,
   `total_minutes`). Use integer minutes. Empty input has an empty rows list and zero totals.
   Manifest is `{"schema":1,"files":{"entries.csv":"<sha256>","summary.json":"<sha256>"}}`.
   Hash bytes as written. Publish only after all inputs and files validate; refuse any existing
   destination with E104 and leave it untouched. Remove your temporary directory on any failure.
3. `verify DIR` checks the exact three filenames, regular files (no symlinks), schema, both
   digests, canonical CSV rows, counts, and recomputed groups. It prints `{"valid":true}`.
   Reject corruption and a self-consistent but false summary with E102.
4. `diff OLD NEW` verifies both bundles first. Require the same grouping or E104. Print
   `{"by":"project","rows":[{"key":"work","before_minutes":10,"after_minutes":25,
   "delta_minutes":15}]}` with the actual grouping and changed keys only, sorted. Include a
   removed key with after=0 and an added key with before=0. Ignore equal totals.
5. Success exits 0. A data or integrity refusal exits 2, prints one JSON object to stderr with
   a `code` field (E101 unreadable input, E102 invalid data/integrity, E104 option conflict),
   and leaves stdout empty. Exact message wording is free. No traceback for expected refusals.
6. Add focused tests for multi-file deduplication, all grouping modes, inclusive windows, empty
   input, existing destination, unreadable and invalid input, corrupt bytes, symlinks, forged
   summaries, cross-group diff, and added/removed keys. Check cleanup and original input bytes.
   Replace docs/bundles.md with commands, wire examples, refusals, publication limits and the
   distinction between digest integrity and authenticity. Do not add signatures or dependencies.

## Bounds

You own `tally/bundles/`, `tests/test_bundles.py`, and `docs/bundles.md`. Read other paths as needed. Do not edit them. Do not stage, commit, create a
branch or tag, push, deploy, use the network, install packages, run a model, or start a background
service. Do not run `make test`, `make test-integration`, or an integration runner. The focused
checks below are the completion bar for this delegation; the lead owns broader checks.
A sandbox, hook or tool refusal stands: record the exact act and reason, continue independent
work, and report the held item. Do not reach the same effect by another route. If a requirement
needs a change outside your paths, report the path and the needed change; leave it for the lead.
Use Python's standard library. Keep all fixture data synthetic. Leave the result uncommitted.

## Checks

Run `python3 -B -m unittest tests.test_bundles`. Use temporary files for export and corruption cases.

## Report to the lead

Give the bundle format and verification limits. Name any filesystem atomicity assumption. Name files changed, checks actually run and their exit status, assumptions, any refusal,
and work left for the lead. Distinguish implementation, checks and integration. Do not claim a
commit, push or deployment. A short factual final answer is enough; no particular prose is needed.
