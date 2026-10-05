# Changelog

All notable changes to OutcomeBound are documented here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and OutcomeBound
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The bump comes from what an adopter must do, not from the commit type; see
[docs/VERSIONING.md](docs/VERSIONING.md). Released sections are not edited.

`[Unreleased]` is the staging area for accepted changes.

## [Unreleased]

### Added

- `outcomebound tickets export` prints two lines: the absolute path of the pinned query that the
  install ships, as a shell comment, and the `gh` command that writes the export of the declared
  repository to `issues.json`. It runs nothing and writes nothing. Before, this command was only in
  the text of the `INPUT_REQUIRED` refusal, and `tickets --help` did not show a way to make an
  export. `INPUT_REQUIRED` now also names the `export` verb.
- The `input:` line of the `tickets check` text report now gives the lowest and the highest issue
  number that the export holds, for example `input: issues.json; modified 2026-09-20T09:00:00Z;
  age 120s; holds #1 to #42`. The JSON report does not change.
- `tickets check --draft` gives the warning `REPEATED_GUIDANCE`, about the run and with no ticket
  id, when two or more drafts are given and a paragraph is in the body of every draft. An example
  is the same paragraph under `## Limits` in each draft of a breakdown. The warning gives the
  first words of the paragraph and the heading that it is under, one time for each paragraph. A
  paragraph is the lines between blank lines, and the comparison ignores the spaces and line
  breaks in it. Headings, the block and the placeholder text of the issue template are not
  compared. No number of drafts and no length of a paragraph is part of the condition. The
  `slice-tickets` skill already tells the slicer to keep such guidance out of the tickets, because
  the tickets fragment says it one time. The warning tells the slicer to drop repeated process
  guidance, and to keep a repeated behaviour that each ticket must meet or move it to a contract
  section that each ticket names in `reads`. The warning does not change the result of the run.

### Changed

- adopt now records one more field in `.outcomebound/manifest.json`, which stays at format 2:
  where the `local` fragment is selected, the `guidance-pointers` record holds `frame`, the sha256
  of the block with the inline text of the local fragment replaced by the mark `\0local\0` (a NUL
  character, `local`, a NUL character). The first install with this release adds the field, so
  `git status` shows the manifest as changed. Commit it. No other step is necessary. An engine of
  1.1.1 or earlier keeps working with this manifest: it ignores the field, and it removes the field
  when it writes the manifest again. adopt reads a record with or without the field.
- Upgrade step for the release: if your CI installs a pinned release and runs
  `outcomebound adopt . --check`, change the pin and commit the result of `outcomebound adopt .`
  in the same change. An engine reads an install that a different release wrote as stale, in the
  two directions: with the old pin and the new install, the check fails, and with the new pin and
  the old install, the check also fails. docs/VERSIONING.md now says this under "How to take a
  release".

### Fixed

- Ctrl-C, or SIGTERM during `adopt --finish-check`, that arrived just after a Done command had
  started, and before the engine had a handle on it, stopped the engine but left the command
  running. Now the engine holds the signal while the command starts, then acts on it, and stops
  the command's process group as at any other time.
- `tickets brief owner/name#20` refused with `TICKET_NOT_FOUND`, also when the export held `#20`
  of the declared repository `owner/name`. Now `<owner>/<name>#<n>` is `#<n>` when it names the
  declared repository, without case. When it names a different repository, `brief` refuses with
  `TICKET_NOT_FOUND` and names the two repositories.
- When the export does not hold a ticket, `TICKET_NOT_FOUND` now gives the path of the export, the
  time that it was written, its age, and the lowest and the highest issue number that it holds,
  and tells you that a ticket newer than the export needs a new export. Before, the refusal did
  not show that the export was older than the ticket. No verb refuses an export because of its
  age.
- adopt refused to upgrade a `guidance-pointers` block without `--force` when a commit had changed
  the local fragment and made the same change in the block, and the new release also renders the
  block in a different way. For example, a release that changes the condition of a selected
  fragment changes its pointer line. The block was then neither its record nor the new render, so
  adopt read it as a person's edit. Now adopt finds that the block is the render of the previous
  release with only the edit of the local fragment in it. It writes the block again without
  `--force`, and it names the block on a `render` line. `adopt --check` reads the block `stale`,
  not `edited`. A record with a `frame` decides this with the `frame`. A record without it, as
  1.1.1 and earlier write, makes adopt read the earlier texts of `.outcomebound/fragments/local.md`
  from the Git history of the project. If Git does not hold the text of the fragment that the previous install rendered,
  or if the block holds a different edit too, adopt refuses as before.
