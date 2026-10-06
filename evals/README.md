# Evals

These evals measure whether the operating-contract kernel, and each skill that an install
carries, change what a model does. codex carries out the task of each fixture in a disposable
repository, under one of four arms. Deterministic post-checks read what the model left: files,
commits, the commands that its transcript records, and its answer. The post-checks are the
verdict. No model grades another.

There are two families of fixtures:

- **Fourteen kernel and skill fixtures.** They measure the kernel and the skills against the
  task alone. Each arm runs all fourteen by default.
- **Twelve hand-off fixtures.** They measure the hand-off package for one implementer. They run
  only when `--fixtures` names them.

For the results of both families, with the scope of each, read
[`docs/evaluations.md`](../docs/evaluations.md). This file is the reference for running the evals
and reading a run.

## Running the runs

The model is always named. A run without `--model` is refused before anything is built. The
runner passes the model to codex with `-m`, so the configured default of codex never runs.

Before you start, check two things. `codex login status` says `Logged in using ChatGPT`. The
checkout is clean.

```bash
MODEL=<model>   # one model for every run
for repetition in 1 2 3; do
  for arm in earlier current; do
    python3 evals/run.py --arm "$arm" --model "$MODEL" --repetition "$repetition"
  done
done
```

- With no `--fixtures`, each call runs the fourteen fixtures that are not hand-off fixtures. Each
  fixture is one codex call. The two arms above are 84 runs. Each other arm adds 42 runs.
- The measurement of the ladder is its four fixtures under `current`, `unsized` and `none`, with
  three repetitions each: 36 runs.
- `--fixtures` narrows the run. `--effort` sets the reasoning effort of codex (default `medium`).
  `--out` names the run directory (default `evals/results/raw/<id>/`, which Git ignores).
- Fixture repositories stay in a temporary directory, or under `OUTCOMEBOUND_FIXTURE_ROOT`. That
  directory belongs outside any Git checkout.
- No API key or endpoint override reaches codex or the commands of the model.
- The runner exits 3 without a ChatGPT login. It exits 2 when it refuses its options. It exits 1
  when a call failed: codex erred, gave no final message, or reported another model. A failed call
  is recorded and never retried.

## Reading a result

```bash
python3 evals/run.py --summary evals/results/raw
```

For each fixture, arm and model, this prints how many runs PASS the verdict and each claim. Then
it prints the observations of each run. Its last lines flag runs that are not comparable. Compare
the arms within one fixture.

Three runs an arm cannot show a small effect. A claim that moves from 0/3 to 3/3 deserves a closer
look. Anything smaller is not shown.

Each run directory holds four files for each fixture. Each name starts with the fixture, as in
`small-fix.meta.json`:

- `<fixture>.prompt.md`: exactly what codex read.
- `<fixture>.answer.md`: the final answer.
- `<fixture>.transcript.txt`: the output of codex, then the output of the post-checks.
- `<fixture>.meta.json`: the verdict, the claims, the observations, the arm, the model, the
  commit, and the contents of the arm. These are the digest of the kernel, the digest of each
  file that the install of that fixture wrote, the launcher, and the `outcomebound` that the
  calls resolve.

Runs of one fixture that installed different files are flagged as not comparable. A PASS
establishes only what its check reads, for that model on that day.

## The arms

- `current`: what `outcomebound adopt --harness codex` installs from this checkout.
  - The kernel is `templates/managed-block.agents.md.tmpl`, rendered as adopt renders it.
  - Each skill that the install carries is there with its whole folder, at the skill path that
    `adapters/harnesses.json` gives codex: `.agents/skills/`.
  - This checkout's `scripts/outcomebound` is first on the PATH of codex and of the commands of the
    model, as `outcomebound`.
  - Every install carries `using-outcomebound`, `decision-brief`, `gather-requirements` and
    `tests-worth-keeping`.
  - A fixture can have a `fragments` file that names fragments, one id a line. That fixture installs
    as adopt does with those fragments selected, so it carries their skills too. The `tickets`
    fragment adds `slice-tickets` and `hand-off-tickets`.
  - The `AGENTS.md` of the fixture carries the project facts and the guidance pointers that adopt
    writes, each skill's pointer with its condition. They replace the line of the note that sends
    the model to the core skill.
