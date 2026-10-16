# Lifecycle: team

A comparison for adoption. `adopt` never installs it, and the project owns every line it writes.
Propose a line below only where the project's committed text does not already lead an agent to the
decision the line changes; most lines are left out.

**Fits when** two or more people in one team maintain a product that others depend on: outside
users, adopters of a package, personal data, money or accounts. Several teams, or owners by area:
use `organization`. One maintainer: use `solo`. A client accepts the work: add `overlay-client`.
A market, a safety standard or an audit adds `overlay-eu-market`, `overlay-safety-critical` or
`overlay-audit`, each tied to its own fact.

**Fragments it would select:** `team`; `deploy` and `runtime` where it runs a service;
`ci-release` where it publishes a package; `db-migrations` where it changes stored data;
`tickets` where a store is declared; `explore` only for a stream whose aim is to learn.

**Scaffold set:** for a new project, or a move the person accepted, `outcomebound scaffold .
--lifecycle team --visibility <visibility>` writes the local fragment, `CONTRIBUTING.md`, the CI
workflow, the update-bot file and `SECURITY.md` (`templates/scaffold/team/` and
`templates/scaffold/common/`).

## Example lines

```text
Exposure — <stream>: who can be hurt: <the users or the holders of the data> [observed <file>];
  who accepts: <the maintainers, or the reviewer a rule names> [observed <file>]; acts that cannot
  be undone: <for example database objects changed with no migration, where the only way back is
  a revert> [observed <file>]; expected life: <...>; maintained by: <...>; agent-written share and
  review capacity: <the share, and whether review keeps up with it> [assumed].
Streams — <stream>: route in <the document the next person can open, or "private, held by <who>">;
  takes <kind of change>.
Better means — <the project's measure, in its words>.
Gates — review: owner one human who is neither the author nor the person who directed the agent,
  evidence their approval in the platform; an AI review, where the change warrants one, runs
  before it and never counts as that approval; no one, admins included, bypasses it.
Gates — <gate>: owner UNVERIFIED (no file names one); reported as a gap, never filled in.
Leave when — several teams, or owners by area (observable: <a second team in the history, or the
  owner's word>; watched by: <who>) → opens a brief to move to `organization`.
Leave when — one maintainer is left, or the owner says it serves only themselves → opens a brief
  to move back to `solo`: which gates and standing grants end, and what is retired.
Changed — <date> (stream: <stream>): "<the person's words>", decided by <who>; retired "<old term>";
  invalidated <what no longer holds>.
```

## When to propose each line, and when to leave it out

- "Exposure —": propose it for a stream whose acts cannot easily be undone and that no committed
  file names. Leave it out where the instructions already carry it; the facts a fragment selects
  from are then in the install report, not in a second place.
- "Streams —": propose it only where a stream has no written route, as lines for the project's own
  document, and then point to that document. Where the route is written and committed, leave it out.
  A route in an ignored file dangles for the next person: name who holds it.
- "Better means —": propose it where the measure is not written where an agent reads it.
- "Gates —": propose the review line where the route does not state its three controls. Propose
  another gate where it has no named owner, and report the gap. Leave it out where it repeats the
  declared edges or the instructions.
- "Leave when —": the right side is the brief to open and what it inventories, mostly the work in
  flight, not a fragment diff. Propose a row only where its signal can be watched and a transition
  is near; leave out a row that fires on a decision that already reaches the owner.
- "Changed —": written after a complete directive or a person's answer to the transition brief, one line for each stream with the older one removed, never at adoption.
