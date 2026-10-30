You are the implementation or analysis delegate for this bounded piece of work. The lead agent
will integrate the result. Read `AGENTS.md` first. You are not alone in the repository; preserve
work outside the paths below.

## Outcome

Build a restart-safe local reconciliation tool with a read-only plan and atomic apply.

## Context and files to read

Read `datapipe/reconcile/__main__.py`, `docs/reconcile.md`, `datapipe/warehouse.py`,
`datapipe/loader.py`, `datapipe/batching.py`, `tests/test_loader.py`, `tests/helpers.py`,
`docs/architecture.md`, and `docs/specs/revenue.md`. Keep the new versioned update tool separate
from existing ingestion and SQL transforms. There is no service or external database.

## Work

Implement `python3 -m datapipe.reconcile plan INPUT --db FILE`, `apply INPUT --db FILE`, and
`inspect --db FILE`. Keep parsing, transition planning and SQLite persistence in separate modules.

1. Input is UTF-8 JSONL. Blank lines are ignored. Each record has `key` (nonempty string),
   `version` (positive integer), `value` (nonnegative integer), and optional `deleted` (boolean,
   default false). Reject booleans as integers, nonobjects, missing required fields and malformed
   JSON with E102 and a 1-based line. Unknown fields are refused. Validate the whole input before
   creating a database or changing one. Input order is the transition order.
2. SQLite holds current items and a history of every seen `(key, version)` with its value and
   deleted state. For an unseen key, a live record inserts; a tombstone deletes. A higher version
   updates, or deletes if it is a tombstone. An unseen lower version is stale. Repeating an exact
   seen key/version/value/deleted record is duplicate, even after a later version exists.
   A different payload for a seen key/version refuses the whole batch with E102 and its input
   line. Keep tombstone versions so an older live record cannot resurrect deleted data.
3. Plan and apply print exactly `{"actions":[{"key":"a","version":1,"action":"insert"}],
   "active_count":1,"total_value":7}` for one live a/1/7 record. Actions are insert, update,
   delete, stale, or duplicate, in input order. Totals cover live current records only.
   `inspect` prints `{"items":[{"key":"a","version":1,"value":7,"deleted":false}],
   "active_count":1,"total_value":7}`, including tombstones in the sorted items list but not
   in totals. A missing DB inspects as empty without creating a file.
4. Plan must leave database bytes unchanged and must not create an absent DB. Apply commits all
   records and history in one transaction; any later conflict rolls back the entire batch,
   including earlier new keys and history. Replay after a new process starts must be duplicate.
   Do not delete or rewrite the database to simulate rollback. Do not make backup files.
5. Successful commands exit 0. Expected input failures exit 2, leave stdout empty, and print one
   JSON stderr object with `code` E102 and `line`. File or database IO failures use E101 and
   line 0. Leave no traceback on expected failures. Never mutate the input file.
6. Add tests for parsing refusals at the right line, duplicate versus stale, conflicting history,
   tombstones, reopening state, dry plans, absent DB behavior, totals and atomic rollback. Use
   temporary SQLite files and literal expected outputs. Document CLI examples, action rules,
   crash/transaction limits, the schema you chose and recovery after a refused batch.
   No migration framework, web endpoint, scheduler integration or third-party dependency.

## Bounds

You own `datapipe/reconcile/`, `tests/test_reconcile.py`, and `docs/reconcile.md`. Read other paths as needed. Do not edit them. Do not stage, commit, create a
branch or tag, push, deploy, use the network, install packages, run a model, or start a background
service. Do not run `make test`, `make test-integration`, or an integration runner. The focused
checks below are the completion bar for this delegation; the lead owns broader checks.
A sandbox, hook or tool refusal stands: record the exact act and reason, continue independent
work, and report the held item. Do not reach the same effect by another route. If a requirement
needs a change outside your paths, report the path and the needed change; leave it for the lead.
Use Python's standard library. Keep all fixture data synthetic. Leave the result uncommitted.

## Checks

Run `python3 -B -m unittest tests.test_reconcile`. Each database used by a test is disposable.

## Report to the lead

Give the action semantics, transaction boundary and restart evidence. Name any SQLite assumption. Name files changed, checks actually run and their exit status, assumptions, any refusal,
and work left for the lead. Distinguish implementation, checks and integration. Do not claim a
commit, push or deployment. A short factual final answer is enough; no particular prose is needed.
