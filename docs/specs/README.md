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

## The rules for a design in this repository

These rules are for the maintainers of this repository and its own designs only.

- There is one current design for each area. Edit it in place. Git holds every earlier version,
  and the commit that changes a decision says why.
- A design holds only the decisions that the code cannot show, and it names no model. It has no
  word limit: a design that grows is split by area, and no decision is cut to make it shorter
  (maintainer, 2026-10-04).
- The table of decisions has the columns Decision, Rejected alternative, Owner and Status. The
  Owner column holds `user` or `agent`. It says whose decision the row is. The Status column
  holds `open`, `assumed` or `decided`.
- A design points to the file that defines a contract, such as a schema or a module. It does not
  restate that file.
- A draft has `status: draft`. The top of a draft says what must happen before it lands. The rules
  above do not bind a draft until it lands.
- A design for a gate (a check whose verdict holds a turn, fails a run or refuses a write: the
  floor, the instruction audit, the finish check, a tickets refusal) states in its Outcome the
  one invariant the gate holds, in one sentence, and lists in its Edges the data each verdict
  reads and who can write it. A verdict rests on data the gated change can write only where the
  Edges say so. An exemption names what it exempts by its exact bytes or identity, never by one
  field, a shape or a syntax; a tightening is judged by its effect on what the gate catches. Each
  exemption row says which invariant it keeps and how. A change that adds an exemption or narrows
  a finding carries the independent review the `local` fragment names, and the pull request links
  it.
- Each finding of the release canary becomes a synthetic case in `tests/test_upgrade_corpus.py`,
  which installs each case with a previous release and upgrades it with this checkout, in the
  pull request that fixes the finding.
- A change to how the engine reads a file that an adopter owns (a default, a resolution rule, the
  meaning of a key) ships with a check that `adopt` runs at each install and upgrade and reports,
  and with an item under "Do these steps first" in the changelog that names each case the change
  moves, a key left out included. Only the adopter can change their file, so the upgrade is where
  they must first see that it reads differently. A test fixture that an engine change breaks is
  an adopter that the change breaks, so the change ships this check and this changelog step, not
  only the fixture fix. A new warning or finding states its hits on the canary (`make canary`)
  and on the tests before it merges, each hit true or false, and a false hit blocks the merge.

## Write a new design

Write a design only when later work relies on a decision that the code cannot show.

```sh
bash scripts/new-spec.sh <slug>
```

The script makes a design from `templates/spec/design.md` under `docs/specs/<slug>/`. Add
`--with-plan` to also copy `templates/spec/plan.md`. Do this only for work whose sequence or
resumption needs a plan.
