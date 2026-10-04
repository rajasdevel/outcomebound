# Changelog

All notable changes to OutcomeBound are documented here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and OutcomeBound
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The bump comes from what an adopter must do, not from the commit type; see
[docs/VERSIONING.md](docs/VERSIONING.md). Released sections are not edited.

`[Unreleased]` is the staging area for accepted changes.

## [Unreleased]

OutcomeBound now lets an agent work for many hours inside clear bounds. A stop holds one item, never
the run, and no limit applies to size, count, length or time unless you set it, a harness documents
it, or a measurement supports it. The overnight runs of 2026-10-04 in six adopting projects showed
the problems that this release removes. Run `outcomebound adopt .` again to get the changes.

### Changed

- The goal envelope (`templates/goal/goal.md`) has no Size line and no size stop. One run stopped
  after less than an hour of work on that stop, which no ruling or measurement supported.
  - An act outside the authorized acts, a check that does not go green, or an unanswered decision
    holds only its item. The agent records it and continues with every item that does not depend
    on it. The run ends only when the Done checks pass or no item can continue.
  - The run starts without answers. A new Decisions line gives the answers that you have.
  - A new Follow-ups line lets the envelope accept the issues that the run files for work it finds.
  - The handoff has no page limit.
- The kernel and the contract say "hold" for one item, not "stop" for the run. A path just outside
  one item's file list, but inside the granted authority, is not wider scope.
- A spec has no word limit in the contract, the spec template or the core skill. It holds only the
  decisions that the code cannot show, and no decision is cut to make it shorter. The designs of
  this repository have no word limit either. The plan template has no step limit.
- Skills:
  - A decision brief never ends the turn. It holds only the work that waits on its answer.
  - `hand-off-tickets` does not ask you for the implementer or its tier. It names the implementer
    that it starts. Without a research clone, it reads the public tier table, and if no table can
    be read, it uses the spec tier.
  - A spec-tier package names the acts that end a step, not "when to stop rather than guess".
  - A ticket that cannot be built as written gets a follow-up or a brief, and the other tickets
    continue.
  - `slice-tickets` draws `bounds` as wide as the authority of the outcome. It settles a contract
    gap that a later commit can undo, and gives you only a gap that is hard to undo.
  - A failed `gh` command runs again from a new export.
- Fragments:
  - `workspace`: a FAIL on a note means that the agent does not rely on that note. Every other
    result of `instructions check` goes into the handoff and blocks nothing. Remove a worktree
    only when its task is finished and nothing in it is still needed. In the Codex sandbox, the
    agent continues with the work that needs no refused write.
  - `commands`: a long command runs in the background, with its output in a file. Slow is not
    hung: the agent never shortens, skips or stops a check because it takes long.
  - `tickets`: where neither `CONTRIBUTING.md` nor `AGENTS.md` says how work lands, the agent uses
    the goal envelope, else local commits on the current branch. It puts the question in the
    handover and goes on to the next ticket.
  - `db-migrations`: a test database from the project's own test setup, or a local one with
    synthetic data, is in scope.
  - `solo`, `research`, `multi-agent` and `ci-release`: unattended work continues inside its
    bounds.
- The finish check:
  - It remembers every verdict for the working tree. On an unchanged tree it runs nothing, and it
    shows an earlier failure again without holding the turn.
  - A command that cannot start in the hook's environment (exit 126 or 127) reads UNVERIFIED and
    does not hold the turn.
  - On Claude Code, it waits while scheduled wake-ups are set, as it does for background tasks.
  - The hold text tells the agent to fix what its change broke and continue.
  - The entry command now carries `--timeout N`. Each 1.0.0 entry reads `stale` until you run
    `adopt` again, and Codex asks you to trust the changed hook in `/hooks`.
- The quality floor:
  - No fixed time limit applies to a tool, a version probe or a Git read.
  - `check` shows every new finding.
  - A claim whose files no longer exist reads PASS, and dropping it is not a loosening.
  - A rename carries its baselined findings.
  - The loosening range starts at the floor's adoption commit when the merge base has no floor.
  - Without a base, gitleaks reads only the tracked files.
  - A baseline line is `path:code`. An older `path:code:message` line still reads.
- `tickets brief`: at a limit, the implementer finishes every part that the limit does not block.
  Without `CONTRIBUTING.md`, the implementer commits on its own branch. The brief has no size line.
  A claim with no timeout shows "no timeout".
- `validation` has no default timeout: a claim waits for its command unless the plan or the claim
  sets `timeout_seconds`.
- `instructions check`:
  - A hidden character in a note reads UNVERIFIED for that note, not FAIL for the repository.
  - A review hit asks for a person at the handoff, not before the work.
  - adopt's own finish-check entry stays a review hit, and its fact quotes the Done commands that
    it runs.
  - A harness row past its re-check date says that only the re-check is due.
- `adopt --detect` proposes the floor's `--base` from the remote's default branch. adopt reads
  every CI workflow file.

### Added

- `adopt --finish-timeout SECONDS` sets the time for the Done commands at a turn end. The default
  is 600 seconds, the documented default of both harnesses.
- The ticket block key `waits-on: <brief id>, ...` names the decision briefs that a ticket waits
  on. `tickets check` shows it as `WAITS_ON_BRIEF`, and `tickets brief` adds a `## Waits on`
  section. Other tickets stay startable.
