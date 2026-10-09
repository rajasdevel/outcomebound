---
name: instructions
status: ratified
---

# Instructions — design

## Outcome

Before a model reads a project's instruction files, a person can see what in them, or in the
harness settings beside them, could steer an agent unseen, and whether the loading facts behind
that reading are current. The invariant the command holds: each file or setting in scope that
could steer an agent unseen is reported on every run, as a FAIL, a review hit or `UNVERIFIED`,
and data in the target can decide only whether a review hit changes the result, as the rows below
say, never whether it is reported. It also reports, without changing its result, each path, Make target or
package script that project-owned instruction text names and the target no longer holds. The
command reads and reports; what a hit means is the person's call.
How: `outcomebound instructions check --help` and `outcomebound_tools/instruction_audit.py`.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| The engine audits an adopting project's instruction files | leaving them to the model that loads them | user | decided |
| `check` is lexical, and OutcomeBound's own suite runs it on this repository | waiting for a model-assisted audit | user | decided |
| The adopt skill's review of a target's instruction files runs `check` and reports for the person to judge; it never edits their files | adopt rewriting a target's instruction files | user | decided |
| Each check carries its rule id and severity from `docs/prompt-standard.md` in the module | reading the ids from a machine-readable catalog of the standard | agent | decided |
| Harnesses come from `--harness`, repeated or comma-separated as `adopt --harness` takes them; else the manifest's, plus each other row, in table order, loading a file the target holds that no row so far covers (`manifest+present`); else every row, where a row that loads no file of the target that another row does not load too (every row loads `AGENTS.md`) is reported and does not change the result. A `generic` install has no row, so `load-resolution` reads it `UNVERIFIED` and its `.outcomebound/skills/` copies are not read | the manifest alone, which the target's own edit could narrow; an unverified row the target does not use deciding every result | agent | decided |
| The agents' notes in `.agents/handoffs/` and `.agents/shared-memory/` are read too, though Git ignores them: the next session reads them as it reads instructions, and planted memory is a measured attack | leaving them unread because Git ignores them | user | decided |
| A person rules a review hit safe with `instructions rule <target> <id>`, which asks at a terminal, refuses without one, and records the ruling in the person's own file, `~/.outcomebound/rulings.json`, outside every target; the id pins the hit's check, path and fact, its file's bytes, and the repository: the clone's common Git directory as Git reports it, which its worktrees share, else the target, since a hook a person ruled safe names that repository's own code. The repository pin scopes a person's own rulings; what holds against the change under check is that the rulings file lies outside the target, and no commit can carry a `.git` path. A ruled hit is still reported on every run, with the day it was ruled, and does not change the result; any change to its file raises it again. Only a review hit that changes the result, on a regular file inside the target, takes a ruling: a gate finding, a hit that changes nothing already, and a change since `--base`, which names a diff and no content, never do; and where the home folder lies inside the target, no ruling is read. The terminal keeps a ruling from being scripted; it does not stop an agent that holds a terminal, so the contract keeps a ruling a person's act (maintainer, 2026-10-06) | a hit that recurs on every run until its file changes, which made exit 2 constant on healthy projects and taught agents to ignore it; a record kept in the target, which the change under check could write; exit 0 wherever nothing fails, which hides every review hit from a caller that reads the exit | user | decided |
| A base64-shaped run counts as concealed content only where a model could read it: a piece between pins or `=`, decoded at its best alignment, holds a stretch of 24 bytes of text, or its pieces' stretches of 8 bytes or more come to 24 together, or a piece starts a compressed stream; text is a printable character read as UTF-8, or printable ASCII read as UTF-16, and one character that is not text between two stretches of 8 bytes or more joins them. A stretch is judged by itself, so pins, `=` and random bytes an author adds around it cannot dilute it; a run of hex characters is judged by its length as before. Not claimed: text broken by a character every 7 bytes or fewer, UTF-32, and non-ASCII text as UTF-16, which a model reads only after decoding with care (maintainer, 2026-10-06) | every run of 60 base64 characters, which flagged agents' notes written with their spaces taken out, so that a note of ordinary words read UNVERIFIED on every run | user | decided |
| An entry adopt wrote into a harness's settings stays a review hit, and its fact quotes the Done commands the manifest records, since the finish check runs them: the manifest is the target's own data and a pull request can write it. The entry is recognised only where its canonical JSON is byte for byte what adopt writes for the row whose `finish_hook` names the file: `finish_check.entry` with the digest of the manifest's Done commands and the timeout the hook carries, where the row admits it, and a manifest `hook` record holds its digest. Another handler type, key, argument or Done digest makes it an ordinary hit. A review hit asks for a person at the handoff and stops no work (maintainer, 2026-10-04) | adopt's own entry reading PASS where the manifest records its digest: a planted manifest would then exempt the commands it adds | user | decided |
| That review hit does not change the result while the Done commands the manifest records are exactly the `Done` line of `AGENTS.md`'s project-facts block: the entry then runs only what the instructions an agent loads already name, and those are read by every check. Where they differ, or the manifest's are unreadable, it changes the result. A planted manifest cannot hide a hook that runs something else: such an entry is never recognised, and Done commands that `AGENTS.md` does not show change the result. What remains for a reviewer: the `Done` line of `AGENTS.md` in a diff, since what it names runs on the branch's own code at every stop, as CI would run it | the entry changing the result on every run, so that exit 2 is read as noise; a separate exit code, which every caller would have to learn | agent | decided |
| An instruction file a selected row says its harness loads from a folder above the target (`ancestors`; Claude Code: research `harnesses/claude-code.md` §1) is named, as a path from the target, and never opened: one review hit each, that does not change the result, since it lies outside the target, which is all this command reads | leaving it unreported, though the parent's contract and pointers load in the nested session; opening files outside the target | agent | decided |
| A hidden character in an agents' note reads UNVERIFIED for that note, with "do not rely on this note"; in a file a harness loads as instructions it stays a FAIL (maintainer, 2026-10-04) | one character in one session's note failing the whole repository | user | decided |
| A review hit's next step asks for a person at handoff and lets the work go on; a row past its re-check date names the day it was verified and that only the re-check is due, still UNVERIFIED (maintainer, 2026-10-04) | "confirm with a person" as a step before the work | user | decided |
| The security and loading checks: no agreement, structure or wording check: none answers a failure seen in a project's instruction files (S13), and OutcomeBound's own text is held by its suite | a catalog of 23 checks, agreement, structure and wording among them, with a worksheet a model answers and an audit skill | agent | decided |
| A third family, `references`, with one check, `stale-reference`: a path, a Make target or a package script that project-owned instruction text names and the target no longer holds. Measured studies of context files found stale code references in many repositories, and an agent follows a command or path a file names: this answers a failure seen in projects' files, which the agreement and wording checks above did not. It answers to rule S14 (agreement), second in the standard's severity order. It never changes the result (`decides: false`), so a healthy project's exit does not move, and it rules nothing safe; it is reported for the person and the agent, as the ancestors hit is. The report's schema gains `references` in its `family` and `check` values and its `counts`, a wire-format change this row decides. Its reads widen the command's outcome from what could steer an agent unseen to what in that text has gone stale too | the reference check in `adopt --check`, which reads only the install's own records; a hit that changes the result, which would make exit 2 constant on projects whose text names a path a build creates; a model that judges whether a reference still holds | agent | decided |
| A target that Git refuses as owned by another user (`dubious ownership`, as in a container whose root runs over a checkout another user made) is walked whole, as a target Git cannot list is, and the report's listing line says that Git refused it and names the command that trusts it (`git config --global --add safe.directory <the target>`). The engine's Git reads never pass `-c safe.directory`: `safe.directory` exists so that a repository another user owns cannot run its own code under yours, and the read-only configuration (`GIT_READ_CONFIGURATION`) closes `core.fsmonitor`, the pager and the external diff only, not every command Git runs for a repository, such as a clean or smudge filter a `.gitattributes` file names. Trusting a target for Git is the person's act, in their own Git configuration, as the floor design decides for the floor | passing `-c safe.directory=<the target>` on each read, which would let a hostile target run a filter under the auditor's own user; reading UNVERIFIED with no reason, which hides what to fix | agent | decided |

