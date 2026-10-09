# Lifecycle: client

A comparison for adoption. `adopt` never installs it, and the project owns every line it writes.
Propose a line below only where the project's committed text does not already lead an agent to the
decision the line changes; most lines are left out.

**Fits when** a client or a regulator accepts the work: a delivery for an outside party, with
acceptance by named people on a build. Work that others use but nobody accepts on a build: use
`shared`. A stream of the same project that no client accepts change by change, such as upkeep, is
a separate stream and may fit `shared`.

**Fragments it would select:** `client`; `solo` or `team`; `deploy` and `runtime` where it runs a
service; `db-migrations` where it changes stored data; `ci-release` where it publishes a package;
`tickets` where the client's tracker or a store is the source. No `explore`.

## Example lines

```text
Exposure — <stream>: who can be hurt: <the client's users or the holders of the data> [observed
  <file>]; who accepts: <the named person or role who accepts, or "no person is named"> [observed
  <file>]; acts that cannot be undone: <a production deploy, a schema change in production, a
  machine identity> [observed <file>]; expected life: <...>; maintained by: <...>; agent-written
  share and review capacity: <...> [assumed].
Streams — <stream>: route in <the document the next person can open, or "private, held by <who>">;
  takes <kind of change>.
Better means — <the project's measure, in its words, and any count it rejects>.
Gates — acceptance: owner <the client's named person>, evidence <their words, naming the build>.
Gates — production go: owner UNVERIFIED (no file names one); reported as a gap, never filled in.
Leave when — the contract ends or the client stops accepting builds (observable: <...>; watched by:
  <who>) → opens a brief to move to `shared` or to retire: the build accepted last, the open
  tickets, the standing grants, any deploy in a partial phase, and what each item now owes.
Leave when — the client's acceptance moves to a regulator or a second party → opens a brief on
  the gates whose owner changes.
Changed — <date>: <what moved> by <who decided>; invalidated: <what no longer holds>.
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
- "Changed —": written after a person's yes on a transition, never at adoption.