- A floor claim can set `timeout_seconds`, and `prefix` for a container or environment runner such
  as `docker compose run --rm app` or `uv run`. The tool still comes first in the argv.
- A GraphQL error inside one issue of the export holds only that issue (`EXPORT_PARTIAL`). The
  export asks for 100 labels and blockers for each issue.
- adopt warns where the instruction files that load into one folder pass a harness's documented
  byte limit.

## [1.0.0] - 2026-10-04

The first public release: the operating contract for coding agents, and the engine that installs
the contract into a repository and keeps it current.

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
  `node-typescript`, `db-migrations`, `ci-release`, `multi-agent`, `solo`, `team`, `tickets`,
  `workspace`, `commands` and `research`.
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
- You can read the research repository from your project. `outcomebound research [PATH]` prints a
  file from a clone of [outcomebound-research](https://github.com/rajasdevel/outcomebound-research).
  The first line of the output is the clone's commit and the sha256 of the file's text. Where no
  clone is configured, the command names the public link. The command finds the clone at
  `OUTCOMEBOUND_RESEARCH`, else at `~/.outcomebound/research`.
- You can fetch and update the clone. `research clone` and `research pull` only preview. They run
  Git only with `--accept`, with the same Git options, and without `GIT_TEMPLATE_DIR` and
  `GIT_EXEC_PATH` in the environment.
- You can send a finding back. `research ingest` writes the finding to
  `.outcomebound/research-inbox/` and prints a prefilled issue link. The inbox file is a local
  record that nothing reads or sends.
- The `research` fragment, selected with `--fragments`, points your project's agents at the
  research repository. The core skill reads a model's advice from it: it finds the model's file
  with `outcomebound research models/README.md` and reads it with
  `outcomebound research models/<maker>/<model-id>.md`. Without a clone, it uses the public link
  to the first file.
- Your agents write reports, decision briefs, handovers, pull request descriptions, commit
  messages and documents for people in plain, short sentences. `adopt --human-style ste` adds
  this as one project fact in `AGENTS.md`. The text follows the style of ASD-STE100 Simplified
  Technical English, with no length limit, every fact kept and the project's own terms unchanged.
  Text that a model reads is out of scope. The standard is named, not quoted. `--human-style ''`
  removes the fact. If you omit the option, the recorded choice stays.
- Your agent hands an accepted ticket to its implementer with a package that fits the
  implementer. This is the skill `hand-off-tickets`, which the `tickets` fragment installs.
  `slice-tickets` asks which implementer will build the work before it slices, unless you have
  named one; the tickets are the same whatever the answer. The package depends on the
  implementer's tier:
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
  harness, with 9 runs a cell ([docs/evaluations.md](docs/evaluations.md), E17). The comparison
  measured hand-written packages, not the `hand-off-tickets` skill. `--detail full` alone scored
  6 of 9, the same as the ticket alone. By the rules written before the runs, it would be cut. The
  project keeps it as the default brief of the spec tier, to be judged on longer work.
- A `commands` fragment gives agents command habits: no pager, editor, credential prompt or
  open stdin can hang a run (`git --no-pager`, `git commit -m`, `GIT_TERMINAL_PROMPT=0`,
  `ssh -o BatchMode=yes -o ConnectTimeout=10 -o LogLevel=ERROR`, `sudo -n`, `< /dev/null`), and
  output stays small without hiding an error (bound it at its source, write long output to a file
  and read its tail and exit code, `curl -fsS`). `adopt --detect` proposes it for every
  repository, because the habits help in any repository and an agent reads the fragment only when
  it runs a command. [docs/commands.md](docs/commands.md) gives each habit's reason and source.
  A detect pattern `"."` matches every target.
- A guide to the agent workspace: [docs/workspace.md](docs/workspace.md). It says how to select the
  `workspace` fragment, what `adopt` writes and removes, what Git keeps and ignores, what a handoff
  holds, and what the fragment does not give you. `adopt --detect` proposes the `workspace`
  fragment when `.agents/worktrees`, `.agents/work`, `.agents/handoffs` or `.agents/shared-memory`
  exists. A folder that holds only `.agents/skills/` does not trigger it.

- Every Git read of a target runs with no pager, no fsmonitor, no untracked cache and no external
  diff (`adopt --detect`, `discovery`, `tickets brief`, `floor` and `finish-check`). A
  `core.fsmonitor` setting in the target's `.git/config` does not run a program.
- `floor provision --accept` runs pip isolated (`python -I -m pip`), so a `pip` package committed
  in the target does not run in place of pip.
- [LICENSE](LICENSE) is Apache-2.0 with an exception. You may use, modify and redistribute the
  text that `adopt` writes into your project (managed blocks, fragment files and skills) as part
  of that project. You do not need the license copy, the changed-file notice or the NOTICE file
  that Sections 4(a), 4(b) and 4(d) require. The wheel's `License` field says that the license
  has an exception.
- Dependabot proposes updates for the pinned GitHub Actions. The new-issue page links to a
  private vulnerability report and to the research repository.

[Unreleased]: https://github.com/rajasdevel/outcomebound/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.0.0
