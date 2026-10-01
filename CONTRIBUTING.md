# Contributing to OutcomeBound

Bug reports, proposals, fragments and fixes are welcome, as GitHub issues and pull requests. A
report made from a real project reaches here in neutral form (see
[Proposals and reports](#proposals-and-reports)). A security vulnerability goes privately, as
[SECURITY.md](SECURITY.md) describes, never in a public issue.

## Your first pull request

1. **Fork and clone.** Fork the repository on GitHub and clone your fork. You need Python 3.10
   or later, Git and a POSIX `sh`. Put the clone's `scripts/outcomebound` on your `PATH`: it runs
   that checkout's engine, so what you edit is what runs.
2. **Branch.** Cut one branch per change from `main`.
3. **Change.** Add or change a test where the change alters behavior
   ([Writing a test](#writing-a-test)). If the change reaches what a release ships, add a bullet
   under `## [Unreleased]` in `CHANGELOG.md`.
4. **Check.** Run the [local checks](#local-checks) until all three pass at your branch's tip.
5. **Sign off.** Commit with `git commit -s` ([DCO](#sign-off-your-commits-dco-no-cla)). A commit
   that does an issue's work names it (`#<n>`) in its message.
6. **Open a pull request** against `main`. Its template asks what changed and why, which checks
   you ran, and whether the change stays in scope.

What happens next: CI runs the gate, this repository's own install check and the suite on the
oldest and newest supported Python, and the quality floor once. When CI is green, a maintainer
reviews the pull request and lands it by rebasing it onto `main`, or as a squash where its
history is not worth keeping; `main` has no merge commits. Review goes where no check reaches: a
change to what the kernel or the contract tells a model (its bounds, its stops, what it asks for)
gets one reading, before it lands, by someone who did not write it. Everything else lands once
its checks pass.

## Local checks

Run the narrowest check that covers the changed risk while you work; all three run once, at the
tip that lands:

```bash
make gate
make check
make test
```

- `make gate` is the standard-library import boundary over `outcomebound_tools/` and `scripts/`.
- `make check` runs the gate, then this repository's quality floor against `origin/main`
  (`OB_BASE=<ref>` names another base): ruff, mypy, gitleaks, `bash -n`, the shell injection scan
  and `scripts/check-structure.py`, with the rules in `ruff.toml` and `mypy.ini`. Install ruff
  and mypy once, in one of two ways:
  - `python3 -m pip install -r requirements-dev.txt` in a virtual environment; or leave them to
    uv: where `python3` lacks them and `uv` is on `PATH`, `make check` runs them through
    `uv run`, as `make test` does, so a finish hook that inherits no activated environment gets
    the same verdict as your shell;
  - `scripts/outcomebound floor provision . --accept`, which pip-installs the pinned ruff and
    mypy into the `python3` on `PATH`, where the floor finds its tools: a virtual environment's,
    since pip refuses a system Python.

  Either way, `scripts/outcomebound floor provision .` prints gitleaks' install command. A missing
  or older tool reads `UNVERIFIED` and fails. Findings that predate the floor are listed in
  `.outcomebound/floor/`; any other fails. Fix a finding rather than listing it: a gained
  baseline line, a changed tool config or an added suppression comment fails the check unless a
  commit in the range carries the line `Floor-Loosening: <what>; ruled <decision id>`. The
  decision id names, in one word, where a maintainer agreed to the loosening: an issue or pull
  request (`#123`), a decision record, or a link.
  `scripts/outcomebound floor ratchet .` deletes the lines no finding matches any more.
- `make test` runs the suite across CPUs, through `uv run --with pytest` where the local `python3`
  has no pytest. CI runs it on the oldest and newest supported Python.

In a Git worktree of this repository, `.agents/tools/runner <command>` runs a command with that
worktree's engine first on `PATH`. There is no editable install (`pip install -e`); the
checkout's launcher is the development route. The package adopters install is built by
`scripts/build_backend.py`, standard library only: `python3 scripts/build_backend.py --sdist`
writes the wheel and the source archive to `dist/`, and `uv build` does the same through the
same backend. `tests/test_package.py` has pip build and install this checkout, and checks the
installed command against it.

## Writing a test

A test builds only the starting state its subject needs, and builds a shared one once. A test
calls the engine in-process unless the command line is its subject. A refusal test asserts the
refusal's message, not only its exit code, so that a refusal for another reason fails it.

## Sign off your commits (DCO, no CLA)

Commits in a pull request carry a `Signed-off-by` trailer certifying the
[Developer Certificate of Origin](https://developercertificate.org/) — that you wrote them or
otherwise have the right to submit them under this project's license. Add it with:

```bash
git commit -s -m "your message"
```

There is no separate contributor license agreement to sign.

## Contributing a fragment

A fragment instantiates the operating contract with facts about one stack (`fragments/stack/`) or
one project setup (`fragments/setup/`); it never adds a rule. Its frontmatter carries `id`,
`family` (`stack` or `setup`), `applies`, `detect` (a JSON list of glob patterns inside the target
root) and `version`. It may carry `condition` (one line: when the pointer to it applies) and
`edges` (a JSON list of the irreversible acts its text names), which feed `AGENTS.md`'s pointers
and project facts, and `skills` (a JSON list of the shipped skills its selection installs). Its
body is exactly five slots, in this order: **Context**, **Bounds**, **Mechanisms**, **Completion
bar** and **Distinguish**. Every backticked name in the Mechanisms
slot is a mechanism id from `outcomebound_tools/mechanisms.py`. `tests/test_fragments.py` rejects
a fragment that invents a mechanism, adds, renames or reorders a slot, or carries a malformed
`detect` or `edges`.

## Proposals and reports

For a general proposal, describe the observable problem, affected configuration, smallest
proposed change, and evidence that would justify retaining it. Include a synthetic
counterexample when it clarifies the decision. An instruction change is a candidate until
its relevant behavioral evidence exists; deterministic tests alone do not demonstrate
better model outcomes.

Keep private project exports, meeting notes, credentials, personal data, internal URLs, and
raw model transcripts out of public issues and fixtures. Reproduce the relevant behavior with
synthetic names and data; retain only necessary configuration, versions, commands, and redacted
results. Check the actual attachments and logs before sharing. A report that cannot be made
safe to post, such as a vulnerability, goes privately, as [SECURITY.md](SECURITY.md) describes.

## Contributing a lesson from a project

A lesson from an adopting project reaches here as a proposal (above) when its decision rule
repeats across projects, or the project's operator wants it generalized; a one-off incident stays
local. Before proposing:

- Separate the durable rule from model-, vendor-, repository- and date-specific detail. A
  model-specific note belongs in `docs/model-guidance.md`, dated and sourced, not in the contract.
- Look for conflicting evidence and for guidance that already covers it; one anecdote is not an
  invariant.
- Change the smallest shared artifact whose decision improves. Adding instructions is not by
  itself a contribution: the result removes machinery, closes a quality gap or improves outcome
  fit.
- A lesson a tool can check ships with that tool's captured output as its fixture, as
  `tests/fixtures/floor/` holds them, not a hand-written one.
- Draft in your fork, never in the files `outcomebound home` prints: those are the engine your
  `outcomebound` runs.

## Agents and releases

Coding agents work in this repository too, under the contract its own `AGENTS.md` installs, and
their changes land the same way as anyone's. An agent's commits carry the same sign-off and no
attribution lines. An agent pushes to `main` only where a goal envelope a maintainer wrote
authorizes that and the checks above pass; otherwise it asks.

A release is its `VERSION`, its changelog section and a release commit, on which
`make release-check` passes. Pushing the release tag cannot be undone; who may push it, and what
`make release-check` confirms first, is in [docs/VERSIONING.md](docs/VERSIONING.md).
