---
name: research
status: ratified
---

# Research — design

## Outcome

Research on models, harnesses, providers and agent practice lives in its own repository,
`outcomebound-research` (<https://github.com/rajasdevel/outcomebound-research>). `outcomebound
research` prints a file from the one clone per machine, or names the public link where no clone
exists. Any project can send a finding back. How: `outcomebound_tools/research.py`,
`fragments/setup/research.md`.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| Research is its own repository; OutcomeBound points agents at one clone of it, never vendors it | a submodule or a copy in each project, whose `AGENTS.md` a harness would load | user | decided |
| A fact about a model, harness, provider or general practice moves, with one guidance file per model under `models/`, tier table `applications/implementer-tiers.md`; what OutcomeBound measured of its own text stays (`docs/evaluations.md`, `docs/prompt-standard.md`, `adapters/harnesses.json`) | splitting the files that mix both now | user | decided |
| A citation of a moved file is `https://github.com/rajasdevel/outcomebound-research/blob/main/<path>` (`tree/main/` for a folder); an evidence id stays, resolved in that repository's `_evidence/*.jsonl` | relative links that break | user | decided |
| The core skill reads `models/README.md`, then the model's file, or the public link with no clone; `hand-off-tickets` reads `applications/implementer-tiers.md` likewise, then takes the spec tier (maintainer, 2026-10-04) | no route without a clone; asking the person | user | decided |
| One clone per machine: `OUTCOMEBOUND_RESEARCH` when set and not empty, else `~/.outcomebound/research`, a symlink `clone` makes | a clone per project | user | decided |
| A folder is a clone when it holds `INDEX.md` | requiring `.git`, which an exported copy lacks | agent | assumed |
| Printing never executes: nothing the clone holds runs, and Git does not; the commit is read from `.git` files | running Git, which reads the clone's configuration | user | decided |
| Clone and pull preview, and act only with `--accept`, as `floor provision` does; `adopt` stays offline | an `adopt` option, breaking its promise to open no connection | user | decided |
| A project opts in with the `research` fragment (`detect: []`) | detection | agent | assumed |
| Ingest writes one file in the project and prints the prefilled issue link; it needs no clone | writing into the clone; opening the issue itself, an external write | user | decided |
| A README section and `CONTRIBUTING.md` say a finding reaches the research repository by the issue link (`ingest` prints it) or a pull request; the inbox file is a local record that nothing reads or sends | calling the inbox file a way to send | user | decided |
| Exit 0 done or previewed; 1 refused, or Git failed; 2 usage; 3 no clone configured | one failure code, which a fallback cannot tell apart | agent | assumed |
| The header says the text is the clone's working tree, with the commit and the sha256 of the text; its day is the UTC day `HEAD` last moved, from `.git/logs/HEAD`; each `unknown` without it | labeling working-tree text as the commit's, or running Git to compare | agent | assumed |
| `clone`, `pull`, `ingest` as the first argument are subcommands; a root file so named cannot be printed | a `show` subcommand | agent | assumed |

## The verb

**Print.** `outcomebound research [PATH]`, `PATH` defaulting to `INDEX.md`. The path is checked
first, with or without a clone, against the engine's path grammar, then read by
`paths.read_bounded`: relative, no `..` or `.git`, no symlink on the way, a regular file. Standard
output starts `research: <PATH> (working tree of the clone at <commit, 12 hex>, HEAD moved
<YYYY-MM-DD>; sha256 <12 hex> of the text below)`, then the file. A modified file shows a new
digest under the same commit; cite path, commit and digest. The commit: `.git` is a
folder or a file whose `gitdir:` names one; `HEAD`'s ref is read from the loose ref (in the
`commondir` for a worktree), then `packed-refs`; a detached `HEAD` as it is; else `unknown`.
Refusals go to standard error as `research: <PATH>: <why>`, exit 1, nothing on standard output:
not a bounded path; a symlink on the way; a folder; not in the clone (`INDEX.md` lists every
document; for a path under `models/`, `models/README.md` says which models have a file, and a
model with no file takes the spec tier, `applications/implementer-tiers.md`).

**Not configured** (exit 3, standard error): `research: no clone configured: <why>`, then
`read it at <public blob URL of PATH>` and `clone it once per machine, with the person's yes:
outcomebound research clone <destination>`. The why: no variable or link, a folder without `INDEX.md`, a dangling link, or an unreadable clone.