- `floor check --base` reported a commit as "carries no Floor-Loosening line" when the commit
  had a `Floor-Loosening:` line that did not parse, for example `Floor-Loosening: baseline; ruled
  Project D31`, where the id has a space in it. Now the reason says that the commit "carries a
  Floor-Loosening line that does not parse", and it shows the correct form: `<what>; ruled <id>`,
  with an id of one word (`Project-D31`, not `Project D31`). The verdict does not change: a line
  that does not parse does not rule a loosening.
- `research <path>` for a file under `models/` that is not in the clone said only that `INDEX.md`
  lists every document. Now it says that `models/README.md` tells which models have a file, and
  that a model with no file takes the spec tier (`applications/implementer-tiers.md`).
- A claims plan can declare a `required_paths` entry that an open ticket will add, such as a test
  file. Before, adopt gave one `warning  tickets:` line for each such claim at each install, and
  `tickets check` gave `CLAIM_PATH_ABSENT`. Each told the person to point the plan's `cwd` at the
  checkout root, also when the `cwd` was already `".."`. Now these warnings come only when the
  checkout holds the path from the checkout root but not from the plan's working directory, which
  shows that the `cwd` is wrong. A path that the checkout holds in neither place is a planned path.
  Neither command warns about it, and a run of that claim reads `UNVERIFIED` until the path exists.
- On Python 3.10 to 3.13, adopt and `instructions check` stopped with a permission error when a
  folder under the target was not readable, for example a folder with mode 000. adopt stopped
  with `adopt: [Errno 13] Permission denied: '<folder>/.git'` in an install and in a dry run.
  `instructions check` stopped in a target outside Git, and in a target whose `.agents/handoffs/`
  or `.agents/shared-memory/` held such a folder. Now each walk passes over a folder that it
  cannot read. In a note folder, `instructions check` lists that folder, and it reads
  `UNVERIFIED`, because no check read the notes in it. These walks now go through one helper, and
  a test keeps a new walk of a target from going around it.
- adopt gave a byte-cap warning for each folder under the target that held an `AGENTS.md` past
  the cap, also in folders that Git ignores. A project that keeps scratch copies of itself in an
  ignored folder got one warning for each copy. Now adopt does not measure a folder that Git
  ignores, as discovery and `instructions check` already do not read it. Another clone does not
  get such a folder.
- `instructions check` gave an `UNVERIFIED concealed-content` line for a commit or checksum hash
  that a label or a word touches with no space, such as `SHA256` followed by 64 hex characters, or
  a word, 40 hex characters and a word. The check reads a run of 60 or more base64 characters with
  no space as a possible hidden payload. Before, the check did not flag a 40- or 64-character hex
  hash only when it stood alone or after `name=`. Now the check takes a stretch of hex characters
  out of the run when the stretch is 40 to 44 or 64 to 68 characters long: one hash, and at most 4
  more hex characters, such as the last letter of `image`. Then it reads the remaining characters
  of the run. When fewer than 60 remain, the run is not flagged. A stretch of any other length
  stays in the run, so a hex run of 60 to 63 characters, or of 69 or more, is still flagged, as is a
  base64 payload of 60 or more characters that a hash touches. A run cut into pieces by hashes, or
  by any base64 character that is not hex, is read as the same pieces between spaces were before.

## [1.1.1] - 2026-10-04

A patch release. adopt now reports a `tickets` claims plan whose claims run in a folder that the
plan was not written for, and it no longer reads a block that holds what it writes as an edit.

Do these steps first:

1. If a `tickets` claims plan has no `cwd`, examine it too. 1.1.0 step 6 names only a relative
   `cwd`, but a plan with no `cwd` also starts at the folder of the plan file. A plan in
   `.outcomebound/` that runs its claims at the checkout root needs `"cwd": ".."`. Run
   `outcomebound adopt .` again: the install report now shows a `warning` line for each such plan,
   with the `cwd` to write.

### Fixed

