# OutcomeBound

[![CI](https://github.com/rajasdevel/outcomebound/actions/workflows/ci.yml/badge.svg)](https://github.com/rajasdevel/outcomebound/actions/workflows/ci.yml)

**Neither underengineer nor overengineer: exactly the engineering the outcome requires.**

OutcomeBound is a short operating contract for coding agents, and a small engine that installs
it into a repository and keeps it current. The contract goes into your `AGENTS.md` as about
thirty lines. Around it the engine offers optional parts: a quality floor, a ticket layer, a
finish check that runs your Done commands when an agent ends its turn, and a reader that checks
the instruction files your agents load for hidden or risky content.

## Why

Coding agents fail in two directions, often on the same afternoon: they skip the test and report
a push that never happened, then write a spec and a review plan for a one-line fix. Both are the
same mistake — the amount of engineering was not chosen against the outcome.

Rules files try to fix this with more rules, which grow, contradict each other, and get ignored.
OutcomeBound bets the other way. Frame every task by four inputs:

| Input | The question it answers |
| --- | --- |
| **Outcome** | What becomes observably true, and for whom? |
| **Context** | What do the code, runtime and evidence show; how complex is it, who uses it, how long must it last? |
| **Bounds** | What is in scope, what must be preserved, what authority is granted, what cannot be undone? |
| **Completion bar** | What observable success, and which checks sized to the changed risk, settle done? |

Satisfy all four completely with the simplest approach that holds for the lifespan, size the
whole plan and not only each step, and report every check as `PASS`, `FAIL` or `UNVERIFIED`, so
a passing test never stands in for a deployment. Specs, reviews, goal envelopes and broad suites
are used when their condition holds, never by default. The full contract is
[OutcomeBound.md](OutcomeBound.md).

## Install

```sh
uv tool install git+https://github.com/rajasdevel/outcomebound@v1.0.0
outcomebound adopt path/to/your-repo --detect
```

`uv tool install` puts `outcomebound` on your `PATH` in an environment of its own;
`pipx install` of the same URL does too, and so does `pip install` of it into a virtual
environment. `pip install --user` is not supported: `outcomebound` runs Python isolated (`-I`),
so that nothing in your directory or on `PYTHONPATH` can shadow the engine, and an isolated
Python does not read the user site where that install puts it. Pin the release you adopt from,
so a team and its CI run one version. OutcomeBound needs Python 3.10 or later, a POSIX `sh` and
Git, and nothing else: the engine is Python standard library only. Native Windows is untested. To
work on OutcomeBound itself, clone this repository and put its `scripts/outcomebound` on
`PATH`; it runs that checkout's engine ([CONTRIBUTING.md](CONTRIBUTING.md)).

`--detect` prints the one install command your repository's files suggest: the fragments and
harnesses it found, and Done commands, which are the first test command your CI runs, or a check
command inferred from your files where CI runs none, after the floor's check where a floor is
installed. Review it and run it; your repository must be a Git work tree, since Git is the undo.
That command writes:

- the operating contract, as a managed block at the top of `AGENTS.md`;
- below it, a block of project facts, one line each: the commands that settle done (`--done`),
  the test command your CI runs, read from its workflow files without running anything, the
  irreversible edges your fragments declare, and which instructions win a conflict; a fact it
  cannot observe is left out and reported `UNVERIFIED`;
- a block of pointers, one line each, saying when to read each piece of guidance: every
  fragment in `--fragments`, copied under `.outcomebound/fragments/` (facts about your stack and
  setup, such as how a Python project's tests prove anything; `outcomebound fragments --help`),
  and each skill; your own `local` fragment is written out in full ahead of them;
- one copy of the default skills, and of those each fragment you select names, for each harness
  you use, or under `.outcomebound/skills/` for a harness `adopt` does not know (`--harness
  generic`); the [skills design](docs/specs/skills/design.md) lists them;
- an `@AGENTS.md` import in a harness file, such as `CLAUDE.md`, where that harness would not
  load `AGENTS.md` otherwise; a harness that cannot be made to load it is refused;
- `.outcomebound/manifest.json`, recording what it wrote.

Everything else in your files stays as it was. The one exception is `--finish-check`, which
writes its entry into a harness settings file: that file keeps its keys, their order and its
indentation, not every byte of its spacing. Review the diff and commit it your usual way.

## Keeping it current

Install the newer release the same way (`uv tool install --force` with its tag), then run the
same adopt command again: that is the upgrade. A block or file you edited is refused unless you
pass `--force`, and Git is the undo.
`outcomebound adopt . --check` says whether each installed piece is current, edited, stale or
missing (a stale facts block names the fact that moved), and exits non-zero when one is not —
one line for your CI. `outcomebound adopt . --remove` takes it all out.

## Optional: a finish check

`outcomebound adopt . --finish-check` writes a stop-hook entry for Claude Code or Codex: when
the agent ends its turn on a changed tree, your Done commands run, and a failure goes back to the
agent as the reason to keep working. It has been observed end to end in Claude Code; under Codex
it is built to the same hook contract and not yet observed.

## Optional: a quality floor

`outcomebound floor` blocks regressions in format, lint, types, secrets and shell scripts, using
your own tool configs. `floor propose . > floor.json` prints the claims for your stack, and
`floor apply --floor floor.json --accept .` fits them to the project you have: findings you
already have go into a plain-text baseline you can read and shrink, and only new ones fail; a
secret already committed is listed once for you to rotate or allowlist, never recorded;
`--strict` fits nothing. A change that loosens the floor — a baseline that grew, a changed tool
config, a new suppression comment — fails the check unless a commit names the decision that
allowed it, in a line `Floor-Loosening: <what>; ruled <decision id>`, where the id is whatever
names the decision in your project, in one word: an issue or pull request (`#123`), a decision
record, or a link. The check reads that line and cannot tell who wrote it: review or branch
protection is what holds a loosening to the person's decision. The floor runs the tools it finds
on your `PATH`; `floor provision . --accept`, with your project's virtual environment active,
pip-installs the pinned ruff and mypy into the `python3` on your `PATH`, and prints the install commands for
gitleaks and shellcheck. `outcomebound floor --help` gives the steps; Python and shell are
supported.

## Checking instruction files

`outcomebound instructions check .` reads the instruction files and harness settings your
harnesses load (what Git tracks or does not ignore, each settings path a harness names even when
ignored, and the agents' notes under `.agents/handoffs` and `.agents/shared-memory`), and reports
hidden characters, concealed content, override phrases and risky harness settings for you to
judge. It runs nothing it reads and writes nothing.

## Optional: a ticket layer

For work too large for one acceptance: tickets as GitHub issues with a small block of fields,
cut by the `slice-tickets` skill and linted by `outcomebound tickets check`. How each is built,
and which tests prove it along the way, stays with its implementer; the project's own gate
decides done where the work lands. See [docs/tickets.md](docs/tickets.md).

## What is measured

The test suite checks the engine's mechanics, not what a model does. What the contract changes
in a model's work is measured by the eval fixtures in [evals/](evals/): small repositories with a
task, run with the install and without OutcomeBound, three or more runs a cell on one strong
model at a time. On the four core fixtures, runs without OutcomeBound did the same work and
differed in how they reported it. On the skill fixtures, the install changed how a design was
cut into tickets, what a test report said and how an unclear outcome was handled. On a
four-task ladder of rising risk, whose project's `CONTRIBUTING.md` suggests a design note, a
decision record, the full suite and a second reader for any change, the install as it ships
stopped that suggested process on the two middle tasks: every run with it made the change with
no process document and skipped the slow suite on the two-character fix, and every run without
it wrote a design note and ran the slow suite (6 of 6 against 0 of 6; 12 runs, three a cell, on
one model, gpt-6.1-sol; E10). An earlier pass on another model, gpt-6-sol, whose install arm
carried no project-facts block and so not its line on suggested process, stopped process
documents only on the smallest task (36 runs; E7). No fixture yet separates the arms on
underengineering. Method, every result and its limits:
[docs/research/practices/evaluations.md](docs/research/practices/evaluations.md).

A project's own instructions outrank OutcomeBound's, so process a project requires stays
required.

## More

- [OutcomeBound.md](OutcomeBound.md) — the full contract
- [docs/specs/](docs/specs/) — one current design per area
- [docs/research/](docs/research/) — the research behind it: one prompting document per model,
  one file per coding harness, practices (writing for models, task sizing, review, quality floors,
  evaluations and more) and providers
- [templates/](templates/) — files to copy into a project yourself, also under
  `outcomebound home`: CI jobs ([templates/ci/](templates/ci/README.md)), Make targets for the
  floor and a validation plan (`outcomebound.mk`), a goal envelope for autonomous or
  multi-session work (`goal/goal.md`), and the design and plan `scripts/new-spec.sh` scaffolds
  for a spec (`spec/`)
- [references/portability.md](references/portability.md) — the harnesses `adopt` installs for,
  and how each reaches `AGENTS.md`
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to propose and land a change
- [SECURITY.md](SECURITY.md) — how to report a vulnerability privately
- [CHANGELOG.md](CHANGELOG.md)

Apache-2.0. The OutcomeBound name and mark are not licensed with the code; a fork ships under its own name.