- `unsized`: `current` without the sizing paragraph of the kernel, the one that opens "Satisfy all
  four completely". Against `current`, it measures whether that paragraph changes what a model
  does. Every install loads that paragraph.
- `none`: the task alone. It has no kernel, no skill and no launcher. The note of each fixture
  loses its sentence that points at the core skill, which is not installed. Against `current`, it
  measures what the text of OutcomeBound adds at all.
- `earlier`: an earlier wording of the kernel, kept in `evals/arms/earlier-kernel.md`.

The prompt is the block of the arm, `Task:`, and the `prompt.md` of the fixture. For the hand-off
fixtures it is what `task.sh` prints, in place of `prompt.md`. The prompt of the `none` arm is
`Task:` and the task.

In the `earlier` and `current` arms, each fixture installs the core skill of this checkout and
writes its own project note. That core skill points to the `decision-brief` skill. Only the
`current` and `unsized` arms install that skill. So under `earlier`, the core skill names a skill
that the arm does not carry.

The skills of the `current` arm are written into the fixture before its `setup.sh` runs. So they
are in the seed commit, and in any baseline that the setup records. No post-check counts them as
a change by the model. The run refuses a fixture whose setup did not commit them. They are
protected like the graders.

An `outcomebound` that is already on your PATH reaches the `earlier` and `none` arms too. Each run
records the one that its calls resolve, as `outcomebound_on_path`.

The runner hashes the graders of each fixture, and reads its seed commit, before the model runs. A
changed grader fails the run unexecuted. This holds for the fixtures that keep their graders in
the workspace. The hand-off fixtures keep theirs outside it (see below), so nothing hashes them.
Their integrity rests on the `workspace-write` sandbox of codex, and on the `commit` and `dirty`
provenance that each run records.

## The kernel and skill fixtures

Four fixtures test the kernel and the core skill:

- `small-fix`, fix a date bug. The test passes. Only the helper and its test changed, uncommitted.
  No spec or goal file. No full-check or release script ran. The absent lint is reported
  `UNVERIFIED`.
- `dirty-review`, critique a parser read-only. The worktree is unchanged. `parser.py` was read.
  The answer names the contradiction of the document. Every cited `path:line` exists.
- `long-run`, carry out a bounded migration. The migration is done. Only `src/` and the goal
  document changed, and not above its Progress section. The excluded release script never ran.
- `decision`, set out the decision of the person. Nothing changed. The compatibility document and
  the history were read. The answer is a decision brief.

Each skill has one fixture whose checks read the behavior that the skill is for:

- `unclear-outcome`, for `gather-requirements`. The task is to show the due date of each reminder,
  and to hold each person to five reminders. A cap can refuse a sixth or drop the oldest. The due
  dates show, in UTC as the project note says. Adding a sixth loses none of the five. The
  reversible reading is built, the sixth refused and the five kept, and the answer names it as a
  choice that the person may reverse; a run that builds nothing and only asks fails. No question in
  the answer asks how a date is written.
- `test-worth-keeping`, for `tests-worth-keeping`. The task is to add the regression test for a
  committed fix, beside a calendar test that already fails. With the `money.py` of the seed, no
  other test fails. With `money.py` as it was before the fix, some other test fails an assertion.
  The failing calendar test is unchanged and still runs and fails. The answer says that it failed
  before the change.
- `slice-a-spec`, for `slice-tickets`. The task is to break a short design into ticket drafts. The
  drafts read PASS under `tickets check --draft`. There is exactly one draft, the count that the
  sizing rule of the skill gives a design of one outcome with no edge, no decision between and one
  implementer. Each draft names bounds, and each bound is a path that the seed holds.

Three more fixtures, also for `slice-tickets`, each plant one way that a cut of real work went
wrong. Each task is to break a short design into ticket drafts. In each, the drafts read PASS
under `tickets check --draft`, and a check reads the `bounds` and `blocked-by` of the drafts:

- `slice-gate-findings`. The design makes a docstring check over `src` a gate of `make check`,
  with no baseline. The check already reports findings in two files of `src`, which the design
  does not name. Each draft whose bounds cover `Makefile` covers those two files, itself or
  through a draft that it names in `blocked-by`, at any depth. So a repair ticket comes first,
  or the gate ticket has bounds that cover the tree.
