---
name: finish-check
status: ratified
---

# Finish check — design

For `claude-code` and `codex`; the evidence is in
[research/harnesses](https://github.com/rajasdevel/outcomebound-research/tree/main/harnesses).

## Outcome

In `claude-code` or `codex`, when a turn ends on a working tree the project's Done commands have
not passed on, those commands run, and a failure goes back to the agent as something to fix, so
the run continues instead of ending on an unchecked "done". The kernel's Done line becomes a
check the harness runs (S2, S5). The hook fires at every turn end, so a turn that changed nothing
reruns nothing. Optional and removable, as every adopt write; every other harness is named as not
available yet. How: `outcomebound finish-check`, the verb the entry calls, and
`outcomebound_tools/adopt.py`, which writes the entry.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| The entry runs `outcomebound finish-check --harness <row> --done <digest>`, the sha256 of the manifest's `done` list as canonical JSON. The verb runs the list only while the digest matches; otherwise nothing runs, `UNVERIFIED`, unheld, "re-run adopt". A Done change is thus a hook change: an install that changes Done rewrites the entry, and only `codex` reviews a changed entry again | commands in the entry, or the list read unchecked | agent | decided |
| Opted into by `--finish-check` on `outcomebound adopt`; `--no-finish-check` takes it out; omitted keeps the record; `--detect` never proposes it | on by default | user | decided |
| Rows first: `claude-code` and `codex`. Every other row is not available yet, and the install report names it with its reason: `gemini`, a hook exists, but it is not built here yet; `cursor`, a follow-up message, not a hold, and CLI support undocumented; `amp` and `pi`, plugin or extension only; `generic`, no hook | `claude-code` and `gemini` first, `codex` and `cursor` after an observed run each | user | decided |
| An open report (<https://github.com/openai/codex/issues/17532>) says `codex`'s project hooks may not fire. On every row the install report reads `UNVERIFIED` that the harness runs the hook until a person sees its `systemMessage` end a run; on `codex`, after trusting the entry in `/hooks` | `codex` held back until that report closes | user | decided |
| The entry's shape is a `finish_hook` field per harness-table row, null where none is available, a schema change. One record, `{kind: hook, path, id: finish-check, harness, created, sha256}`, the entry's canonical JSON digested, `created` true where adopt made the file, admitted by adopt's `_own`; `--check` reads `current`, `edited`, `stale` (the entry's Done digest is not the manifest's) or `missing` | the whole file digested | agent | decided |
| adopt parses the row's settings document, adds its entry under the row's event, and writes it back with key order and indentation kept, through `fileplan.write`; a document it cannot parse, comments included, or whose rewrite would change more than whitespace (an escape, a number's form, a repeated key), is refused before any write. `--remove` takes out the entry, what it emptied, and an otherwise empty file adopt created | managed-block markers, which JSON cannot carry | agent | decided |
| Guard: the row's `stop_hook_active`. Once set, the check runs and its report goes to the person as `systemMessage`, never to the model: one retry per finish, stateless. Stdin unreadable or without the field counts as set. Nothing runs on `claude-code` while `background_tasks` is non-empty | a counter file keyed by session id | agent | decided |
| The verb skips, unheld, when the working tree (tracked diff plus untracked files) is the one Done last passed on for this target, a digest kept in the Git directory, never committed, and remembered only where the commands left the tree as they found it; a Done the agent itself ran on a changed tree runs once more | running at every turn end | agent | decided |
| Time limit: adopt writes 600 seconds in the row's `timeout` field; the verb runs each command in its own process group and kills the group 570 seconds after the hook started, its Git reads included, so it, not the harness, reports: the command reads `UNVERIFIED`, the run ends unheld, and the report says the check is the person's to shorten or drop; no command starts once the limit has passed, and every Git read runs within it; reading the tree again and remembering a pass stop fifteen seconds before it, so a pass that late is reported and not remembered | a recorded limit and a flag | agent | decided |
| A hold asks the agent to fix what its change broke, and to finish saying so where the failure predates its change or it is stopping to ask the person; the guard makes either one hold | a hold that says only "fix what failed", which sends the agent to repair a failure the tests-worth-keeping skill says to leave as found, and to work past a stop the kernel names | agent | decided |
| On failure the model receives an agent-readable report (S6): the verdict; one line per command in run order, `PASS`, `FAIL` with exit code and seconds, or `UNVERIFIED` with why, stopping at the first failure; then that command's last lines, fenced as data labeled `output`, control characters stripped, a run of more than fifteen backticks written as its count, the whole under 4,000 characters, since on `codex` the reason becomes a new prompt | the whole output | agent | decided |
| A pass returns `{"systemMessage": "finish-check PASS: <commands>, <s>s; not reviewed, not landed"}`; nothing reaches the model. A silent path prints `{}`, since `codex` reads JSON on stdout. The verb exits 0 whenever it ran; a usage error exits 1, never 2, which both rows read as holding the finish | plain text | agent | decided |
| No Done recorded: `--finish-check` is refused, "record one with `--done`"; an install that empties Done removes the entry in the same run | an entry that runs nothing | agent | decided |
| The instruction audit's `harness-config` check reports the entry as a review hit wherever it is installed; nothing exempts it, since an exemption would come from the manifest, which a pull request can also write | the audit trusting the manifest | agent | decided |
| The target is the nearest directory holding the manifest upward from the input's `cwd`, else from the process's working directory, for both rows; found nowhere, the report names the directory searched, unheld | a root variable, which stays at the session's start when the agent enters a worktree | agent | decided |
| The launcher is named, `outcomebound`, never pathed: the entry runs the engine that name installs ([distribution](../distribution/design.md)) | the checkout's absolute path | agent | decided |
| The install report names each row's one-time accept: `codex`, trust in `/hooks`; `claude-code`, workspace trust interactively and nothing under `-p`; and `outcomebound` on the harness process's PATH | silence | agent | decided |

## Rows

The table's `finish_hook` carries each row's event, file, guard and accept, with sources; evidence in
the research record.

| Row | Event | Reason to the model | Guard | Limit field | File |
| --- | --- | --- | --- | --- | --- |
| `claude-code` | `Stop` | `decision: "block"` + `reason` holds the finish | `stop_hook_active`; the harness caps at 8 | `timeout`, seconds | `.claude/settings.json` |
| `codex` | `Stop` | `decision: "block"` + `reason` becomes a new prompt | `stop_hook_active` | `timeout`, seconds | `.codex/hooks.json`, added to the row's `config.paths` |

## Edges

adopt rewrites bytes it did not write in one place: a settings document's whitespace, when it
adds or removes its entry. The entry is one more committed hook a pull request's review must
read: `claude-code` trusts a folder once and never reviews a changed entry. The entry runs with
the person's privileges and without the permission prompt the agent's own command would meet; it
is committed, so every teammate's harness runs it after its own accept. A harness launched from
a desktop without `outcomebound` on its PATH shows a named hook error and holds nothing; one
that never fires the hook fails silently, as the install report says. A mixed selection installs
the entry where a row has one and names the rest; with no selected row that has one,
`--finish-check` is refused.

## Validation

`tests/test_finish_check.py` runs the verb on scratch targets in each row's input form, one
test a decision above; `tests/test_adopt.py` covers the entry's install, check and removal.
`claude-code` has been observed in a live session: a turn end ran the Done commands and the PASS
message reached the transcript, in a session started before the entry too. `codex`, and
`cursor`, which runs the `claude-code` entry too, stay `UNVERIFIED`, as does each install's harness, whose PATH may lack `outcomebound` or its tools.