## Checks

A gate reads PASS or FAIL, UNVERIFIED where a fact it needs is not verified. A review reads PASS
where nothing matched, else UNVERIFIED with the line quoted and the hit's ruling id. The security checks answer to rule
S4 and report first; `stale-reference` answers to S14 and reports next, `load-resolution` to S7 after it.

| Check | Observes | Kind |
| --- | --- | --- |
| `hidden-characters` | tag characters, zero-width and bidirectional controls, variation selectors (one after a symbol excepted), private-use and unassigned characters, a combining mark after ASCII, any non-ASCII in a URL or code span (a span wraps within its paragraph; fenced code is none); a file left unopened reads UNVERIFIED; in an agents' note that no harness loads as an instruction file, a hit reads UNVERIFIED for that note | gate |
| `concealed-content` | HTML comments but OutcomeBound's block markers; base64-shaped runs of 60 or more characters with no space, judged after each stretch of hex characters 40 to 44 or 64 to 68 long (a pin and at most 4 more hex characters, the largest seen in field hits) is taken out: a pin alone, after `name=`, or glued to a label or word is no payload; a hex stretch of 60 to 63 or 69 or more characters stays in and is flagged, as is a payload of 60 or more with a pin attached; pieces cut by pins or by any base64 character that is not hex read as pieces between spaces; a run that is not all hex counts only where a piece holds a stretch of 24 bytes of text (one stray character between stretches of 8 bytes or more joins them), as UTF-8 or as UTF-16 ASCII, its pieces' stretches of 8 bytes or more come to 24 together, or a piece starts a compressed stream; fetch-and-run lines | review |
| `override-phrases` | phrases that override earlier instructions, ask for secrecy, grant autonomy or plant memory | review |
| `harness-config` | in each configuration file a row names, keys holding commands, tool servers, all tool servers at once, endpoints or permission bypasses; TOML is read lexically, an unsettled value reading UNVERIFIED; an entry adopt wrote is one hit that quotes the Done commands it runs | review; a secret-shaped value is a gate |
| `instruction-change` | with `--base <ref>`, each file in scope, and `.outcomebound/manifest.json`, changed between the ref and HEAD; a ref that does not resolve reads UNVERIFIED | review |
| `load-resolution` | per harness, whether its row is verified and inside its re-check date (past it, the fact names the day the row was verified and that only the re-check is due); where its configuration was read, one line naming the key categories the row leaves unsettled; and each file the row's `ancestors` loads from a folder above the target, a review that does not change the result | gate |
| `stale-reference` | in project-owned instruction text, each inline code span that is a concrete relative path, `make <target>`, or `npm run`, `pnpm run` or `yarn run` and a script name. Project-owned text is each Markdown file in scope (`.md`, `.mdc`) leaving out OutcomeBound's managed blocks, the skill and fragment copies the manifest records, and the agents' notes, plus the project's own `.outcomebound/fragments/local.md`; the manifest is the target's data, which a non-deciding finding may trust. A concrete relative path holds no whitespace or control character; does not start with `@`, `-`, `~`, `/`, a scheme (`x://`) or a drive letter; holds no `<`, `>`, `$`, `*`, `{` or `\`; ends in a file extension or in `/`, read without a trailing location (`:12`, `::name`, `#anchor`), so that a label such as `read/write` is none; is not in a sentence that names its owner as another project, by a capitalized possessive right before it (`Acme's`) or by a named repository (`the Acme repository at`), a determiner such as `this` naming this repository instead; and its first segment exists at the file's folder or at the root, so a Git ref, a package scope, a repository slug or a path in another repository is no reference, and neither is a path in `.git`, which the command never enters; a removed top-level folder is therefore missed. It is flagged where neither the file's folder nor the root holds it, Git does not ignore it (asked only where Git lists the target; where it cannot say, the path reads `UNVERIFIED`), and it resolves inside the target (one that resolves outside is skipped). A Make target is looked for in the nearest `GNUmakefile`, `makefile` or `Makefile` upward from the file's folder, then at the root, after flags and `VAR=` words are left out: a rule line or a `.PHONY` entry defines it; a `-C` or `-f` form, an `include`, a pattern rule or a rule named by a variable reads a target it does not show `UNVERIFIED`. A script is looked for in the nearest `package.json` upward, then the root; a target or script with no makefile or `package.json` at or above the file is flagged, and one whose file is not a regular file in the target, or no JSON object, reads `UNVERIFIED`; under `yarn run`, a name `package.json` does not define reads `UNVERIFIED`, since `yarn run` also runs a dependency's binary | review that does not change the result |

