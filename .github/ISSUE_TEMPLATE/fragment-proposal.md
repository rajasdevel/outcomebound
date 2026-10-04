---
name: Fragment proposal
about: Propose a new stack or setup fragment for fragments/
title: "fragment: "
labels: area:fragments
---

Thank you for proposing a fragment. A fragment applies the operating contract to the facts of one
stack or one project setup. It never adds a rule. Fill in the frontmatter and all five slots
below, in this order. If a slot is hard to fill, write what you know and say what is missing.
`CONTRIBUTING.md` has the full rules. You can also open a pull request with the fragment file
instead of this issue.

## Frontmatter

```yaml
id: <short, lowercase, hyphenated>
family: <stack|setup>
applies: <one line: what projects this fragment is for>
detect: ["<glob>", "<glob>"]
version: 1
```

Each `detect` glob is relative to the target root, and must not leave it. The optional keys
`condition`, `edges` and `skills` are in `CONTRIBUTING.md`.

## Context

What counts as real evidence for this stack or setup. Say what a claim is, and what actually ran.

## Bounds

What state must stay as it is. What step is an irreversible edge.

## Mechanisms

When each registry mechanism fires for this stack or setup. The registry has seven ids: `spec`,
`goal-envelope`, `failing-test-first`, `review`, `policy-gate`, `broad-suite` and
`runtime-check`. Use only these ids as backticked names in this slot. The fragment parser refuses
any other name.

## Completion bar

The checks that give real confidence here. For each check, say what it settles and what it does
not settle.

## Distinguish

The states that must not stand in for one another. For example: "edited ≠ collected by pytest ≠
passing ≠ installed".
