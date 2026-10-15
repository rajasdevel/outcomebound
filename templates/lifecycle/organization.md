# Lifecycle: organization

A comparison for adoption. `adopt` never installs it, and the project owns every line it writes.
Propose a line below only where the project's committed text does not already lead an agent to the
decision the line changes; most lines are left out.

**Fits when** several teams maintain the product, or owners hold areas of it, and many people or
other teams depend on it. One team owns every area: use `team`. An audit of the controls adds
`overlay-audit`; it is not part of this lifecycle.

**Fragments it would select:** as `team`: `team`; `deploy` and `runtime`, `ci-release`,
`db-migrations` and `tickets` by fact.

**Scaffold set:** for a new project, or a move the person accepted, `outcomebound scaffold .
--lifecycle organization --visibility <visibility>` writes what `team` writes, with the emergency
path and a disclosure policy; `--with codeowners` and `--with pr-template` write the code owners
file and the pull request template (`templates/scaffold/organization/`, `templates/scaffold/team/`
and `templates/scaffold/common/`).

## Example lines

```text
Exposure — <stream>: who can be hurt: <the users, the other teams, the holders of the data>
  [observed <file>]; who accepts: <the owners of each area> [observed <file>]; acts that cannot be
  undone: <...> [observed <file>]; expected life: <...>; maintained by: <the teams>;
  agent-written share and review capacity: <the share, and whether review keeps up with it>
  [assumed].
Streams — <stream>: route in <the document the next person can open>; takes <kind of change>.
Gates — review: owner one human who is neither the author nor the person who directed the agent,
  evidence their approval in the platform; an AI review runs first and never counts as that
  approval; no one, admins included, bypasses it.
Gates — code-owner review: owner <the owners of each area, or UNVERIFIED (no file names them)>,
  where a branch rule enforces it.
Agents act under their own identity with a scoped token, never an admin token, and their actions
  and approvals are logged.
The emergency path is the route's normal path made fast, with its review recorded after.
Leave when — one team owns every area (observable: <...>; watched by: <who>) → opens a brief to
  move back to `team`: which gates and standing grants end.
Changed — <date> (stream: <stream>): "<the person's words>", decided by <who>; retired "<old term>";
  invalidated <what no longer holds>. One line for each stream; it replaces the stream's older one.
```

## When to propose each line, and when to leave it out

- "Exposure —" and "Streams —": as for `team`.
- "Gates —": propose the code-owner line only where a branch rule enforces code-owner review; a
  code owners file without the rule binds nothing. A gate with no named owner is reported as a gap.
- The agent identity line: propose it where agents hold any token; leave it out where the route
  already says so.
- The emergency path: propose it where the route has none; an emergency is not a reason to skip
  the production go.
- "Leave when —" and "Changed —": as for `team`.
