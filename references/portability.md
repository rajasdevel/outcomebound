# Harness support

OutcomeBound keeps one short contract. Each harness loads it in its own way. This page says what
`outcomebound adopt --harness <name>` does for each harness, and what is verified. Read the row
for your harness. Then read the notes under the table.

## What `adopt` does for a harness

- `AGENTS.md` holds the project instructions and the contract.
- `adopt` puts one copy of each skill in the folder where the harness reads skills.
- If the harness reads another file in place of `AGENTS.md`, `adopt` writes an `@AGENTS.md`
  import block into that file.
- `adapters/harnesses.json` is the harness table. It is the source of record for this page.
  `adopt` reads these fields of each row: `skill_install_path`, `pointer_mechanism`, `verified`,
  `reads_agents_md` and `finish_hook`. `outcomebound instructions check` reads what each row says
  the harness loads (`reads`, `nested`, `overrides` and `config`) and its `recheck_on` date.

## The harnesses

| Harness | `--harness` | Skills folder | Reaches `AGENTS.md` through | Finish hook | Verified |
| --- | --- | --- | --- | --- | --- |
| Claude Code | `claude-code` | `.claude/skills/` | `CLAUDE.md` with `@AGENTS.md` | `Stop`, in `.claude/settings.json` | 2026-08 |
| Codex | `codex` | `.agents/skills/` | `AGENTS.md` | `Stop`, in `.codex/hooks.json` | 2026-09 |
| Amp | `amp` | `.agents/skills/` | `AGENTS.md` | none | 2026-08 |
| Gemini CLI | `gemini` | `.gemini/skills/` | `GEMINI.md` with `@AGENTS.md` | none | 2026-08-23 |
| Cursor | `cursor` | `.cursor/skills/` | `AGENTS.md` | none | 2026-08-23 |

"None" in the finish-hook column means that `adopt --finish-check` has no entry for that
harness. The [finish-check design](../docs/specs/finish-check/design.md) says why for each
harness.

Before `adopt` writes anything, it refuses a harness that the table does not name, `generic`
aside. It also refuses a row that is not verified, and a row whose route cannot load `AGENTS.md`.
The refusal lists the harnesses that can.

### Claude Code

- `adopt` writes the import block only where `CLAUDE.md`, `.claude/CLAUDE.md` or
  `CLAUDE.local.md` exists. It writes the block into `CLAUDE.md`. It writes nothing if that file
  already imports `@AGENTS.md` or is a link to `AGENTS.md`.
- With none of those files, Claude Code reads `AGENTS.md` itself. It does this from v2.1.277.
  `adopt` relies on it from v2.1.281, the version from which every session reads `AGENTS.md`.
- The finish check is observed in a live session.

### Codex

- The default `workspace-write` sandbox keeps `.agents/`, `.codex/` and `.git/` read-only
  (approvals and security page, read 2026-10-01). A Codex session reads the skills. It cannot
  edit them, and it cannot write the `.agents/` folders of the workspace fragment.
- With `--add-dir <repository>/.agents`, a session can write them. This is observed with
  codex-cli 0.159.2 on 2026-10-01. To commit, add `--add-dir <repository>/.git` as well.
- The finish check is built for Codex. It is not yet observed there.

### Amp

Amp shares `.agents/skills/` with Codex. If you name both, `adopt` installs one copy.

### Gemini CLI

Gemini CLI reads `GEMINI.md`, not `AGENTS.md`. The import block in `GEMINI.md` brings in
`AGENTS.md`.

### Cursor

- Cursor also reads `CLAUDE.md`. By default it runs the hooks of Claude Code from
  `.claude/settings*.json`, with no loop limit. Only the `.cursor/hooks.json` format of Cursor can
  set a limit (hooks and third-party hooks pages, read 2026-10-01).
- So a finish-check entry that you installed for Claude Code also runs in Cursor. The entry holds
  a finish only when its input says `stop_hook_active` is false. Cursor does not document that it
  sends this field. Whether the entry works in Cursor is `UNVERIFIED`.
- Cursor also reads `.agents/skills/` and `.claude/skills/`. If you adopt Codex or Claude Code
  beside Cursor, a skill sits in two folders that Cursor reads. Whether Cursor lists that skill
  twice is `UNVERIFIED`.

### Any other harness: `--harness generic`

`generic` is the default when you name no harness. Use it for a harness that the table does not
list. `adopt` puts the skills in `.outcomebound/skills/` and writes no import block. The install
report says `UNVERIFIED` that the harness reads `AGENTS.md`. You check that your harness loads
`AGENTS.md` and the skills. Any other name that the table does not list is refused.

### pi

`adopt` refuses `pi`. The harness table has not verified how pi loads `AGENTS.md`. The table
holds a row for pi (`.pi/skills/`, a candidate path), and `adopt` does not use it as fact until
someone verifies it. To use pi now, adopt with `--harness generic`.

## How current is this table

A verified row rests on first-party documentation. The date on the row says when it was checked.
The date is a record of the check. It does not promise that nothing has changed since. An
unverified row is never installed as fact.

Each row also has a `recheck_on` date. After that date, `outcomebound instructions check` reads
the loading facts of that harness as `UNVERIFIED`, until someone checks the row again.

These are the first-party skills pages as they stood when the rows were verified, in 2026-08 and
2026-09. A page may have moved since.

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Codex skills](https://developers.openai.com/codex/skills)
- [Cursor Agent Skills](https://cursor.com/docs/skills)
- [Gemini CLI Agent Skills](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/using-agent-skills.md)
- [Amp manual: Agent Skills](https://ampcode.com/manual)

Each row of `adapters/harnesses.json` cites the pages behind its other facts, with the day each
page was read. The research repository lists them too, in
[harnesses/cross-harness.md](https://github.com/rajasdevel/outcomebound-research/blob/main/harnesses/cross-harness.md#sources).

## Project-document size limits

A harness can limit the size of the project document that it loads. `doc_byte_cap` in
`adapters/harnesses.json` records a known limit. Only `codex` has one: 32768 bytes. This is the
documented `project_doc_max_bytes` default from the Codex docs of 2026-08. Check it again before
you rely on it. The `note` in the row says where the value comes from. That note rates the value
of the cap. The `verified` flag of the row rates the documented install layout.

For every other row, `doc_byte_cap` is `null`. This means that no limit is known. It does not mean
that none exists.

`outcomebound fragments compose --harness <name>` warns when the composed output is larger than
the declared cap. The warning matters because a harness does not show the model what it cut.
Codex logs a warning when it truncates a project document. Other harnesses may say nothing.
