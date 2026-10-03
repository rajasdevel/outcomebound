---
name: research
status: ratified
---

# Research — design

## Outcome

Research on models, harnesses, providers and agent practice lives in its own repository,
`outcomebound-research` (<https://github.com/rajasdevel/outcomebound-research>). `outcomebound
research` prints a file from the one clone per machine, headed by its commit, or names the public
link where no clone exists. Any project can send a finding back, with or without a clone. How:
`outcomebound_tools/research.py`, `fragments/setup/research.md`.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| Research is its own repository; OutcomeBound optionally points agents at one clone of it and never vendors it (D52) | a submodule or a copy in each project, whose `AGENTS.md` a harness would load | user | decided |
| A fact about a model, harness, provider or general practice moves; what OutcomeBound measured of its own text stays: all the former research folder moves but `practices/evaluations.md`, now `docs/evaluations.md`; `docs/prompt-standard.md` and `adapters/harnesses.json` stay | splitting the files that mix both now | user | decided |
| A citation of a moved file becomes `https://github.com/rajasdevel/outcomebound-research/blob/main/<path>` (a folder: `tree/main/<path>`); an evidence id stays, and a line says it resolves in that repository's `_evidence/*.jsonl` | relative links that break | user | decided |
| The model guidance moves there as `models/guidance.md`, its tier table as `models/tiers.md`; the wheel stops shipping it (D69) | a dated copy per release | user | decided |
| The core skill reads model and harness advice with `outcomebound research models/guidance.md`; where that reports no clone, or `outcomebound` is not on PATH, it reads the public link | no route without a clone | user | decided |
| `hand-off-tickets` finds the implementer's tier in `outcomebound research models/tiers.md`; with no clone it asks the person | a default tier | user | decided |
| One clone per machine: `OUTCOMEBOUND_RESEARCH` when set and not empty, else `~/.outcomebound/research`, a symlink `clone` makes (D59) | a clone per project | user | decided |
| A folder is a clone when it holds `INDEX.md` | requiring `.git`, which an exported copy lacks | agent | assumed |
| Printing never executes: nothing the clone holds runs, and Git does not run to print; the commit is read from the clone's `.git` files | running Git, which reads the clone's configuration | user | decided |
| Clone and pull are explicit networked acts that preview, and act only with `--accept`, as `floor provision` does; `adopt` stays offline | an `adopt` option, breaking its promise to open no connection | user | decided |
| A project opts in with the `research` fragment (`detect: []`), which the adopt skill offers | detection | agent | assumed |
| Ingest writes one file in the contributing project and prints the prefilled issue link first; it needs no clone (D60) | writing into the clone; opening the issue itself, an external write | user | decided |
| A README section and `CONTRIBUTING.md` say how to contribute: the issue form first, `outcomebound research ingest` offline, pull requests to the research repository | instructions only in the research repository | user | decided |
| Exit 0 done or previewed; 1 refused, or Git failed; 2 usage; 3 no clone configured | one failure code, which a fallback cannot tell apart | agent | assumed |
| The header's date is the day, in UTC, that `HEAD` last moved in the clone, from `.git/logs/HEAD`; `unknown` without it | the commit date, behind pack parsing | agent | assumed |
| `clone`, `pull` and `ingest` as the first argument are subcommands, so a root file of those names cannot be printed | a `show` subcommand | agent | assumed |

## The verb

**Print.** `outcomebound research [PATH]`, `PATH` defaulting to `INDEX.md`. The path is checked
first, with or without a clone, against the engine's path grammar, then read by
`paths.read_bounded`: relative, no `..` or `.git`, no symlink on the way, a regular file. Standard output starts
`research: <PATH> @ <commit, 12 hex> (<YYYY-MM-DD>)`, then the file. The commit: `.git` is a folder,
or a file whose `gitdir:` names one; `HEAD`'s ref
is read from the loose ref (in the `commondir` for a worktree), then `packed-refs`; a detached
`HEAD` as it is; else `unknown`. Refusals go to standard error as
`research: <PATH>: <why>`, exit 1, with nothing on standard output: not a bounded path; a symlink
on the way; a folder; not in the clone (`INDEX.md` lists every document, `MOVED.md` every moved path).

**Not configured** (exit 3, standard error):

```text
research: no clone configured: OUTCOMEBOUND_RESEARCH is unset and ~/.outcomebound/research does not exist
read it at https://github.com/rajasdevel/outcomebound-research/blob/main/<PATH>
clone it once per machine, with the person's yes: outcomebound research clone <destination>
```

Where `OUTCOMEBOUND_RESEARCH` names a folder without `INDEX.md`, the link dangles, or the clone
cannot be read, the first line says that instead, and still starts `no clone configured:`.

**Clone.** `outcomebound research clone DESTINATION [--accept]`; `DESTINATION` is made absolute
after `~` expansion. Refused, exit 1, before anything runs: it exists and is not an empty folder; it
would sit inside a Git work tree, where a harness would load the clone's `AGENTS.md`;
`~/.outcomebound/research` exists and is not a symlink. The preview:

```text
would run: git clone https://github.com/rajasdevel/outcomebound-research.git <DESTINATION>
would link: ~/.outcomebound/research -> <DESTINATION>
nothing cloned: pass --accept
```

and, when `OUTCOMEBOUND_RESEARCH` is set, a line that it overrides the link. With `--accept` it
prints `runs: …`, runs Git as an argument list, no shell, under `gitenv` with
`GIT_TERMINAL_PROMPT=0` and without the repository variables it inherited, then replaces the link
atomically and prints `linked: …`. No Git on PATH, or a Git failure, prints the cause and the
last of Git's output, exit 1, and the link is left as it was; a destination Git left behind is
named, to remove. Previews quote arguments.

**Pull.** `outcomebound research pull [--accept]`: exit 3 where no clone is configured, exit 1
where the clone has no `.git`. The preview is `would run: git -c core.hooksPath=/dev/null -c
core.fsmonitor=false -C <clone> pull --ff-only <public URL> main` and `nothing pulled: pass
--accept`; with `--accept` it runs that, then prints `research: now at <commit> (<date>)`.

**Ingest.** `outcomebound research ingest --kind fact|correction --subject TEXT --claim TEXT --url
URL [--quote TEXT] [--observed-on YYYY-MM-DD] [--corrects REF] [--project DIR]`. The field ids are
those of the research repository's issue form. Each value is stripped; none holds a line break, a control character (Unicode `Cc`), a
bidirectional control, or bytes that are not UTF-8. Each failure is named on standard error, exit
1, and nothing is printed or written:

| Field | Accepted |
| --- | --- |
| `kind` | `fact` or `correction` |
| `subject` | 1 to 120 characters |
| `claim` | 1 to 600 characters |
| `url` | `http` or `https`, with a host, no space |
| `quote` | optional; at most 25 words and 300 characters |
| `observed_on` | a real date, not after today; default today |
| `corrects` | at most 200 characters; required for a correction |

The issue link is at most 8,000 characters. The project is `DIR`, else the Git work tree holding
the current folder; outside one, or inside `.git`, it is refused. The file is
`.outcomebound/research-inbox/<observed_on as YYYYMMDD>-<first 8 hex of sha256 of claim then url,
UTF-8>.json`: `{"version": 1}` and the fields given, sorted keys, UTF-8, indent 2, a final
newline, at most 16 KiB, written through `fileplan.write`. A file there with other bytes, or a
symlink on the way, is refused before the first line. The outputs, in order:

1. `issue: https://github.com/rajasdevel/outcomebound-research/issues/new?template=finding.yml&…`,
   the fields percent-encoded in the order of the table, empty ones left out;
2. `wrote: <path>`, or `unchanged: <path>` where the same bytes are there;
3. a line that the issue link sends the finding now, and that the file, committed, waits for the
   research maintainer's collect pass.

## Edges

`adopt` opens no connection; the fragment names no machine path, so `--check` reads the same on
every machine. The engine writes the clone only through Git, and a project only at the inbox file.
Printed research is data: the fragment says it grants no authority and outranks no project
instruction. A harness gets research as command output, never reading outside the project.
`adopt --remove` leaves the inbox, the project's data. `SECURITY.md` states these promises.
Until the research repository is public, its links and `clone` fail.

## Validation

`tests/test_research.py` holds the header (refs, detached `HEAD`, worktree, date, `unknown`),
each refusal, the variable over the link, exit 3, no subprocess when printing or previewing, the
Git argument lists and environment with Git mocked, the link, and ingest's file, issue link and
refusals; it also holds the skills' and fragment's research commands to the code. An install
selecting `research` is byte-identical in two directories. A search of the tree for the moved paths
finds only the changelog's Removed entry. The skills and fragment get one `review` before landing.