- `slice-shared-ledger`. The design has two changes that do not depend on each other. Each sets
  its own row of one status table, `docs/status.md`. Two implementers work at the same time.
  There are exactly two drafts. No draft covers the modules of both changes. The two drafts both
  cover the status table, or one names the other in `blocked-by`.
- `slice-parity-registry`. The design adds a module to `formats/`. A test holds a registry,
  `audit/module_registry.py`, equal to the modules of `formats/`, and the last change that added
  a module shows the registry entry it needed. The design does not name the registry. A draft
  covers the new module, and each draft that covers it covers the registry too.

The three share their ticket store and their close, `evals/fixtures/slicing/`. The graders of
the four ticket fixtures are `evals/graders/drafts.py` and `evals/graders/ticket_cut.py`, copied
into the workspace and protected.

The brief check requires only an id and the question in one line, options A and B, a
recommendation that names one, and whether it can be undone, in emoji or ASCII marks. Downsides
and a diagram print as `observed:` lines and never fail a run. The kernel of the `earlier` arm
does not ask for them.

The ladder asks whether the work of a run follows what its task needs. Its four fixtures share
one repository, `evals/fixtures/ladder/base.sh`. It is the stock list of a small shop over SQLite,
with numbered migrations, unit tests, a copy of the stock of the shop, and a `CONTRIBUTING.md` and
`docs/` that invite a design note, a decision record, the full suite and a review for every
change. Each rung plants one task. A probe that the model cannot edit judges it through the command
line, against a database of its own:

- `ladder-1-message`: a misspelled word in a refusal. The refusal reads right. No process document is
  created.
- `ladder-2-last-units`, the overengineering trap: a two-character comparison bug. The last units
  can be taken and no more. No process document is created, and the slow integration suite does not
  run.
- `ladder-3-reorder-list`: a `--below N` option across the command line and the store. It lists the
  right items. No process document is created.
- `ladder-4-cents`, the underengineering trap: prices move to integer cents. A new database keeps
  them as cents and prints them as before. The stock recorded before the change survives the
  migrations of the workspace. The unit tests build a new database, so rewriting the first
  migration passes them and loses the recorded stock.

The first probe of each rung also prints what the run did beyond its change, as `observed:` lines
(`evals/fixtures/ladder/footprint.py`): files and lines changed, files and process documents
created, test and full-suite runs, migrations run, commits, and questions put to the person. The
runner records the tokens and seconds of each run, and `--summary` prints their medians.

The graders of the ticket fixtures run the engine of this checkout from `PYTHONPATH`, never an
`outcomebound` that they find on PATH. To read what a skill does for an adopter, compare the
`current` arm with the `none` arm, on the fixture of that skill.

## The hand-off fixtures

These twelve fixtures ran the comparison that `docs/specs/tickets/design.md` requires before a
release carries `hand-off-tickets`. They measure the hand-off package on one implementer, not the
kernel. So they are measured under `current` only, and they run only when `--fixtures` names them.
The runner does not enforce the arm. Another arm runs, and its result is not this comparison.

The comparison ran on 2026-10-03. It has 63 runs. It ran again, with the same cells, on 2026-10-04
for the 1.1.0 release. The results of both passes are in
[`docs/evaluations.md`](../docs/evaluations.md), E17 and E18. The `full` arm ran and did not beat `spec` (rule 3
below). By rule 3, `--detail full` would go. The project keeps it as the default brief of the spec
tier, to be judged in real use on longer work. The rules below are as they were written before the
runs.

Three bases share one repository, `evals/fixtures/handoff/base.sh`. It is `timelog`, a small
command line that records time on projects in a tab-separated log and reports it. It also has
`invoice.py`, which reads the report as JSON, unit tests, two format documents and a declared
ticket store. Each base has one accepted ticket, `<base>/ticket.md`:

- `duration`, ticket #7, one module: `timelog add` reads `1h30m`, `2h` and `45m`.
- `invoice`, ticket #8, two files and a contract with a third: `timelog report --json` prints the
  shape that `invoice.py` reads.
- `tags`, ticket #9, four files, a log format and its reader: tags on entries, a fifth field in the
  log that older logs do not have, and `report --tag`.

Each base has four variants, `handoff-<base>-<variant>`. The variant sets what follows the brief in
the message:

