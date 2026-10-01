# Kernel and skill evals

These evals measure whether the operating-contract kernel, and each skill an install carries,
change what a model does. codex carries out each fixture's task in a disposable repository
under one of four arms, and deterministic post-checks read what it left: files, commits, the
commands its transcript records, and its answer. The post-checks are the verdict; no model
grades another.

## The arms

- `earlier`: an earlier wording of the kernel, kept in `evals/arms/earlier-kernel.md`.
- `current`: what `outcomebound adopt --harness codex` installs from this checkout:
  `templates/managed-block.agents.md.tmpl` rendered as adopt renders it; each skill that
  install carries, its whole folder, at the skill path `adapters/harnesses.json` gives codex,
  `.agents/skills/`; and this checkout's `scripts/outcomebound`, as `outcomebound`, first on
  the PATH codex and the model's commands get. Every install carries `using-outcomebound`,
  `decision-brief`, `gather-requirements` and `tests-worth-keeping`. A fixture whose
  `fragments` file names fragments, one id a line, installs as adopt does with those selected,
  so it carries their skills too: the `tickets` fragment adds `slice-tickets`. The fixture's
  `AGENTS.md` carries the project facts and the guidance pointers adopt writes, each skill's
  pointer with its condition, in place of the note's own line sending the model to the core
  skill.
- `unsized`: `current` without the kernel's sizing paragraph, the one that opens "Satisfy all
  four completely". Against `current`, it measures whether that paragraph, which every install
  loads, changes what a model does.
- `none`: the task alone. No kernel, no skill and no launcher; each fixture's note loses its
  sentence pointing at the core skill, which is not installed. Against `current`, it measures
  what OutcomeBound's text adds at all.

The prompt is the arm's block, `Task:`, and the fixture's `prompt.md`; the `none` arm's is
`Task:` and the prompt. In the earlier and current arms each fixture installs this checkout's
core skill and writes its own project note. That core skill points to the `decision-brief`
skill, which only the current and unsized arms install, so under earlier the core skill names
a skill that arm does not carry. The current arm's skills are written into the
fixture before its `setup.sh` runs, so they are in the seed commit and in any baseline the setup
records: no post-check counts them as the model's change, and the run refuses a fixture whose
setup did not commit them. They are protected like the graders. An `outcomebound` already on
your PATH reaches the earlier and none arms too; each run records the one its calls resolve as
`outcomebound_on_path`.

## The fixtures

- `small-fix`, fix a date bug: the test passes; only the helper and its test changed,
  uncommitted; no spec or goal file; no full-check or release script ran; the absent lint is
  reported `UNVERIFIED`.
- `dirty-review`, critique a parser read-only: the worktree is unchanged; `parser.py` was
  read; the answer names the document's contradiction; every cited `path:line` exists.
- `long-run`, carry out a bounded migration: the migration is done; only `src/` and the goal
  document changed, and not above its Progress section; the excluded release script never ran.
- `decision`, set out the person's decision: nothing changed; the compatibility document and
  the history were read; the answer is a decision brief.

Each skill has one fixture whose checks read the behaviour the skill is for:

- `unclear-outcome`, for `gather-requirements`: show each reminder's due date, and hold each
  person to five reminders, which can refuse a sixth or drop the oldest. The due dates show,
  in UTC as the project note says; adding a sixth loses none of the five; a reading of the cap
  that was built is named in the answer as a choice the person may reverse, or, with none built,
  a decision brief names the cap; no question in the answer asks how a date is written.
- `test-worth-keeping`, for `tests-worth-keeping`: add the regression test for a committed
  fix, beside a calendar test that already fails. With the seed's `money.py` no other test
  fails, and with `money.py` as it was before the fix some other test fails an assertion; the
  failing calendar test is unchanged and still runs and fails; the answer says it failed
  before the change.
- `slice-a-spec`, for `slice-tickets`: break a short design into ticket drafts. The drafts
  read PASS under `tickets check --draft`; there is exactly one, the count the skill's sizing
  rule gives a design of one outcome with no edge, no decision between and one implementer;
  each draft names bounds, and each is a path the seed holds.

