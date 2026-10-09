# Lifecycle: personal

A comparison for adoption. `adopt` never installs it, and the project owns every line it writes.
Propose a line below only where the project's committed text does not already lead an agent to the
decision the line changes; most lines are left out.

**Fits when** the tool is the person's own, or the owner and a few people they know use it, and a
failure harms no one but them. Others depend on it, or it holds their data, money or
accounts: use `shared`. A throwaway item needs no template.

**Fragments it would select:** `solo` (one maintainer), `explore` (when the first aim is to learn),
`workspace` and `commands` as the project already has them. No `team`, `deploy`, `ci-release` or
`client`. `db-migrations` only where stored data is changed.

## Example lines

```text
Exposure — who can be hurt: the owner [confirmed]; who accepts: the owner [confirmed]; acts that
  cannot be undone: <the one act, such as deleting the only copy of the data> [observed <file>];
  expected life: <to learn, then discard | to learn, then keep what the signal justifies, with the
  sacrificial parts named | the life of a product>; maintained by: the owner [confirmed]; agent-written
  share and review capacity: <the share, and who reads the diff> [assumed].
Better means — <the owner's own measure, in their words, such as "I use it every week without a
  workaround">.
Gates — <gate>: owner <the owner>, evidence <what they look at>.
Leave when — a second person starts to depend on it (observable: the owner says so, or a second
  author appears in the history; watched by: the owner) → opens a brief to move to `shared`:
  the work in flight, the standing grants and their end dates, and what each item now owes.
Leave when — nobody has used it since <the date the owner names> → opens a brief to retire it.
Changed — <date>: <what>, decided by <who>, invalidated <what no longer holds>.
```

## When to propose each line, and when to leave it out

- "Exposure —": propose it only for an act that cannot be undone and that no committed file names,
  or for a life that is not the default of a long-lived tool. Leave it out when the instructions
  already say who uses the tool and what must never be touched.
- "Streams —": leave it out. One stream with one owner has no route that needs a pointer.
- "Better means —": propose it where the measure is not written where an agent reads it and a
  change could trade it away; leave it out when the README states the aim.
- "Gates —": leave it out unless the owner wants a gate that no file shows. The owner is the only
  gate; a line that says so changes no decision.
- "Leave when —": propose the move to `shared` where the history shows a second author, an invited
  user or a public repository coming. Leave it out when none is near.
- "Changed —": write it only after a person's yes on a transition, never at adoption.