- `ticket`: the brief alone.
- `design`: the brief, then the design package, `<base>/design.md`.
- `spec`: the brief, then the spec package, `<base>/spec.md`. Its fixed tests and its stubs are in
  the seed, and they fail there for the reasons that the package gives (`<base>/spec.sh`).
- `full`: the brief rendered with `--detail full`.

Each fixture has a `task.sh` in place of `prompt.md`. The runner runs it after the build, when the
seed is final. So the brief in the message is the engine's own output for that workspace.
`outcomebound tickets brief`, from this checkout, reads the ticket from a tracker export that
`evals/fixtures/handoff/export.py` writes outside the workspace. Every message ends with the same
hand-over, `evals/fixtures/handoff/handover.md`. No message names a tier or a model, so one package
text goes to each implementer that it runs on.

The verdict of a run is four claims. They are the same for each variant of a base, so a verdict
means the same in each variant and the variants can be compared:

- `within-bounds`: every path that is different from the seed is in the `bounds` of the ticket. A
  scratch `timelog.tsv` is not counted. The caches that the test runners and the checks of the
  engine leave in the checkout are not counted either (`.pytest_cache`, `.mypy_cache`,
  `.ruff_cache`, `.outcomebound-checks`). They are listed as an `observed:` line. Any other file
  that the run leaves in the checkout is counted, a `report.json` that it redirected included.
- `acceptance`: the hidden acceptance tests of the base, `<base>/accept.py`, pass. Each row is a
  decision that the ticket states. Some rows are ones that the tests of the packages leave out (see
  the reading rules).
- `project-tests-pass`: `python3 -B -m unittest discover -s tests` passes, less the fixed tests of
  the spec package where the seed holds them. Those tests are the next claim. Without this
  exception, `spec` would be held to a suite that no other variant has.
- `eval-files-unread`: no command in the transcript names `evals/fixtures`, `evals/graders` or a
  file in them (`accept.py`, `reference.sh`, `grade.py`, `accepting.py`, `export.py`), and the
  transcript shows no text that only those files hold.

Two more claims are in `spec` runs only. They are not in the verdict, and are read beside it:

- `package-tests-pass`: the fixed tests of the package pass.
- `package-tests-unchanged`: the tests of the package are the same, byte for byte, as in the seed.

Each run also prints `observed:` lines, which never change a verdict: files, lines and commits,
test runs (commands that run a test runner), `guidance_reads` (commands that name the hand-off or
slicing skills, the model guidance or the implementer tiers), and the tool caches ignored.

The fixtures select no fragments, so the installed skills are the core ones. The hand-off and
slicing skills, which say what a package does to a strong model, are not in the workspace. A run
that reads them through this checkout shows in `guidance_reads`.

The acceptance tests and the graders (`evals/fixtures/handoff/grade.py`) are never in the
workspace. The runner gives the post-checks the `evals/` of this checkout in
`OUTCOMEBOUND_EVAL_DIR`, and the plan runs them from there. A model can read files outside its
workspace, so `eval-files-unread` shows a run that did, by the commands it ran. A read that no
recorded command shows is not seen.

Each `<base>/reference.sh` is a reference solution. `tests/test_eval_handoff.py` shows that the
post-checks of each variant fail on its seed and pass on the reference. It also shows that each
test of a spec package fails on its seed for the reason that the package gives. It also shows that
a build that breaks one row that the ticket states fails `acceptance`. The rows it plants are: a
log with its projects out of order, six fields read without an error, a changed read-error
message, `--to` dropped, the `H:MM` of the report changed, and the log-format document left as it
was.

The comparison is seven cells. Each cell is one implementer and one variant, on the three bases,
for three repetitions: 63 runs.

- `gpt-6-astra` at `high` (the outcome tier) runs `ticket` and `spec`.
- `gpt-6-sol` at `medium` (the design tier) runs `ticket` and `design`.
- `gpt-6-luna` at `xhigh` (the spec tier) runs `ticket`, `spec` and `full`.

```bash
cell() {  # cell MODEL EFFORT VARIANT
  for base in duration invoice tags; do
    for repetition in 1 2 3; do
      python3 evals/run.py --arm current --model "$1" --effort "$2" \
        --fixtures "handoff-$base-$3" --repetition "$repetition" \
        --out "evals/results/raw/handoff/$1-$3-$base-$repetition"
    done
  done
}
cell gpt-6-astra high ticket; cell gpt-6-astra high spec
cell gpt-6-sol medium ticket; cell gpt-6-sol medium design
cell gpt-6-luna xhigh ticket; cell gpt-6-luna xhigh spec; cell gpt-6-luna xhigh full
python3 evals/run.py --summary evals/results/raw/handoff
```

