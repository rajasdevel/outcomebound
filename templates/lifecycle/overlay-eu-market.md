# Lifecycle overlay: eu-market

A comparison for adoption. `adopt` never installs it, and the project owns every line it writes.
Propose a line below only where the project's committed text does not already lead an agent to the
decision the line changes; most lines are left out.

**Fits when** the person states that the product is placed on the EU market in a commercial
activity. That fact, not the size of the team, is what Regulation (EU) 2024/2847 follows; whether
the Regulation reaches the product is the person's to decide, with legal advice, and no line here
decides it. It goes on `solo`, `team` or `organization`, never on `prototype`.

**Fragments it would select:** none of its own.

**Scaffold set:** `+eu-market` adds the local lines of `templates/scaffold/eu-market/local.md`,
which name the reporting deadlines and the documentation period with their source and the day they
were read; the edge `rewriting published history`; a coordinated disclosure block in `SECURITY.md`,
which it writes on a private `solo` too; and rows for the design's decision table (the
cybersecurity risk assessment, the due diligence on third-party components, the support period).

## Example lines

```text
Context: the person stated the trigger; whether the Regulation reaches the product is theirs, with
  legal advice; conformity is the manufacturer's own assessment, which no file here makes.
Gates — the report of an actively exploited vulnerability or a severe incident: owner UNVERIFIED
  (no file names one); reported as a gap, never filled in.
Completion bar: each release publishes an SBOM of at least its top-level dependencies.
```

## When to propose each line, and when to leave it out

- The trigger line: propose it once the person has stated the fact; the scope question itself goes
  to the person as a decision brief.
- The reporting gate: propose it where no route names who reports; its owner is the person's to
  name.
- The SBOM line: propose it where releases are published and no step makes one.
- Leave out every claim of conformity: a file can hold evidence and point to a duty, never meet it.
