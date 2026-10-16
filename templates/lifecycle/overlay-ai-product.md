# Lifecycle overlay: ai-product

A comparison for adoption. `adopt` never installs it, and the project owns every line it writes.
Propose a line below only where the project's committed text does not already lead an agent to the
decision the line changes; most lines are left out.

**Fits when** the product itself calls a model. Agents that write the code are not this fact. It
goes on any lifecycle.

**Fragments it would select:** none of its own.

**Scaffold set:** `+ai-product` adds the local lines of `templates/scaffold/ai-product/local.md`
(the evaluation tasks and their grader as part of Done, written before the code that calls the
model; the provider) and rows for the design's decision table: the provider, and how its output is
evaluated.

## Example lines

```text
Completion bar: the evaluation tasks and their grader run as part of Done, by <the evaluation
  command>, and were written before the code that calls the model.
Context: the model provider is <the provider>, until the design's provider row holds it.
```

## When to propose each line, and when to leave it out

- The evaluation line: propose it whenever the product calls a model and Done runs no evaluation.
- The provider line: propose it until the design records the provider; then leave it out.
