You are the implementation or analysis delegate for this bounded piece of work. The lead agent
will integrate the result. Read `AGENTS.md` first. You are not alone in the repository; preserve
work outside the paths below.

## Outcome

Make an inclusive date-window API that another change can use without changing the CLI.

## Context and files to read

Read `tally/model.py`, `tally/errors.py`, `tally/readers.py`, `tally/window.py`, `tests/helpers.py`,
`tests/test_model.py`, and `docs/window.md`. The CLI integration belongs to the lead.

## Work

Implement `select(entries, since=None, until=None)`. Bounds are `datetime.date` or `None`.
Return a new list in input order, including both boundary days. An absent bound is open.
Consume a one-shot iterable once and leave entries unchanged. For a reversed window, raise
`TallyError` with code `E104` and field `since` even for an empty iterable. Keep duplicate
entries. Do not parse strings or add CLI flags. Add tests with literal expected entries for a
closed range, each open range, equal bounds, empty input, duplicates and a reversed range.
Replace the proposed API note with the implemented contract and a worked boundary example.

## Bounds

You own `tally/window.py`, `tests/test_window.py`, and `docs/window.md`. Read other paths as needed. Do not edit them. Do not stage, commit, create a
branch or tag, push, deploy, use the network, install packages, run a model, or start a background
service. Do not run `make test`, `make test-integration`, or an integration runner. The focused
checks below are the completion bar for this delegation; the lead owns broader checks.
A sandbox, hook or tool refusal stands: record the exact act and reason, continue independent
work, and report the held item. Do not reach the same effect by another route. If a requirement
needs a change outside your paths, report the path and the needed change; leave it for the lead.
Use Python's standard library. Keep all fixture data synthetic. Leave the result uncommitted.

## Checks

Run `python3 -B -m unittest tests.test_window`. This is a library-only change.

## Report to the lead

Explain the inclusive endpoints and the reversed-range refusal. The lead will wire the CLI. Name files changed, checks actually run and their exit status, assumptions, any refusal,
and work left for the lead. Distinguish implementation, checks and integration. Do not claim a
commit, push or deployment. A short factual final answer is enough; no particular prose is needed.
