# Lifecycle: solo

A comparison for adoption. `adopt` never installs it, and the project owns every line it writes.
Propose a line below only where the project's committed text does not already lead an agent to the
decision the line changes; most lines are left out.

**Fits when** one person maintains a product, whatever the number of people who depend on it. Its
life starts with learning, kept or thrown away by what the signal shows: use `prototype`. A
second maintainer: use `team`. A throwaway item needs no template.

**Fragments it would select:** `solo`; `deploy` and `runtime` where it deploys a service;
`ci-release` where it publishes a package; `db-migrations` where it changes stored data;
`workspace` and `commands` as the project already has them. No `team` or `explore`. An outside
party that accepts the work adds `overlay-client`.

**Scaffold set:** for a new project, or a move the person accepted, `outcomebound scaffold .
--lifecycle solo --visibility <visibility>` writes the local fragment, the CI workflow and the
update-bot file, and `SECURITY.md` on a public repository (`templates/scaffold/solo/` and
`templates/scaffold/common/`).

## Example lines

```text
Exposure — who can be hurt: <the dependants, or the owner alone> [observed <file>]; who accepts:
  the owner [confirmed]; acts that cannot be undone: <the one act, such as deleting the only copy
  of the data> [observed <file>]; expected life: the life of a product; maintained by: one person
  (the owner) [confirmed]; agent-written share and review capacity: <the share, and who reads the
  diff> [assumed].
Better means — <the owner's own measure, in their words, such as "I use it every week without a
  workaround">.
Gates — <gate>: owner <the owner>, evidence <what they look at>.
Leave when — a second person starts to maintain it (observable: the owner says so, or a second
  author appears in the history; watched by: the owner) → opens a brief to move to `team`: the
  work in flight, the standing grants and their end dates, and what each item now owes.
Leave when — nobody has used it since <the date the owner names> → opens a brief to retire it.
Changed — <date> (stream: <stream>): "<the person's words>", decided by <who>; retired "<old term>";
  invalidated <what no longer holds>. One line for each stream; it replaces the stream's older one.
```

A change reaches the main branch by a pull request with CI green, the owner merges their own, and
the way back is a revert of the merge; human review is not required with one maintainer.

## When to propose each line, and when to leave it out

- "Exposure —": propose it for an act that cannot be undone and that no committed file names, or
  for dependants the README does not name. Leave it out when the instructions already say who uses
  the product and what must never be touched.
- "Streams —": leave it out. One stream with one owner has no route that needs a pointer.
- "Better means —": propose it where the measure is not written where an agent reads it and a
  change could trade it away; leave it out when the README states the aim.
- "Gates —": leave it out unless the owner wants a gate that no file shows. The owner is the only
  gate; a line that says so changes no decision.
- "Leave when —": propose the move to `team` where the history shows a second author coming.
  Leave it out when none is near.
- "Changed —": write it after a complete directive or a person's answer to the transition brief, one line for each stream with the older one removed, never at adoption.
