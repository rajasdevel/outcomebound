---
name: finish-check
status: retired
---

# Finish check — design (retired in 1.7.0)

Versions 1.5.0 and 1.6.0 could write a hook into the settings of `claude-code` and `codex`
(`outcomebound adopt --finish-check`). At the end of a turn, the hook ran the Done commands that the
project recorded, and it sent a failure back to the agent. 1.7.0 retires it. This design keeps the
reason, the way an install upgrades from the hook, and the verb that the old entries still call.

## Outcome

`outcomebound adopt` installs no hook in any harness and runs no Done command. A project that a
1.6.0 install made upgrades with `outcomebound adopt <target>`. That run takes out the entries and
the records that 1.6.0 wrote, and it keeps every other entry and key of the settings document.
Between `pip install -U outcomebound` and that run, the harness still calls
`outcomebound finish-check ...` from the old entry. The call does nothing, so no turn waits, fails
or holds, and no one sees an error.

The agent runs the Done commands, as the person does. The kernel names them in the project facts,
and the agent's report says which of them ran.

Why the hook went:

- A hook costs time and attention at every turn end, also when the work needs no check.
- The tests belong to the agent and to the person. They choose when a check is worth its time,
  and what to do about a failure.
- A hook that only reminds the agent of a check is noise.

A hook can come back where it does one thing: it enforces a practice that an agent would miss,
the same way every time, without lowering the quality of the model's work. A hook never runs the
tests of a project.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| 1.7.0 ships no hook, and `adopt` runs no Done command (maintainer, 2026-10-17) | keeping the hook behind a flag, where it costs a code path and a record nobody needs; a hook that reminds the agent to run the checks, which is noise | user | decided |
| A new hook needs a practice that an agent would miss, a check that gives the same answer every time, and no loss of quality in the model's work. It never runs the tests of a project | a hook for each practice that is good to have | user | decided |
| The verb stays as a stub until a later major release, and the harness table, the manifest and the instruction audit keep nothing for the hook (the rows below) | removing the verb at once, which makes every old entry fail between an upgrade of the package and the next `adopt`; keeping a `finish_hook` field in the table for the migration, which needs none: a `hook` record names its file, and the entry is found in that file | agent | decided |
| The validation contract and the process control that this design once held are now in the [floor design](../floor/design.md), where `outcomebound validation` and `programs.py` belong | deleting them with the hook | agent | decided |

## What an install does with an old install

| Case | Result |
| --- | --- |
| `adopt` on a project that holds `hook` records (ids `finish-check` and `finish-check-mark`) | It takes out the entry of each record: the group whose canonical digest is the record's, else the first group that runs `outcomebound finish-check` at the stop (at the turn start for the mark id). It takes out the event list and the `hooks` object that this empties, and the records. It prints one `note` line for each entry. Every other key and entry of the document stays, with its order, its indentation, its line endings and its byte-order mark. |
| The document was created by an earlier `adopt` (`created` in the record) and now holds nothing | It is deleted. A document that a project made, or that holds another key or entry, stays. |
| A person edited the entry (its digest is not the record's) | It stays, and the install stops with the usual line, `differs from what adopt wrote; restore it, or pass --force`. With `--force` the install takes it out. |
| The entry is already gone | The record is dropped. The document is not read, so a document with comments, which adopt cannot rewrite, does not stop the install. While such a document still holds an entry, the install stops and says to remove the entry by hand. |
| `adopt --check` before the upgrade | Each `hook` record reads `stale`, `edited` or `missing`, with the event and the command of the entry that the next install takes out. The exit counts it as for any record. |
| `--finish-check`, `--no-finish-check`, `--finish-timeout`, `--verify` and `--done-skip` | Each is still accepted and is hidden from `--help`. Each prints one `note` line and changes nothing else. Beside `--check`, `--detect` or `--remove` they stop the command, as every flag of an install does. |
| An old manifest that holds the `done_skip` key of the facts record, or a `timeout` in a hook record | It is read without a refusal. The next install writes the facts record without `done_skip`, so the Done fact has no "is not run when" clause, and drops the hook records. |
| The instruction audit | A hook entry is a review hit like any other, also one that an earlier `adopt` wrote. No entry is recognised as `adopt`'s own, and no manifest digest exempts one. |

## The stub

`outcomebound finish-check` accepts any arguments. It reads no input and writes nothing to disk. It
prints nothing to standard error and returns exit code 0 at once. On standard output it prints what
1.6.0 printed when it had nothing to report:

| Call (as 1.6.0 wrote it) | Standard output |
| --- | --- |
| `claude-code` stop entry: `--constant-time --harness claude-code --done <digest> --timeout <seconds>` | nothing |
| `claude-code` turn-start entry: `--mark --harness claude-code --done <digest>` | nothing |
| `codex` stop entry: `--constant-time --harness codex --done <digest> --timeout <seconds>` | `{}` and a line break |
| `codex` turn-start entry: `--mark --harness codex --done <digest>` | nothing |
| any other arguments, including `--run`, `--status` and an unknown option | nothing |

The `codex` stop is the one call that prints. Its hook reads JSON on standard output, and a plain
text output is not valid for that event (research, `harnesses/codex.md`, section 7.1). `{}` is the
value 1.6.0 printed for a stop that held nothing. A closed standard output does not change the
exit code. The verb is not in the verb list of `outcomebound --help`; the verb table still routes it.

The stub stays until a later major release. Before then, a project that has not run `adopt` since
1.6.0 still works.

## Edges

- Whether a native `claude-code` or `codex` session accepts the stub's output was not observed in
  this change. The outputs are the bytes that 1.6.0 printed for a call with nothing to report, and
  the tests of the engine check them. This is `UNVERIFIED` for a native session.
- An old entry stays a committed hook until `adopt` runs. The instruction audit reports it, as it
  reports every hook, and the stub runs nothing of the project.
- `adopt` changes only the entries that it takes out, what they empty, and the whitespace of the
  document. A document with comments, a repeated key or a number in an odd form cannot be rewritten
  with a change of whitespace alone. While such a document holds an entry, the install stops and
  the person removes the entry by hand.

## Validation

`tests/test_retired_hooks.py` builds a 1.6.0 install for `claude-code` and `codex` (with a project
that has its own hooks and keys, and without a settings file) from the entry shapes that 1.6.0
wrote. It checks that a re-install takes out only the entries and the records and keeps every other
byte, that it deletes a document that `adopt` created and that holds nothing now, that a byte-order
mark and CRLF stay, that `--check` reads the install as not current and names each entry, that a
hand-edited entry is kept and refused without `--force`, that a record whose entry is gone is
dropped, that each retired flag prints one note and installs and runs nothing, and that the stub
answers each call of the table with the stated output, an empty standard error, no file written and
no delay. `tests/test_upgrade_corpus.py` upgrades real installs of earlier releases that hold the
hook. `tests/test_package.py` runs the stub from the installed wheel.