- A recorded block or file that holds what `adopt` writes there now, but not what it recorded,
  is no edit. An example is a guidance-pointers block that a person changed with the local
  fragment it comes from. `adopt --check` read it `edited` and told the person to use `--force`.
  Now `--check` reads it `stale` and says why, and `adopt` records it without `--force` and
  names it on a `kept` line. A block or file that differs from both is refused without
  `--force`, as before.
- A claims plan below the checkout root with no `cwd`, or with `"cwd": "."`, runs its claims in the
  folder of the plan file. Before, `tickets check` gave no warning for such a plan when its claims
  declared no `required_paths`, and adopt gave no warning at all.

### Added

- `tickets check` gives the warning `CLAIM_CWD_PLAN_FOLDER`, about the plan and with no ticket id,
  when the plan's claims run in the folder of the plan file and that folder is not the checkout
  root. Its next step gives the `cwd` that runs the claims at the root, `..` from `.outcomebound/`.
- adopt, at each install and upgrade, gives a `warning` line for the claims plan that
  `.outcomebound/tickets.json` declares: one for each claim that `CLAIM_PATH_ABSENT` names, and one
  for the condition of `CLAIM_CWD_PLAN_FOLDER`. Each line gives the `cwd` to write. adopt does not
  change the plan and refuses nothing. `tickets check` and adopt use one rule for both conditions.

## [1.1.0] - 2026-10-04

A stop now holds one item, never the run. No limit applies to size, count, length or time unless
you set it, a harness documents it, or a measurement supports it. The finish check can keep the
failures that Done already has as known failures, and then it holds a turn only on a new failure.

Do these steps first:

1. Run `outcomebound adopt .` again. Until you do, `adopt --check` reads each 1.0.0 finish-check
   entry as `stale`, and your install does not get the new fragments, skills and templates.
2. In Codex, trust the changed finish-check entry again in `/hooks`. The install report shows an
   `action` line for each changed `codex` entry.
3. If an edge in `.outcomebound/fragments/local.md` contains a `;`, split it into two list items,
   or put a comma in place of the `;`. adopt refuses such an edge.
4. If your project publishes a package and selects no `ci-release` fragment, add
   `publishing a package` to `edges:` in your local fragment. Add `moving a shared registry tag`
   too if your project does that. The `python` and `node-typescript` fragments do not add
   publishing edges now.
5. If you wrote `.outcomebound/.gitignore` yourself, move its lines to the root `.gitignore` and
   delete the file. Then run adopt again. adopt refuses that file, also with `--force`.
6. If a `tickets` claims plan has a relative `cwd`, examine it. A relative `cwd` now starts at the
   folder of the plan file. A plan in `.outcomebound/` that runs its claims at the root needs
   `"cwd": ".."`.
7. Put a `Floor-Loosening:` line in each commit that loosens the floor. A line now rules only the
   loosenings of its own commit, so a range that passed before can fail.
8. If a `validation` claim must stop after a time, set `timeout_seconds` on the claim or on the
   plan. `validation` has no default timeout now.

### Security

- `floor check --base`: a `Floor-Loosening: <what>; ruled <id>` line rules only the loosenings
  that its own commit makes. Before, one line anywhere in the range let every loosening in the
  range pass.
  - A merge commit carries the line for a loosening that its own edit makes. A loosening that a
    side commit makes stays the side commit's to rule.
  - A loosening in a file that a later commit renames counts at the path of the file at HEAD. The
    result is the same in each merge order of the rename and the loosening.
  - The first baseline of a claim is not a loosening only when the claim is new at HEAD. A claim
    that the range drops and then adds again does not get this exemption.
  - A tool config loosens by each line that it gains, loses or moves. A blank line, or spaces at
    the end of a line, do not count.
  - `<what>` stays free text, so the lines in earlier commits read as before.
- In `pyproject.toml`, the loosening check also reads the `[tool]` table and the lines before the
  first header. There, a dotted key such as `tool.ruff.lint.ignore = ["F401"]` changes a ruff or
  mypy setting, and the check did not see it before. A dotted key there for another tool also
  reads as a change.

### Added

- Each release is now a GitHub release with the wheel and the source archive. CI builds them from
  the tagged commit, attests them with signed build provenance, and publishes the release only
  when every check on the tag passes. Verify a downloaded file with
  `gh attestation verify <file> -R rajasdevel/outcomebound`.
