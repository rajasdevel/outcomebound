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
- [floor](floor/design.md): the quality floor, `outcomebound floor`, and the plan runner `outcomebound validation`
  with its retained results and `validation status`; and, in its last section, this repository's
  own floor and CI.
- [tickets](tickets/design.md): the ticket layer, `outcomebound tickets`, including `tickets verify`.
- [decision-support](decision-support/design.md): how a decision, a lesson or a question goes to
  a person. The decision brief, `outcomebound brief`, its read-only lookups of recorded answers
  (`brief lookup`, `brief open`), and the explorable page, `outcomebound explorable`.
- [instructions](instructions/design.md): read-only checks on the instruction files of a project,
  `outcomebound instructions`.
- [finish-check](finish-check/design.md): retired in 1.7.0. `adopt` installs no hook; the design
  holds the reason, the way an install takes out the entries that 1.6.0 wrote, and the stub that
  the verb `outcomebound finish-check` is now. The result contract of `outcomebound validation`
  (`outcomebound_tools/validation.py`, plan schema `schemas/validation-plan.schema.json`), its
  retained results (`outcomebound_tools/validation_record.py`,
  `schemas/validation-result.schema.json`), `validation status` and the process control of
  `programs.py` are in the [floor](floor/design.md) design.
- [sources](sources/design.md): requirement sources, `outcomebound sources`. Import a markdown or
  text source into items, check the ledger that disposes of each item, and check the links of
  Markdown files (`sources links`).
- [review](review/design.md): the review file and `outcomebound review`: `check`, `sweep` and
  `since` hold that every finding ends in a disposition, and `council` asks reviewers of other
  harnesses and models for a read-only second opinion.
- [size](size/design.md): `outcomebound size`. How big a change is against a base, and what kind of
  lines it holds. Other verbs share its Git reader.
- [workspace](workspace/design.md): `outcomebound workspace audit`. A read-only report of the
  project's worktrees and which pass the mechanical removal rule.
- [research](research/design.md): the research repository. How the engine finds, prints and
  updates its clone, and how it takes findings back.

- [lifecycle](lifecycle/design.md): the complete lifecycle route, cross-area handoffs and the v1.5.0 qualification scope, and `outcomebound where`, the report of the work in flight. Area contracts stay in their current designs.
- [scaffold](scaffold/design.md): the scaffold verb. The project files of a lifecycle preset
  and its overlays, written once where absent, for a new project or a move.

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
- A retired design has `status: retired`. It keeps why the area went, what an upgrade from it does,
  and what remains of it in the engine.
- A design for a gate (a check whose verdict holds a turn, fails a run or refuses a write: the
  floor, the instruction audit, a tickets refusal) states in its Outcome the
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
