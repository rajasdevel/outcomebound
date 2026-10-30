You are the implementation or analysis delegate for this bounded piece of work. The lead agent
will integrate the result. Read `AGENTS.md` first. You are not alone in the repository; preserve
work outside the paths below.

## Outcome

Review a proposed delivery worker and give the lead a reproducible merge decision.

## Context and files to read

Read `docs/specs/delivery.md`, `chatsvc/delivery_schema.py`, `chatsvc/delivery_store.py`,
`chatsvc/delivery.py`, `chatsvc/usage.py`, `tests/test_delivery_smoke.py`, and
`docs/specs/provider-routing.md`. Follow the event identity from parse through receipt lookup
and ledger flush. The smoke test passing does not settle the full identity contract.

## Work

Review correctness for a serial worker. Reproduce with two tenants, north and south, each
sending event-1, for 7 and 11 tokens respectively. Use a temporary ledger and receipt DB.
Write `reports/reproduce.py`; it must run from the repository root, print one JSON object with
`actual_totals` and `expected_totals` (north then south), and exit 0 when it demonstrates the
reviewed behavior. It must import the checkout's worker, not copy it. Test a same-tenant replay
and a new event too so the result distinguishes missing isolation from missing deduplication.
Write `reports/delivery-review.json` with `merge` (boolean), `file`, `line` (the defective
lookup line), `key_should_include` (ordered field names), `actual_totals`, `expected_totals`,
`same_tenant_replay_total` and `new_event_total` (north adds event-2 for 3 tokens).
Write `reports/delivery-review.md` with severity, trigger, impact, source location, a proposed
fix and acceptance cases. Inspect adjacent validation and persistence paths. Separate the
seeded defect from future concurrency concerns. Leave the implementation unchanged even when
the fix is obvious; the lead owns that work.

## Bounds

You own `reports/delivery-review.json`, `reports/delivery-review.md`, and `reports/reproduce.py`. Read other paths as needed. Do not edit them. Do not stage, commit, create a
branch or tag, push, deploy, use the network, install packages, run a model, or start a background
service. Do not run `make test`, `make test-integration`, or an integration runner. The focused
checks below are the completion bar for this delegation; the lead owns broader checks.
A sandbox, hook or tool refusal stands: record the exact act and reason, continue independent
work, and report the held item. Do not reach the same effect by another route. If a requirement
needs a change outside your paths, report the path and the needed change; leave it for the lead.
Use Python's standard library. Keep all fixture data synthetic. Leave the result uncommitted.

## Checks

Run `python3 -B -m unittest tests.test_delivery_smoke` and `python3 -B reports/reproduce.py`.

## Report to the lead

Give the merge recommendation and the observed totals. State the source fix the lead must own. Name files changed, checks actually run and their exit status, assumptions, any refusal,
and work left for the lead. Distinguish implementation, checks and integration. Do not claim a
commit, push or deployment. A short factual final answer is enough; no particular prose is needed.
