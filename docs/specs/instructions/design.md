---
name: instructions
status: ratified
---

# Instructions — design

## Outcome

Before a model reads a project's instruction files, a person can see what in them, or in the
harness settings beside them, could steer an agent unseen, and whether the loading facts behind
that reading are current. The command reads and reports; what a hit means is the person's call.
How: `outcomebound instructions check --help` and `outcomebound_tools/instruction_audit.py`.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| The engine audits an adopting project's instruction files | leaving them to the model that loads them | user | decided |
| `check` is lexical, and OutcomeBound's own suite runs it on this repository | waiting for a model-assisted audit | user | decided |
| The adopt skill's review of a target's instruction files runs `check` and reports for the person to judge; it never edits their files | adopt rewriting a target's instruction files | user | decided |
| Each check carries its rule id and severity from `docs/prompt-standard.md` in the module | reading the ids from a machine-readable catalog of the standard | agent | decided |
| Harnesses come from `--harness`; else the manifest's, plus each other row, in table order, loading a file the target holds that no row so far covers (`manifest+present`); else every row. A `generic` install has no row, so `load-resolution` reads it `UNVERIFIED` and its `.outcomebound/skills/` copies are not read | the manifest alone, which the target's own edit could narrow | agent | decided |
| The agents' notes in `.agents/handoffs/` and `.agents/shared-memory/` are read too, though Git ignores them: the next session reads them as it reads instructions, and planted memory is a measured attack | leaving them unread because Git ignores them | user | decided |
| A review hit recurs on every run until the file changes | a record of a person's judgment that silences the hit | agent | decided |
| An entry adopt wrote into a harness's settings stays a review hit, and its fact quotes the Done commands the manifest records, since the finish check runs them: the manifest is the target's own data and a pull request can write it. The entry is recognised by the digest a manifest `hook` record holds and a command that runs only `outcomebound finish-check` with plain arguments; any other entry is an ordinary hit. A review hit asks for a person at the handoff and stops no work (maintainer, 2026-10-04) | adopt's own entry reading PASS where the manifest records its digest: a planted manifest would then exempt the commands it adds | user | decided |
| A hidden character in an agents' note reads UNVERIFIED for that note, with "do not rely on this note"; in a file a harness loads as instructions it stays a FAIL (maintainer, 2026-10-04) | one character in one session's note failing the whole repository | user | decided |
| A review hit's next step asks for a person at handoff and lets the work go on; a row past its re-check date names the day it was verified and that only the re-check is due, still UNVERIFIED (maintainer, 2026-10-04) | "confirm with a person" as a step before the work | user | decided |
| Six checks in two families, security and loading. No agreement, structure or wording check: none answers a failure seen in a project's instruction files (S13), and OutcomeBound's own text is held by its suite | a catalog of 23 checks, agreement, structure and wording among them, with a worksheet a model answers and an audit skill | agent | decided |

## Checks

A gate reads PASS or FAIL, UNVERIFIED where a fact it needs is not verified. A review reads PASS
where nothing matched, else UNVERIFIED with the line quoted. The security checks answer to rule
S4 and report first; `load-resolution` answers to S7.

| Check | Observes | Kind |
| --- | --- | --- |
| `hidden-characters` | tag characters, zero-width and bidirectional controls, variation selectors (one after a symbol excepted), private-use and unassigned characters, a combining mark after ASCII, any non-ASCII in a URL or code span (a span wraps within its paragraph; fenced code is none); a file left unopened reads UNVERIFIED; in an agents' note that no harness loads as an instruction file, a hit reads UNVERIFIED for that note | gate |
| `concealed-content` | HTML comments but OutcomeBound's block markers; base64-shaped runs, a 40- or 64-character hex pin excepted; fetch-and-run lines | review |
| `override-phrases` | phrases that override earlier instructions, ask for secrecy, grant autonomy or plant memory | review |
| `harness-config` | in each configuration file a row names, keys holding commands, tool servers, all tool servers at once, endpoints or permission bypasses; TOML is read lexically, an unsettled value reading UNVERIFIED; an entry adopt wrote is one hit that quotes the Done commands it runs | review; a secret-shaped value is a gate |
| `instruction-change` | with `--base <ref>`, each file in scope, and `.outcomebound/manifest.json`, changed between the ref and HEAD; a ref that does not resolve reads UNVERIFIED | review |
| `load-resolution` | per harness, whether its row is verified and inside its re-check date (past it, the fact names the day the row was verified and that only the re-check is due); where its configuration was read, one line naming the key categories the row leaves unsettled | gate |

The files read are those each selected row says its harness loads: root and nested instruction
files, imports, project override files, rules and skill directories, and configuration. In a Git
work tree they come from what Git tracks or does not ignore, plus each path a row names exactly,
plus every file in `.agents/handoffs/` and `.agents/shared-memory/`; a target Git cannot list,
or ignores, is walked whole, and the report says which. Nested repositories and `.git` are not
entered.

## Edges

It never opens a file the harness table records as one person's, by name or through a link, nor
anything outside the target but the engine's own data; a path it leaves unopened, a link out
included, reads UNVERIFIED. It never walks what Git ignores but those two note folders, never
runs, follows or obeys what it reads, and escapes quoted text so no file can steer the terminal.
Its one process is Git, to list the files and for `--base`: from PATH's absolute entries, with
no pager, fsmonitor, external diff or textconv, and no time limit. It opens no connection, writes nothing, rules no
hit benign, applies no edit and gives no score.

A clean pass does not rule out an injection: the lexical checks claim only the classes they
list, and `load-resolution` trusts the table, never watching a harness load. The steps it
prints are the person's to run, sandboxed.

## Exits

0 PASS; 1 FAIL, on any gate FAIL; 2 UNVERIFIED, on any review hit or unverified fact, or a usage
error. `--strict` counts UNVERIFIED as FAIL; `--json` prints one report
(`schemas/instruction-audit-report.schema.json`); `--verbose` adds the checks that passed.

## Validation

`tests/test_instruction_audit.py`: each check's planted defect and clean control, the limits,
the exits and `--base`; this repository's instruction files, and every shipped file under
`skills/`, `fragments/` and `templates/`, pass the gates.
