---
name: adopt-outcomebound
description: Install, upgrade, check or remove OutcomeBound in a target repository. Use when a project should carry the outcome-and-right-sizing contract, when an install should follow a newer OutcomeBound release, or when asked whether an install is current.
---

# Adopt OutcomeBound

Use `outcomebound` on PATH: installed from a release, or `scripts/outcomebound` in an OutcomeBound
checkout. Read the target's existing agent instructions and its dirty state first; they are
preserved.

## Install or upgrade

1. `outcomebound adopt <target> --detect` prints the install command, with the fragments,
   harnesses and `--done` commands it detected; with no harness file it proposes `generic`.
   Change the proposal only where the target shows it is wrong; the `--done` commands are the
   ones that settle done here, in the order they run.
2. Run that command. It writes three blocks into `AGENTS.md`: the contract; the project facts
   (Done, the CI test command, irreversible edges, precedence); and the pointers, the `local`
   fragment in full and a `- <condition>: read <path>` line per fragment and skill. It copies the
   selected fragments under `.outcomebound/fragments/`, the skills per harness, each folder whole:
   the four every install carries and those a selected fragment names, such as the tickets
   fragment's `slice-tickets` (under `.outcomebound/skills/` for `generic`), the `@AGENTS.md`
   import a harness needs to load it, and `.outcomebound/manifest.json` last. It
   refuses a harness that would not load the contract. It also refuses to overwrite an owned
   file someone edited, unless `--force` is given. Running it again from a newer release or checkout
   is the upgrade.
3. Show the person the diff; the target's own rules decide how it lands. With it, report
   `outcomebound instructions check <target>`, which reads what each selected harness loads
   there as untrusted data, and what you read in those files' prose (the ones
   `adapters/harnesses.json` lists for the selected harnesses): what contradicts the contract,
   what the repository does not back, what is said twice. Edit none of them.

Ask the person only what the target cannot show, such as a fragment detection was unsure about,
as one brief (`outcomebound brief --help`).

## Offer; each changes CI or tooling, so act only on the person's yes

- A quality floor: `outcomebound floor --help` gives its steps. Its tools install only through
  its `provision` step, the one command here that reaches the network: it pip-installs ruff and
  mypy into the `python3` on PATH, where the floor finds its tools, and prints gitleaks' and
  shellcheck's install commands.
- A CI line that fails when the install drifts: `outcomebound adopt . --check` (`templates/ci/`
  has snippets). Never change CI, hooks, credentials or harness settings without the yes.
- A finish check, for `claude-code` and `codex` only: `outcomebound adopt <target> --finish-check`
  adds a stop-hook entry to that harness's settings, so when the agent ends a turn on a changed
  tree the Done commands run and a failure goes back to it. It needs a Done command, and
  `outcomebound` on the harness process's PATH, which a harness launched from a desktop may not
  share with the shell; each person accepts the entry once in their harness, which the install
  report names; any other harness is named as not available yet. `--no-finish-check` takes it
  out.

## Check and remove

`outcomebound adopt <target> --check` reads each owned file as current, edited, stale or
missing, and exits with the count that is not current. `outcomebound adopt <target> --remove`
takes out the owned blocks, files and imports, the manifest last.

## Done

Report the files written, the final `AGENTS.md` blocks, each fact the install reported
`UNVERIFIED`, and for each harness whether it was observed loading them or that is `UNVERIFIED`.