- `adopt --finish-check` now runs the Done commands one time, after its writes. It runs each
  command to its end, past each failure, with no time limit. It shows the verdict and the seconds
  of each command. When Done takes longer than the timeout less 30 seconds, it shows `UNVERIFIED`
  and gives a larger `--finish-timeout` to use. An install without `--finish-check` does not run
  Done. It shows the record that applies, or it says that Done was not measured.
- Known failures: adopt keeps each Done command that fails at this measurement, with its exit code
  and the failure ids that its output names. The record is in the Git common directory and is not
  committed. At a turn end, the finish check does not hold the turn while a known command fails
  with the same exit code and names no new failure id. It reads failure ids from the summary lines
  of pytest, unittest, go test, cargo test, jest, vitest and make. Where neither the record nor the
  output names a failure id, the exit code alone decides, and the report says so.
  - A record applies only in a checkout whose HEAD descends from the measured commit. In other
    checkouts, every failure holds the turn.
  - A known command that passes leaves the record, so its next failure holds the turn.
  - When a new measurement replaces a record, adopt prints each failure that the earlier record did
    not hold. Read this output: an agent that runs `adopt --finish-check` after its change broke
    the code makes those failures known.
- `adopt --finish-timeout SECONDS` sets the time for the Done commands at a turn end. The default
  is 600 seconds, the documented default of both harnesses.
- `tickets publish --draft <file>...` prints a POSIX shell script that publishes the drafts as
  issues with `gh`. The script creates the issues in the order of their relations, and sets
  `--parent` and `--blocked-by`. It applies the ticket label, and the hold label for a
  `human-only: yes` ticket. The verb runs `check --draft` first and refuses with
  `PUBLISH_REFUSED` on an error. It runs nothing itself.
- The ticket block key `waits-on: <brief id>, ...` names the decision briefs that a ticket waits
  on. `tickets check` shows it as `WAITS_ON_BRIEF`, and `tickets brief` adds a `## Waits on`
  section. Other tickets stay startable.
- `tickets check` gives the warning `CLAIM_READS_OUTSIDE_BOUNDS` when a `done-when` claim declares
  `required_paths` that the ticket's `bounds` do not cover.
- `tickets check` gives the warning `CLAIM_PATH_ABSENT` when a claim declares a `required_paths`
  entry that the checkout does not hold, as it resolves from the plan's `cwd`. A plan in
  `.outcomebound/` with `"cwd": "."`, written for 1.0.0, gets this warning (step 6 above).
- A floor claim can set `timeout_seconds`, and `prefix` for a container or environment runner such
  as `docker compose run --rm app` or `uv run`. The tool still comes first in the argv. A change
  to `timeout_seconds` is not a loosening.
- `floor propose` offers the new `secrets` recipe to each project in which Git tracks a file, not
  only to a Python project. A floor that already holds `python.secrets` keeps it. For a TypeScript
  project, `propose` says why it gives no type or lint claim, and prints `tsc --noEmit` and
  `eslint .` as claims that the project can add.
- Every install writes `.outcomebound/.gitignore`, which adopt owns. It keeps `research-inbox/` and
  each `.outcomebound-checks/` below `.outcomebound/` out of Git. A validation plan outside
  `.outcomebound/` writes `.outcomebound-checks/` next to it, and the project must ignore that
  folder itself.
- adopt gives warnings, and refuses nothing, for these conditions:
  - a path that the install writes and that Git ignores. The warning names the rule.
  - a change to a tracked `AGENTS.md` that has changes that are not committed.
  - a `CLAUDE.md` or `AGENTS.md` above the target that Claude Code also loads.
  - instruction files that load into one folder and pass a harness's documented byte limit.
- With `codex`, the install report shows one `UNVERIFIED` line about the Codex sandbox: how to add
  `.agents` and the Git common directory as writable roots.
- The `claude-code` row of `adapters/harnesses.json` has an optional `ancestors` field: the
  instruction files that Claude Code loads from the folders above the working directory.
  `instructions check` names each such file above the target as a review hit that does not change
  the result.
- Each finding of `instructions check --json` has a new field, `decides`. A finding with
  `decides: false` is reported but does not change the exit code.
- A GraphQL error inside one issue of the export holds only that issue (`EXPORT_PARTIAL`). The
  export asks for 100 labels and blockers for each issue.

