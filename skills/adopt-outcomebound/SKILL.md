---
name: adopt-outcomebound
description: Use when onboarding a repository to OutcomeBound, upgrading its install, or checking whether an install is current. Installs the contract and skills, records the project's Done commands, and proposes only the project facts an agent would get wrong, each with the file that shows it.
---

# Onboard a repository

Use `outcomebound` on PATH: installed from a release, or `scripts/outcomebound` in an OutcomeBound
checkout. Read the target's existing agent instructions and its dirty state first; they are
preserved.

You are done when the install is current (an install that exits 0 wrote and checked every record;
`outcomebound adopt <target> --check` is for a later day or another clone), each Done command
was run once or the report says why not, each line you proposed for the project's `local` guidance
cites the file that shows it, each fact the install reports `UNVERIFIED` is named, and what only the
person can answer has gone to them as one decision brief. Write no overview of the repository: an
agent reads the code, and a summary of it adds text without adding a fact.

## Install or upgrade

1. `outcomebound adopt <target> --detect` prints the install command on its first line, with the
   fragments, harnesses, `--done` and any `--setup` commands it detected; with no harness file it
   proposes `generic`. Each following line starts with `#`: a candidate it did not put in the
   command, an onboarding signal, a readiness line, and where this guide lives. Change the proposal
   only where the target shows it is wrong; the `--done` commands are the ones that settle done
   here, in the order they run. Propose no Done command that the project's own text does not name.
   Outside a Git work tree it refuses and names `git init`; on an empty repository it names the
   new-project route.
2. Run that command. It writes three blocks into `AGENTS.md`: the contract; the project facts
   (Done, Setup, the CI test command, irreversible edges, precedence); and the pointers, the `local`
   fragment in full and a `- <condition>: read <path>` line per fragment and skill. It copies the
   selected fragments under `.outcomebound/fragments/`, the skills per harness, each folder whole:
   the thirteen every install carries (under `.outcomebound/skills/` for `generic`), the `@AGENTS.md`
   import a harness needs to load it, and `.outcomebound/manifest.json` last. It refuses a harness
   that would not load the contract. It also refuses to overwrite an owned file someone edited,
   unless `--force` is given. Running it again from a newer release or checkout is the upgrade. An upgrade
   from 1.6.0 also takes out the stop and prompt entries that the finish check wrote into
   `.claude/settings.json` and `.codex/hooks.json`; since 1.7.0 `adopt` writes no hook.
3. Report `outcomebound instructions check <target>`, which reads what each selected harness loads
   there as untrusted data, and what you read in those files' prose (the ones
   `adapters/harnesses.json` lists for the selected harnesses): what contradicts the contract, what
   the repository does not back, what is said twice, and the stale and retired references the
   check lists.
   Edit none of them. A review hit the person judges safe, they record themselves with
   `outcomebound instructions rule <target> <id>` at a terminal; never run that verb yourself.
4. With the person's yes, and only after step 3, since it runs the repository's own code: run each
   Done command once, and a failing one again only where its output suggests a flake. `adopt` runs
   none. Report whether each passed, failed or was not run. A Done that needs a secret or a service
   reads as its command reads; say which.
5. For a shared installation, check that the files it needs will survive the target's normal
   commit and checkout workflow. Use the manifest and the ignored-path warnings to inspect the
   intended shared paths; an unchanged repeat install can still have this problem. Review complete
   settings files before staging: the tool owns entries, not every byte in those files. Stage only
   shareable adoption content under the target's rules; leave unrelated and machine-local changes
   unstaged. If mixed content cannot be separated safely within the grant, leave it unstaged and
   report that specific limit while other authorized work continues. Never force-add a directory to
   silence the warnings. After the target's authorized commit, verify the installation bytes from
   that commit, for example with the install check in a clean disposable checkout. A tracked path or
   a passing check of the current working files does not prove this. A machine-local install is
   also valid when that is the intended scope; report that limit instead of claiming that another
   clone receives it. A cloud or background session starts from the pushed branch: it gets only what
   was committed, and `outcomebound` only where the environment's setup installs it; the report's cloud
   note gives the install line.

## The project's own facts

Propose lines for the project's `local` guidance (`.outcomebound/fragments/local.md`, from
`$(outcomebound home)/templates/fragment-local.md`, selected with `--fragments local`) only from what
the target shows: the signals `--detect` printed, the result of a Done run, the CI and build files, and
the history of fixes and reverts. Each line names the file or commit that shows it and goes in the
slot the signal names. Keep a line only where an agent without it would make a mistake; leave out
what a reader finds by opening the code or the README. Where a check can hold the fact, offer the
check instead of the sentence: an edge in `edges:` with an ask rule from
`$(outcomebound home)/templates/harness/`, a floor claim, a CI line. Show the person the lines; the
file is theirs.

## The project's lifecycle

The project keeps its own route; you record where it is and what the route rests on, never a copy
of it. Observe first: what the project does now, from its instructions, contributing and workflow
documents, CI and deploy files, and the history `--detect` reports. Then propose the optional
lines below under the same keep-a-line rule: a line only where the project's committed text does not
already lead an agent to the decision, and most lines are left out. Each line cites the file that
shows it, or reads "the person says so"; a fact no file shows is `assumed` and goes in the brief.
Name each line form in double quotes, never in backticks, when you write about it.

