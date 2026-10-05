---
name: finish-check
status: ratified
---

# Finish check — design

For `claude-code` and `codex`; the evidence is in
[research/harnesses](https://github.com/rajasdevel/outcomebound-research/tree/main/harnesses).

## Outcome

In `claude-code` or `codex`, when a turn ends on a working tree the project's Done commands have
not been checked on, those commands run, and a failure goes back to the agent as something to
fix, so the run continues instead of ending on an unchecked "done". The invariant the hook
holds: a turn that ends on a changed tree reads as checked only where the Done commands passed
on that tree; a failure holds the turn, unless adopt measured it as a known failure on a commit
this checkout descends from and it fails the same way (the record of known failures is in no
committed file); and a Done that does not run or does not finish reads `UNVERIFIED`. The kernel's Done line
becomes a check the harness runs (S2, S5). The hook fires at every turn end, so a turn that
changed nothing reruns nothing, whatever the last verdict was. A command that already failed when
adopt measured Done, on a commit this checkout descends from, holds no turn while it fails the same
way; any other failure holds. The hook
checks the checkout at the working directory its input names, and no other. The project sets how
long Done may run (maintainer, 2026-10-04). Optional and removable, as every adopt write; every other harness is named as not
available yet. How: `outcomebound finish-check`, the verb the entry calls, and
`outcomebound_tools/adopt.py`, which writes the entry.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| The entry runs `outcomebound finish-check --harness <row> --done <digest> --timeout <seconds>`, the digest the sha256 of the manifest's `done` list as canonical JSON, the seconds the entry's own `timeout`. The verb runs the list only while the digest matches; otherwise nothing runs, `UNVERIFIED`, unheld, "re-run adopt". A Done change is thus a hook change: an install that changes Done or the timeout rewrites the entry, and only `codex` reviews a changed entry again: its documentation says trust is kept against the hook's current hash and a new or changed hook is skipped until trusted (research `harnesses/codex.md` §7.1), so an install that changes the `codex` entry says, as an `action` line, that each person trusts it again in `/hooks`. Which fields that hash covers is not documented (`UNVERIFIED`), as is whether a trust carries to a worktree's path; it covers the entry, not the program the entry runs | commands in the entry, or the list read unchecked | agent | decided |
| Opted into by `--finish-check` on `outcomebound adopt`; `--no-finish-check` takes it out; omitted keeps the record; `--detect` never proposes it | on by default | user | decided |
| Rows first: `claude-code` and `codex`. Every other row is not available yet, and the install report names it with its reason: `gemini`, a hook exists, but it is not built here yet; `cursor`, a follow-up message, not a hold, and CLI support undocumented; `amp` and `pi`, plugin or extension only; `generic`, no hook | `claude-code` and `gemini` first, `codex` and `cursor` after an observed run each | user | decided |
| An open report (<https://github.com/openai/codex/issues/17532>) says `codex`'s project hooks may not fire. On every row the install report reads `UNVERIFIED` that the harness runs the hook until a person sees its `systemMessage` end a run; on `codex`, after trusting the entry in `/hooks` | `codex` held back until that report closes | user | decided |
| The entry's shape is a `finish_hook` field per harness-table row, null where none is available, a schema change. One record, `{kind: hook, path, id: finish-check, harness, timeout, created, sha256}`, the entry's canonical JSON digested, `timeout` the entry's seconds (600 where absent, as 1.0.0 wrote it), `created` true where adopt made the file, admitted by adopt's `_own`; `--check` reads `current`, `edited`, `stale` (the entry's Done digest is not the manifest's, or the engine now writes it otherwise) or `missing` | the whole file digested | agent | decided |
| adopt parses the row's settings document, adds its entry under the row's event, and writes it back with key order and indentation kept, through `fileplan.write`; a document it cannot parse, comments included, or whose rewrite would change more than whitespace (an escape, a number's form, a repeated key), is refused before any write. `--remove` takes out the entry, what it emptied, and an otherwise empty file adopt created | managed-block markers, which JSON cannot carry | agent | decided |
| Guard: the row's `stop_hook_active`. Once set, the check runs and its report goes to the person as `systemMessage`, never to the model: one retry per finish, stateless. Stdin unreadable or without the field counts as set. Nothing runs on `claude-code` while `background_tasks` or `session_crons` is non-empty: a paused session (research `harnesses/claude-code.md` §7.1) | a counter file keyed by session id | agent | decided |
| The verb runs nothing, unheld, when the working tree (tracked diff plus untracked files) is the one Done was last checked on for this target: `{}` after a `PASS`; after a `FAIL` or `UNVERIFIED` under the same timeout, that report again as `systemMessage`, "not run again". The record (tree digest, timeout, verdict, a non-pass's results) is kept in the Git directory, never committed, and written only where the commands left the tree as they found it; a Done the agent itself ran on a changed tree runs once more | remembering only a pass, which reran a failing tree at every turn end and re-held an old failure each user turn | agent | decided |
| Time limit: data (maintainer, 2026-10-04). `adopt --finish-timeout SECONDS`, whole seconds above 30, default 600 (both rows' documented default, not a ceiling: research `harnesses/claude-code.md:267`, `harnesses/codex.md:143`), goes in the entry's `timeout` and the verb's `--timeout`, and is recorded; omitted keeps the recorded value; refused without a finish check. The verb kills each command's process group 30 seconds before the timeout, Git reads included, and reports it itself: `UNVERIFIED`, unheld, offering a larger `--finish-timeout` first, then `--no-finish-check`; no command starts past the limit; reading the tree again and remembering take at most fifteen of the 30 seconds, else the verdict is reported, not remembered | a fixed 570-second kill, with a report to shorten or drop Done | user | decided |
| Known failures. A Done command that fails when adopt measures Done is kept as a known failure with its exit code and the failure ids its output names, under the commit adopt measured on (`HEAD`), the Done digest and the target's place in the work tree, in the Git common directory: never committed, one file of records that every worktree of the repository reads. A record applies only in a checkout whose `HEAD` descends from its commit (`git merge-base --is-ancestor`, read-only, under the hook's deadline), the newest such record first; elsewhere a failure it names may be the change's own, so every failure holds. A new record replaces the target's records for the same commit, for a commit its own descends from, and for another Done list, and keeps the rest, so measuring one target or one branch displaces no other. At a turn end, a known command's FAIL is `known, not held` where its exit code is the recorded one and, where either side names failure ids, every id its output names now is among the recorded ones; where neither names any, the exit code alone decides, and the report says so (`known by its exit code only`). A new id, or ids on one side only, holds, the new ids named. Failure ids come from a table of one pattern per runner's summary line, matched against the output tail the hook keeps: pytest `FAILED`/`ERROR` up to its ` - ` before the message, so a parametrize id with a space stays whole, unittest `FAIL:`/`ERROR:` with the rest of the line, go `--- FAIL:`, cargo `test ... FAILED`, jest and vitest `✕`/`×` without the timing, make `*** [target] Error`. A record whose failure is a bare exit code reads as naming no ids. The next command runs after a known failure; only a failure that is not known holds. A known command that passes leaves the record, so a later failure of it holds. A run with known failures only goes to the person as `systemMessage`, `finish-check FAIL, known`, naming the commit each was measured on. No record that applies holds on every failure, as before | the exit code alone, which the common one-runner Done (`make test`, `pytest`, `npm test`) makes the whole suite (review of pull request #31); one record for every branch, which silences on a branch a failure measured on another; compare the failing command's output lines with the recorded ones, which timings, run order and temporary names change at each run, so it holds anyway, or which a normalisation makes hide a new case; a known list in the committed manifest, which goes stale for every clone and which a pull request can write | agent | decided |
| adopt measures Done once: after its writes, only where `--finish-check` is named, so that no install runs the project's Done unasked (review of pull request #31, 2026-10-04); never on `--dry-run`, `--check` or `--remove`. It runs every command to its end, past each failure and with no time limit, from the target's root; it prints each command's verdict and seconds, the total against the timeout less 30, and where the total is longer, `UNVERIFIED` with a `--finish-timeout` above the measured seconds plus 30. It keeps the failures as known, and the tree it left as checked, so a turn end on that tree runs nothing. Where the new record replaces the one that applied in this checkout, it prints, as a `known` line, each failure the replaced record did not hold: a command, a new exit code, or a new failure id, with that record's day and commit. Ctrl-C or SIGTERM stops the running command's process group, keeps nothing, prints `UNVERIFIED`, and exits 128 plus the signal's number. An install that does not name the flag names the record that applies here, with the day, the commit, the seconds and the known failures, and repeats the timeout warning from the measured seconds; where none applies, it says Done was not measured and that every failure holds | a Done run at every install that finds no record, which runs a slow suite unasked in a fresh clone or after a Done change; a time limit on the measurement, which cannot tell how much longer Done needs | agent | decided |
| A hold asks the agent to fix what its change broke and continue; where the failure predates its change, a tool is missing here, or the fix needs an act outside its authority, to say so in its report and continue with the work it does not block; to end its turn only when its work is done (maintainer, 2026-10-04). The guard makes it one hold | "fix what failed", which sends the agent to repair a failure the tests-worth-keeping skill says to leave; "finish" on such a failure, which ends a run with work open | agent | decided |
| Exit 126 or 127, or a command that cannot start, reads `UNVERIFIED`, unheld, "could not run in the hook's environment": the hook has the harness's PATH and no activated virtual environment (research `harnesses/claude-code.md` §7.1). So does a failing command whose last line of output, make's own error lines aside, is a runner saying a tool is not on this PATH: make's `<tool>: No such file or directory`, a script's `<tool>: command not found` or `not found` after a line number, a shell's `<tool>: command not found`, or a Python launcher's `No module named <module>`; the report names the tool. A test's own message (`FileNotFoundError: ... No such file or directory: '<path>'`, `ModuleNotFoundError: No module named '<module>'`) has no such form and still fails. A missing tool that is the project's own still fails, since its absence is the work's: a path inside the target, relative or absolute (a script the change removed or renamed); a bare name that an executable file in HEAD carries (a recipe that puts the project's own `bin` on PATH); or a `python -m` module whose top package or module, a namespace package's folder included, is in the target's tree or its HEAD commit. A command that fails at measurement, and passes once more with the full PATH, may also be an order-dependent or flaky command; it reads `UNVERIFIED`, never a pass. The tool must also be absent where the command ran, not only said to be: a name `shutil.which` does not find on that PATH, or a module the named Python launcher cannot find; a command that prints such a line for a tool that is there still fails. Another failure in the same output keeps the failure: failure ids a runner's summary names (make's own error lines aside), a count of failed tests or errors, or two failed targets of one make. Forms not listed (another shell's wording, a localized message, `Permission denied`) still fail, which holds where it need not and lets nothing through; a typo the agent makes in a Done script's tool name reads `UNVERIFIED`, as the shell's 127 already did (maintainer, 2026-10-05) | `FAIL`, held on a failure the change did not cause; for the runner's lines, every non-zero exit held, which held each turn end of a project whose `make test` named a tool only an activated environment holds | agent | decided |
| adopt measures Done without a PATH entry inside the target, without a virtual environment's `bin` (a folder whose parent holds `pyvenv.cfg`) and without `VIRTUAL_ENV`, and names the entries it left out, as a hook of a desktop harness runs Done; a command that fails without them runs once more with them, and where it then passes, or fails with another exit code or other failure ids, or does not run, it reads `UNVERIFIED`, kept as no known failure; an empty or relative PATH entry names a folder of the target, since Done runs from its root. A record such a measurement keeps carries `as_hook`; an install that keeps a record without it says so, and that `--finish-check` measures again, keeping each failure it finds as known, so a same-named tool elsewhere on PATH cannot turn the measurement into a known failure that hides later ones. A conda environment's `bin` holds no `pyvenv.cfg` and is not told apart (maintainer, 2026-10-05) | measuring with the agent's PATH, which recorded PASS for a Done that then could not run at any turn end | agent | decided |
| On failure the model receives an agent-readable report (S6): the verdict; one line per command in run order, `PASS`, `FAIL` with exit code and seconds (and `known, not held` for a known failure), or `UNVERIFIED` with why, stopping at the first failure that is not known; then that command's last lines, fenced as data labeled `output`, control characters stripped, a run of more than fifteen backticks written as its count, the whole under 4,000 characters, since on `codex` the reason becomes a new prompt | the whole output | agent | decided |
| A pass returns `{"systemMessage": "finish-check PASS: <commands>, <s>s; not reviewed, not landed"}`; nothing reaches the model. On `codex` the documentation says a `block` reason becomes a new user prompt, and past about 2,500 tokens the model gets a head-and-tail preview while the full text is written to disk (the report stays under 4,000 characters, well below that), and a `systemMessage` is "surfaced as a warning in the UI or event stream" (research `harnesses/codex.md` §7.1): a hold reaches the model, and a pass, a known failure or an `UNVERIFIED` reaches the person only. That a Codex release runs the hook at all is `UNVERIFIED` (openai/codex#17532), and no run has been observed. A silent path prints `{}`, since `codex` reads JSON on stdout. The verb exits 0 whenever it ran; a usage error exits 1, never 2, which both rows read as holding the finish | plain text | agent | decided |
| No Done recorded: `--finish-check` is refused, "record one with `--done`"; an install that empties Done removes the entry in the same run | an entry that runs nothing | agent | decided |
| The instruction audit reports the entry as a review hit wherever it is installed, its fact the Done commands it runs; nothing exempts it, since an exemption would come from the manifest, which a pull request can also write. A review hit stops no work: the workspace fragment carries it to the handoff (maintainer, 2026-10-04) | the audit trusting the manifest | agent | decided |
| The target is the nearest directory holding the manifest upward from the input's `cwd`, else from the process's working directory, for both rows; found nowhere, the report names the directory searched, unheld. The hook checks that checkout only: on `claude-code` the input's `cwd` follows the agent into a worktree it enters; on `codex` hooks run in the session's working directory (research `harnesses/claude-code.md` §7.1, `harnesses/codex.md` §7.1). Where the agent works in a worktree while that directory stays in the main checkout, a PASS says nothing about the worktree, so the agent runs the Done commands in the worktree itself before it lands the work | a root variable, which stays at the session's start when the agent enters a worktree; the hook searching for worktrees, which cannot tell the one under work | agent | decided |
| The launcher is named, `outcomebound`, never pathed: the entry runs the engine that name installs ([distribution](../distribution/design.md)) | the checkout's absolute path | agent | decided |
| The install report names each row's one-time accept: `codex`, trust in `/hooks`; `claude-code`, workspace trust interactively and nothing under `-p`; and `outcomebound` on the harness process's PATH | silence | agent | decided |

## Rows

The table's `finish_hook` carries each row's event, file, guard and accept, with sources; evidence in
the research record.

| Row | Event | Reason to the model | Guard | Limit field | File |
| --- | --- | --- | --- | --- | --- |
| `claude-code` | `Stop` | `decision: "block"` + `reason` holds the finish | `stop_hook_active`; the harness caps at 8 | `timeout`, seconds, default 600 | `.claude/settings.json` |
| `codex` | `Stop` | `decision: "block"` + `reason` becomes a new prompt | `stop_hook_active` | `timeout`, seconds, default 600 | `.codex/hooks.json`, added to the row's `config.paths` |

## Edges

adopt rewrites bytes it did not write in one place: a settings document's whitespace, when it
adds or removes its entry. The entry is one more committed hook a pull request's review must
read: `claude-code` trusts a folder once and never reviews a changed entry. The entry runs with
the person's privileges and without the permission prompt the agent's own command would meet; it
is committed, so every teammate's harness runs it after its own accept. A harness launched from
a desktop without `outcomebound` on its PATH shows a named hook error and holds nothing; one
that never fires the hook fails silently, as the install report says. Where a command's output names no
failure ids a known failure covers the whole command: while it fails with its recorded exit code,
a new failure inside it holds nothing, and the person sees it only in the `systemMessage`, which
says `known by its exit code only`. A Done split into narrower commands narrows that, and
`adopt --finish-check` measures Done again. adopt measures in the person's shell, while the hook
runs with the harness's PATH; a command that fails at install for a reason of that shell alone is
kept as known, and a failure with the same exit code and no ids is then silent in the hook. The
record of known failures keeps a pull request out, not the session's agent: an agent that can
write the Git directory can write the record, as it can edit the manifest's Done or the hook
entry, and the record is in no diff a reviewer reads. The agent can also reach the same end through
a sanctioned command: run `adopt --finish-check` after its change broke code, and its failures
become known in a record that replaces the honest one. What guards both is visibility: a known
failure goes to the person with its output and its commit, on both rows, and a measurement that
replaces a record names each failure new since it. A known failure that a later commit fixed, with
no turn end since on a tree where the command passed, stays in the record: if the agent breaks it
again with the same exit code and failure ids, it is not held. A pull does not measure again;
`adopt --finish-check` after it does. A mixed selection installs
the entry where a row has one and names the rest; with no selected row that has one,
`--finish-check` is refused.

What each verdict reads, and who writes it (`outcomebound_tools/finish_check.py`). The hook's
input on stdin (`cwd`, `stop_hook_active`, `background_tasks`, `session_crons`) is the harness's.
The Done commands come from the manifest, which the change under check can write; they run only
while their digest equals the one in the committed hook entry, so a changed Done list runs
nothing and reads `UNVERIFIED`, unheld, to the person. That is flagged, not held: a hold cannot
tell a planted list from a new one, and the instruction audit keeps the entry a review hit that
quotes the Done commands. The timeout is the entry's own, also committed. The known-failure
record is in the Git common directory and the checked-tree record in the Git directory, neither
committed: adopt writes the first and the verb edits it, since a known command that passes leaves
it; the verb writes the second. A pull request can write neither, and an agent in the session
can, as the paragraph above says.

## Validation

`tests/test_finish_check.py` runs the verb on scratch targets in each row's input form, one
test a decision above, known failures (failure ids, another branch, two targets) and `measure`
included; `tests/test_adopt.py` covers the entry's install, check and removal, the one Done run
at install with its timeout warning and its stop by SIGINT, and the `codex` trust line on a
changed entry.
`claude-code` has been observed in a live session: a turn end ran the Done commands and the PASS
message reached the transcript, in a session started before the entry too. `codex`, and
`cursor`, which runs the `claude-code` entry too, stay `UNVERIFIED`, as does each install's harness, whose PATH may lack `outcomebound` or its tools.
