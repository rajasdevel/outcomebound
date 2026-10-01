---
last_checked: 2026-09-25
volatility: VOLATILE (Pi's documentation lives on its main branch and changes without versioned releases of the pages)
sources:
  - https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/configuration.md
  - https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/settings.md
  - https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/extensions.md
  - https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/usage.md
  - https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/how-pi-works.md
---

# Pi

Re-check when Pi changes which context files it reads, what project trust gates, its extension
events or its settings keys; before relying on a field name; and by 2026-12-27, the re-check date
`adapters/harnesses.json` carries. OutcomeBound's adopt refuses Pi until its route is verified.

What Pi loads and what waits for project trust, its skills, its finish event (an extension event,
not a command hook), the settings that run code, and where it keeps sessions. For anyone placing
text, skills or an extension where Pi will load them, opening an untrusted checkout in Pi, or
re-checking the `pi` row of `adapters/harnesses.json`. The comparison with other harnesses, the key
findings (H1–H12) and the evidence classes are in [cross-harness.md](cross-harness.md).

Configuration read 2026-09-25 [chk-pi], settings 2026-09-27, extensions 2026-09-29; the
configuration, settings, usage, how-Pi-works and MCP pages re-read 2026-10-01. A claim read later
than `last_checked` carries its date.

## 1. Instruction files and precedence

- **Context files.** `AGENTS.override.md`, `AGENTS.md`, `AGENTS.MD`, `CLAUDE.md` or `CLAUDE.MD` in
  the agent directory (`~/.pi/agent` by default), the working directory and its parents. An
  `AGENTS.override.md` replaces `AGENTS.md` or `CLAUDE.md` only in its own directory; it does not
  suppress context files from the agent directory or other directories [chk-pi]. L.
- **System prompt files.** `<agent-dir>/SYSTEM.md` replaces Pi's default system prompt and
  `<agent-dir>/APPEND_SYSTEM.md` adds to it; a trusted project's `.pi/SYSTEM.md` and
  `.pi/APPEND_SYSTEM.md` do the same for the project and take precedence over the agent-directory
  file of the same name, which is not combined with it (configuration page) [as-of 2026-10-01]. L.
- **Order of loading.** Pi resolves project trust, loads the project's settings and resources, then
  loads context files (how-Pi-works page) [as-of 2026-10-01].

## 2. Caps and skills

- No enforced cap is documented.
- Skills, in the Agent Skills format with name and description preloaded, from `.pi/skills/`
  (project, after trust) and `<agent-dir>/skills/` (user) [chk-pi]. L.

## 3. Trust

- **Context files load without trust.** "Context-file discovery does not require project trust", so
  an untrusted checkout's `AGENTS.md` and `CLAUDE.md` reach the model [chk-pi; configuration page,
  read 2026-10-01].
- **The project's `.pi/` directory waits for trust:** `settings.json`, `mcp.json`, `SYSTEM.md`,
  `APPEND_SYSTEM.md`, extensions, skills and prompts load only after project trust is granted; the
  one exception is `sessionDir`, read before trust so Pi can find sessions (configuration page,
  2026-10-01).
- **No prompt per tool call.** "Pi does not ask before every tool call. Review commands and changed
  files, and use a sandbox for untrusted or unattended work." Enabled tools run with the
  operating-system permissions of the Pi process, and extensions execute inside it (usage and
  how-Pi-works pages, 2026-10-01). L.

## 4. Hooks: extensions

Source: <https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/extensions.md>,
read 2026-09-29. Marks: *doc*, `UNVERIFIED`, as in
[cross-harness.md](cross-harness.md#1-scope-method-and-evidence).

| Finish event | Holds the finish and returns a reason | Loop guard | Time limit | Project configuration |
| --- | --- | --- | --- | --- |
| `agent_before_settle`, an extension event (doc) | `continue: true`, one more model request (doc) | the extension's own condition (doc) | none documented (`UNVERIFIED`) | a TypeScript extension under `.pi/extensions/`; a `project_trust` event precedes loading (doc) |

- "`agent_before_settle` is the final actionable boundary: it can append entries and request one
  continuation"; a run goes on to `agent_end`, and "`agent_settled` is final and
  notification-only". A handler "can return `continue: true` for one next model request".
- "Guard continuation conditions because an unconditional continuation can loop"; no guard is built
  in. No time limit documented.
- Extensions live in `~/.pi/agent/extensions/`, `.pi/extensions/` or `--extension`. "Only personal
  and explicit command-line extensions can participate in the `project_trust` event that runs
  before project extensions load." "An extension runs inside the Pi process with the same
  operating-system permissions."
- What makes any harness's hook unsafe is in
  [cross-harness.md](cross-harness.md#92-what-makes-a-hook-unsafe-or-unusable).

## 5. Settings that run code or widen permissions

Settings read 2026-09-27; `.pi/mcp.json` added 2026-10-01, which an earlier reading had missed.
"Executes" means the key names a command or program the harness runs.

| Project files | Executes | Tool servers | Enables all servers | Endpoint overrides | Permission bypass | Deny rules |
| --- | --- | --- | --- | --- | --- | --- |
| `.pi/settings.json`, `.pi/mcp.json` (trusted project) | `extensions`, `packages`, `shellCommandPrefix`, `shellPath`, `npmCommand`; `mcpServers.*.command` | `mcpServers` in `.pi/mcp.json` | — | `httpProxy` | not settled | not settled |

## 6. Sessions and compaction

Usage and how-Pi-works pages, read 2026-10-01. L.

- A session is Pi's record of a conversation (messages, tool calls and results, model changes,
  compactions), saved automatically as a JSONL file unless persistence is disabled; entries form a
  tree, and the active branch supplies the history for the next request. Continuing from an earlier
  entry creates a branch in the same file; `/fork` and `/clone` copy history into a new file.
- Compaction (`/compact`) inserts a summary entry that replaces older messages in later requests;
  the original entries stay in the session tree.
- Sessions are grouped by the folder Pi runs in; `pi --continue` resumes the most recent one there;
  `/session` shows its file, id, message count, token usage and cost. `/share` uploads a session
  (as a private GitHub gist, or to an organization's viewer); the page warns it can hold prompts,
  tool output, file contents and credentials.

## 7. Elsewhere

- On DeepSWE v1.1, DeepSeek-V4.1-Flash scored 66.2 in Pi, against 74.2 in mini-SWE and 69.8 in
  Claude Code ([cross-harness.md](cross-harness.md#132-the-documented-direction)).
- MiniMax Code is built on a harness "based on … OpenCode and Pi"; GLM reaches coding agents through
  Pi among others ([others.md](others.md#opencode), [others.md](others.md#zcode-zai)).
- Whether a reply's Mermaid block is drawn is unknown [as-of 2026-09-23].

## Sources

- Configuration
  <https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/configuration.md>
  [chk-pi] (2026-09-25, 2026-10-01); settings
  <https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/settings.md>
  (2026-09-27, 2026-10-01); extensions
  <https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/extensions.md>
  (2026-09-29); usage, how Pi works and MCP pages under the same `docs/` path (2026-10-01).

Checks defined here (verdict PASS, read 2026-09-25): [chk-pi], the configuration page above.

Evidence ids in brackets resolve in [`../_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl).
