# Changelog

All notable changes to OutcomeBound are documented here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and OutcomeBound
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The bump comes from what an adopter must do, not from the commit type; see
[docs/VERSIONING.md](docs/VERSIONING.md). Released sections are not edited.

`[Unreleased]` is the staging area for accepted changes.

## [Unreleased]

### Added

- You can read the research repository from your project. `outcomebound research [PATH]` prints a
  file from a clone of [outcomebound-research](https://github.com/rajasdevel/outcomebound-research).
  The first line of the output is the clone's commit and the sha256 of the file's text. Where no
  clone is configured, the command names the public link. The command finds the clone at `OUTCOMEBOUND_RESEARCH`, else at
  `~/.outcomebound/research`.
- You can fetch and update the clone. `research clone` and `research pull` only preview. They run
  Git only with `--accept`.
- You can send a finding back. `research ingest` writes the finding to
  `.outcomebound/research-inbox/` and prints a prefilled issue link.
- The `research` fragment, selected with `--fragments`, points your project's agents at the
  research repository.
- Your agents write reports, decision briefs, handovers, pull request descriptions, commit
  messages and documents for people in plain, short sentences. `adopt --human-style ste` adds
  this as one project fact in `AGENTS.md`. The text follows the style of ASD-STE100 Simplified Technical
  English, with no length limit, every fact kept and the project's own terms unchanged. Text that a
  model reads is out of scope. The standard is named, not quoted. `--human-style ''` removes the
  fact. If you omit the option, the recorded choice stays.
- Your agent hands an accepted ticket to its implementer with a package that fits the
  implementer. This is the new skill `hand-off-tickets`, which the `tickets` fragment installs.
  The package depends on the implementer's tier:
  - At the outcome tier, the package is the ticket alone.
  - At the design tier, the package adds the approach, signatures, invariants, an edge-case table
    and milestones.
  - At the spec tier, the ticket is cut into steps. Each step has failing tests and stubs, written
    first and reviewed before the next step. The brief is compiled with
    `outcomebound tickets brief <id> --detail full`.

  The tier comes from you, or from the research repository's placement table, which you read with
  `outcomebound research applications/implementer-tiers.md`. Without a clone, the skill asks you.
  In a comparison of 63 runs (2026-10-03), the spec-tier package raised gpt-6-luna at xhigh from 6
  of 9 to 9 of 9, and it left gpt-6-astra at high at 9 of 9. The effect of the design package did
  not show, because gpt-6-sol at medium passed 9 of 9 with the ticket alone. All six failures
  were one sentence of one ticket. Each tier had one model, all from one maker, through one
  harness, with 9 runs a cell ([docs/evaluations.md](docs/evaluations.md), E17). The `tickets`
  fragment is now version 6. Run `adopt` again to install the skill.
- A guide to the agent workspace: [docs/workspace.md](docs/workspace.md). It says how to select the
  `workspace` fragment, what `adopt` writes and removes, what Git keeps and ignores, what a handoff
  holds, and what the fragment does not give you.
- A `commands` fragment gives agents command habits: no pager, editor, credential prompt or
  open stdin can hang a run (`git --no-pager`, `git commit -m`, `GIT_TERMINAL_PROMPT=0`,
  `ssh -o BatchMode=yes -o ConnectTimeout=10 -o LogLevel=ERROR`, `sudo -n`, `< /dev/null`), and
  output stays small without hiding an error (bound it at its source, write long output to a file
  and read its tail and exit code, `curl -fsS`). `adopt --detect` proposes it for every
  repository, because the habits help in any repository and an agent reads the fragment only when
  it runs a command. [docs/commands.md](docs/commands.md) gives each habit's reason and source.
  A detect pattern `"."` now matches every target.
- `adopt --detect` now proposes the `workspace` fragment when `.agents/worktrees`, `.agents/work`,
  `.agents/handoffs` or `.agents/shared-memory` exists. A folder that holds only `.agents/skills/`
  does not trigger it. The `workspace` fragment is now version 3. Run `adopt` again to update the
  copy.
- Dependabot now proposes updates for the pinned GitHub Actions. The new-issue page now links to
  a private vulnerability report and to the research repository.

### Changed

- The core skill now reads a model's advice from the research repository. It finds the model's
  file with `outcomebound research models/README.md` and reads it with
  `outcomebound research models/<maker>/<model-id>.md`. Without a clone, it uses the public link
  to the first file. Run `adopt` again to install the changed skill.
- [LICENSE](LICENSE) adds an exception to Apache-2.0. You may use, modify and redistribute the text
  that `adopt` writes into your project (managed blocks, fragment files and skills) as part of
  that project. You do not need the licence copy, the changed-file notice or the NOTICE file that
  Sections 4(a), 4(b) and 4(d) require.
- `slice-tickets` now asks which implementer will build the work before it slices, unless you have
  named one. The tickets are the same whatever the answer.

### Removed

- `docs/research/` and `docs/model-guidance.md`. The research moved to outcomebound-research. The
  wheel no longer ships `docs/model-guidance.md`. OutcomeBound's own evaluation record is now
  `docs/evaluations.md`.

## [1.0.0] - 2026-10-01

The operating contract for coding agents, and the engine that installs the contract into a
repository and keeps it current.

### Added

- The operating contract, [OutcomeBound.md](OutcomeBound.md). It tells an agent to do four
  things:
  - Frame every task by its outcome, context, bounds and completion bar.
  - Satisfy all four with the simplest approach that holds for the lifespan.
  - Size the whole plan, not only each step.
  - Report every check as `PASS`, `FAIL` or `UNVERIFIED`.

  The short form of the contract is the block that `adopt` puts at the top of `AGENTS.md`.
- You can install the engine with
  `uv tool install git+https://github.com/rajasdevel/outcomebound@v1.0.0`. `pipx install` of the
  same address works too. So does `pip install` of it into a virtual environment. This puts
  `outcomebound` on `PATH`. The package comes from this repository's own standard-library backend.
  `outcomebound home` prints where the engine's files are.
- `outcomebound adopt` installs, upgrades, checks (`--check`) and removes (`--remove`) the contract
  in a Git work tree. `--detect` proposes the install command from the repository's files. `adopt`
  writes these items:
  - the contract block
  - a block of project facts: the Done commands, the CI test command (read from the workflow
    files), the irreversible edges, and which instructions win a conflict
  - a block of pointers that says when to read each piece of guidance
  - the default skills for each harness used
  - the `@AGENTS.md` import that a harness needs
  - a manifest of what it owns

  `adopt` refuses an owned file that someone edited, unless you use `--force`.
- Harnesses: `amp`, `claude-code`, `codex`, `cursor` and `gemini`. Each one is described, with its
  sources, in [adapters/harnesses.json](adapters/harnesses.json). `generic` serves any other
  harness that reads `AGENTS.md`. The table also has a `pi` row, which `adopt` refuses until its
  route is verified.
- Fragments, which are facts about a stack or a setup that the pointers block names: `python`,
  `node-typescript`, `db-migrations`, `ci-release`, `multi-agent`, `solo`, `team`, `tickets` and
  `workspace`.
- Skills. Every install gets `using-outcomebound`, `decision-brief`, `gather-requirements` and
  `tests-worth-keeping`. The `tickets` fragment adds `slice-tickets`. `adopt-outcomebound` is the
  skill for installing OutcomeBound from this checkout.
- `outcomebound floor` is a quality floor over format, lint, types, secrets and shell scripts. It
  runs the project's own tool configurations. It fits itself to the findings that a project
  already has, with plain-text baselines. It fails only on what is new. It also fails a change
  that loosens the floor, unless a commit names the decision that allowed it.
- `outcomebound tickets` keeps tickets as GitHub issues with a small block of fields. The
  `slice-tickets` skill cuts them. `check` reports what the open tickets say. `brief` prints one
  ticket.
- `outcomebound brief` draws the decisions that an agent puts to a person as decision briefs.
- `outcomebound instructions check` reads the instruction files and settings that each harness
  loads. It reports hidden characters, concealed content, override phrases and risky settings.
- `outcomebound finish-check` and `adopt --finish-check` use the stop hook of Claude Code and
  Codex. The project's Done commands run at the hook. A failure goes back to the agent.
- Evals are fixtures that measure what the contract and the skills change in a model's work. They
  run against the install and against no OutcomeBound ([evals/README.md](evals/README.md)).

[Unreleased]: https://github.com/rajasdevel/outcomebound/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.0.0