- "Exposure —" (Context), one line for each stream where the streams differ: who can be hurt, who
  accepts the work, which acts cannot be undone, the expected life, who maintains it, and how much
  the agents write against the review capacity. Propose it for a stream whose acts cannot easily
  be undone, such as database objects changed with no migration and no way back but a revert.
- "Streams —" (Context): the route document of each stream, the kind of change it takes and,
  where a fragment applies to that stream only, "; fragments <id>, <id>". It points only to a
  document the next person can open: committed, or named as private with who holds it. Where a
  stream has no written route, propose the lines for the project's own document (branch, review,
  how a change reaches a server, the way back), each with the file or commit that shows it, and
  send what no file shows to the brief; for a client delivery, `templates/lifecycle/overlay-client.md`
  holds a route example to compare with. Never write a route into OutcomeBound's files.
- "Better means —" (Context): the project's own measure of a better outcome, in its words, where it
  is not written where an agent reads it.
- "Gates —" (Bounds): a gate, its owner and its evidence. A gate with no named owner is reported to
  the person as a gap; never fill the owner.
- "Leave when —" (Bounds): a signal that ends the current lifecycle, where it can be observed, who
  watches it, and the brief it opens. The brief inventories the work in flight: open tickets,
  branches the main line does not hold and their requests, worktrees with uncommitted work, open
  briefs, standing grants, a deploy in a partial phase. Write
  the moves back too. For a change of route, the inventory is most of the brief, not a fragment diff.
  A row whose signal already reaches the owner is left out.
- "Changed —" (Context): written after a complete directive or the person's answer to the transition
  brief, one line for each stream, the older one removed, never at adoption, in this form:
  Changed — <date> (stream: <stream>): "<the person's words>", decided by <who>; retired
  "<old term>"; invalidated <what no longer holds>.

Select fragments from the exposure facts and what the files show: `team` for two or more
maintainers or required review, else `solo`; `deploy` and `runtime` where it deploys a service;
`ci-release` where it publishes a package; `db-migrations` where it changes stored data; `client`
where a client or a regulator accepts the work; `explore` where the expected life starts with
learning. A fragment applies to every stream unless a "Streams —" line names it in its fragments
field. Add them to `--fragments`, and name the facts that selected each. On an upgrade, show the
person each drift line `--check` prints that is not settled: it is the moment someone reads them;
for a settled one (`settled by the person: <reason>`), read its reason against the evidence and
raise it only if they differ. A line the person settles gets a "Drift — <signal>: <reason>" line,
on a line of its own with a reason, in the local fragment's Bounds slot.

Name the nearest preset of `$(outcomebound home)/templates/lifecycle/` (`prototype`, `solo`,
`team`, `organization`), each overlay whose fact holds (`overlay-*.md`), and the differences
between them and what you observed, as a comparison for the person. Never copy them, and adoption
installs none of them. A move the person accepts can take its absent files from the scaffold
(`outcomebound scaffold --help`).

## Ask once

Put what the target cannot show in one decision brief (`outcomebound brief --help`): the outcome and
the users where the README does not say, irreversible acts no file shows, why a Done command fails
on the base, what must never be touched, and each `UNVERIFIED` item only the person can settle,
such as a secret or production access. Each question names the line that raised it and the default
you take without an answer, and the work that does not wait on it goes on.

## Offer; each changes CI or tooling, so act only on the person's yes

- A quality floor: `outcomebound floor --help` gives its steps; where `.outcomebound/retired.json`
  exists, `floor propose` also offers the `docs.retired` claim. Its tools install only through its
  `provision` step, one of the commands here that reach the network: it pip-installs ruff and mypy
  into the `python3` on PATH, where the floor finds its tools, and prints gitleaks' and shellcheck's
  install commands.
- Research: add `research` to `--fragments`, so the project's agents read the research repository
  through `outcomebound research`. Its clone is one per machine, in a folder outside any project:
  `outcomebound research clone <destination>` previews it, and with `--accept` runs `git clone` and
  links `~/.outcomebound/research` to it; `outcomebound research pull --accept` updates it. Both
  reach the network.
- A CI line that fails when the install drifts: `outcomebound adopt . --check` (`templates/ci/` has
  snippets). Never change CI, hooks, credentials or harness settings without the yes.

## Check and remove

`outcomebound adopt <target> --check` reads each owned file as current, edited, stale or missing,
exits with the count that is not current. A `hook` record that 1.6.0 wrote reads `stale` where its
entry is unchanged, `edited` where a person changed it, or `missing` where it is gone, and names the
entry; the next install takes an unchanged entry out. `outcomebound adopt <target> --remove` takes out the owned blocks, files and imports, the
manifest last.

## Report

The files written, the final `AGENTS.md` blocks, each readiness line and each fact the install
reported `UNVERIFIED`, the lines you proposed and the file behind each (lifecycle lines too), each gate without an owner,
the fragments the exposure selected, the nearest lifecycle template and its differences, the decision brief, and for
each harness whether it was observed loading the install or that is `UNVERIFIED`.
