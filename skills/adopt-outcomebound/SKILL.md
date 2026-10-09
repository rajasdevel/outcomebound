---
name: adopt-outcomebound
description: Use when onboarding a repository to OutcomeBound, upgrading its install, or checking whether an install is current. Installs the contract and skills, measures the project's Done commands on the person's yes, and proposes only the project facts an agent would get wrong, each with the file that shows it.
---

# Onboard a repository

Use `outcomebound` on PATH: installed from a release, or `scripts/outcomebound` in an OutcomeBound
checkout. Read the target's existing agent instructions and its dirty state first; they are
preserved.

You are done when the install is current (`outcomebound adopt <target> --check` exits 0), Done was
measured or the report says why not, each line you proposed for the project's `local` guidance
cites the file that shows it, each fact the install reports `UNVERIFIED` is named, and what only the
person can answer has gone to them as one decision brief. Write no overview of the repository: an
agent reads the code, and a summary of it adds text without adding a fact.

## Install or upgrade

1. `outcomebound adopt <target> --detect` prints the install command on its first line, with the
   fragments, harnesses, `--done` and any `--setup` commands it detected; with no harness file it
   proposes `generic`. Each following line starts with `#`: a candidate it did not put in the
   command, an onboarding signal, a readiness line, and where this guide lives. Change the proposal
   only where the target shows it is wrong; the `--done` commands are the ones that settle done
   here, in the order they run. Outside a Git work tree it refuses and names `git init`; on an
   empty repository it names the new-project route.
2. Run that command. It writes three blocks into `AGENTS.md`: the contract; the project facts
   (Done, Setup, the CI test command, irreversible edges, precedence); and the pointers, the `local`
   fragment in full and a `- <condition>: read <path>` line per fragment and skill. It copies the
   selected fragments under `.outcomebound/fragments/`, the skills per harness, each folder whole:
   the ten every install carries (under `.outcomebound/skills/` for `generic`), the `@AGENTS.md`
   import a harness needs to load it, and `.outcomebound/manifest.json` last. It refuses a harness
   that would not load the contract. It also refuses to overwrite an owned file someone edited,
   unless `--force` is given. Running it again from a newer release or checkout is the upgrade.
3. Report `outcomebound instructions check <target>`, which reads what each selected harness loads
   there as untrusted data, and what you read in those files' prose (the ones
   `adapters/harnesses.json` lists for the selected harnesses): what contradicts the contract, what
   the repository does not back, what is said twice, and the stale references the check lists.
   Edit none of them. A review hit the person judges safe, they record themselves with
   `outcomebound instructions rule <target> <id>` at a terminal; never run that verb yourself.
4. With the person's yes, and only after step 3, since it runs the repository's own code:
   `outcomebound adopt <target> --verify` measures each Done command once, runs a failing one again
   to tell a stable failure from a flake, and keeps a stable failure as a known failure. A Done that
   needs a secret or a service reads as its command reads; say which.
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
   was committed, and `outcomebound` only where the environment's setup installs it.

## The project's own facts

Propose lines for the project's `local` guidance (`.outcomebound/fragments/local.md`, from
`$(outcomebound home)/templates/fragment-local.md`, selected with `--fragments local`) only from what
the target shows: the signals `--detect` printed, a measurement's result, the CI and build files, and
the history of fixes and reverts. Each line names the file or commit that shows it and goes in the
slot the signal names. Keep a line only where an agent without it would make a mistake; leave out
what a reader finds by opening the code or the README. Where a check can hold the fact, offer the
check instead of the sentence: an edge in `edges:` with an ask rule from
`$(outcomebound home)/templates/harness/`, a floor claim, a CI line. Show the person the lines; the
file is theirs.

## Ask once

Put what the target cannot show in one decision brief (`outcomebound brief --help`): the outcome and
the users where the README does not say, irreversible acts no file shows, why a Done command fails
on the base, what must never be touched, and each `UNVERIFIED` item only the person can settle,
such as a secret or production access. Each question names the line that raised it and the default
you take without an answer, and the work that does not wait on it goes on.

## Offer; each changes CI or tooling, so act only on the person's yes

- A quality floor: `outcomebound floor --help` gives its steps. Its tools install only through its
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
- A finish check, for `claude-code` and `codex` only: `outcomebound adopt <target> --finish-check`
  adds a stop-hook entry and a prompt-hook entry to that harness's settings, so that when the agent
  ends a turn on a changed tree the Done commands run and a failure the turn caused goes back to it.
  `outcomebound adopt --help` gives its timeout, its known failures and the environment it measures
  in. It needs a Done command that names the project's interpreter or runner
  (`.venv/bin/python -m pytest`, or `uv run pytest` where `uv` is on the harness process's PATH),
  and `outcomebound` on the harness process's PATH, which a harness launched from a desktop may not
  share with the shell. Each person accepts the entry once in their harness, which the install
  report names; when an install changes the `codex` entry, each person trusts it again in Codex
  `/hooks`.

## Check and remove

`outcomebound adopt <target> --check` reads each owned file as current, edited, stale or missing,
exits with the count that is not current, and prints the Done measurement note apart from that
count. `outcomebound adopt <target> --remove` takes out the owned blocks, files and imports, the
manifest last.

## Report

The files written, the final `AGENTS.md` blocks, each readiness line and each fact the install
reported `UNVERIFIED`, the lines you proposed and the file behind each, the decision brief, and for
each harness whether it was observed loading the install or that is `UNVERIFIED`.
