---
name: research
status: draft
---

# Research — design

Landing this draft takes the change it describes, with the gate green; it then reads `ratified`.

## Outcome

Research on models, harnesses, providers and agent practice lives in its own repository,
`outcomebound-research` (<https://github.com/rajasdevel/outcomebound-research>). An agent in any
project reaches it on demand: `outcomebound research` prints a file from one clone per machine,
headed by its commit, or names the public link where no clone exists. Any project can send a
finding back, with or without a clone. How: `outcomebound_tools/research.py`,
`fragments/setup/research.md`.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| Research is its own repository; OutcomeBound optionally points agents at one clone of it and never vendors it (D52) | a submodule or a copy inside each project, whose `AGENTS.md` a harness loads into that project's sessions, and which every worktree carries | user | decided |
| A fact about a model, harness, provider or general practice moves; what OutcomeBound measured of its own text stays. All of `docs/research/` moves but `practices/evaluations.md`, now `docs/evaluations.md`; `docs/prompt-standard.md` and `adapters/harnesses.json` stay | splitting the files that mix both now | user | decided |
| A citation of a moved file becomes `https://github.com/rajasdevel/outcomebound-research/blob/main/<path>` (a folder: `tree/main/<path>`); an evidence id stays, and a line says it resolves in that repository's `_evidence/*.jsonl` | relative links that break | user | decided |
| `docs/model-guidance.md` moves there as `models/guidance.md`, its tier table as `models/tiers.md`, and the wheel stops shipping it (D69) | a dated copy in every release | user | decided |
| The core skill reads model, effort, harness and prompting advice with `outcomebound research models/guidance.md`; where that reports no clone, or `outcomebound` is not on PATH, it reads the public link | no route without a clone | user | decided |
| `hand-off-tickets` finds the implementer's tier in `outcomebound research models/tiers.md`; with no clone it asks the person which tier, outcome, design or spec | a default tier | user | decided |
| One clone per machine: `OUTCOMEBOUND_RESEARCH` when set and not empty, else `~/.outcomebound/research`, a symlink `clone` points at the destination the person names (D59) | a clone per project | user | decided |
| A folder is a clone when it holds `INDEX.md` | requiring `.git`, which an exported copy lacks | agent | assumed |
| The verb prints and never executes: nothing the clone holds runs, and Git does not run to print; the commit is read from the clone's `.git` files | running Git, which reads the clone's configuration | user | decided |
| Clone and pull are explicit networked acts that preview, and act only with `--accept`, as `floor provision` does; `adopt` stays offline | an `adopt` option, breaking its promise to open no connection | user | decided |
| A project opts in with the `research` fragment (`detect: []`), which the adopt skill offers; this repository selects it | detection | agent | assumed |
| Ingest writes one file in the contributing project and prints the prefilled issue link first; it needs no clone (D60) | writing into the clone; opening the issue itself, an external write | user | decided |
| People learn how to contribute from a README section and `CONTRIBUTING.md`: the issue form first, `outcomebound research ingest` offline, pull requests to the research repository under its own `CONTRIBUTING.md` | instructions only in the research repository | user | decided |
| Exit 0 done or previewed; 1 refused, or Git failed; 2 usage; 3 no clone configured | one failure code, which a fallback cannot tell from a bad path | agent | assumed |
| The header's date is the day, in UTC, that `HEAD` last moved in the clone, from `.git/logs/HEAD`; `unknown` without it | the commit date, behind pack parsing in a fresh clone | agent | assumed |
| `clone`, `pull` and `ingest` as the first argument are subcommands, so a root file of those names cannot be printed | a `show` subcommand, longer for the common case | agent | assumed |

## The verb

**Print.** `outcomebound research [PATH]`, `PATH` defaulting to `INDEX.md`. The path is read
through the engine's path grammar, `paths.read_bounded`: relative, no `..` or `.git`, no symlink on
the way, a regular file. Standard output starts `research: <PATH> @ <commit, 12 hex> (<YYYY-MM-DD>)`,
then the file. The commit: `.git` is a folder, or a file whose `gitdir:` names one; `HEAD`'s ref
is read from the loose ref (in the `commondir` for a worktree), then `packed-refs`; a detached
`HEAD` is read as it is; otherwise `unknown`. Refusals go to standard error as
`research: <PATH>: <why>`, exit 1, with nothing on standard output: not a bounded path; a symlink
on the way; a folder; not in the clone, adding that `INDEX.md` lists every document and `MOVED.md`
every path that moved.

**Not configured** (exit 3, standard error):

```text
research: no clone configured: OUTCOMEBOUND_RESEARCH is unset and ~/.outcomebound/research does not exist
read it at https://github.com/rajasdevel/outcomebound-research/blob/main/<PATH>
clone it once per machine, with the person's yes: outcomebound research clone <destination>
```

Where `OUTCOMEBOUND_RESEARCH` names a folder without `INDEX.md`, or the link dangles, the first line
says that instead.

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
`GIT_TERMINAL_PROMPT=0`, then replaces the link atomically and prints `linked: …`. No Git on PATH,
or a Git failure, prints the cause and the last of Git's output, exit 1, and the link is left as it
was.

**Pull.** `outcomebound research pull [--accept]`: exit 3 where no clone is configured, exit 1
where the clone has no `.git`. The preview is `would run: git -C <clone> pull --ff-only` and
`nothing pulled: pass --accept`; with `--accept` it runs that, then prints
`research: now at <commit> (<date>)`.

**Ingest.** `outcomebound research ingest --kind fact|correction --subject TEXT --claim TEXT --url
URL [--quote TEXT] [--observed-on YYYY-MM-DD] [--corrects REF] [--project DIR]`. The field ids are
those of the research repository's issue form. Each value is stripped; none holds a line break or a
control character. Each failure is named on standard error, exit 1, and nothing is printed or
written:

| Field | Accepted |
| --- | --- |
| `kind` | `fact` or `correction` |
| `subject` | 1 to 120 characters |
| `claim` | 1 to 600 characters |
| `url` | `http` or `https`, with a host, no space |
| `quote` | optional; at most 25 words |
| `observed_on` | a real date, not after today; default today |
| `corrects` | required for a correction, optional for a fact |

The project is `DIR`, else the Git work tree holding the current folder; outside one, it is
refused. The file is `.outcomebound/research-inbox/<observed_on as YYYYMMDD>-<first 8 hex of
sha256 of claim then url, UTF-8>.json`: `{"version": 1}` and the fields given, sorted keys, UTF-8,
indent 2, a final newline, at most 16 KiB, written through `fileplan.write`. A file there with
other bytes, or a symlink on the way, is refused before the first line. The outputs, in order:

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
`adopt --remove` leaves the inbox, the project's data. `SECURITY.md` states these promises. Until the research repository is public, its
links do not resolve and `clone` fails at Git.

## Validation

`tests/test_research.py` holds the header (loose ref, packed ref, detached `HEAD`, worktree,
date, `unknown`), each refusal, the variable over the link, exit 3, no subprocess when printing or
previewing, the exact Git argument lists with Git mocked, the link's creation and repointing, and
ingest's file, issue link and refusals. An install selecting `research` is byte-identical in two
directories. `git grep -n "docs/research\|model-guidance"` finds nothing outside released changelog
sections. The skills and fragment changed get one `review` before landing.
