# Lifecycle: prototype

A comparison for adoption. `adopt` never installs it, and the project owns every line it writes.
Propose a line below only where the project's committed text does not already lead an agent to the
decision the line changes; most lines are left out.

**Fits when** the aim is to learn: the owner, or the few who build it, try an idea, then discard
it or keep what the signal justifies. Nobody depends on it but invited testers, and it holds no
real personal data and no production credential. The first outside user or real personal data
ends it: use `solo` or `team`. A throwaway item needs no template.

**Fragments it would select:** `explore`; `solo`, or `team` where several build it; `workspace`
and `commands` as the project already has them. No `deploy`, `ci-release`, `db-migrations` or
`client`.

**Scaffold set:** for a new project, `outcomebound scaffold . --lifecycle prototype` writes the
local fragment only (`templates/scaffold/prototype/` and `templates/scaffold/common/`).

## Example lines

```text
Exposure — who can be hurt: the owner and <the invited testers> [confirmed]; who accepts: the
  owner [confirmed]; acts that cannot be undone: none, with no real data and no production
  credential [confirmed]; expected life: to learn, then discard or keep what the signal
  justifies, with <the sacrificial parts> named; maintained by: one person (the owner)
  [confirmed]; agent-written share and review capacity: <the share, and who reads the diff>
  [assumed].
Better means — <an observable signal, such as what a tester does, not a feeling>.
Leave when — the first outside user or real personal data (observable: an invitation, a sign-in
  from outside, a data import; watched by: the owner) → opens a brief to move to `solo` or `team`
  that names the parts kept; probe code is rebuilt, never promoted.
Changed — <date> (stream: <stream>): "<the person's words>", decided by <who>; retired "<old term>";
  invalidated <what no longer holds>. One line for each stream; it replaces the stream's older one.
```

## When to propose each line, and when to leave it out

- "Exposure —": propose it where the expected life, the sacrificial parts or the absence of real
  data is not written where an agent reads it. Leave it out when the working note already says so.
- "Better means —": propose it where the signal sought is a feeling or is not written; the line
  names what a tester does.
- "Leave when —": propose it from the start; the end of a prototype is the signal most often
  missed.
- "Changed —": write it after a complete directive or a person's answer to the transition brief, one line for each stream with the older one removed, never at adoption.
