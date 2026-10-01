---
last_checked: 2026-09-25
volatility: VOLATILE (Gemini CLI releases weekly; context loading, hooks and settings keys change between them)
sources:
  - https://geminicli.com/docs/cli/gemini-md/
  - https://raw.githubusercontent.com/google-gemini/gemini-cli/main/packages/core/src/prompts/snippets.ts
  - https://geminicli.com/docs/reference/configuration
  - https://geminicli.com/docs/hooks/
  - https://geminicli.com/docs/hooks/reference/
---

# Gemini CLI

Re-check when a Gemini CLI release changes which context files it loads, how its system prompt
ranks them, its hooks or its settings keys; before relying on a field name; and by 2026-12-27, the
re-check date `adapters/harnesses.json` carries.

What Gemini CLI loads and how its system prompt ranks it, its skills, its `AfterAgent` finish hook,
the settings keys that run code or widen permissions, and how to see what loaded. For anyone placing
text or hooks where Gemini CLI will load them, or re-checking the `gemini` row of
`adapters/harnesses.json`. Antigravity, Google's consumer harness that inherited Gemini CLI's
skills, hooks, subagents and extensions, is in [others.md](others.md#antigravity-googles-consumer-harness).
The comparison with other harnesses, the key findings (H1–H12) and the evidence classes are in
[cross-harness.md](cross-harness.md).

Read at version 0.61.0 (2026-09-23). Since 2026-06-18 it serves only Code Assist Standard and
Enterprise users and paid API keys, consumers having moved to Antigravity. Docs read 2026-09-25,
the system prompt source last changed 2026-09-08; configuration read 2026-09-27, hooks 2026-09-29
[gemini-harness, harness-loading-coverage-20, gemini-f19]. A claim read later than `last_checked`
carries its date.

## 1. Instruction files and precedence

- **Files.** `GEMINI.md` by default. It concatenates the global `~/.gemini/GEMINI.md`, `GEMINI.md`
  in workspace directories and their parents, and "just-in-time" files found in a directory and its
  ancestors up to a trusted root when a tool touches that directory, and resends them with every
  prompt. L.
- **`AGENTS.md`** loads only when `settings.json` sets `context.fileName` (for example
  `["AGENTS.md","GEMINI.md"]`); otherwise an `@AGENTS.md` import in `GEMINI.md` reaches it.
  `@./path.md` imports. L.
- **Authority.** The system prompt wraps loaded files in `<loaded_context>` and calls them
  "foundational mandates" that take "absolute precedence over the general workflows and tool
  defaults", ranking sub-directories above the workspace root, extensions and global files; they do
  not override its core safety mandates [gemini-f19]. L.
- **Defaults the prompt sets.** "Assume all requests are Inquiries unless they contain an explicit
  instruction to perform a task", and its default workflow reproduces a bug with a test first
  unless project guidance overrides it. A project that wants either behaviour changed says so in a
  loaded file. L.

## 2. Caps

No enforced cap is documented.

## 3. Skills

`.gemini/skills` or its `.agents/skills` alias (which wins within the same tier), plus
`~/.gemini/skills` or `~/.agents/skills`. Only name and description load up front; the body loads
after `activate_skill` and the user's consent. A skill installed in `.agents/skills` for Codex is
therefore found by Gemini CLI too. L.

## 4. Compaction and sessions

Not read for this reference beyond the resend of loaded files with every prompt (§1).

## 5. Trust

Just-in-time files are read only up to a trusted root (§1); project hooks are fingerprinted and a
changed one is treated as new and untrusted (§6).

## 6. Hooks

Sources: <https://geminicli.com/docs/hooks/> and <https://geminicli.com/docs/hooks/reference/>, read
2026-09-29 from the page source. Marks: *doc*, *report*, `UNVERIFIED`, as in
[cross-harness.md](cross-harness.md#1-scope-method-and-evidence).

| Finish event | Holds the finish and returns a reason | Loop guard | Time limit | Project configuration |
| --- | --- | --- | --- | --- |
| `AfterAgent` (doc) | `decision: "deny"` + `reason`, or exit 2 with stderr (doc) | `stop_hook_active`; no cap documented (`UNVERIFIED`); a loop defect fixed 2026-03 (report) | `timeout`, milliseconds, default 60000 (doc) | `.gemini/settings.json`, fingerprinted, warned on change (doc) |

- `AfterAgent`: "When agent loop ends", impact "Retry / Halt"; "Fires once per turn after the model
  generates its final response."
- `decision: "deny"` rejects the response and forces a retry; `reason` is "Required if denied. This
  text is sent to the agent as a new prompt to request a correction." Exit code 2 "Rejects the
  response and triggers an automatic retry turn using `stderr` as the feedback prompt"; other
  non-zero exits warn and continue; `continue: false` stops the session without retrying.
- `stop_hook_active` "Indicates if this hook is already running as part of a retry sequence." No cap
  documented. google-gemini/gemini-cli#20426, "AfterAgent hooks endless loop in version 0.30.0",
  reported the flag staying false; closed 2026-03-06 by a fix (report).
- `timeout` in milliseconds, default 60000. `systemMessage` is "Displayed immediately to the user in
  the terminal" and does not reach the model. `GEMINI_PROJECT_DIR` is "The absolute path to the
  project root."
- **Trust.** "Hooks execute arbitrary code with your user privileges." "Project-level hooks are
  particularly risky when opening untrusted projects. Gemini CLI fingerprints project hooks. If a
  hook's name or command changes (for example, via `git pull`), it is treated as a new, untrusted
  hook and you will be warned before it executes."
- What makes any harness's hook unsafe is in
  [cross-harness.md](cross-harness.md#92-what-makes-a-hook-unsafe-or-unusable).

## 7. Settings that run code or widen permissions

Configuration reference, read 2026-09-27. Files: `.gemini/settings.json` (project),
`~/.gemini/settings.json`, `/etc/gemini-cli/settings.json`, and extensions. "Executes" means the key
names a command or program the harness runs.

| Project files | Executes | Tool servers | Enables all servers | Endpoint overrides | Permission bypass | Deny rules |
| --- | --- | --- | --- | --- | --- | --- |
| `.gemini/settings.json` | `hooks` | `mcpServers` | — | environment variables, not settings | `general.defaultApprovalMode`, `tools.allowed`, `mcpServers.*.trust` | `tools.exclude`, `mcp.excluded` |

## 8. Observing what loaded, and surface signals

- `/memory show` and `/memory reload` inspect and refresh what loaded.
- Gemini CLI sets `GEMINI_CLI=1` in every command it runs (OutcomeBound's `adapters/surfaces.json`).
- Whether a reply's Mermaid block is drawn is unknown [as-of 2026-09-23].

## Sources

- `GEMINI.md` <https://geminicli.com/docs/cli/gemini-md/> (page updated 2026-06-18, read
  2026-09-25); system prompt
  <https://raw.githubusercontent.com/google-gemini/gemini-cli/main/packages/core/src/prompts/snippets.ts>
  (last commit 2026-09-08).
- Configuration <https://geminicli.com/docs/reference/configuration> (2026-09-27).
- Hooks <https://geminicli.com/docs/hooks/> and <https://geminicli.com/docs/hooks/reference/>
  (2026-09-29); issue <https://github.com/google-gemini/gemini-cli/issues/20426> (2026-09-29).

Evidence ids in brackets resolve in [`../_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl).
