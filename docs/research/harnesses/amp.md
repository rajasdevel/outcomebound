---
last_checked: 2026-09-25
volatility: VOLATILE (Amp changes its loading, skills and plugin API between releases; several of its pages carry no version)
sources:
  - https://ampcode.com/docs/customize/agents-md
  - https://ampcode.com/docs/customize/skills
  - https://ampcode.com/docs/customize/mcp
  - https://ampcode.com/docs/plugin-api
---

# Amp

Re-check when Amp changes which instruction files it reads, where it finds skills, its plugin
events or its settings keys; before relying on a field name; and by 2026-12-27, the re-check date
`adapters/harnesses.json` carries.

What Amp loads and from where, its skills directories, its finish event (a plugin event, not a
command hook), and the settings keys that run code or widen permissions. For anyone placing text,
skills or a plugin where Amp will load them, or re-checking the `amp` row of
`adapters/harnesses.json`. The comparison with other harnesses, the key findings (H1–H12) and the
evidence classes are in [cross-harness.md](cross-harness.md).

Instruction files and skills read 2026-09-25 [chk-amp-agents, chk-amp-skills], MCP and settings
2026-09-27, the plugin API 2026-09-29. A claim read later than `last_checked` carries its date.

## 1. Instruction files and precedence

- **Files.** `AGENTS.md`, falling back to `AGENT.md` and then `CLAUDE.md`, in the working directory
  and its parents up to `$HOME`; subtree files once the agent reads a file there;
  `~/.config/amp/AGENTS.md` and `~/.config/AGENTS.md` [chk-amp-agents]. L.
- **Mentions.** `@` mentions pull in other files, scoped with `globs` frontmatter [chk-amp-agents].
- A `CLAUDE.md` is read only when no `AGENTS.md` or `AGENT.md` is present in that directory.

## 2. Caps

No enforced cap is documented.

## 3. Skills

From `~/.config/agents/skills`, `~/.agents/skills`, `~/.config/amp/skills`, `.agents/skills` and
`.claude/skills` (project and parents), `~/.claude/skills` and `amp.skills.path`, so a skill
installed in `.agents/skills` for Codex, or in `.claude/skills` for Claude Code, is installed for
Amp too [chk-amp-skills]. Name and description are preloaded and the body loads on use. L.

## 4. Hooks: the plugin API

Source: <https://ampcode.com/docs/plugin-api>, read 2026-09-29 (`/docs/customize/hooks` returned
HTTP 404 and the manual has no hook section). Marks: *doc*, `UNVERIFIED`, as in
[cross-harness.md](cross-harness.md#1-scope-method-and-evidence).

| Finish event | Holds the finish and returns a reason | Loop guard | Time limit | Project configuration |
| --- | --- | --- | --- | --- |
| `agent.end`, a plugin event (doc) | `action: 'continue'` + `userMessage` starts a new turn (doc) | `maxContinuations`, default 5 (doc) | none documented (`UNVERIFIED`) | a TypeScript program under `.amp/plugins/`, run by Bun (doc); trust rule not found (`UNVERIFIED`) |

- `agent.end`: "Fired when the agent finishes handling a user prompt", with `status: 'done' | 'error'
  | 'cancelled'` and the turn's messages. A handler returns `{ action: 'continue', userMessage }` to
  "Automatically send a follow-up user message to start a new agent turn".
- `maxContinuations`: "How many plugin `continue` turns may run in a row after the last user-sent
  message… Defaults to 5. Any message the user sends resets the count."
- No time limit is documented for a handler (dispose callbacks get about three seconds).
- Plugins "are JavaScript/TypeScript programs", in `.amp/plugins/` (project) or
  `~/.config/amp/plugins/`, run by Bun; whether a project plugin loads without the person's act is
  not stated. A finish check in Amp is therefore a program in another language, not a command in a
  JSON file.
- What makes any harness's hook unsafe is in
  [cross-harness.md](cross-harness.md#92-what-makes-a-hook-unsafe-or-unusable).

## 5. Settings that run code or widen permissions

Read 2026-09-27. "Executes" means the key names a command or program the harness runs.

| Project files | Executes | Tool servers | Enables all servers | Endpoint overrides | Permission bypass | Deny rules |
| --- | --- | --- | --- | --- | --- | --- |
| `.amp/settings.json` or `.jsonc` | not settled (plugins under `.amp/plugins/`) | `amp.mcpServers` | — | `amp.url` | `amp.dangerouslyAllowAll` | `amp.permissions`, `amp.mcpPermissions` |

## 6. Trust, compaction and sessions

Whether a project plugin or project settings need the person's trust was not found
(`UNVERIFIED`). Compaction and session storage were not read for this reference.

## 7. Observing what loaded, and rendering

No command for listing loaded instruction files was recorded. Whether a reply's Mermaid block is
drawn is unknown [as-of 2026-09-23].

## Sources

- `AGENTS.md` <https://ampcode.com/docs/customize/agents-md> [chk-amp-agents]; skills
  <https://ampcode.com/docs/customize/skills> [chk-amp-skills] (2026-09-25).
- MCP <https://ampcode.com/docs/customize/mcp> (2026-09-27).
- Plugin API <https://ampcode.com/docs/plugin-api> (2026-09-29).

Checks defined here (verdict PASS, read 2026-09-25): [chk-amp-agents] and [chk-amp-skills], the
`AGENTS.md` and skills pages above.

Evidence ids in brackets resolve in [`../_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl).