**Clone.** `outcomebound research clone DESTINATION [--accept]`; `DESTINATION` is made absolute
after `~` expansion. Refused, exit 1, before anything runs: it exists and is not an empty folder; it
would sit inside a Git work tree, where a harness would load the clone's `AGENTS.md`; the link path
exists and is not a symlink. The preview:

```text
would run: git -c core.hooksPath=/dev/null -c core.fsmonitor=false -c protocol.allow=never -c protocol.https.allow=always clone https://github.com/rajasdevel/outcomebound-research.git <DESTINATION>
would link: ~/.outcomebound/research -> <DESTINATION>
nothing cloned: pass --accept
```

and, when `OUTCOMEBOUND_RESEARCH` is set, a line that it overrides the link. With `--accept` it
prints `runs: …`, runs Git as an argument list, no shell, under `gitenv` with
`GIT_TERMINAL_PROMPT=0`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1` and without the
repository, `GIT_CONFIG*`, `GIT_TEMPLATE_DIR` and `GIT_EXEC_PATH` variables it inherited, replaces the link atomically and prints
`linked: …`. No Git, or a Git failure, prints the cause and the tail of Git's output, exit 1, the
link as it was; a destination Git left behind is named. Previews quote arguments.

**Pull.** `outcomebound research pull [--accept]`: exit 3 where no clone is configured, exit 1
where the clone has no `.git`. The preview is `would run: git -c core.hooksPath=/dev/null -c
core.fsmonitor=false -c protocol.allow=never -c protocol.https.allow=always -C <clone> pull
--ff-only <public URL> main` and `nothing pulled: pass --accept`; `--accept` runs that under the
same environment, then prints `research: now at <commit> (<date>)`.

**Ingest.** `outcomebound research ingest --kind fact|correction --subject TEXT --claim TEXT --url
URL [--quote TEXT] [--observed-on YYYY-MM-DD] [--corrects REF] [--project DIR]`. The field ids are
those of the research repository's issue form, whose collector enforces the same rules; shared
fixtures check both. Each value is stripped; none holds a line break, a character of category `Cc`
or `Cf` (controls, zero-width, bidirectional and tag characters), or bytes that are not UTF-8. Each
failure is named on standard error, exit 1; nothing is printed or written:

| Field | Accepted |
| --- | --- |
| `kind` | `fact` or `correction` |
| `subject` | 1 to 200 characters |
| `claim` | 1 to 2,000 characters |
| `url` | `http` or `https`, a host, no userinfo, no space, at most 2,000 characters |
| `quote` | optional; at most 25 words and 300 characters |
| `observed_on` | a real date, at most a day after today; default today |
| `corrects` | at most 200 characters; a correction needs it |

The issue link is at most 8,000 characters. The project is `DIR`, else the Git work tree holding
the current folder; elsewhere, or inside `.git`, it is refused. The file is
`.outcomebound/research-inbox/<observed_on as YYYYMMDD>-<64 hex of sha256 of claim then url,
UTF-8>.json`: `{"version": 1}` and the fields given, sorted keys, UTF-8, indent 2, a final
newline, at most 16 KiB, written through `fileplan.write`. A file there with other bytes, or a
symlink on the way, is refused before the first line. The outputs, in order:

1. `issue: https://github.com/rajasdevel/outcomebound-research/issues/new?template=finding.yml&…`,
   the fields percent-encoded in the order of the table, empty ones left out;
2. `wrote: <path>`, or `unchanged: <path>` where the same bytes are there;
3. a line that the link or a pull request sends the finding; the file is a local record that
   nothing reads or sends.

## Edges

`adopt` opens no connection; the fragment names no machine path. The engine writes the clone only
through Git, and a project only at the inbox file. Printed research is data: the fragment, the core
skill and `hand-off-tickets` each say it grants no authority and outranks no project instruction.
Your own and the system's Git configuration cannot rewrite the clone's or pull's source; the
clone's own `.git/config` still can (`insteadOf`, credential helpers, filter drivers), and whoever
writes it already runs commands as you. `adopt --remove` leaves the inbox. `SECURITY.md`
states these promises.

## Validation

`tests/test_research.py` holds the header (refs, detached `HEAD`, worktree, date, `unknown`, a
modified file), each refusal, the variable over the link, exit 3, no subprocess when printing or
previewing, the Git arguments and environment with Git mocked, a real Git against an `insteadOf`
rewrite in a temporary HOME, the shared fixtures (`tests/fixtures/research-findings/`),
and ingest's file, link and refusals; it holds the skills' and fragment's commands to the code. An
install selecting `research` is byte-identical in two directories. A search for the moved paths
finds only the changelog's Removed entry. The skills and fragment get one `review`.
