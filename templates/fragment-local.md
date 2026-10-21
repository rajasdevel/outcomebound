---
id: local
family: setup
applies: facts specific to this repository — replace this line
edges: []
detect: []
version: 1
---
**Context** — what counts as evidence here, and what the code alone does not tell you. Keep all
five slots, in this order, each starting its line as here: adopt refuses a fragment without one.
Optional lifecycle lines go here, each only where it changes a decision an agent would get wrong:
"Exposure —", "Streams —", "Better means —" and, after a complete directive or a person's answer
on a change of route, "Changed —", one line for each stream, the older one removed. The adopt
skill says how to propose them.
**Bounds** — which actions are irreversible, protected, or outside default authority. Each
irreversible act also goes in `edges:` as its own item of that one-line JSON list, in double
quotes and with no `;`, as in `edges: ["pushing a tag"]`, so it joins the
Irreversible edges fact; a project that publishes without selecting `ci-release` lists
`publishing a package` there itself. A harness that reads its own ask rules can ask before each
edge: examples are under `$(outcomebound home)/templates/harness/`. Optional lines here: "Gates —"
(a gate, its owner, its evidence), "Leave when —" (a signal that ends the current lifecycle, and
the brief it opens) and "Drift —" (a signal settled, with its reason).
**Mechanisms** — which registry mechanisms typically fire here, each named as a backticked id
(`spec`, `goal-envelope`, `failing-test-first`, `review`, `policy-gate`, `broad-suite`,
`runtime-check`) and the condition that fires it. Only mechanism ids take backticks on this line;
write a command or any other name without them.
**Completion bar** — the real commands or observations that establish success here, and the
evidence layer each one settles.
**Distinguish** — the states that must not impersonate each other in this project.
