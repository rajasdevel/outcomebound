# OutcomeBound portability: one contract, each harness's own route

OutcomeBound keeps one compact contract portable while letting each harness use its native
discovery mechanism:

- `AGENTS.md` holds the project instructions.
- `outcomebound adopt <target> --harness <name>` places one copy of each skill an install
  carries where that harness reads skills, and an `@AGENTS.md` import block in the file the
  harness reads in place of `AGENTS.md`.
- `adapters/harnesses.json` is the harness table of record; adopt reads each row's
  `skill_install_path`, `pointer_mechanism`, `verified`, `reads_agents_md` and `finish_hook`,
  and `outcomebound instructions check` reads what each row says the harness loads (`reads`,
  `nested`, `overrides`, `config`) and its `recheck_on` date.

## Harness matrix

| Harness | Skills | Reaches `AGENTS.md` through | Finish hook | Notes |
| --- | --- | --- | --- | --- |
| Claude Code | `.claude/skills/` | `CLAUDE.md@AGENTS.md` | `Stop`, in `.claude/settings.json` | verified 2026-08; adopt writes the import block only where `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` exists (into `CLAUDE.md`), unless the file already imports `@AGENTS.md` or is a link to `AGENTS.md`; with none, Claude Code reads `AGENTS.md` itself (from v2.1.277; adopt counts on it from v2.1.281, the version from which every session reads it) |
| Codex | `.agents/skills/` | `AGENTS.md` | `Stop`, in `.codex/hooks.json` | verified 2026-09; its default `workspace-write` sandbox keeps `.agents/`, `.codex/` and `.git/` read-only (approvals and security page, read 2026-10-01), so a Codex session reads the skills but cannot edit them or write the workspace fragment's `.agents/` folders; started with `--add-dir <repository>/.agents` it can (observed with codex-cli 0.159.2, 2026-10-01), and committing needs `--add-dir <repository>/.git` as well |
| Amp | `.agents/skills/` | `AGENTS.md` | — | verified 2026-08; shares `.agents/skills/` with Codex, so naming both installs one copy |
| Gemini CLI | `.gemini/skills/` | `GEMINI.md@AGENTS.md` | — | verified 2026-08-23 |
| Cursor | `.cursor/skills/` | `AGENTS.md` | — | verified 2026-08-23; Cursor also reads `CLAUDE.md` and, by default, runs Claude Code's hooks from `.claude/settings*.json` with no loop limit, which only Cursor's own `.cursor/hooks.json` format can set (hooks and third-party hooks pages, read 2026-10-01): a claude-code finish-check entry runs there too, and holds a finish only when its input says `stop_hook_active` is false, which Cursor does not document sending, so in Cursor it is UNVERIFIED ; Cursor also reads `.agents/skills/` and `.claude/skills/`, so with Codex or Claude Code adopted beside it a skill sits in two folders it reads, and whether it lists that skill twice is UNVERIFIED |
| Pi | `.pi/skills/` (candidate) | unverified | — | adopt refuses it until its route is verified |

Values mirror `adapters/harnesses.json`. Before writing anything, adopt refuses a harness the
table does not name, `generic` aside, a row it has not verified, and a row whose route cannot
load `AGENTS.md`; the refusal lists the harnesses that can. A dash in the finish-hook column
means `adopt --finish-check` has no entry for that harness; the
[finish-check design](../docs/specs/finish-check/design.md) says why for each.

## Adapter status

Verified rows are based on first-party documentation, checked on the date each row carries;
the date is provenance, not a promise that nothing moved since. An unverified row is never
installed as fact. Each row also carries a `recheck_on` date: past it,
`outcomebound instructions check` reads that harness's loading facts as `UNVERIFIED` until the
row is checked again.

These are the first-party skills pages as they stood when the rows were verified, in 2026-08
and 2026-09; a page may have moved since. The pages behind each row's other facts are cited in
the row itself, with the day each was read, and in
[docs/research/harnesses/](../docs/research/harnesses/cross-harness.md#sources).

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Codex skills](https://developers.openai.com/codex/skills)
- [Cursor Agent Skills](https://prod.cursor.com/docs/skills)
- [Gemini CLI Agent Skills](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/using-agent-skills.md)
- [Amp manual: Agent Skills](https://ampcode.com/manual)

## Project-document byte caps

`doc_byte_cap` in `adapters/harnesses.json` records a harness's known limit on the project
document it injects. `codex` declares 32768, and its `note` carries the cap's own provenance:
the documented `project_doc_max_bytes` default per Codex docs, 2026-08, to be re-verified
before anything relies on it. That note rates the cap value, not the row: the row's
`verified` flag rates the documented install layout. Every other row is `null`, meaning no
cap is known, not that none exists. `outcomebound fragments compose --harness <name>` warns
when the composed output exceeds a declared cap, because what a harness cut is not shown to the
model: Codex logs a warning when it truncates a project document [harness-loading-coverage-19], and
other harnesses may say nothing.
