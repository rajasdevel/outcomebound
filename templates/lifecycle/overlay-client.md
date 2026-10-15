# Lifecycle overlay: client

A comparison for adoption. `adopt` never installs it, and the project owns every line it writes.
Propose a line below only where the project's committed text does not already lead an agent to the
decision the line changes; most lines are left out.

**Fits when** a client or a regulator accepts the work: a delivery for an outside party, with
acceptance by named people on a build. It goes on `solo`, `team` or `organization`, never on
`prototype`. Work that others use but nobody accepts on a build: no overlay. A stream of the same
project that no client accepts change by change, such as upkeep, is a separate stream and follows
the base lifecycle's route.

**Fragments it would select:** `client`, beside the base lifecycle's; `deploy` and `runtime` where
it runs a service; `db-migrations` where it changes stored data; `ci-release` where it publishes a package;
`tickets` where the project declares its own ticket store; the client's tracker is a source, read
through the `sync-tracker` skill. No `explore`.

**Scaffold set:** `+client` on the base's `--lifecycle` adds the delivery stream, the acceptance
gate with its owner left for the person to name, and the client route to `CONTRIBUTING.md`, which it
writes on `solo` too (`templates/scaffold/client/`).

## Example lines

```text
Exposure — <stream>: who can be hurt: <the client's users or the holders of the data> [observed
  <file>]; who accepts: <the named person or role who accepts, or "no person is named"> [observed
  <file>]; acts that cannot be undone: <a production deploy, a schema change in production, a
  machine identity> [observed <file>]; expected life: <...>; maintained by: <...>; agent-written
  share and review capacity: <...> [assumed].
Streams — <stream>: route in <the document the next person can open, or "private, held by <who>">;
  takes <kind of change>; fragments client.
Streams — upkeep: route in <the maintenance document>; takes <small fixes nobody accepts per build>.
Better means — <the project's measure, in its words, and any count it rejects>.
Gates — acceptance: owner <the client's named person>, evidence <their words, naming the build>.
Gates — production go: owner UNVERIFIED (no file names one); reported as a gap, never filled in.
Leave when — the contract ends or the client stops accepting builds (observable: <...>; watched by:
  <who>) → opens a brief to take the overlay off, or to retire: the build accepted last, the open
  tickets, the standing grants, any deploy in a partial phase, and what each item now owes.
Leave when — the client's acceptance moves to a regulator or a second party → opens a brief on
  the gates whose owner changes.
Changed — <date> (stream: <stream>): "<the person's words>", decided by <who>; retired "<old term>";
  invalidated <what no longer holds>. One line for each stream; it replaces the stream's older one.
```

## When to propose each line, and when to leave it out

- "Exposure —": propose it for a stream whose acts cannot easily be undone, or whose acceptance
  nobody names. Leave it out where the contract or the instructions already carry it.
- "Streams —": propose it where the route lives in a private or ignored file, naming who holds it,
  or where no route is written, as lines for the project's own document. Leave it out where the
  route is committed and the instructions point to it.
- "Better means —": propose it where the measure is private. Leave it out where a committed
  document states it.
- "Gates —": the line that earns most here. A gate without a named owner (acceptance, production
  go) is reported as a gap to the person; an agent never fills the owner, and its own pre-run is
  never the acceptance.
- "Leave when —": propose a row only where a transition is near and its signal can be watched.
- "Changed —": written after a complete directive or a person's answer to the transition brief, one line for each stream with the older one removed, never at adoption.

## A route example for a client delivery

Where the project has no written route, this is one to compare with and adapt into the project's
own document; it is not installed, and a project's own route wins. Each stage names who acts, and a
person decides only where the stage says so.

1. Intake (business, the agent drafts): call transcripts, data traces, stories and designs become a
   draft of the business part of the spec; each requirement is stated with its quote or inferred
   (the `gather-requirements` skill and its source kinds; a client's card through `sync-tracker`).
2. Business definition (business): rules, each with a wanted and an unwanted example. Gate: the
   client's named person accepts the outcome and the examples.
3. Shape (tech lead): the technical part of the spec, a design answer for each requirement, the
   hard-to-undo choices, each example mapped to a check, milestones with their basis.
4. Refine (developer): `explain-spec`, the open decisions as briefs, a ready check; a readiness
   sign-off is a step the project may require, not a gate.
5. Slice and hand off (tech lead): `slice-tickets`, each ticket naming the card; `hand-off-tickets`.
   The breakdown is accepted before it is published.
6. Build (implementer): tests that can fail, runtime evidence, the Done checks.
7. Review and land (tech): `land-change`; a technical sign-off by someone other than the author
   where the project requires one; merge and deploy to non-production under their grants.
8. Acceptance (business users): `run-acceptance` on the build the environment serves. Gate: the
   named acceptor accepts each change on that build.
9. Release (release authority): the accepted build is promoted, never rebuilt from a branch.
   Where a built artifact is promoted, it is promoted unchanged and the release commit only labels
   it; where the project deploys from source at a tag, the tagged commit may be a child of the
   accepted commit whose diff touches only the version and changelog files, and the record names
   both commits. A fix found here goes back to build and through acceptance. Gate: the
   production go.
10. Verify and close (tech and business): the result, Successful, Failed or Inconclusive; the
    business acceptance after the observation window; a closing note on the card.

Paths by kind of change: work with no code takes 1, 2, 8 where users must accept, and 10; a small
code change an existing check proves may skip design and slicing, and takes 1, 6, 7, 8, 9 and 10;
it skips 8 only where the contract puts the change in a stream nobody accepts (upkeep) or the
record shows that an existing acceptance covers the exact change on the exact build; a new area, a
shared system or personal data takes every stage with probes before the timeline; an emergency
takes 6, 7, 9 and 10, with the production go first and, where the project's emergency route puts
them there, the acceptance examples after the promotion.
