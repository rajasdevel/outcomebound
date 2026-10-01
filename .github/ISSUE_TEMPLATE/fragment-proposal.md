---
name: Fragment proposal
about: Propose a new stack or setup fragment under fragments/
title: "fragment: "
labels: fragment
---

A fragment instantiates the operating contract with facts about one stack or one project setup;
it never adds a rule. Fill in the frontmatter and all five slots below, in order. See
`CONTRIBUTING.md` for the full rule (mechanisms must be registry ids, `detect` globs must resolve
inside the target root).

## Frontmatter

```yaml
id: <short, lowercase, hyphenated>
family: <stack|setup>
applies: <one line: what projects this fragment is for>
detect: ["<glob>", "<glob>"]
version: 1
```

## Context

What evidence is real for this stack or setup — what a claim is versus what actually ran.

## Bounds

What is preserved state here, and what crossing is an irreversible edge.

## Mechanisms

When each registry mechanism (`spec`, `goal-envelope`, `failing-test-first`, `review`,
`policy-gate`, `broad-suite`, `runtime-check`) typically fires for this stack or setup. Only
these backticked ids are allowed in this slot: the fragment parser refuses any other.

## Completion bar

The checks that actually establish confidence here, and what each one does and does not settle.

## Distinguish

The states that must not stand in for one another (e.g. "edited ≠ collected by pytest ≠
passing ≠ installed").
