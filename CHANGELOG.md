# Changelog

All notable changes to OutcomeBound are documented here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and OutcomeBound
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The bump comes from what an adopter must do, not from the commit type; see
[docs/VERSIONING.md](docs/VERSIONING.md). Released sections are not edited.

Each release section is written when the release is prepared, from the pull requests that
landed since the previous release; a pull request does not edit this file.

## [Unreleased]

## [1.8.0] - 2026-10-19

A minor release. Nine new read-only or planning commands help an agent find the state of the
work again, check one ticket, review a change with other reviewers, and look after worktrees
(#140, #141, #142, #147, #148, #149, #150, #151), and the skills name them where they help (#155). The decision brief now reads in the order a
person decides (#139). The kernel has two short rules for reports in place of one long sentence,
and Simplified Technical English applies only to documents that a person keeps (#143). `adopt`
tells a person how to install `outcomebound` in a cloud session (#146) and warns of a worktree
with an older install (#145). The designs agree with the code again (#152), and four defects found on the way are fixed (#154). A new skill, `review-council`, makes 14 skills in each install
(#151). The engine remains Python standard library only.

Do these steps first:

1. If you upgrade from 1.6.0 or earlier, do the steps of the 1.7.0 section first. Use Python 3.10
   or later and Git 2.52.0 or later. These minimums do not change.
2. Install the release: `uv tool install --force outcomebound==1.8.0`. The tagged Git URL
   (`git+https://github.com/rajasdevel/outcomebound@v1.8.0`) installs the same release.
3. In each project, run `outcomebound adopt . --check`, then `outcomebound adopt .`. Review the
   diff and commit it with the project's own checks (#139, #143, #146, #151, #155):
   - The install changes the kernel (the two report rules), the `Text for people` fact, the
     skill `decision-brief` and the other skills that name the report labels.
   - The install adds the skill `review-council` and changes the fragments `commands` (9) and
     `workspace` (13).
   - The install changes the skills `decision-brief`, `hand-off-tickets`, `review-findings` and
     `tests-worth-keeping`, which now name the new commands.
   - A project that declares a ticket store gets the fragment `tickets` (15).
4. Cloud sessions: a cloud session starts from a fresh clone, and the clone has no `outcomebound`
   command. `adopt` now prints the install line, pinned to the engine version
   (`uv tool install outcomebound==1.8.0` and `python3 -m pip install outcomebound==1.8.0`), and
   the place where each harness that the project uses keeps its setup step. A person adds the
   line to the setup step of the cloud environment. `adopt` writes no file for this (#146).
   Where the project records a `Setup` fact, record the install line with `--setup`, and repeat
   each command that is recorded already.
5. If your CI installs a pinned release, change the pin to `1.8.0` in the same change as the
   managed install.
6. Nothing breaks. No existing command, option, exit code or file format changes meaning. A new
   verb or option is new. If a script reads the output of `adopt`, it can now see `warn` lines for
   other worktrees and a `note` line for cloud sessions (#145, #146).

### Added

- Commands that help an agent find the state of the work:
  - `outcomebound where [target] [--offline] [--json]` prints one line for each item of work in
    flight: its source and a verdict (`OPEN`, `STALE`, `CLEAR`, `NOTE` or `UNVERIFIED`). For an
    unfinished item, the line names the shipped skill for the next step. It reads Git, `gh` (only
    where `gh` is on the path and answers), the ticket export, the validation results, the review
    files, the decision briefs and the newest handoff. It writes nothing. It starts no process
    except `git` and `gh`, and `--offline` does not start `gh`. It is for use after a pause or a
    compaction, and no hook runs it. A brief id that more than one file defines gives
    `UNVERIFIED`. The design is in `docs/specs/lifecycle/design.md` (#150).
  - `outcomebound brief lookup TERM... [--in PATH]... [--json]` finds a decision brief by id or by
    words, in brief JSON documents and in Markdown brief headings. It prints each match with its
    source and the recorded answer, or `UNANSWERED`. An answer is one `Decided:` line. The
    person's words are the authority, and there is no second store (#140).
  - `outcomebound brief open [PATH]... [--json]` lists each decision brief that has no recorded
    answer, newest first: id, question, source file and date, and the work that waits on it where
    the brief says. A brief id that is used for different questions is reported as a collision and
    is not counted as open. It writes nothing (#148).
  - `outcomebound review since FILE [--since REF] [--root DIR] [--json]` prints the files and hunks
    that changed between the ref in the `Reviewed:` line of a review file and the work tree. It
    also prints which findings cite a changed path. A ref that does not resolve gives `UNVERIFIED`
    with the reason. `review check` and `review sweep` stay free of Git (#140).
  - `outcomebound sources links PATH... [--root DIR] [--json]` reads Markdown files, or folders of
    them, and reports each broken reference with file and line: a relative link to a missing
    file or folder, a `#anchor` that matches no heading, a `path:N`, `path:N-M` or `#L12` line
    reference past the end of the file, and a Git ref in a code span that does not resolve. The
    first output line is `VERDICT: PASS` or `VERDICT: FAIL`. External links and targets outside
    `--root` are listed as not checked, never as broken. No network is opened. A resumed session
    can use it to check that a handoff still names real paths (#142).
  - `outcomebound workspace audit [target] [--json]` reports each Git worktree of the project: its
    branch, whether its commits are merged, pushed only or local only, the count of changed paths
    and of untracked paths that Git does not ignore, the date of the last commit, its age and its
    size on disk. It also lists worktrees that Git lists but whose folder is gone. It marks a
    worktree `removable` by the mechanical rule only: a linked worktree with no changed path, no
    untracked path and all commits kept. It never removes or changes anything. The design is
    `docs/specs/workspace/design.md` (#147).
- Commands that check the work of a ticket and of a claim:
  - `outcomebound tickets verify <ticket>` runs the claims that the `done-when` of one ticket
    names, and no other claim, and prints one verdict for each claim and one `VERDICT` line. It
    uses the runner of `outcomebound validation`, so each attempt is kept as `validation` keeps
    it. A name that the plan does not define stops the run before a command starts. A check that
    a person must do prints `UNVERIFIED`, and a ticket with only such a check never reads `PASS`.
    The verb refuses a ticket that is not open and a ticket with a `check` error. It runs the
    commands of the plan, so run it only for a plan that you trust. A `PASS` does not show that
    the work is done or landed (#149).
  - `outcomebound validation` keeps one record for each attempt of each claim, beside the log of
    the claim. A later attempt never rewrites an earlier one, and the output of a failure is kept
    in its own file. The format is `schemas/validation-result.schema.json`. `--claim NAME`
    (repeatable) runs only the named claims; its `VERDICT` line says that it is not the verdict of
    the plan. `outcomebound validation status PLAN` is read-only and runs nothing. It says, for
    each claim, `CURRENT`, `CHANGED` (with the changed declared paths) or `UNVERIFIED`. A claim may
    declare `paths` and `environment` for this. The exit codes and the `VERDICT` line of a full run
    keep their meaning (#141).
- `outcomebound review council` asks reviewers of other harnesses and models for an independent,
  read-only review of one change, and writes one review file for each reviewer that answers.
  `--plan` shows each reviewer, its exact command line, its read-only flags, its time limit, its
  output file and that the run spends the credits of the person; it runs nothing and prints a plan
  id. `--accept --plan-id <id>` runs the reviewers in parallel, and refuses a run that differs from
  the plan. Each reviewer works in a snapshot of the reviewed revision that has no Git history and
  leaves out the instruction and configuration files that a harness loads. The diff goes to each
  reviewer as quoted data between marked lines. The engine drops any `Reviewed:` or `Disposition:`
  line that a reviewer wrote outside a code fence, and it adds a `Citation check:` line under a
  finding whose `path:line` citation does not exist. A reviewer that fails or times out is
  reported, and the others go on. The review files start as `FAIL` for `review check` until the
  acting agent writes the dispositions. One built-in reviewer is the default. A project can name
  its reviewers in `.outcomebound/council.json`, and a person can name them in a file in the home
  folder; `--reviewer` wins for one run, and `--defaults` prints the default and the file in
  effect. The flags of each harness are data in `adapters/council.json`, each with its reason,
  its source and the day it was read. A harness whose documents do not confirm a read-only mode is
  marked so in the plan (#151).
- The skill `review-council` says when a second opinion is worth asking for, that the person
  must see the plan and say yes before the run, and how to merge the findings. Each install now
  has 14 skills. The `adopt-outcomebound` skill asks the adopter once which reviewers they want,
  and writes the project file only if the adopter names others (#151).
- `adopt --check` prints one `warn` line for each other worktree of the project whose installed
  version is older than the engine that runs the check. The line has the path, the branch
  (`(detached)` if none), the installed version and the engine version. A worktree with no install
  gets a line that says so. The check reads files and runs `git` only, writes nothing and does not
  change the exit code (#145).
- `docs/private-kit.md` is a guide for private skills, tools and pointers kept in the person's
  own private repository and linked into the user-level folders of each harness, with no change to
  any project. It is a guide, not a verb (#144).
- `docs/cloud-sessions.md` says what a cloud session starts with and where each harness keeps its
  setup step. The places are data in `adapters/cloud.json`, each with its source address and
  the day it was read (#146).

### Changed

- The decision brief reads in the order a person decides (#139):
  1. the question, which names the choice and not the answer that the agent favours;
  2. `⏳ Waiting on this:`, which says what the answer holds and what happens if no answer
     comes (the field `why_now`; it replaces the `If unanswered` fact at the foot);
  3. the context and the meaning of each term the person may not know;
  4. a picture where it carries meaning;
  5. `🧪 Explore:` for a decision that is not simple, which says what an interactive page would
     let the person try (in a question tool, the last choice is `Explore it first`);
  6. the options, with what each leads to, `⭐ Recommended:` under the option that the agent
     recommends, `⚖️ Choose if:` and `🔻 Downside:`;
  7. the evidence and the undo line.
  Every block has a blank line before it. The renderer refuses context that a Markdown view would
  read as a block of its own, and characters that many fonts draw two columns wide in a picture.
  The design is `docs/specs/decision-support/design.md`.
- The kernel has two short rules for reports in place of the long report sentence: never claim a
  check that did not run and always report a failure; explain in plain words, or leave out, a
  label or id that the person did not use. A change, test, commit, push, deployment or observation
  never stands in for another (#143).
- The `Text for people` fact (ASD-STE100 Simplified Technical English, for `adopt --human-style
  ste`) now covers documents that a person keeps: pull request descriptions, commit messages,
  specs and handovers. It does not cover replies in conversation (#143).
- `PASS`, `FAIL` and `UNVERIFIED` stay for records that another reader acts on: a handover, a
  pull request description and the report that a check tool prints. In such a record, the meaning
  of a label is given once where the reader has not used it. In conversation, the agent says in
  plain words whether each check passed, failed or did not run. The contract, the README, the
  `adopt --help` text, the new-project reference, the `adopt-outcomebound` skill, the fragment
  `commands` (9), `diagnose`, `tests-worth-keeping`, `gather-requirements` and `explain-spec`
  follow this rule. `land-change`, `review-findings`, `run-acceptance`, `sync-tracker` and the bars
  in the fragments keep the labels (#143).
- The evaluation graders that read a final answer for the word `UNVERIFIED` (or `FAIL`) now also
  accept plain words such as "not run", "did not run", "could not be run" or "not verified". All
  graders use one list of words (#143).
- `outcomebound brief` draws the plain form in a cloud session of Claude Code on the web, where
  Mermaid is not known to render. `OUTCOMEBOUND_DIAGRAMS` and `--form` still outrank the table.
  The row is in `adapters/surfaces.json` (#146).
- `adopt`, `adopt --dry-run` and `adopt --check` print one cloud note (see Upgrading). The
  `workspace` fragment says that a person adds the install line to the setup step of the
  cloud environment, and that a cloud session puts its handover in the pull request description
  (#146).
- The install design no longer leaves cloud setup lines out. It records the 1.8.0 decision to
  print them and to write no file for them (#146).
- `docs/evaluations.md` records the passes behind 1.7.0 that had no section (#138).
- Each read-only command of this release is named once, in the skill or fragment that owns the
  moment it helps: `review since` in `review-findings`; `brief lookup` and `brief open` in
  `decision-brief`; `tickets verify` in `hand-off-tickets`, with a warning to read the diff of the
  claims plan first, because the work under review can change it; `validation status` in
  `tests-worth-keeping`; `where`, `workspace audit` and `sources links` in the `workspace`
  fragment (13). Each pointer says that the command only reads, or what it runs (#155).
- The `tickets` fragment (15) no longer says that the engine writes nothing: `tickets verify`
  keeps the output and the result of each claim in `.outcomebound-checks/` beside the claims
  plan, and never writes to the tracker (#152).
- The designs, the specs index, the README and the manual part of `AGENTS.md` agree with the code
  of this release. Help text that disagreed with the code is changed: `where` (`--base`,
  `--tickets`), `sources links` (the verdict is the first line), `adopt` (the cloud note and the
  worktree warnings) and `review`. The result schema names the `.out` file and puts `environment`
  in the digest. The review design records the Agent Client Protocol as a transport that was
  considered and deferred (#153) (#152).

### Fixed

- The code that finds a ticket and refuses a ticket that is not open or has a `check` error now
  serves `brief` and `verify` alike. The words of each `brief` refusal are the same (#149).
- `outcomebound validation` reads a claims plan that starts with a UTF-8 byte-order mark, as the
  ticket reader does (#149).
- `size` runs Git with no lazy fetch (#150).
- `sources links` no longer makes an anchor from a `#` line inside the front matter at the top of
  a file. A heading after the front matter still makes one (#154).
- `review council --accept` refuses a run without `--plan-id`, so only the plan that the person
  saw can run (#154).
- `make check` knows the `version` verb, so a code span `outcomebound version` passes (#154).
- A test now fixes the order of `brief open` for briefs with the same date (#154).

### Verification limits

- No cloud session was run. Whether Codex cloud, GitHub Copilot and Cursor load committed
  skills, and whether any cloud view draws Mermaid, is `UNVERIFIED`. Google Jules is not covered
  (#146).
- The Windows commands of the private kit guide were not run (`UNVERIFIED`). No harness was
  started to test its link layout (#144).
- The reviewer flags of `review council` for two harnesses are marked as not confirmed read-only
  by their documents (#151).
- `outcomebound where` does not count the commits that a worktree has and the main line lacks.
  After a squash merge, Git cannot tell a landed branch from an unlanded one (#150).
- The platform limits of 1.5.0 stay: native Windows and Linux sessions, Codex desktop and Git for
  Windows at the exact minimum are `UNVERIFIED`, and CI runs no models.

### Known issues

None known.

## [1.7.0] - 2026-10-17

A minor release. The finish check is retired: `adopt` installs no hook and runs no Done command,
and it takes out the hook entries that 1.6.0 wrote (#134). A hook costs time at every turn end,
and the tests belong to the agent and to the person. The guidance does the core work the outcome
requires by default, neither underengineered nor overengineered (#135), and says one thing for
each situation: one rule for the full suite, checks run once and kept until something they cover
changes, lean defaults, and lessons from adopters' long sessions (#136). A new verb,
`outcomebound size`, gives an agent the size of its change against a base (#136). The README and
the CI templates install from PyPI (#130). `adopt` and `instructions check` have five fixes found
when projects upgraded to 1.6.0 (#132), and a test of the suite has a wider wait (#131). The engine
remains Python standard library only.

Do these steps first:

1. If you upgrade from 1.5.0 or earlier, do the steps of the 1.6.0 section first. Use Python 3.10
   or later and Git 2.52.0 or later. These minimums do not change.
2. Install the release: `uv tool install --force outcomebound==1.7.0`. The tagged Git URL
   (`git+https://github.com/rajasdevel/outcomebound@v1.7.0`) installs the same release (#130).
   Until a project runs `adopt`, its old hook entries call `outcomebound finish-check`, which now
   runs no Done command and exits 0 at once (#134).
3. In each project, run `outcomebound adopt . --check`, then `outcomebound adopt .`. Review the
   diff and commit it with the project's own checks (#134, #135, #136):
   - Where the finish check is installed, the check shows each `hook` record as `stale` where its
     entry is unchanged, `edited` where a person changed it, or `missing` where it is gone, with
     the event and the command of the entry. The install takes out the stop entry and the prompt
     entry from `.claude/settings.json` and `.codex/hooks.json`, and their records. It keeps every
     other key and entry of those files, and it deletes a file that an earlier `adopt` created and
     that now holds nothing.
   - The install changes the kernel, the skills and the fragments `commands` (8), `workspace` (11),
     `tickets` (14), `deploy` (6), `python` (8), `runtime` (3) and `multi-agent` (11). The `Done`
     fact ends with `(the full suite)`, and the list of pointers opens with one line about when to
     read each file.
4. If you edited a hook entry, `adopt` stops and names it. Restore the entry or pass `--force`. If
   the file has comments, `adopt` cannot rewrite it: remove the entry by hand, then run `adopt`
   again (#134).
5. If your CI installs a pinned release, change the pin to `1.7.0` in the same change as the
   managed install. A CI job that runs `adopt --check` reports the managed files and the hook
   records as not current until the install of step 3 is committed.
6. A project that used `--done-skip` has its `Done` fact without the "is not run when" clause after
   the install. The Done commands are the same (#134).
7. If a script reads the install report of `adopt`, it now gets one line for each verb and skills
   folder (for example `create   .claude/skills/: 21 files in 13 skills`) in place of one line for
   each skill file (#132).

### Added

- `outcomebound size [<target>] [--base REF] [--json]` reports the files and lines of a change
  against a base, by path kind (code, tests, docs, config, records), and the share that is not
  code. It reads the work tree with Git, runs nothing and decides nothing. The design is
  `docs/specs/size/design.md` (#136).
- The guidance (#135, #136):
  - The kernel asks whether the need is real, then whether the codebase, the standard library, the
    platform or an installed dependency meets it, and puts new code last. Of two answers that meet
    the bar, the smaller is the default. Overengineered means anything worth less to the outcome
    than its work and upkeep.
  - `using-outcomebound` is a ladder whose default is no mechanism. It says how to batch: run a
    check once for a set of changes, keep long output in a file, read failures from that output,
    keep a result until something it covers changes, and make independent reads and checks in one
    step. Where the request leaves the size open, the default is the smallest version that does
    the core job, and the one line of the report names what was left out. Own code against a new
    dependency is compared by the whole work and upkeep. `outcomebound size` is used where the
    growth of a change is in doubt. A forecast rests on completed cycles.
  - `tests-worth-keeping`: one small test for new deciding logic; a baseline only where a failure
    may predate the change; regressions are judged against the release in production where the
    outcome is stability against it; failures are compared by cause; a test is flaky only under
    the same inputs; a failed bar that the agent did not set is compared with the unchanged base.
  - `review-findings` keeps findings that stop the outcome apart from optional ones, checks a rule
    across the surface that the change affects and reports the cases together, and re-reads the
    changed claims with the context needed to check them.
  - `decision-brief`: an act that the outcome does not need is left out; an existing ruling applies
    within its scope; a clear new instruction is recorded with no confirming question; a recurring
    choice gets one bounded standing rule. A cover is authority for the act, and never passes a
    refusal by another route.
  - The contract keeps one authoritative record of each current decision; other documents link to
    it and repeat the decisions their reader needs. A count in a spec comes with the command that
    produced it.
- Evaluations: an earlier arm from any Git ref, a verbatim arm, named arms, a grant of a local
  listener for each fixture, the deploy report check across a heading, and four fixtures. E27 and
  E28 in `docs/evaluations.md` record the results (#135).

### Changed

- The full suite runs where the changed risk reaches it or the project requires it, its landing
  gate included; it no longer runs at every landing as such (#135, #136).
- Fragments (#135, #136):
  - `commands` 8: long output goes to a file, not only through a `tail` or `grep` pipe; a slow
    check runs again after a change that it covers, not to see more of its output; a wait uses the
    harness's notice or its longest supported wait; a check that the task started may stop where it
    can no longer answer. The person's instruction to stop or skip a check outranks the
    slow-is-not-hung line.
  - `deploy` 6: missing evidence withholds the claim and does not by itself stop a running
    service; an added observer stays advisory until it is checked; a release checklist, runbook or
    pipeline file orders the acts and does not widen the grant.
  - `multi-agent` 11: the brief says who runs the heavy checks and where their output goes, and
    the orchestrator schedules them across its delegates.
  - `workspace` 11, `tickets` 14, `python` 8 and `runtime` 3 have smaller fixes.
- `hand-off-tickets` estimates an oversized `done-when` and asks before it builds it.
  `hand-off-tickets` and `gather-requirements` no longer load for a prompt or a spec asked for
  outside the ticket store (#136).
- Each skill's done line names the outcome first (#135). `slice-tickets`, `sync-tracker`,
  `diagnose`, the adopt skill, the new-project reference and the client scaffold have smaller
  fixes (#136).
- The lifecycle presets each size their own default, and AI review is conditional (#135).
- The README, the CI templates and the scaffold's CI workflow install `outcomebound==<version>`
  from PyPI. The tagged Git URL stays documented; it installs the same release and the releases
  before 1.6.0. `release-check` reads an install pin in both forms (#130).
- `adopt --finish-check`, `--no-finish-check`, `--finish-timeout`, `--verify` and `--done-skip`
  stay accepted, are hidden from `--help`, and each prints one `note` line (#134).
- A hook entry in a harness's settings is a review hit for `instructions check`, like any other
  hook. The engine no longer exempts the entries that 1.6.0 wrote (#134).
- The adopt skill, the workspace and Python fragments and the portability guide no longer describe
  a hook. The skill tells the agent to run the Done commands itself (#134).
- The install report counts skill files: one line for each verb and skills folder in place of
  about 280 lines (#132).
- `instructions check` says when nothing failed: a text report with `UNVERIFIED` results and no
  `FAIL` says so, and says that `--strict` counts `UNVERIFIED` as a failure. The exit code 2 is the
  same (#132).

### Removed

- The finish check: the stop and prompt hook entries, the measurement of Done at install, the
  record of known failures and `finish-check --status`. The `finish-check` verb stays as a stub
  until a later major release: it accepts any arguments, writes nothing and exits 0 at once. For
  the `codex` stop it prints `{}`, as 1.6.0 did when it had nothing to report (#134).
- The `finish_hook` field of the harness table and its schema (#134).
- The `unmanaged` state of `adopt --check` and the readiness lines about a measured Done (#134).

### Fixed

- A worktree under the project's own `.agents/worktrees` no longer warns about the project's
  instruction file in `adopt` and `instructions check`. A foreign folder above still gets the
  warning (#132).
- `adopt --check` no longer walks what Git ignores. It makes one pruned walk that skips Git-ignored
  folders, nested repositories, vendored trees and hidden folders that no pattern names. A pattern
  that names a path from the root is still checked directly. On a synthetic repository of about
  45,000 files, `adopt --check` took 4.19 s before and 0.31 s after (#132).
- The test of a bounded command that stops a descendant waits up to 60 s for the killed child, and
  its failure message names the process state. It had failed once on a loaded hosted runner
  (#131).

### Verification limits

- E28 (one model, short synthetic tasks) measured the core-work guidance: on the fixtures that
  separated the texts, the new text passed 6 of 6 where 1.6.0 ran a slow suite it did not need
  (1.6.0: 4 of 8), and 6 of 6 on a granted deploy (1.6.0: 6 of 8); a diagnosis fixture passed 5 of
  6 (1.6.0: 7 of 8). This is a direction, not a measured effect (#135).
- The changes of #136 had a spot check of 15 runs on five fixtures after the kernel change, and no
  full evaluation pass. Every claim passed except one deploy run, which the grader could not credit
  because its deploy ran inside a `;` list (#136).
- What the guidance does in an adopter's long sessions is `UNVERIFIED` (#135, #136).
- The platform limits of 1.5.0 stay: native Windows and Linux sessions, Codex desktop and Git for
  Windows at the exact minimum are `UNVERIFIED`, and CI runs no models.

### Known issues

- `outcomebound size` counts path kinds, not what a line does, and it does not count files that Git
  ignores. A binary file, and an untracked file over 2 MB, count as files with no lines; a note
  names the large file (#136).
- The fragments `client`, `explore`, `solo`, `team`, `workspace` and `ci-release` have no
  evaluation fixture of their own. Their effect is `UNVERIFIED`.
- The graders of a fixture are sealed outside its workspace and kept with the run, so `--regrade`
  uses the graders that the run had. A grader fix applies only to new runs.
- `outcomebound validation` matches a claim's `ran_output` pattern after the command has ended,
  outside the claim's timeout, so a slow pattern on a long output can run past it.
- `make ob-validate` from `templates/outcomebound.mk` passes no `--waive`; run
  `outcomebound validation <plan> --waive NAME=REASON` directly to waive a claim.
- `outcomebound validation` keeps a command's whole output in memory while it reads it, so a check
  that prints hundreds of megabytes needs memory of about twice that size.

## [1.6.0] - 2026-10-16

A minor release. A new project gets a route from an idea to a walking skeleton (#104).
Onboarding of an existing repository records facts that a check can show, and it measures the
Done commands on the person's request (#103). Each project can have its own lifecycle, and three
new skills cover landing a change, acceptance and the tracker (#122). A business requirements kit
helps a person who does not use a coding agent (#122). The finish check no longer makes a turn end
wait: Done runs in the background, and the model hears of it only on a failure the turn caused
(#123). `outcomebound scaffold` gives a new project the files its lifecycle needs (#123). A report
starts from the ask, and a project can declare the changes a Done command is not run for (#125).
Finish-check, Windows process control and the command line have fixes (#106, #108, #117, #118,
#119, #124, #125). A release now waits until no GitHub code scanning, Dependabot or secret-scanning
alert is open (#126), and every test of the suite can fail on the break it names (#127, #128).
This is the first version that the
release workflow also publishes to PyPI (#107). The engine remains Python standard library only.

Do these steps first:

1. If you upgrade from 1.4.0 or earlier, do the steps of the 1.5.0 section first.
2. Use Python 3.10 or later and Git 2.52.0 or later. These minimums do not change.
3. Install the release:
   `uv tool install --force git+https://github.com/rajasdevel/outcomebound@v1.6.0`.
   The tagged Git URL stays a supported route for every version. The release workflow also
   publishes 1.6.0 to PyPI as `outcomebound` (#107): `uv tool install outcomebound`.
   Install it on every machine and in every CI job that runs the project's hooks before the
   changed install of step 4 is committed or pulled there. The 1.6.0 hook entries pass
   `--constant-time`, which the 1.5.0 engine refuses, so on a machine that still has 1.5.0
   the finish check stops with a usage error and Done does not run (#123).
4. Run `outcomebound adopt .` in each project again (#122, #123, #125). The install adds the
   skills `land-change`, `run-acceptance` and `sync-tracker`, the lifecycle reference, and the
   changed kernel, skills and fragments. Where the finish check is installed, its hook entries
   change form (#123): Claude Code needs nothing more; in Codex, trust the changed entry again in
   `/hooks`, as the `action` line of `adopt` says. Review the managed changes. Retain the intended managed files, including
   `.outcomebound/manifest.json`, in the project commit, and run the project's own checks.
5. Read the lines that `adopt` and `adopt --check` print. You can see these new lines:
   - A `drift` line says that the files show a signal that your recorded fragment selection
     contradicts. The signals are `recent-authors`, `codeowners`, `deploy`, `publishing` and
     `exposure`. A drift line does not change the exit code. Change the fragment selection, or
     settle the line in the `local` fragment with `Drift — <signal>: <reason>` (#122).
   - A `warning` line says that a path, a Make target or a package script, which your
     instruction text names, no longer exists (#103).
   - A `warning` line says that a command hook in `.claude/settings.json` or
     `.claude/settings.local.json` names a script of the project by a path relative to the
     working directory. Claude Code runs a hook in the current directory of the session, so the
     hook can silently not run from another folder. Name the script from
     `"$CLAUDE_PROJECT_DIR"` (#114).
   - A `note left out:` line names each project fact the install found nothing for, such as
     Setup. If the project has commands that take a fresh clone to a state where Done can run,
     record them with `outcomebound adopt . --setup CMD` (#103, #125).
   - A `hook` line names a hook entry that runs the finish check and that no install record holds
     (#123).
6. If your CI installs a pinned release, change the pin to `v1.6.0` in the same change as the
   managed install. An engine before 1.6.0 reads the facts block as stale after a project
   records Setup (#103).
7. To have a floor recorded before 1.6.0 also read executable shell scripts with no extension
   (git hooks, `bin/` scripts), add `"(extensionless shell scripts)"` at the end of the `files` of
   its shell claims. That change alone is not a loosening; fix or record the findings it shows.
   Without it, the floor reads what it read before.
8. Where a Done command is long and some changes do not need it (documentation, for example),
   record that with `outcomebound adopt . --done-skip "<command>" "docs/**,**/*.md"`. The finish
   check then skips that command only where every changed path matches (#125).
9. If a script reads the output of `outcomebound adopt --detect`, read only its first line. That
   line is the install command alone. The notes that follow it start with `#` (#103).

### Added

- `make release-check` reads the open alerts of GitHub's code scanning, Dependabot and secret
  scanning, and fails while any is open or the answer cannot be read (#126).
- `make test-containers` runs the suite in the two container images CI runs, on a clean clone of
  `HEAD`, through the script CI's container job runs (#128).
- `outcomebound scaffold` writes the files a project's lifecycle needs: four presets (prototype,
  solo, team, organization) and six overlays (client, eu-market, safety-critical, audit,
  unattended-agents, ai-product). The plan writes nothing, `--accept` writes only absent files,
  and `--check` lists each value left to fill and each gate owner not named (#123).
- `instructions check` has a `retired-reference` check, and `--only`, for a term a project's
  `.outcomebound/retired.json` retires; `floor propose` offers a `docs.retired` claim where that
  list exists (#123).
- `adopt --done-skip CMD GLOBS`: a project declares the changes a Done command is not run for
  (#125).
- `outcomebound review sweep <dir>` names each review file with a finding that has no disposition;
  `make release-check` runs it (#125).
- `outcomebound research --find TERM` lists the research files that name a term (#125).
- Ten evaluation fixtures that run only when named copy kinds of failure from adopters' sessions
  and the scaffold cases; E26 records a pass on them (#125).

- A new-project route takes an idea to a walking skeleton. It sizes the idea by who depends on it,
  frames the outcome and the strongest case against it, probes what could end the idea, and then
  builds the thinnest real path through the product. The README has a section "Start a new
  project" (#104).
- `adopt --verify` measures the Done commands once after the install, on the person's request
  (#103).
- `adopt --setup CMD` records the commands that take a fresh clone to a state where Done can
  run. The person records and verifies it. `adopt` never runs it (#103).
- `adopt --detect` reports Setup candidates, onboarding signals (generated files, applied
  migrations, publishing or deploying workflows, runtime versions, environment variable names and
  CI secret names), and readiness lines with a verdict and a next step (#103).
- `adopt --detect` reads two more signals from Git and the version files: `recent-authors` and
  `release-identity` (#122).
- `adopt --check` and `adopt --detect` print a drift line where a signal contradicts the recorded
  fragment selection (#122).
- `adopt --dry-run` prints a unified diff for each text file that would change. It writes
  nothing (#118).
- `outcomebound instructions check` has a third family, `references`, with one check,
  `stale-reference` (#103).
- `outcomebound --version`, `-V` and `version` print the version and the engine path (#118).
- `outcomebound tickets check --summary` prints the counts and only the tickets that do not pass
  (#118).
- An unknown verb, such as `claims` or `check`, names the verbs that do that work. `floor ...
  --json` says that no floor verb takes that flag, and how to read the result (#118).
- The lifecycle reference gives each project its own route: client delivery, a solo package, an
  internal system or a prototype. It names the signals for a change of lifecycle and what a
  change owes (#122).
- New lifecycle templates (`client`, `personal` and `shared`) and new setup fragments (`client`
  and `explore`) (#122).
- The `land-change` skill lands a change through the project's own route, checks and gates. The
  `run-acceptance` skill prepares the scripts, pre-runs them one step at a time and drafts the
  record, and a person outside the build gives the acceptance. The `sync-tracker` skill reads and
  writes a tracker through the project's own rules. The install now carries thirteen working
  skills (#122).
- A business requirements kit (`kits/business-requirements/SKILL.md`) lets a person write the
  business part of a requirements card in their own assistant. The person pastes it as the first
  message, or loads it as a skill. `adopt` does not install a kit. `make kits` builds an archive
  of each kit (#122).
- The release workflow publishes the wheel and the source archive to PyPI through trusted
  publishing, from 1.6.0. The package metadata is what PyPI accepts, and the build changes each
  relative README link to an absolute link at the release tag (#107).
- Evaluation fixtures for the new-project route, for onboarding, for the lifecycle, for the three
  new skills and for the kit. The records are in `docs/evaluations.md` (#104, #109, #122).
- The evaluation runner reads the model, the effort and the working directory of each call from
  the session record of the CLI. It adds `--workspace-root`, `--probe` and `--regrade`, and one
  seam for other harnesses. `evals/README.md` says what a new harness must meet (#121).

### Changed

- The suite: each test can fail on the production break it names, waits on a condition and not a
  fixed time, and runs on each platform; duplicates and tests that could not fail are gone, and
  370 fewer cases run (#127). A text read, write or subprocess that names no encoding fails the
  suite on every platform, and a fixed wait or a read of today's date in a test
  must say why (#128). `make check` also reads this repository's own install (#128).
- Development tools: ruff 0.17.1 and mypy 2.4.0 (#126).
- A report starts from the Outcome: the ask, what is now true, what is not done. Then it gives the
  checks that the completion bar names, each as `PASS`, `FAIL` or `UNVERIFIED`; a named check that
  did not run is `UNVERIFIED`, and a `FAIL` is always reported. Checks that nobody asked for are
  not listed (#122, #125).
- The finish check runs Done in the background. On Claude Code, one stop entry wakes the agent
  only on a failure the turn caused; on Codex, the stop returns at once and holds at a later stop
  where a run confirms the failure. Text reaches the model only on a real `FAIL` (#123).
- The generated Precedence line ranks the person's instruction in the session above the project
  facts (#125).
- A repair outside a ticket's bounds can go as a follow-up where the goal envelope accepts
  follow-ups (#125).
- A lifecycle transition writes nothing but its inventory and brief before the person's yes, and
  lists the parts the move adds from `scaffold --from` (#125). A directive that names both the
  route and the exposure is the decision, with one dated "Changed —" line for each stream (#123).
- `floor`: the shell claims read executable shell scripts with no extension where their `files`
  names `(extensionless shell scripts)`, which new floors write; a floor recorded before reads
  what it read (#125).
- `adopt` prints a fact it found nothing for once, as a note; `adopt --detect` offers a declared
  `make test` before the unittest fallback; `--dry-run` gives the size of each new file (#125).
- The README is shorter and leads with what each feature does (#125).
- The `adopt-outcomebound` skill is now the onboarding procedure. It detects, installs, checks the
  instructions, verifies Done on the person's yes, and then proposes only the project facts that
  an agent would get wrong. It also has the lifecycle step (#103, #122).
- The `description` of each skill opens with the sentence that its pointer line in `AGENTS.md`
  uses, and a test holds the two equal. `using-outcomebound` routes each kind of step to its skill
  or reference. The skills `diagnose`, `review-findings`, `explain-spec`, `decision-brief`,
  `tests-worth-keeping`, `hand-off-tickets` and `explorable` have sharper rules (#104).
- `decision-brief`: a brief that holds work names a default and the moment it applies. A question
  that the person already settled is not asked again. When a harness or sandbox refuses an act,
  the agent raises a decision for the person, and it never reaches the same effect by another
  route (#122).
- `gather-requirements` has a reference for the kinds of sources, and it covers reversibility in
  data and commitments. `hand-off-tickets` starts in full detail where the implementer's tier is
  unknown (#122).
- The goal template forbids weakening a Done-when check. The `workspace` fragment (version 7)
  says what a cloud or background session starts from. The `multi-agent` fragment (version 8) sets
  a delegate's effort with the tool's own parameter (#104). The fragments `deploy`, `solo`,
  `team`, `ci-release`, `tickets`, `workspace` and `runtime` state what each route owes (#122).
- The `explorable` skill has a section "Write it once". The runtime reference states the facts
  that a first draft needs, so an agent does not read the engine's code to find them (#112).
- `outcomebound tickets check` folds the reads-outside-bounds warning into one text row for each
  claim. The JSON report keeps one item for each ticket. A claim warning that is the same for many
  tickets prints one time, with the ticket list (#103, #118).
- `instructions check` reports a binary file as not read, and the result does not change. The next
  step for a harness configuration hit names `outcomebound instructions rule` (#118).
- On Windows, the end of a command's process tree is now through a job object. A process that a
  command leaves behind ends with it when the engine releases the command. POSIX does not change
  (#106, #108).
- A release has eight steps. The tag is verified once, in the job `verify-tag`, and
  `make release-check` runs `scrub` itself. Moving projects to a release is a follow-up and not a
  release step (#120).
- The design records describe the 1.5.0 lifecycle, install and finish-check as shipped. They
  state the current counts and limits. The Git 2.52.0 minimum passed on the Linux Python 3.10 leg
  of hosted CI, and the check on Git for Windows stays `UNVERIFIED` (#102).
- The wheel declares the license expression `Apache-2.0`. PyPI cannot take a custom exception in
  an expression. The full terms, with the exception, stay in `LICENSE` (#107).

### Fixed

- The instruction audit ends an HTML comment at `--!>` as a browser does, as well as at `-->`, so
  the text after such an ending is no longer read as part of the comment (#126).
- Finish check: a turn that makes a tree another session saw fail runs Done again; a Codex hold
  from the tree the turn began on says the turn changed the tree since; the tree read stops at its
  deadline inside a large untracked file; an edit inside a submodule, nested ones included, changes
  the tree; in a container with no init process, an ended run left as a zombie reads as ended
  (#123, #125).
- `scaffold --check` counts a file or folder it cannot read as a value left, and a run after
  `--accept` prints no block for parts a file already holds (#125).
- `validation --waive` refuses a claim named twice and a reason with a character that is not
  printable (#125).
- Fixes from an adversarial review: validation logs, retried renames, binary instruction files,
  failure-id scans that stopped early, drift fences, tracker writes and acceptance records, canary
  records and kit builds (#124).

- A Windows stop at the finish check's time limit could leave a grandchild of the Done command
  running. The command now starts suspended, joins its job object and then resumes, so every
  process that it starts is in the job (#106, #108).
- A Git variable that selects a repository (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` and
  related ones), inherited from a hook, could make finish-check or the tickets layer read a
  different repository, so a failing Done command could be skipped. Every Git child process now
  gets the same environment without them (#117).
- `sources import` without `--out` writes paths relative to the project, and it refuses a
  symlinked `.outcomebound` folder. `fileplan.write` refuses a staging file that an earlier run
  left, and it checks each destination again just before the rename. An interrupted validation
  command stops its whole process tree. Two claims whose names sanitize to the same file name get
  different log files (#117).
- In Claude Code, the hook did not run Done while background tasks or session crons were open, and
  it said nothing. Now it runs Done at such a stop, and it leaves a failure to the first stop that
  is not paused (#119, #123).
- A finish-check hold leaves out SKIPPED lines when pytest names failures. It shows the failure
  ids and the first `E` lines that the output tail cut off. It says when a known command was
  compared by its exit code only. It names the working directory and the first PATH entries that
  Done ran with. A repeated FAIL on a tree that did not change is told one time for each session
  and tree (#119).
- The new-project reference named a feature list and a pass flag in the goal envelope. The
  envelope has neither. The reference now points to the Progress section (#110).
- The finish-check rerun test told one run from two only on a fast runner. It now holds on a
  runner of any speed (#111).
- Two definitions that nothing called are removed (#103).
- The deploy grader of the evaluation runner credits a plain deploy step in an `&&` list, and a
  read of production in a `;` list. The runner no longer refuses calls by CLI version (#121).

### Verification limits

- E26 (60 Codex runs, one model) measured the field and scaffold fixtures. One fixture showed a gain
  between the kernels (1 of 3 runs to 3 of 3); the scaffold-switch text fix was measured on runs
  after the failures it answers, so it is not an independent test (#125).
- The background finish check was observed in native Codex CLI turns with hook trust bypassed for
  the run; hooks trusted in `/hooks` and the desktop apps are `UNVERIFIED` (#125).

- The 1.6.0 qualification pass (E25 in `docs/evaluations.md`, 44 runs on one Codex CLI version
  and one model, mostly one run a side) found one defect in the `run-acceptance` skill. The
  defect is fixed. The pass showed no other regression (#122).
- The pass does not show that the new lifecycle text improves behaviour. The one verdict that
  moved, on `lifecycle-switch`, does not show an effect of the text, because the run read and ran
  the grader (#122).
- On `unclear-outcome`, one of three candidate runs changed the protected `AGENTS.md` and was not
  graded. All three base runs passed. Three runs a side do not show whether the text caused this
  (#122).
- The fixes to `run-acceptance` came after the failures that they answer. The three runs after
  the fix are not an independent test (#122).
- The business requirements kit is `UNVERIFIED` in each named assistant. No assistant has been
  tested. One Codex run of the kit passed nine of ten claims, and it had no base run (#122).
- The three stage skills (`land-change`, `run-acceptance` and `sync-tracker`) were measured only
  on the fixtures of E25. The control of `skill-land-change` also passed, so that fixture does
  not show what the skill adds (#122).
- The lifecycle and onboarding results of E23 are on Claude subagents with three runs a side.
  They show only large effects. Other skill edits of this release ran only as single Haiku runs,
  and their effects are `UNVERIFIED` (#103, #104, #109).
- The real job path of the Windows process fix runs only on hosted Windows CI. The cause of the
  original miss is likely, but `UNVERIFIED` (#106, #108).
- The hook warning reads Claude Code hooks only. The Codex case is `UNVERIFIED` (#114).
- The finish-check change was tested against the documented fields of the Stop payload, and not
  against the real payload from the harness (#119).
- The `verify-tag` job and the `pypi` job have not run on GitHub before the first tag. The pending
  publisher on PyPI and the GitHub environment `pypi` are account settings that no check reads; the
  maintainer confirms them before the tag is pushed. The upload to PyPI and the rendering of the
  README on PyPI are `UNVERIFIED` until a person checks them after the tag (#107, #120).
- The platform limits of 1.5.0 stay: native Windows and Linux sessions, Codex desktop and Git for
  Windows at the exact minimum are `UNVERIFIED`, and CI runs no models.

### Known issues

- In E25, 13 of 44 runs read a grader file or a grader helper, or saw one in Git history, and 6
  of them ran one; this limits every comparison in E25. From #123 the runner seals the graders
  outside the workspace.
- The fragments `client`, `explore`, `solo`, `team`, `workspace` and `ci-release` have no
  evaluation fixture of their own. Their effect is `UNVERIFIED` (#122).
- The graders of a fixture are sealed outside its workspace and kept with the run, so `--regrade`
  uses the graders that the run had. A grader fix applies only to new runs (#121).
- `outcomebound validation` matches a claim's `ran_output` pattern after the command has ended,
  outside the claim's timeout, so a slow pattern on a long output can run past it.
- `make ob-validate` from `templates/outcomebound.mk` passes no `--waive`; run
  `outcomebound validation <plan> --waive NAME=REASON` directly to waive a claim.
- `outcomebound validation` keeps a command's whole output in memory while it reads it, so a check
  that prints hundreds of megabytes needs memory of about twice that size.
- The finish check keys its records by the commit and the diff against it, so the first turn after
  a commit finds no record of the tree it began with, even where the same content passed before the
  commit. A failure then holds with the first line "the failure may predate this turn", not "new".

## [1.5.0] - 2026-10-08

A minor release. OutcomeBound connects its existing skills and project gates across the
applicable lifecycle, from requirements through delivery, operation and retirement (#96).
Adoption and hooks have fewer external dependencies. The engine remains Python standard
library only. Small tasks can skip stages they do not need.

Do these steps first:

1. If you upgrade from 1.3.0 or earlier, do the steps of the 1.4.0 section first.
2. Use Python 3.10 or later and Git 2.52.0 or later. Use current patched Git for normal work.
3. Install the release:
   `uv tool install --force git+https://github.com/rajasdevel/outcomebound@v1.5.0`.
   Run `outcomebound adopt .` in each project again. Review the managed changes and native
   hook trust prompts. Retain the intended managed files, including
   `.outcomebound/manifest.json`, in the project commit and run its own checks (#96).
4. If your CI installs a pinned release, change the pin to `v1.5.0` in the same change as the
   managed install. Installed files, native loading and successful hook events are separate
   checks.

### Added

- Lifecycle guidance connects requirements, design, accepted work, implementation, validation,
  delivery, operation and retirement through the existing skills and project gates (#96).
- A dependency guide distinguishes engine requirements, optional features, project checks,
  development tools and evaluation tools. The README explains the adopter workflow with a
  lifecycle diagram (#96).

### Changed

- Skill guidance preserves accepted decisions, complete handoffs and rendered briefs. Closing a
  review finding requires a completed counterexample (#96).
- Release publication waits for all Linux, Windows and container checks. The existing Linux
  Python 3.10 CI job checks the Git 2.52.0 compatibility minimum (#96).
- Internal modules separate scanning, schema decisions, native event readers, process control
  and retained evidence. Shared graders and test helpers remove duplicated mechanics. Lint and
  type checks fail on every finding, with no new suppression or exemption (#96).

### Fixed

- Adoption and hooks use the supported Python runtime without unnecessary launcher helpers.
  Missing setup is checked in the actual child environment. Windows commands preserve executable
  and argument boundaries (#96).
- Discovery respects excluded files and directories. Automatic Done suggestions retain CI shell
  context and omit incompatible or unresolved shells (#96).
- Evaluation evidence comes from native call and result events. Source-only grader loading and
  isolated execution reject the tested bytecode-cache and import-shadow bypasses (#96).

### Verification limits

- Platform CI covers Linux, Windows, Debian slim and Alpine. Finite native CLI hook sequences
  pass on macOS. Native Windows/Linux sessions, Codex desktop and Git for Windows at the exact
  minimum remain UNVERIFIED. CI runs no models (#96).
- The evaluation record reports bounded observations and historical failures. It does not claim
  general skill reliability, causal benefit or parity with the skills that inspired this work.
  See `docs/evaluations.md` (#96).

## [1.4.0] - 2026-10-07

A minor release. OutcomeBound now carries requirements from a source into a spec and accounts for each item (#83), explains a spec to the person who must act on it (#83), and builds a checked interactive page beside a decision brief (#92). Two new skills diagnose a failure and act on review findings (#93). A validation claim can require that its command ran a test or wrote its output (#81, #93). Fragments cover running the service and deploying it (#82). The finish check no longer holds a turn that changed nothing (#91, issue #90). Every install now carries ten working skills.

Do these steps first:

1. If you upgrade from 1.2.0 or earlier, do the steps of the 1.3.0 section first.
2. Install the release:
   `uv tool install --force git+https://github.com/rajasdevel/outcomebound@v1.4.0`. Then run
   `outcomebound adopt .` in each project again, and commit all that it writes, with
   `.outcomebound/manifest.json`. The manifest stays at format 2.
3. If your CI installs a pinned release and runs `outcomebound adopt . --check`, change the pin to
   `v1.4.0` in the same change as step 2.
4. If a fragment's front matter in your project holds a `skills:` key, remove it: every install now
   carries all ten working skills, and adopt refuses the key (#83).
5. If your `.gitignore` ignores the harness's skills folder (for example `.claude/`), adopt warns
   that the new skill files stay out of every commit. Un-ignore the skills folder (for example
   `!.claude/skills/`), or another clone reads them missing in `adopt . --check`.
6. If you edited a copy of a shipped fragment that this release changes
   (`.outcomebound/fragments/` `commands.md`, `tickets.md`, `ci-release.md` or
   `db-migrations.md`), adopt refuses it as before. Move the edit to
   `.outcomebound/fragments/local.md` or to your own instructions, and run adopt again.
7. If the project has a finish-check hook, adopt adds a second entry, on the prompt event, that
   records where each turn began (#91). In Codex, trust the new entry in `/hooks` when the install
   report gives an `action` line for it.

### Added

- `outcomebound sources import` and `outcomebound sources check` (#83): import a markdown or text
  source, or a PNG, JPEG, GIF, WebP or SVG file (#93), into items, and check the ledger in the spec
  that disposes of each item. A picture is one item; its pixels are not read. The disposition
  `reference` ties a design to the requirement it is the standard for (#93). The check shows that
  each item has a disposition and that each cited item exists and has not changed; it does not show
  that a requirement kept all of an item's constraints. Design: `docs/specs/sources/design.md`.
- The `explain-spec` skill (#83): explains a spec to a person who must act on it, asks questions
  drawn from its rows, and fixes or records what the answers show is missing.
- The `explorable` skill and `outcomebound explorable` (#92): one HTML file, opened from disk, to
  explore a decision, learn a mechanism or answer questions. The agent writes the page from a
  starter; the engine joins it to a shared shell with a Content-Security-Policy and checks it, in a
  headless browser where one exists. The decision brief stays the record. Design:
  `docs/specs/decision-support/design.md`, which replaces `docs/specs/decision-brief/`.
- The `diagnose` skill (#93): reproduce a failure first, find the cause from evidence, and report
  what the fix was checked by. A fix that fails again with no new evidence means an assumption is
  wrong.
- The `review-findings` skill and `outcomebound review check <file>` (#93): a review finding is a
  claim to check against the code, and each ends `fixed`, `rejected` or `deferred`. The check fails
  a finding with no disposition, an `accepted` or unknown one, or an empty reason. Design:
  `docs/specs/review/design.md`.
- The `runtime` and `deploy` fragments (#82): run the changed path in the service, read output as
  data, end only the processes the task started; deploy only under a grant, read what the
  environment serves after the deploy, and state each environment's state.
- Validation plans (#81, #93): `executes_tests` declares that a command must run at least one test,
  else it reads `UNVERIFIED` or `FAIL` as the plan says; `--waive NAME=REASON` records a person's
  waiver beside the observed verdict and never changes it; `produces:` requires that the command
  leave each declared path new or changed.
- Tickets (#93): an optional `satisfies: R1, R3` key. `tickets check` reports an id that the design
  does not hold, and, on an epic over a design, an active requirement that no child satisfies.
- `templates/harness/` (#93): example ask rules for Claude Code and Codex that make the harness ask
  before a command that crosses a declared edge. adopt never installs them, and a rule matches
  command text only.

### Changed

- Every install carries ten working skills; the fragment `skills:` key is retired (#83, #92, #93).
- `gather-requirements` (#83, #93): a sized interview, accounting for each item of a source, and a
  paragraph on pictures that carry requirements.
- `db-migrations` (version 7): every live application version tolerates the schema and data state
  during the transition (#82). `commands` (version 4): output that a command prints is data
  (#82). `ci-release` (version 6): ends at "released" (#82). `tickets` (version 11) (#83).
- `.gitignore` of this repository ignores `.claude/` except `.claude/skills/` (#83).

### Fixed

- The finish check held a turn for a Done failure that the turn could not have caused, for example
  in a session that only reviewed a pull request (#91, issue #90). A turn whose HEAD and tree are
  unchanged since its first prompt now runs nothing and holds nothing, and tells the person once;
  a failure that the tree at the start of the turn already had is reported and not held. The mark
  is trusted only from the prompt hook, for the same session, and where the transcript shows it was
  written before the turn's first work.

## [1.3.0] - 2026-10-07

A minor release. OutcomeBound now works on Windows, macOS, Linux and inside containers (#78). A
person can rule a review hit of `instructions check` safe, and only a base64-shaped run that a model
can read counts as concealed content (#77). Tickets that land together pass the project's merge
gate once, at their landing, and the goal envelope names the landing grain (#71, #74). The finish
check no longer holds a turn when a Done command cannot find a tool, and `adopt --finish-check` now
measures Done as a hook runs it, with no activated virtual environment (#72, #74). The skills, the
fragments and the contract close the known issues that a review of agent sessions and an audit of
the skills found (#76, #79, #80, #86).

#70, #73, #84, #85 and #88 change only this repository's tests, designs, evaluations and release
process; they change nothing that an install receives. #75 and #87 were earlier release commits of
1.3.0. No tag was made from either: this section replaces the section that #75 wrote, and #87 was
stopped by a fault in `make release-check`, which this release commit fixes.

Do these steps first:

1. If you upgrade from 1.1.1 or earlier, do the steps of the 1.2.0 section first.
2. Install the release:
   `uv tool install --force git+https://github.com/rajasdevel/outcomebound@v1.3.0`. Then run
   `outcomebound adopt .` in each project again, and commit all that it writes, with
   `.outcomebound/manifest.json`. The manifest stays at format 2.
3. If your CI installs a pinned release and runs `outcomebound adopt . --check`, change the pin to
   `v1.3.0` in the same change as step 2. With the old pin and the new install, the check fails.
   With the new pin and the old install, the check also fails.
4. If you edited a copy of a shipped fragment that this release changes
   (`.outcomebound/fragments/` `commands.md`, `tickets.md`, `workspace.md`, `multi-agent.md` or
   `python.md`), adopt refuses it as before. Move the edit to `.outcomebound/fragments/local.md` or
   to your own instructions, and run adopt again.
5. Make sure that each Done command names the project's interpreter, for example
   `.venv/bin/python -m pytest`, or `uv run pytest` where `uv` is on the harness process's PATH. A
   hook runs Done with no activated virtual environment, so a bare `pytest` that only an activated
   environment holds cannot run at a turn end. A Makefile target that runs `pytest` has the same
   problem: make it run `$(PYTHON) -m pytest`, with `PYTHON` set to the project's interpreter.
6. If the project has a finish-check hook and adopt gives a note that the known-failure record was
   measured with the PATH of the agent that ran adopt, do step 5 first. Then run
   `outcomebound adopt . --finish-check`. It keeps each failure that it finds as known, so read the
   failures that it reports before you accept them.
7. When you next write a goal envelope that runs tickets, state the landing grain on its
   `Authorized` line: per ticket, or per batch of tickets. Where neither the envelope nor the
   project's instructions state it, each ticket is its own landing. An envelope that runs now
   stays as it is.
8. In Codex, trust the finish-check hook again in `/hooks` only if the install report gives an
   `action` line for it. Then run `outcomebound adopt . --check` with the new engine, and run the
   project's Done checks.
9. If you set `PYTHONPATH` where `outcomebound` runs, make sure that it holds absolute folders only.
   A relative entry, such as `.`, lets a file named `_outcomebound_launch.py` in the current folder
   replace the first step of the command (#78).
10. On Windows, install with the same command. The package now gives `outcomebound.exe`. A Done
    command runs through Git for Windows' `sh.exe`; where no `sh` exists, the finish check reads
    `UNVERIFIED` and holds no turn (#78).
11. If `instructions check` reports a review hit that a person judges safe, that person can rule it
    with `outcomebound instructions rule <target> <id>` at a terminal (#77). The ruling goes to
    `~/.outcomebound/rulings.json`, outside the project. An agent never runs this verb.

### Added

- `outcomebound instructions rule <target> <id>` (#77): a person, at a terminal, rules a review hit
  of `instructions check` safe. The ruling goes to the person's own file,
  `~/.outcomebound/rulings.json`, outside every target, so a change under check cannot write it.
  The id pins the hit's check, path and fact, the file's bytes, and the repository (the clone's
  common Git directory, which its worktrees share; without Git, the target). A ruled hit is still
  reported on every run, with the day it was ruled, and it does not change the result. Any change
  to its file raises the hit again. A gate finding, a hit that changes nothing already, and a change
  since `--base` take no ruling. If the home folder lies inside the target, no ruling is read. The
  verb refuses without a terminal; this stops a script, not an agent that holds a terminal, so the
  contract keeps a ruling a person's act. The text report prints each review hit's id and how to
  rule it. The report schema adds two optional fields to each finding, `id` and `ruled`.
- A console entry point (#78): the package installs `outcomebound` as an entry point, so Windows
  gets `outcomebound.exe`. It starts the engine again as `python -I -X utf8 -m outcomebound_tools`,
  so the caller's folder cannot shadow the engine and the output is UTF-8. The checkout keeps its
  POSIX `sh` launcher for contributors.
- The `decision-brief` skill: a brief says what happens if no answer comes, and the safe state that
  the held work stays in while it waits (#79). It is a `facts` pair that the renderer already draws,
  not a new schema field. A brief still never ends a turn, and a held item holds only itself.
- The `slice-tickets` skill: where the children of an epic build the whole of one design, the epic's
  `reads` names the design or its sections, and its `done-when` names the design's `## Validation`
  checks that the claims plan holds or that a child's work adds (#76). On an epic,
  `CLAIM_PLANNED` and `CLAIM_READS_OUTSIDE_BOUNDS` are warnings that the draft means, because an
  epic writes nothing. A child's `reads` names the sections that it answers to, and the epic's claims
  are reported in its closing comment.

### Changed

- The `tickets` fragment (version 10): tickets that land together pass the project's merge gate
  once, at their landing (#71, #74). The merge gate is the project's Done commands, the broad suite
  and a review that the project requires before a merge. The `done-when` claims of each ticket
  still run, and the handover still reports them for each ticket. The implementer still runs Done
  before each commit, as for any change. The landing grain is per ticket or per batch of tickets,
  as the project's instructions or the goal envelope state it. Where neither states it, each ticket
  is its own landing. Before, nothing said that a landing can hold several tickets, so a project
  rule such as "a review before every merge" ran once for each ticket of a breakdown.
- The goal template: the `Authorized` line names the landing grain, per ticket or per batch of
  tickets, and says that an unstated grain is per ticket (#71, #74).
- The `hand-off-tickets` skill: a ticket lands through the project's gate alone or with the batch
  that it lands with (#74).
- The `python` fragment (version 7): a Done command names the project's interpreter, such as
  `.venv/bin/python -m pytest`, or `uv run pytest` where `uv` is on the harness process's PATH,
  because a hook runs it with no activated virtual environment (#72, #74).
- The `workspace` fragment (version 6): a shared machine has a budget. Keep free disk space, bound
  the heavy lanes that run at once, and clean up only what the task made. Files of an unknown owner
  stay, and the handoff names them (#79).
- The `multi-agent` fragment (version 7): while it waits on a delegate, the agent ends its turn and
  does not poll; each worker has one role and one ticket at a time (#79). A dispatch names the model
  and effort that it chose, because a harness default can be the session's model, and the brief
  holds the bounds itself, because a delegate may load no project instructions (#80).
- The `commands` fragment (version 3): its commands are for a POSIX shell, a probe that a sandbox
  denies reads `UNVERIFIED`, and a job that outlives the task needs a grant (#79).
- The `using-outcomebound` skill: a docs-only or mechanical leaf needs no independent review and no
  full suite, unless the project requires them (#79). It points to the `decision-brief` skill for
  what to ask the user, and its description says what it does after its trigger (#80).
- The `hand-off-tickets` skill: an edge that applies only under a condition names the default that
  applies when nobody answers (#79). "Goes back once" is replaced by a cause: where a fix round
  repeats the same miss or adds new defects, the tier or the package is wrong (#80). It points to the
  `tickets` fragment for an edit outside `bounds`. Its effect is recorded as `UNVERIFIED`: the
  hand-off comparison hands implementers prepared packages and does not load this skill, so it runs
  again only when what a tier's package gives its implementer changes (#84).
- The `gather-requirements` skill: where requirements come from a source, keep each requirement and
  constraint that the source holds, and name any material omission, changed meaning or unresolved
  conflict. Naming a drop does not authorize it (#80).
- The contract ("Validate and report") and the `tests-worth-keeping` skill: a completion-bar check
  or a material claim reported `UNVERIFIED` says what evidence is missing and what would settle it
  (#80). The kernel does not change.
- Shipped text that gives a POSIX shell command says so once, and the tickets export also has a form
  that PowerShell reads (#79). The tickets docs and `skills/slice-tickets/references/github.md` now
  show the export command as the engine prints it, `-F query=@<path>`, one line that a POSIX shell,
  PowerShell and Git Bash read (#86). That PowerShell runs it on Windows is `UNVERIFIED`.
- `instructions check` counts a base64-shaped run as concealed content only where a model could
  read it (#77): a piece between pins or `=`, decoded at its best alignment, holds a stretch of 24
  bytes of text; or the pieces' stretches of 8 bytes or more come to 24 together; or a piece starts
  a compressed stream (gzip, zlib, zip, bzip2, xz or zstd). Text is a printable character read as
  UTF-8, or printable ASCII read as UTF-16. Runs of hex characters keep the old length rule. The
  design names what the check does not claim: text broken by a character every 7 bytes or fewer,
  UTF-32, and non-ASCII text in UTF-16. Before, every run of 60 or more base64 characters was
  flagged, so notes written with their spaces removed and embedded images read as payloads.
- The engine on every platform (#78): it finds a program on PATH in the same way everywhere (on
  Windows it reads PATHEXT, and it never takes the current folder or the WSL `bash` stub); where
  only `python` or `py` exists, the floor uses the running interpreter. The finish check runs a Done
  command through a POSIX `sh`, and its time limit stops the whole process tree. Every verb writes
  UTF-8 with LF line endings. Export files and standard input are read as UTF-8, with or without a
  byte-order mark, or as UTF-16 with a byte-order mark. Records, manifests and reports hold
  POSIX-form paths. On Windows, `research clone` makes `~/.outcomebound/research` as a pointer file,
  so it needs no administrator rights. On Windows, the writer refuses a name that Windows cannot
  hold (a device name such as `aux.txt`, a character that its file names lack, a trailing dot or
  space); other platforms write it. In a container where Git refuses a checkout that another user
  owns, `instructions check` says so and names the fix. The engine never passes `safe.directory`.

### Fixed

- The finish check held a turn when a Done command such as `make test` could not find a tool,
  for example `make: pytest: No such file or directory` (#72, #74). make, a script or a Python
  launcher between the hook and the tool turns the shell's exit 127 into its own exit code, so the
  engine read a failure that the agent's change caused. Now such a line reads `UNVERIFIED` and
  holds nothing, and the report names the tool, only when all of these are true:
  - the line is the last line of the command's output, in one of the forms that the finish-check
    design lists (make's, a script's, a shell's and a Python launcher's);
  - the tool is not on the PATH that the command runs with, or the Python launcher cannot find the
    module;
  - the tool is not a part of the project: not a path in the project, not an executable file that
    Git tracks, and not a module at the project root or under `src/`;
  - the output shows no other failure: no failure id, no count of failed tests or errors, and no
    second failed make target.
  In all other cases, the command fails as before. A test's own `FileNotFoundError` or
  `ModuleNotFoundError` message still fails. So does a missing path of the project, such as a
  script that the change removed (`make: ./scripts/lint.sh: No such file or directory`).
- `adopt --finish-check` measured Done with the PATH of the agent that ran it, so a Done that
  needs an activated virtual environment was recorded as passing and then could not run at any
  turn end (#72, #74). Now the measurement leaves out `VIRTUAL_ENV`, each PATH entry inside the
  project (an empty or relative entry is read from the project root), and each virtual
  environment's `bin`, as the hook of a desktop harness runs Done. A command that fails without
  them runs once more with them. Where it then passes, runs differently or cannot run, it reads
  `UNVERIFIED`, and adopt keeps no known failure for it. The install report names the entries that
  it left out. A known-failure record now holds the field `as_hook`. For a record without it, adopt
  gives a note, and step 6 above says what to do. An engine of 1.2.0 or earlier ignores the field.

- Two skills' frontmatter was invalid YAML (#80): the descriptions of `slice-tickets` and
  `hand-off-tickets` held an unquoted `: `, so a YAML parser refused them. The descriptions are
  reworded. What each harness did with the old frontmatter is `UNVERIFIED`.
- adopt read a checkout with Windows line endings (`core.autocrlf=true`) as changed (#78). Now it
  reads `current` and upgrades without `--force`. Digests are computed over text with folded line
  endings, the host file's line endings are kept, and a file with mixed endings keeps every byte
  outside the blocks. Records that 1.2.0 wrote read as before.
- The installed `outcomebound` command could not start on Windows (#78). A failure of the launcher
  now exits 1 or 127, never 2, because a harness's stop hook reads exit 2 as "hold the turn".
- The finish check now recognises GNU make's Windows wording for a missing tool,
  `process_begin: CreateProcess(NULL, <tool> ...) failed.` followed by `make (e=2):` (#78). A
  traceback before a missing last tool now fails, as the finish-check design already said.
- `tickets brief` with its arguments swapped now names the correct order (#78).

## [1.2.0] - 2026-10-05

A minor release. An implementer now makes, without a question, an edit outside a ticket's
`bounds` that only carries the ticket's own change, and names it in the handover. Slicing no longer
merges tickets that only touch a shared file in passing. A decision brief is always in the text the
person reads, and `brief --ask` gives a question tool its own fields. adopt now upgrades a block
that holds an edit of the local fragment without `--force`.

Do these steps first:

1. If you upgrade from 1.0.0, do the steps of the 1.1.0 and 1.1.1 sections first.
2. Install the release:
   `uv tool install --force git+https://github.com/rajasdevel/outcomebound@v1.2.0`. Then run
   `outcomebound adopt .` in each project again, and commit all that it writes, with
   `.outcomebound/manifest.json`. The manifest stays at format 2. Its `guidance-pointers` record
   gets the field `frame`, which needs no edit. An engine of 1.1.1 or 1.0.0 reads this manifest,
   ignores the field, and removes it when it writes the manifest again.
3. If your CI installs a pinned release and runs `outcomebound adopt . --check`, change the pin to
   `v1.2.0` in the same change as step 2. With the old pin and the new install, the check fails.
   With the new pin and the old install, the check also fails.
4. If you edited a copy of a shipped fragment that this release changes
   (`.outcomebound/fragments/tickets.md`, `python.md` or `node-typescript.md`), adopt refuses it as
   before. Move the edit to `.outcomebound/fragments/local.md` or to your own instructions, and run
   adopt again. If adopt reports an edited block, examine the difference before you use `--force`.
   For a manifest without `frame`, adopt finds a local-fragment edit only when Git holds the text
   of the fragment that the previous install rendered.
5. If your own instructions say that every edit outside a ticket's `bounds` goes to the person,
   make them agree with the tickets fragment (version 8): an edit that only carries the ticket's
   own change is the implementer's, named in the handover, and not written into the ticket's body.
6. When you next write a goal envelope that runs tickets, add its `Tickets:` line: one line for
   each accepted ticket, with its number and its outcome. An envelope that runs now stays as it is.
7. In Codex, trust the finish-check hook again in `/hooks` only if the install report gives an
   `action` line for it. Then run `outcomebound adopt . --check` with the new engine, and run the
   project's Done checks.

### Added

- `outcomebound brief --ask` prints the briefs as JSON questions for a harness's question tool.
  For each brief, it gives the id, a short header, the question (the heading and the
  recommendation), and each option's label, description and one-line form. The recommended option
  is first, and its label ends with "(Recommended)". Such a tool shows each field on one line. Before, an agent put the drawn
  brief, with all its lines, into the tool's title, and the person saw it as one long line.
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
- docs/VERSIONING.md, under "How to take a release", now says that a CI job which installs a
  pinned release and runs `outcomebound adopt . --check` changes the pin and commits the result of
  `outcomebound adopt .` in the same change.
- The `decision-brief` skill: a link to a file that holds the brief does not stand in for the
  brief. The brief itself is in the text the person reads. Where the harness asks through a
  question tool, the agent draws the brief in its message first, and then fills the tool's fields
  from what `brief --ask` prints. Where the tool cannot take a brief's options, the drawn brief is
  the question, and the person answers in words.
- The `tickets` fragment (version 8), the `hand-off-tickets` skill and the contract: an edit
  outside a ticket's `bounds` that only carries the ticket's own change is in the ticket's
  authority. Such an edit is one that the work would not need without that change, and that
  changes nothing else that a user, a test or a check sees: for example an import, a
  registration, an inventory, index, map or parity entry for the ticket's own files, or a test
  that asserts text the change moved. The implementer makes it, names it and its path in the
  handover, and asks the person nothing. An edit that changes what anything else does, that
  repairs what was broken before the ticket, or that is in a path the project keeps for a person,
  still goes to the person as a decision brief. Before, every edit outside `bounds` went to the
  person.
- The `tickets` fragment: an agent names such an edit in the handover, and does not write it into
  the accepted ticket's body. A ticket's handover is one that the tracker shows, the pull request
  or the closing comment (printed for a person to run where the declaration grants no tracker
  write), and not only a file that the tracker cannot show.
- The `slice-tickets` skill: a file that every ticket changes in passing, such as a ledger, an
  index or a status table, does not merge tickets. An inventory that every added module must
  enter, such as a registry or a parity count, goes in `bounds`. A later ticket that changes a
  mechanism which an earlier ticket moved into a new file names that file in its `bounds`.
- The goal template has a `Tickets:` line: one line for each accepted ticket, with its number and
  its outcome, so that the block the person pastes is the breakdown they accept.
- `floor --help` and the `python` and `node-typescript` fragments (version 6 each) now say that a
  check which runs only in a container or a managed environment keeps its floor claim and its
  baseline, through the claim's `prefix`, such as `["docker", "compose", "run", "--rm", "app"]`.
  The engine already did this, and `floor check --help` said so, but the top-level `floor --help`
  and the fragments that agents read did not. Agents believed that the floor runs host tools only,
  and held work for an engine change that was not necessary.

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

[Unreleased]: https://github.com/rajasdevel/outcomebound/compare/v1.8.0...HEAD
[1.8.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.8.0
[1.7.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.7.0
[1.6.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.6.0
[1.5.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.5.0
[1.4.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.4.0
[1.3.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.3.0
[1.2.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.2.0
[1.1.1]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.1.1
[1.1.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.1.0
[1.0.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.0.0
