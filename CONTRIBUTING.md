# Contributing to OutcomeBound

Thank you for helping. Bug reports, proposals, fragments, research and fixes are all welcome, as
GitHub issues and pull requests. You do not need to know the project well. If a step here is
unclear, open an issue and name the step. That is a useful contribution too.

## Where to start

| You want to | Do this |
| --- | --- |
| Report a bug | Open an issue with the **Bug report** form |
| Propose a change | Read [Propose a change](#propose-a-change), then open an issue |
| Add support for a stack or a project setup | Read [Contributing a fragment](#contributing-a-fragment) |
| Add a fact about models, harnesses, providers or practices | Read [Contributing research](#contributing-research) |
| Report a security vulnerability | Report it privately, as [SECURITY.md](SECURITY.md) describes. Never open a public issue for it |

For a small fix, open a pull request directly. For a larger change, open an issue first. Then
we can agree on the aim before you write the code.

## Your first pull request

1. **Fork and clone.** Fork the repository on GitHub, and clone your fork. You need Python 3.10
   or later, Git and a POSIX `sh`. Put the clone's `scripts/outcomebound` on your `PATH`. It
   runs the engine of that checkout, so the code that you edit is the code that runs.
2. **Branch.** Make one branch from `main` for each change.
3. **Change.** If the change alters behavior, add or change a test
   ([Writing a test](#writing-a-test)). If the change reaches what a release ships, add a bullet
   under `## [Unreleased]` in `CHANGELOG.md`. Do not edit a released section of the changelog.
   Do not add a third-party dependency: `outcomebound_tools/` and `scripts/` import only the
   Python standard library, and `make gate` fails when they import more.
4. **Check.** Run the [local checks](#local-checks) until all three pass at the tip of your
   branch.
5. **Sign off.** Commit with `git commit -s` ([DCO](#sign-off-your-commits-dco-no-cla)). If a
   commit does the work of an issue, name the issue (`#<n>`) in its message.
6. **Open a pull request** against `main`. Its template asks what changed and why, which checks
   you ran, and whether the change stays in scope.

What happens next:

- CI runs the gate, this repository's own install check and the suite on the oldest and the
  newest supported Python. It runs the quality floor once.
- When CI is green, a maintainer reviews the pull request.
- A maintainer lands it by rebasing it onto `main`. If its history is not worth keeping, the
  maintainer squashes it. `main` has no merge commits.

Review goes where no check reaches. When a change alters what the kernel, the contract, a skill,
a fragment or a template tells a model (its bounds, its holds, or what it asks for), the pull
request carries the label `needs-maintainer` and an independent review, and a maintainer approves
and lands it. Every other change lands when its checks pass.

`main` accepts changes only through a pull request: a ruleset requires both CI checks, a linear
history, and no force push or deletion. This holds for maintainers and agents alike.

## Local checks

While you work, run the narrowest check that covers the changed risk. At the tip that lands,
run all three:

```bash
make gate
make check
make test
```

- `make gate` checks the standard-library import boundary over `outcomebound_tools/` and
  `scripts/`.
- `make check` runs the gate. Then it runs this repository's quality floor against `origin/main`.
  Use `OB_BASE=<ref>` to name another base. The floor runs ruff, mypy, gitleaks, `bash -n`, the
  shell injection scan, `scripts/check-structure.py` and `scripts/check-public-text.py`. The rules
  are in `ruff.toml` and `mypy.ini`.
- `make test` runs the suite across CPUs. If your `python3` has no pytest, it runs pytest through
  `uv run --with pytest`.
- `make scrub` applies a local list of private names to the same text as the public-text check
  ([Agents and releases](#agents-and-releases)). A maintainer runs it before a merge.

The floor needs ruff and mypy. Get them in one of three ways:

- Run `python3 -m pip install -r requirements-dev.txt` in a virtual environment.
- Leave the tools to uv. If your `python3` lacks them and `uv` is on `PATH`, `make check` runs
  them through `uv run`, as `make test` does. A finish hook that inherits no activated environment
  then gets the same verdict as your shell.
- Run `scripts/outcomebound floor provision . --accept`. It pip-installs ruff and mypy, at the
  versions the floor names, into the `python3` on `PATH`. Use a virtual environment, because pip
  refuses a system Python. A tool that is on `PATH` at that version or later is not installed.

`scripts/outcomebound floor provision .` also prints the command that installs gitleaks. A missing
or older tool reads `UNVERIFIED`, and the check fails.

The floor lists the findings that existed before it in `.outcomebound/floor/`. Any other finding
fails. Fix a finding. Do not list it. These changes make the floor weaker, so they fail the check:
a new baseline line, a changed tool configuration, and a new suppression comment. The commit
that makes the change can allow it with this line:
`Floor-Loosening: <what>; ruled #123`. The line allows only the changes of its own commit. After
`ruled`, write one word that says where a maintainer agreed to the change. It can be an issue or pull request (`#123`), a decision record, or a link. `scripts/outcomebound floor ratchet .` deletes the baseline
lines that no finding matches any more.

A change to a gate (the floor, the instruction audit, the finish check, a tickets refusal)
that adds an exemption or narrows what the gate counts needs an independent review. The review
tries to pass the gate without the ruling the gate requires. The pull request links the review.

In a Git worktree of this repository, `.agents/tools/runner <command>` runs a command with that
worktree's engine first on `PATH`. There is no editable install (`pip install -e`). The launcher
of the checkout is the way to develop. The package that adopters install comes from
`scripts/build_backend.py`, which uses only the standard library. The command
`python3 scripts/build_backend.py --sdist` writes the wheel and the source archive to `dist/`.
The command `uv build` does the same through the same backend. `tests/test_package.py` has pip
build and install this checkout, and then checks the installed command against it.

## Writing a test

A test builds only the starting state that its subject needs. If tests share a state, they build
it once. A test calls the engine in-process, unless the command line is its subject. A test of a
refusal asserts the message of the refusal, not only the exit code. Then a refusal for another
reason fails the test. The `tests-worth-keeping` skill in `skills/` says more about what a test
must earn.

## Sign off your commits (DCO, no CLA)

Each commit in a pull request carries a `Signed-off-by` trailer. The trailer certifies the
[Developer Certificate of Origin](https://developercertificate.org/): you wrote the commit, or
you have the right to submit it under the license of this project. Add the trailer with:

```bash
git commit -s -m "your message"
```

There is no contributor license agreement to sign.

## Propose a change

For a proposal, describe four things:

- the problem that you can observe,
- the configuration it affects,
- the smallest change that you propose,
- the evidence that would justify keeping the change.

A synthetic counterexample helps when it makes the decision clearer. An instruction change is a
candidate until its behavioral evidence exists. Deterministic tests alone do not show that a model
does better.

Keep these out of public issues and fixtures: private project exports, meeting notes,
credentials, personal data, internal URLs and raw model transcripts. Reproduce the behavior with
synthetic names and data. Keep only the configuration, versions, commands and redacted results
that the reader needs. Check the attachments and logs before you share them. If a report cannot be
made safe to post, such as a vulnerability, send it privately, as [SECURITY.md](SECURITY.md)
describes.

### A lesson from your own project

A lesson from a project that uses OutcomeBound belongs here when its decision rule repeats across
projects, or when the operator of the project wants it generalized. A one-off incident stays in
that project. Before you propose a lesson:

- Separate the lasting rule from the details of a model, vendor, repository or date. A note about
  one model belongs in the file for that model under `models/` in the research repository, with a
  date and a source. It does not belong in the contract
  ([Contributing research](#contributing-research)).
- Look for evidence that disagrees, and for guidance that already covers the lesson. One anecdote
  is not a rule.
- Change the smallest shared artifact whose decision improves. Adding instructions is not a
  contribution by itself. A good change removes machinery, closes a quality gap or fits the
  outcome better.
- If a tool can check the lesson, ship the tool's captured output as its fixture, as
  `tests/fixtures/floor/` does. Do not write the fixture by hand.
- Draft in your fork. Never draft in the files that `outcomebound home` prints, because your
  `outcomebound` runs those files.

## Contributing a fragment

A fragment applies the operating contract to one stack (`fragments/stack/`) or one project setup
(`fragments/setup/`). It states facts. It never adds a rule.

The frontmatter of a fragment has these keys:

- `id`, `family` (`stack` or `setup`), `applies`, `version`.
- `detect`: a JSON list of glob patterns inside the target root.
- `condition` (optional): one line that says when the pointer to the fragment applies.
- `edges` (optional): a JSON list of the irreversible acts that the text names. They feed the
  pointers and the project facts in `AGENTS.md`.
- `skills` (optional): a JSON list of the shipped skills that selecting the fragment installs.

The body has exactly five slots, in this order: **Context**, **Bounds**, **Mechanisms**,
**Completion bar** and **Distinguish**. Each backticked name in the Mechanisms slot is a mechanism
id from `outcomebound_tools/mechanisms.py`. `tests/test_fragments.py` rejects a fragment that
invents a mechanism, adds, renames or reorders a slot, or has a malformed `detect` or `edges`.
Look at `fragments/stack/python.md` for a short example. You can also open an issue with the
**Fragment proposal** form first.

## Contributing research

Research on models, harnesses, providers and agent practice is not in this repository. It is in
[outcomebound-research](https://github.com/rajasdevel/outcomebound-research). Its text is under
CC BY 4.0, and its code is under Apache-2.0. You can contribute in three ways:

- **A fact or a correction.** Open a
  [finding issue](https://github.com/rajasdevel/outcomebound-research/issues/new?template=finding.yml)
  there. Give what it is about, the claim in your own words, the URL of the source, and the day
  you read it. If it helps, add a quote of at most 25 words.
- **From an agent in your project.** `outcomebound research ingest` takes the same fields and
  prints that issue, prefilled, for you to open in a browser. It also writes the finding under
  `.outcomebound/research-inbox/`. That file is a local record. Nothing reads or sends it. A finding reaches
  the research repository only by the issue link or by a pull request.
- **Anything larger.** Open a signed-off pull request to outcomebound-research. Its
  [CONTRIBUTING.md](https://github.com/rajasdevel/outcomebound-research/blob/main/CONTRIBUTING.md)
  says how.

Keep the names of projects, clients and people out of a finding. This repository records what the
text of OutcomeBound did in an evaluation, in [docs/evaluations.md](docs/evaluations.md).

## Agents and releases

Coding agents also work in this repository, under the contract that its own `AGENTS.md` installs.
Their changes land the same way as anyone's changes: an agent opens a pull request from its own
branch and never pushes to `main`. A person directs the agent, reviews its commits and signs them
off under the DCO; the sign-off is that person's certification. An agent may land its own pull
request once CI is green, unless the pull request carries `needs-maintainer`. Issues are the
backlog, and a milestone names what a release waits for.

Each pull request lands as one squash commit. Its title and description become that commit on
`main`, and GitHub adds the `Signed-off-by` lines of the pull request's commits, so the
description is the commit message that a person reads. Merge with `gh pr merge <n> --squash` and
no `--subject` or `--body`: nobody types a merge message or an identity at the merge. The
required checks must pass on a branch that is up to date with `main`;
`gh pr update-branch <n> --rebase` brings it up to date. CI checks the title and the description
again each time they change, and checks that each commit of the pull request, except a merge
commit, has a `Signed-off-by` line (the workflow `pr-text.yml`).

An agent's pull request text, commit messages and files are public. They name no project that
uses OutcomeBound, no person, no local path, no id or role from a private working file, and no
count or anecdote from a private run. A private working file includes a decision brief that no
public issue or pull request holds. If a commit or a `ruled` line cites a brief, a public issue or
pull request holds that brief, and the citation uses its number. Describe a behavior in general
terms, with a synthetic reproduction. `make check` runs `scripts/check-public-text.py` over the
tracked files and over the commits since `OB_BASE`. It finds each path under a home folder, and
each email address that a person can read, in the text and in the author and committer of a
commit. A GitHub no-reply address and an address at a domain reserved for examples are not hits.
It reads PASS or FAIL. `make scrub` also applies a local list of private names. The environment
variable `OB_SCRUB_LIST` names the list, and the list stays outside this repository. With the
list, `make scrub` reads PASS or FAIL. Without it, `make scrub` reads `UNVERIFIED`, and a
maintainer runs it before the merge. CI applies the same checks to the title and the description
of a pull request. CI applies the list only when the repository has the secret `OB_SCRUB_LIST`. A pull request from
a fork does not get the secret, so for that pull request CI reads `UNVERIFIED` for the list and
does not fail.

`make canary` runs the engine of your checkout beside the installed release, and changes
nothing. It runs on each project of a local list, under Python 3.10 and under the Python of the
installed release. The environment variable `OB_CANARY_LIST` names the list: one project path on
each line, and `#` for a comment. The list stays outside this repository, and the report names
each project by its number only. On each project, both engines run `adopt --dry-run`,
`adopt --check` and `instructions check`. Where the project has `.outcomebound/floor.json`, they
also run `floor check --base HEAD`, and the report gives the seconds of each floor run. Where
the claims plan of the project's ticket declaration has a `tickets check --draft` command, they
run `tickets check --draft` on those draft files. Where `issues.json` is in the project root,
they run `tickets check` on that export. If a command does not run, the report gives the
reason; with no export, the report says `UNVERIFIED`, because the canary calls no tracker. The
caches of the floor's tools go to a temporary folder. A crash, an exception, a refusal, a
command that prints no valid report, or a change to a project's tree (ignored entries included)
is FAIL. If the installed release fails and the candidate does not, the report says
`no baseline: installed engine failed`, and it does not compare that command. The report also gives the warning and finding kinds that the candidate adds or
removes, for a person to judge. Without the list, `make canary` reads `UNVERIFIED`. Run
`make canary` before you open a pull request that changes `adopt`, `tickets`, `floor`,
`instructions` or `discovery`, and on the committed release commit. The pull request gives the
summary in counts.

A release is its `VERSION`, its changelog section and a release commit. `make release-check` passes
on the release commit, and it fails unless `make canary` recorded PASS for the tree of that commit. Nobody can undo the push of a release tag. [docs/VERSIONING.md](docs/VERSIONING.md)
gives the sequence of the release steps, says who may push the tag, and says what
`make release-check` confirms first. When the CI run on the tag
passes, CI publishes the GitHub release with the attested wheel and source archive.
