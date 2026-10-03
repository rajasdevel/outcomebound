# Designs

A design records the decisions about one area that the code cannot show. Read the design for the
area you plan to change before you change it. If a shipped file and the design disagree, the
shipped file is the defect, unless the decision itself changed. In that case, edit the design in
the same change.

## Find a design

- [install](install/design.md): `outcomebound adopt`. Install, upgrade, check and remove.
- [distribution](distribution/design.md): how `outcomebound` reaches an adopter. The package, its
  build and the launcher.
- [skills](skills/design.md): which skills ship, to whom, and the bar that each one meets.
- [floor](floor/design.md): the quality floor, `outcomebound floor`.
- [tickets](tickets/design.md): the ticket layer, `outcomebound tickets`.
- [decision-brief](decision-brief/design.md): how a decision goes to a person,
  `outcomebound brief`.
- [instructions](instructions/design.md): read-only checks on the instruction files of a project,
  `outcomebound instructions`.
- [finish-check](finish-check/design.md): at the stop hook of `claude-code` and `codex`, the
  recorded Done commands run, and a failure goes back to the agent. The verb is
  `outcomebound finish-check`.
- [research](research/design.md): the research repository. How the engine finds, prints and
  updates its clone, and how it takes findings back.

## The rules for a design

- There is one current design for each area. Edit it in place. Git holds every earlier version,
  and the commit that changes a decision says why.
- A design has at most 1,500 words, and it names no model.
- The table of decisions has the columns Decision, Rejected alternative, Owner and Status. The
  Owner column holds `user` or `agent`. It says whose decision the row is. The Status column
  holds `open`, `assumed` or `decided`.
- A design points to the file that defines a contract, such as a schema or a module. It does not
  restate that file.
- A draft has `status: draft`. The top of a draft says what must happen before it lands. The rules
  above do not bind a draft until it lands.

## Write a new design

Write a design only when later work relies on a decision that the code cannot show.

```sh
bash scripts/new-spec.sh <slug>
```

The script makes a design from `templates/spec/design.md` under `docs/specs/<slug>/`. Add
`--with-plan` to also copy `templates/spec/plan.md`. Do this only for work whose sequence or
resumption needs a plan.
