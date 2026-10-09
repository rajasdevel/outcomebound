# Lifecycle: shared

A comparison for adoption. `adopt` never installs it, and the project owns every line it writes.
Propose a line below only where the project's committed text does not already lead an agent to the
decision the line changes; most lines are left out.

**Fits when** others depend on the work: outside users, adopters of a package, personal data, money
or accounts. Regulated work (health, finance, safety, infrastructure) is `shared` plus the
new-project reference's decision brief for each compliance choice. A client or a regulator accepts
the work: use `client`. The tool is the person's own: use `personal`.

**Fragments it would select:** `solo` for one maintainer or `team` for two or more or required
review; `deploy` and `runtime` where it runs a service; `ci-release` where it publishes a package;
`db-migrations` where it changes stored data; `tickets` where a store is declared; `explore` only
for a stream whose aim is to learn. No `client`.

## Example lines

```text
Exposure — <stream>: who can be hurt: <the users or the holders of the data> [observed <file>];
  who accepts: <the maintainer, or the reviewer a rule names> [observed <file>]; acts that cannot
  be undone: <for example database objects changed with no migration, where the only way back is
  a revert> [observed <file>]; expected life: <...>; maintained by: <...>; agent-written share and
  review capacity: <the share, and whether review keeps up with it> [assumed].
Streams — <stream>: route in <the document the next person can open, or "private, held by <who>">;
  takes <kind of change>.
Better means — <the project's measure, in its words>.
Gates — <gate>: owner <role>, evidence <kind>.
Gates — <gate>: owner UNVERIFIED (no file names one); reported as a gap, never filled in.
Leave when — a client or a regulator starts to accept the work (observable: <a contract file, a
  tracker field, or the owner's word>; watched by: <who>) → opens a brief to move to `client`:
  the open tickets, the worktrees with uncommitted work, the open briefs, the standing grants, and
  what each item now owes.
Leave when — the last outside user is gone, or the owner says it serves only themselves → opens a
  brief to move back to `personal`: which gates and standing grants end, and what is retired.
Leave when — a resume finds worktrees with uncommitted work and nothing landed → asks whether the
  pause is deliberate before any step is planned again.
Changed — <date>: <what moved> by <who decided>; invalidated: <what no longer holds>.
```

## When to propose each line, and when to leave it out

- "Exposure —": propose it for a stream whose acts cannot easily be undone and that no committed
  file names. Leave it out where the instructions already carry it; the facts a fragment selects
  from are then in the install report, not in a second place.
- "Streams —": propose it only where a stream has no written route, as lines for the project's own
  document, and then point to that document. Where the route is written and committed, leave it out.
  A route in an ignored file dangles for the next person: name who holds it.
- "Better means —": propose it where the measure is not written where an agent reads it.
- "Gates —": propose it where a gate has no named owner, and report the gap. Leave it out where it
  repeats the declared edges or the instructions.
- "Leave when —": the right side is the brief to open and what it inventories, mostly the work in
  flight, not a fragment diff. Propose a row only where its signal can be watched and a transition
  is near; leave out a row that fires on a decision that already reaches the owner.
- "Changed —": written after a person's yes on a transition, never at adoption.