The files read are those each selected row says its harness loads: root and nested instruction
files, imports, project override files, rules and skill directories, and configuration. In a Git
work tree they come from what Git tracks or does not ignore, plus each path a row names exactly,
plus every file in `.agents/handoffs/` and `.agents/shared-memory/`; a target Git cannot list,
or ignores, is walked whole, and the report says which. Nested repositories and `.git` are not
entered, and no link is followed. A folder that cannot be listed is not entered and stops
nothing: in a walk of the whole target it is passed over, as Git's own listing passes it over;
in a note folder it is listed itself, so it reads UNVERIFIED unopened, as a linked folder does.

## Edges

It never opens a file the harness table records as one person's, by name or through a link, nor
anything outside the target but the engine's own data (above the target it only sees whether an
`ancestors` file exists) and the person's own rulings file, `~/.outcomebound/rulings.json`, which a
malformed or missing file leaves empty; a path it leaves unopened, a link out
included, reads UNVERIFIED. It never walks what Git ignores but those two note folders, never
runs, follows or obeys what it reads, and escapes quoted text so no file can steer the terminal.
Beyond the files in scope it reads, for `stale-reference` only, the project's `.outcomebound/fragments/local.md` and the makefiles and `package.json` files it looks targets and scripts up in, as text; it runs none of them. Its one process is Git, to list the files, to ask which candidate paths it ignores, and for `--base`: from PATH's absolute entries, with
no pager, fsmonitor, external diff or textconv, and no time limit. It opens no connection, rules no
hit benign itself, applies no edit and gives no score; `check` writes nothing, and `rule` writes
only the person's rulings file.