The ladder asks whether the work a run does follows what its task needs. Its four
fixtures share one repository, `evals/fixtures/ladder/base.sh`: a small shop's stock list over
SQLite, with numbered migrations, unit tests, a copy of the shop's stock, and a
`CONTRIBUTING.md` and `docs/` that invite a design note, a decision record, the full suite and
a review for every change. Each rung plants one task, and a probe the model cannot edit judges
it through the command line against a database of its own:

- `ladder-1-message`: a misspelt word in a refusal. The refusal reads right; no process
  document is created.
- `ladder-2-last-units`, the overengineering trap: a two-character comparison bug. The last
  units can be taken and no more; no process document is created, and the slow integration
  suite does not run.
- `ladder-3-reorder-list`: a `--below N` option across the command line and the store. It lists
  the right items; no process document is created.
- `ladder-4-cents`, the underengineering trap: prices move to integer cents. A new database
  keeps them as cents and prints them as before; and the stock recorded before the change
  survives the workspace's own migrations. The unit tests build a new database, so rewriting
  the first migration passes them and loses the recorded stock.

Each rung's first probe also prints what the run did beyond its change as `observed:` lines
(`evals/fixtures/ladder/footprint.py`): files and lines changed, files and process documents
created, test and full-suite runs, migrations run, commits, and questions put to the person.
The runner records each run's tokens and seconds, and `--summary` prints their medians.

The ticket fixture's graders run this checkout's engine from `PYTHONPATH`, never an
`outcomebound` found on PATH. What a skill does for an adopter is read as the current arm
against the `none` arm, for that skill's fixture.

The brief check requires only an id and the question in one line, options A and B, a
recommendation naming one, and whether it can be undone, in emoji or ASCII marks. Downsides
and a diagram are printed as `observed:` lines and never fail a run: the earlier arm's kernel
does not ask for them.

The runner hashes each fixture's graders, and reads its seed commit, before the model runs;
a changed grader fails the run unexecuted.

## Running the runs

The model is always named: a run without `--model` is refused before anything is built, and
the runner passes the model to codex with `-m`, so codex's configured default never runs.

First: `codex login status` says `Logged in using ChatGPT`, and the checkout is clean.

```bash
MODEL=<model>   # one model for every run
for repetition in 1 2 3; do
  for arm in earlier current; do
    python3 evals/run.py --arm "$arm" --model "$MODEL" --repetition "$repetition"
  done
done
```

Each invocation runs the eleven fixtures, one codex call each: 66 runs for the two arms above,
and 33 more for each other arm. The ladder's measurement is its four fixtures under
`current`, `unsized` and `none`, three repetitions each: 36 runs. `--fixtures` narrows it, `--effort` sets codex's reasoning
effort (default `medium`), and `--out` names the run directory (default
`evals/results/raw/<id>/`, git-ignored). Fixture repositories are kept in
a temporary directory, or under `OUTCOMEBOUND_FIXTURE_ROOT`, which belongs outside any Git
checkout.

No API key or endpoint override reaches codex or the model's commands. The runner exits 3
without a ChatGPT login, 2 when it refuses its options, and 1 when a call failed: codex
erred, gave no final message, or reported another model. A failed call is recorded, never
retried.

## Reading a result

```bash
python3 evals/run.py --summary evals/results/raw
```

For each fixture, arm and model, this prints how many runs PASS the verdict and each claim,
then each run's observations; its last lines flag runs that are not comparable. Compare the
arms within one fixture. Three runs an arm cannot show a small effect: a claim that moves
from 0/3 to 3/3 is worth a closer look, and anything smaller is not shown.

Per fixture, a run directory holds `prompt.md` (exactly what codex read), `answer.md`,
`transcript.txt` (codex's output, then the post-checks') and `meta.json` (verdict, claims,
observations, arm, model, commit, and the arm's contents: the kernel's digest, the digest of
each file that fixture's install wrote, the launcher, and the `outcomebound` its calls
resolve). Runs of one fixture that installed different files are flagged as not comparable.
A PASS establishes only what its check reads, for that model on that day.

Recorded results, each with the scope it covers, are in
[`docs/research/practices/evaluations.md`](../docs/research/practices/evaluations.md).