`--summary` gives one block for each fixture and implementer. A block has the count of runs that
PASS the verdict and each claim, the median tokens and seconds, and the calls that failed. A cell
is the three blocks of its variant for one implementer, nine runs. A failed call is not counted,
so count it beside the cell. Read the cells by these rules, written before any run. They are as
written then, with three phrases reworded to stand on their own (rules 2 and 4).

A cell's score is its verdict PASS count of 9. Each rule is read on the cells' totals, and
the per-base counts (duration, invoice, tags: three runs each) are reported beside them, since
the nine runs are three clusters of three.

1. Does the tier's package help its implementer? For `gpt-6-sol`, `design` against `ticket`. For
   `gpt-6-luna`, `spec` against `ticket`. A package helps when its cell has at least 3 more
   verdict PASSes of 9. It does not help when the difference is 1 or less, or the package's cell
   is lower, and the `ticket` cell has 6 or fewer PASSes. Between these, the result is
   inconclusive. For `gpt-6-astra`, `ticket` is its tier's package, so it has no such
   comparison.
2. Does the spec package make a result worse on an outcome-tier implementer? For `gpt-6-astra`,
   `spec` against `ticket`. A drop of 3 or more of 9 supports the hypothesis that the spec package
   makes an outcome-tier implementer overfit. A smaller drop is inconclusive, and no drop does not
   support it.
3. Does `--detail full` beat the spec package? For `gpt-6-luna`, `full` against `spec`. It beats
   it only when its cell has at least 3 more verdict PASSes than `spec`'s, the same margin as in
   rule 1. Thus `--detail full` stays only then, as the tickets design says.
4. No headroom. Where the cell that a rule uses as its baseline has 7 or more of 9 (`ticket` in
   rules 1 and 2, `spec` in rule 3), a difference of 3 cannot show. The result is "no headroom:
   inconclusive", never "does not help", and no part is cut on it. In rule 3
   `--detail full` cannot stay on such a result; such a result is a
   ceiling, not a finding. A drop of 3 or more in rule 2 is still a drop.
5. Noise. Report `gpt-6-luna` `ticket` against `full` as well. `full` adds only generic steps
   to the ticket's own text, so the difference between them is the nearest thing to a repeat
   of one cell. A package's difference that does not exceed it is not a result.

Rule 3 names the tickets design as it read before the runs. The outcome is in
[docs/evaluations.md](../docs/evaluations.md), E17: `full` scored 6 of 9 against 9 of 9 for
`spec`, so by rule 3 `--detail full` would be cut. The project keeps it against that rule, as the
default brief of the spec tier, to be judged on longer work. The tickets design now records that
choice.

Read `acceptance` beside the verdict: a run can build the ticket and fail only `within-bounds`.
For `spec` runs, read `package-tests-pass` and `package-tests-unchanged` beside the verdict too.
Read tokens, seconds and the `observed:` lines beside the counts. Nine runs a cell can show only
a large effect, and a PASS shows only what its check reads, for that model on that day.

What the comparison can show about question 2. The graded rows that the spec package's tests
leave out are these. `duration`: the command line and the report, which a build that changes
only `durations.py` keeps. `invoice`: a day given on one side only, the projects in the log's
own order, an empty report read by `invoice.py`, and the unchanged text report. `tags`: `--to`,
a line of three fields, the read error at the command line, and the text of
`docs/log-format.md`. A drop on `acceptance` can come only through these rows, where a build that
follows the package departs from the ticket, so `duration` gives the least room for it. A drop
in the verdict can also come through `within-bounds`. State this with the result.

What the spec cells measure. A spec package carries the algorithm as steps, the data structure
and the verbatim text, with tests that fail first. It is close to the solution. A `spec` cell
reads whether the implementer applies a near-complete package and stays in its bounds, and rule
3 compares `--detail full` with that.

## Recorded results

Recorded results, each with the scope that it covers, are in
[`docs/evaluations.md`](../docs/evaluations.md). The run records are not in the repository. Git
ignores `evals/results/raw/`.
