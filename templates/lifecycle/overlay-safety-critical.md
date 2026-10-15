# Lifecycle overlay: safety-critical

A comparison for adoption. `adopt` never installs it, and the project owns every line it writes.
Propose a line below only where the project's committed text does not already lead an agent to the
decision the line changes; most lines are left out.

**Fits when** a failure can harm a person, and the person names a lifecycle standard, such as IEC
62304 or DO-178C, that the product's development follows. That standard's own process decides each
step it covers; no general template meets it, and this one says so.

**Fragments it would select:** none of its own.

**Scaffold set:** `+safety-critical` adds the local lines of
`templates/scaffold/safety-critical/local.md`: this scaffold is not that lifecycle, and agent
output counts as unverified until a person or a qualified process verifies it.

## Example lines

```text
Context: this scaffold is not the lifecycle that <the standard> requires, and that standard's own
  process decides each step it covers.
Distinguish: agent output ≠ verified output.
```

## When to propose each line, and when to leave it out

- Propose both lines whenever the fact holds; they keep an agent from reading the general route as
  the standard's.
- Leave out any class, level or tool status: those are the standard's process to settle.