### Changed

- The goal envelope (`templates/goal/goal.md`):
  - It has no Size line and no size stop. No ruling or measurement supported that stop.
  - An act outside the authorized acts, a check that does not go green, or an unanswered decision
    holds only its item. The agent records the hold one time, when it starts, and continues with
    every item that does not depend on it. The run ends only when every item is closed and the
    Done checks pass, or when no item can continue.
  - A continuation turn does not ask a held question again. The run does not replace the goal's
    objective with its own text.
  - New lines: Decisions gives the answers that you have, and the run starts without answers.
    Order gives the order of the items. Follow-ups lets the envelope accept the issues that the run
    files for work that it finds. Handoff names the path of the handoff.
  - Not authorized always names every credential act: unlock a credential store, add a key to an
    SSH agent, log in, and read or print a secret.
  - The note tells you to paste the envelope as one block, as the run's first message, and to keep
    your own instructions outside that block. The handoff has no page limit.
- The kernel and the contract say "hold" for one item, not "stop" for the run. Where a ticket, a
  package or a delegation names the paths of an item, those paths are the authority of that item.
  Where nothing names them, a path inside your owned scope is not wider scope.
- A spec has no word limit in the contract, the spec template or the core skill. It holds only the
  decisions that the code cannot show, and no decision is cut to make it shorter. The plan template
  has no step limit.
- Skills:
  - A decision brief never ends the turn. It holds only the work that waits on its answer.
  - `decision-brief`: each brief gets an id that no other session can take. Where the project keeps
    one numbering for briefs, the agent takes the next id from it. Otherwise it puts the task's
    name before the number, for example `fix-login-D1`.
  - `hand-off-tickets` does not ask you for the implementer or its tier. It names the implementer
    that it starts. A tier that the project's committed instructions give a model comes before the
    placement table. Where neither places the model, the handover says so and uses the spec tier.
  - A spec-tier package names the acts that end a step, not "when to stop rather than guess".
  - A ticket that cannot be built as written gets a follow-up or a brief, and the other tickets
    continue.
  - `slice-tickets` draws `bounds` as wide as the authority of the outcome. Where a `done-when`
    command reads more than the ticket's own paths, the `bounds` cover what it reads, or a repair
    ticket comes first. The skill publishes with the script of `tickets publish`. It settles a
    contract gap that a later commit can undo, and gives you only a gap that is hard to undo.
  - A failed `gh` command runs again from a new export.
- Fragments:
  - `workspace` (version 5): a FAIL on a note means that the agent does not rely on that note.
    Every other result of `instructions check` goes into the handoff and blocks nothing.
    - In Codex, the agent asks you one time to add `.agents` and the Git common directory as
      writable roots. Until you do, it holds each item that writes there and continues with reads
      and checks.
    - A scan that walks ignored folders reads each worktree as a second copy of the repository, so
      the agent runs such a scan from the worktree's root.
    - The commits of a worktree land as the project's instructions or the goal envelope say.
    - The finish-check hook checks only the session's working directory. Before the agent lands
      work from a worktree, it runs Done in that worktree.
    - Work in another repository goes in a session that starts there, so that its hooks and
      sandbox apply.
    - A handoff that starts a run gives you one block to paste. Remove a worktree only when its
      task is finished and nothing in it is still needed.
  - `python` and `node-typescript` (version 5) add no publishing edges. `ci-release` (version 5)
    also names "moving a shared registry tag" as an irreversible edge.
  - `templates/fragment-local.md` states three rules: all five slots are present, only mechanism
    ids take backticks on the Mechanisms line, and an edge is one line with no `;`.
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
  - A command that cannot start in the hook's environment (exit 126 or 127) reads `UNVERIFIED` and
    does not hold the turn.
  - On Claude Code, it waits while scheduled wake-ups are set, as it does for background tasks.
  - The hold text tells the agent to fix what its change broke and continue.
  - The entry command now carries `--timeout N`.
  - The documentation says what Codex shows the model and the person, and that a changed entry
    needs a new trust. That a Codex release runs the hook stays `UNVERIFIED`.
