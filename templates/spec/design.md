---
name: <slug>
status: draft
---

# <slug> — design

> Write a spec only when later work relies on a decision the code cannot show. Keep it to those
> decisions, one spec per area, edited in place when a decision changes; version control is its
> history. Point to the file that defines a contract (a schema, a module) instead of restating it.
> Decisions: one row per decision the code cannot show, with its owner (`agent` or `user`) and a
> status of `open`, `assumed` or `decided`; resolve what you can and surface only the user-owned
> rows.

## Outcome

<!-- Observable result and completion bar. -->

## Requirements

<!-- Optional. Only where requirements come from a source: one line each, starting with an id
`R1`, `R2` and so on. Ids are never renumbered or reused. Add `[assumed]` to a line that no source
states. Delete this section otherwise. -->

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| <name> | <the near alternative, and why not> | agent | assumed |

## Validation

<the checks that settle the material risks, named once>

## Sources

<!-- Optional. Only where requirements come from a source: `outcomebound sources import` reads
the source, `outcomebound sources check --skeleton <manifest>` prints these rows, and
`outcomebound sources check <manifest>... <this file>` checks them. Delete this section
otherwise. A quote is the shortest phrase that anchors the requirement: this file may be public
where the source is not. -->

| Source item | Disposition | Where | Basis |
| --- | --- | --- | --- |
| <id> #<revision> | carried | R1 | stated: "<quote>" |
