# Changelog

All notable changes to OutcomeBound are documented here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and OutcomeBound
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The bump comes from what an adopter must do, not from the commit type; see
[docs/VERSIONING.md](docs/VERSIONING.md). Released sections are not edited.

`[Unreleased]` is the staging area for accepted changes.

## [Unreleased]

### Added

- `adopt --human-style ste` adds one project fact: text an agent writes for a person (reports,
  decision briefs, handovers, pull request descriptions, commit messages, documents) follows the
  style of ASD-STE100 Simplified Technical English, with no length limit, every fact kept and the
  project's own terms unchanged. Text a model reads is out of scope. The standard is named, not
  quoted. `--human-style ''` removes the fact; omitted, the recorded choice stays.

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