A clean pass does not rule out an injection: the lexical checks claim only the classes they
list, and `load-resolution` trusts the table, never watching a harness load. The steps it
prints are the person's to run, sandboxed.

What each verdict reads, and who writes it (`outcomebound_tools/instruction_audit.py`). The
instruction files, settings and skills in scope are the target's, which the change under check
can write; every check reads them, and nothing in them removes a hit. Which harness rows apply
comes from `--harness`, which the caller names, else from the manifest, which the change can
write: each row that loads a file the target holds and no row so far covers is added to it
(`manifest+present`), so an edit to the manifest cannot take a file a harness loads out of the
read. The manifest's Done commands decide only whether adopt's own entry's review hit changes
the result, and only while they equal the `Done` line of `AGENTS.md`, which every check reads.
A person's rulings decide only whether the review hits they name change the result: the person
writes them, outside the target, and a change to a hit's file makes its ruling match nothing.
The harness table and the rule ids are the engine's (`adapters/harnesses.json`,
`docs/prompt-standard.md`). The agents' notes are written by agents in a session, not by a commit.

## Exits

0 PASS; 1 FAIL, on any gate FAIL; 2 UNVERIFIED, on any review hit or unverified fact, or a usage
error. A finding that does not change the result (`decides: false` in the report, "(does not
change the result)" in the text) is reported and leaves the exit as it is; a review hit a person
ruled safe is one. `rule` exits 0 when each hit it asked about was recorded or declined, and 2
without a terminal, on an id that names no current review hit, or on a rulings file it cannot
read. `--strict` counts
UNVERIFIED as FAIL; `--json` prints one report (`schemas/instruction-audit-report.schema.json`);
`--verbose` adds the checks that passed.

## Validation

`tests/test_instruction_references.py`: the `stale-reference` check's grammar, its lookups of paths,
Make targets and package scripts, whose files it reads as text, and the limits it keeps.
`tests/test_instruction_audit.py`: each other check's planted defect and clean control, the limits,
the exits and `--base`; a ruled hit, a changed file, a planted or malformed rulings file and
`rule` without a terminal; a ruling in another repository, in a worktree of the same clone, and
for a change since `--base`; words run together against encoded text, diluted by pins, `=` or random bytes, in another script and as UTF-16; this repository's instruction files, and every shipped file under
`skills/`, `fragments/` and `templates/`, pass the gates.