- The quality floor:
  - No fixed time limit applies to a tool, a version probe, a Git read or `provision`.
  - `check` shows every new finding.
  - A claim whose pattern matches no tracked file reads PASS, with 0 findings in 0 files. To drop
    such a claim is still a loosening.
  - A rename carries its baselined findings.
  - The loosening range starts at the floor's adoption commit when the merge base has no floor and
    no commit from the merge base to the adoption commit touches `floor.json`. Then the secrets
    claim also scans the tracked files.
  - Without a base, gitleaks reads only the tracked files.
  - A baseline line is `path:code`. An older `path:code:message` line still reads.
  - A folder or Python file that Git tracks, added to a types claim, is not a loosening. Any other
    added word is a loosening, also a word that starts with `@`, which mypy reads as a file of
    options.
  - The proposed types claim names each outermost folder whose `__init__.py` Git tracks, where the
    mypy config names no `files`.
  - `floor apply` and `floor remove` print `next: outcomebound adopt <root>` when they add or
    remove `floor.json` in an install.
- adopt:
  - `adopt --detect` proposes the floor's `--base` from the remote's default branch, and says when
    no default branch resolves. It reads `.codex/` as a sign of `codex`. A test command that comes
    from discovery and not from CI gets a comment: the command runs on the host.
  - adopt reads every CI workflow file.
  - `discovery` does not enter a folder that Git ignores, or a folder with its own `.git`.
- `instructions check`:
  - `--harness` accepts a comma list, as `adopt --harness` does.
  - adopt's own finish-check entry stays a review hit, and its fact quotes the Done commands that it
    runs. The hit does not change the result only when the entry is exactly what adopt writes for
    the Done commands of the manifest and of `AGENTS.md`. Exit 2 again means that something needs
    action.
  - A hidden character in a note reads `UNVERIFIED` for that note, not FAIL for the repository.
  - A review hit asks for a person at the handoff, not before the work.
  - A harness row past its re-check date says that only the re-check is due.
- Tickets:
  - `tickets brief . 20` names the ticket `#20`.
  - A `bounds` entry can end in `/`. A `reads` entry with no `#anchor` names the whole file.
  - `tickets check` shows all `CLAIM_PLANNED` warnings as one row. `--json` still lists each claim.
  - On a `human-only: yes` ticket, the item `<name>: human: <observation>` in `done-when` names the
    person's own check. On every other ticket it is still an error.
  - `tickets check --draft` gives `RELATION_UNCHECKED` for a relation to a published ticket.
  - `INPUT_REQUIRED` prints the export command for the declared repository.
  - `tickets brief`: at a limit, the implementer finishes every part that the limit does not
    block. Without `CONTRIBUTING.md`, the implementer commits on its own branch. The brief has no
    size line. A claim with no timeout shows "no timeout".
- Designs and the prompt standard:
  - Rule S23 in `docs/prompt-standard.md`: a number or a stop in text that a model reads names
    its evidence. A test holds this rule over the contract, the kernel, the templates, the
    fragments and the skills.
  - Each gate design (floor, finish check, instructions, tickets) states the invariant that its
    gate holds, which data each verdict reads, and who can write that data.
- For contributors: the floor claim `public-text` fails on a home path or a person's email
  address in a tracked file, or in a commit of the range (its message, author and committer). `make scrub` also applies a local list of private terms, which
  `OB_SCRUB_LIST` names, and reads `UNVERIFIED` without it. `CONTRIBUTING.md` says what public
  text leaves out.

### Fixed

- `floor provision` does not install a tool that is on `PATH` at its `min_version` or later, so it
  does not ask a system Python that pip refuses.
- When mypy stops (exit 2), the floor shows the error that stopped it. It gives the advice about
  `files` only for the module-mapping hint.
- When ruff or mypy cannot write its cache in the tree, the floor gives it a temporary cache
  folder. A claim with a `prefix` does not get it.
- A local-fragment edge with a `;` read as two edges. Now adopt refuses it and names the rule.
- `tickets` and `validation` resolve a relative claims-plan `cwd` from the same folder: the folder
  of the plan file.
- `tickets check` refuses a `bounds` entry such as `src/[]` or `src//`, and a `discovered-from`
  that names the ticket itself.

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

[Unreleased]: https://github.com/rajasdevel/outcomebound/compare/v1.1.1...HEAD
[1.1.1]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.1.1
[1.1.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.1.0
[1.0.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.0.0
