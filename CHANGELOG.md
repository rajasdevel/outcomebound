# Changelog

All notable changes to OutcomeBound are documented here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and OutcomeBound
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The bump comes from what an adopter must do, not from the commit type; see
[docs/VERSIONING.md](docs/VERSIONING.md). Released sections are not edited.

`[Unreleased]` is the staging area for accepted changes.

## [Unreleased]

### Added

- `outcomebound research` prints a file from a clone of
  [outcomebound-research](https://github.com/rajasdevel/outcomebound-research), the research
  repository, headed by the clone's commit, or names the public link where no clone is configured.
  `research clone` and `research pull` preview, and run Git only with `--accept`; `research ingest`
  writes a finding to `.outcomebound/research-inbox/` and prints a prefilled issue link. The clone
  is found at `OUTCOMEBOUND_RESEARCH`, else `~/.outcomebound/research`.
- The `research` fragment, selected with `--fragments`, points a project's agents at it.
- `adopt --human-style ste` adds one project fact: text an agent writes for a person (reports,
  decision briefs, handovers, pull request descriptions, commit messages, documents) follows the
  style of ASD-STE100 Simplified Technical English, with no length limit, every fact kept and the
  project's own terms unchanged. Text a model reads is out of scope. The standard is named, not
  quoted. `--human-style ''` removes the fact; omitted, the recorded choice stays.
- `hand-off-tickets`, a skill the `tickets` fragment installs: an accepted ticket is handed to its
  implementer with a package shaped by the implementer's tier. At the outcome tier the package is
  the ticket alone. At the design tier it adds the approach, signatures, invariants, an edge-case
  table and milestones. At the spec tier the ticket is cut into steps, each with failing tests and
  stubs written first and reviewed before the next. The tier comes from the person, or from the
  research repository's tier table, read with `outcomebound research
  applications/implementer-tiers.md`; without a clone the skill asks the person. At the spec tier
  the brief is compiled with `--detail full`. In a comparison of 63 runs (2026-10-03), the
  spec-tier package raised gpt-6-luna at xhigh from 6 to 9 of 9 and left gpt-6-astra at high at 9
  of 9; the design package's effect did not show, since gpt-6-sol at medium passed 9 of 9 with the
  ticket alone. The `tickets` fragment is now version 6: run `adopt` again to install the skill.
- Dependabot updates for the pinned GitHub Actions, and issue-form links to private vulnerability
  reports and to the research repository.

### Changed

- The core skill finds a model's file with `outcomebound research models/README.md` and reads it
  with `outcomebound research models/<maker>/<model-id>.md`, or the public link to the first
  without a clone. Run `adopt` again to install the changed skill.
- [LICENSE](LICENSE) adds an exception to Apache-2.0: the text `adopt` writes into a project
  (managed blocks, fragment files, skills) may be used, modified and redistributed as part of that
  project without the licence-copy, changed-file notice and NOTICE duties of Sections 4(a), 4(b)
  and 4(d).
- `slice-tickets` asks which implementer will build the work before slicing, unless the person
  has named one. The tickets are the same whatever the answer.

### Removed

- `docs/research/` and `docs/model-guidance.md`: the research moved to outcomebound-research, and
  the wheel no longer ships `docs/model-guidance.md`. OutcomeBound's own evaluation record is now
  `docs/evaluations.md`.

## [1.0.0] - 2026-10-01

The operating contract for coding agents, and the engine that installs it into a repository and
keeps it current.

### Added

- The operating contract, [OutcomeBound.md](OutcomeBound.md): frame every task by its outcome,
  context, bounds and completion bar; satisfy all four with the simplest approach that holds for
  the lifespan; size the whole plan, not only each step; report every check as `PASS`, `FAIL` or
  `UNVERIFIED`. Its short form is the block `adopt` puts at the top of `AGENTS.md`.
- Installing: `uv tool install git+https://github.com/rajasdevel/outcomebound@v1.0.0` (or
  `pipx install` of the same, or `pip install` of it into a virtual environment) puts
  `outcomebound` on `PATH`, from a package built by this repository's own standard-library
  backend; `outcomebound home` prints where the engine's files are.
- `outcomebound adopt`: install, upgrade, check (`--check`) and remove (`--remove`) the contract
  in a Git work tree. `--detect` proposes the install command from the repository's files. It
  writes the contract block, a block of project facts (the Done commands, the CI test command read
  from the workflow files, the irreversible edges, which instructions win a conflict) and a block
  of pointers saying when to read each piece of guidance; the default skills for each harness
  used; the `@AGENTS.md` import a harness needs; and a manifest of what it owns. An owned file
  someone edited is refused without `--force`.
- Harnesses: `amp`, `claude-code`, `codex`, `cursor` and `gemini`, each described in
  [adapters/harnesses.json](adapters/harnesses.json) with its sources; a `pi` row, which adopt
  refuses until its route is verified; and `generic` for any other harness that reads `AGENTS.md`.
- Fragments, facts about a stack or a setup that the pointers block names: `python`,
  `node-typescript`, `db-migrations`, `ci-release`, `multi-agent`, `solo`, `team`, `tickets`
  and `workspace`.
- Skills: `using-outcomebound`, `decision-brief`, `gather-requirements` and
  `tests-worth-keeping` in every install; `slice-tickets` with the `tickets` fragment; and
  `adopt-outcomebound`, for installing OutcomeBound from this checkout.
- `outcomebound floor`: a quality floor over format, lint, types, secrets and shell scripts that
  runs the project's own tool configurations, fits itself to the findings a project already has
  with plain-text baselines, fails only on what is new, and fails a change that loosens it unless
  a commit names the decision that allowed it.
- `outcomebound tickets`: tickets as GitHub issues with a small block of fields, cut by the
  `slice-tickets` skill; `check` reports what the open tickets say and `brief` prints one.
- `outcomebound brief`: draws the decisions an agent puts to a person as decision briefs.
- `outcomebound instructions check`: reads the instruction files and settings each harness loads
  and reports hidden characters, concealed content, override phrases and risky settings.
- `outcomebound finish-check` and `adopt --finish-check`: at the stop hook of Claude Code and
  Codex, the project's Done commands run, and a failure goes back to the agent.
- Evals: fixtures that measure what the contract and skills change in a model's work, run against
  the install and against no OutcomeBound ([evals/README.md](evals/README.md)).

[Unreleased]: https://github.com/rajasdevel/outcomebound/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.0.0
