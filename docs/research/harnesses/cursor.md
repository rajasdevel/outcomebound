---
last_checked: 2026-09-25
volatility: VOLATILE (Cursor ships monthly; rules, hooks and third-party loading change between releases)
sources:
  - https://cursor.com/docs/rules
  - https://cursor.com/help/customization/rules
  - https://cursor.com/docs/hooks
  - https://cursor.com/docs/reference/third-party-hooks
  - https://cursor.com/docs/cli/headless
  - https://cursor.com/docs/context/mcp
  - https://cursor.com/docs/cli/reference/permissions
  - https://cursor.com/changelog/2-2
---

# Cursor

Re-check when a Cursor release changes how it reads rules, `AGENTS.md` or `CLAUDE.md`, runs hooks
(its own or Claude Code's), or gates trust; before relying on a field name; and by 2026-12-27, the
re-check date `adapters/harnesses.json` carries.

What Cursor loads and in what order, how its rules activate and which surfaces they reach, its
skills directories, its `stop` hook, the Claude Code files it reads and runs, and the configuration
that runs code. For anyone placing text or hooks where Cursor will load them, committing Claude
Code configuration to a repository Cursor users open, or re-checking the `cursor` row of
`adapters/harnesses.json`. The comparison with other harnesses, the key findings (H1–H12) and the
evidence classes are in [cross-harness.md](cross-harness.md).

Rules read 2026-09-25, configuration 2026-09-27, hooks 2026-09-29; the rules docs, the rules help
page and the hooks pages re-read 2026-10-01 [harness-loading-coverage-17, grok-f1, grok-harness].
A claim read later than `last_checked` carries its date.

## 1. Instruction files and precedence

- **Files.** `.cursor/rules/*.mdc` with four activation modes; `AGENTS.md` at the root and nested;
  user rules and team rules [harness-loading-coverage-17].
- **Precedence.** "All applicable rules are merged; earlier sources take precedence when guidance
  conflicts", in the order Team, Project, User, so organisation rules outrank project rules; nested
  `AGENTS.md` files "are combined with parent directories, with more specific instructions taking
  precedence". L.
- **`CLAUDE.md`** [as-of 2026-10-01]. The rules page does not mention it, but the rules help page
  says Cursor "reads `CLAUDE.md` files the same way it reads `AGENTS.md`", picks up a root
  `CLAUDE.md` automatically, and applies it "to every conversation, regardless of any `alwaysApply`
  frontmatter setting", for compatibility with Claude Code. A `CLAUDE.md` written only for Claude
  Code therefore reaches Cursor's agent as well, and a `CLAUDE.md` holding `@AGENTS.md` is read as
  Cursor reads `AGENTS.md`. L.
- **What counts as a rule** [as-of 2026-10-01]. A project rule must be an `.mdc` file: "A plain
  `.md` file in `.cursor/rules` is ignored by the rules system", without a warning, because it has
  no frontmatter; the root `.cursorrules` file "is legacy and will be deprecated". Path-scoped rules
  carry `alwaysApply` and `globs` in their frontmatter. L.
- **Where rules reach.** Rules "only apply to Agent (Chat)", not to Tab completion, Inline Edit or
  Bugbot pull-request reviews, so those surfaces load none of the project's instructions (rules help
  page, read 2026-10-01). L.
- **Other harnesses read Cursor's files.** Grok Build reads `.cursor/rules` behind a compatibility
  toggle that defaults on ([others.md](others.md#grok-build-xai)); Cline reads `.cursorrules`
  ([others.md](others.md#cline)).

## 2. Caps

No enforced cap is documented. Advisory: keep rules under 500 lines
[harness-loading-coverage-17].

## 3. Skills

Agent Skills `SKILL.md` format, name and description preloaded and the body loaded on use, from
`.cursor/skills` and `.agents/skills` (project), `~/.agents/skills`, and, for compatibility,
`.claude/skills` and `.codex/skills` (Cursor's skills page, read 2026-10-01). A skill installed in
`.agents/skills` for Codex, or in `.claude/skills` for Claude Code, is installed for Cursor too. L.

## 4. Hooks

### 4.1 The finish hook

Sources: <https://cursor.com/docs/hooks> (the same page as `/docs/agent/hooks`) and
<https://cursor.com/docs/cli/headless>, read 2026-09-29 from the page source; the hooks page
re-read 2026-10-01 from its Markdown source. Marks: *doc*, *report*, `UNVERIFIED`, as in
[cross-harness.md](cross-harness.md#1-scope-method-and-evidence).

| Finish event | Holds the finish and returns a reason | Loop guard | Time limit | Project configuration |
| --- | --- | --- | --- | --- |
| `stop` (doc) | no hold: `followup_message` is submitted as the next user message after the loop ends (doc) | `loop_count`; `loop_limit`, default 5 (doc) | `timeout`, seconds, default not stated (`UNVERIFIED`) | `.cursor/hooks.json`, trusted workspaces and cloud agents (doc); also Claude Code's `.claude/settings*.json` hooks, on by default, with `loop_limit` `null`, no limit, which only Cursor's own format can set (doc); CLI support undocumented (`UNVERIFIED`) |

- `stop`: "Called when the agent loop ends. Can optionally auto-submit a follow-up user message to
  keep iterating." Input: `status` (`completed`, `aborted`, `error`) and `loop_count`, no `cwd`;
  every hook also receives `conversation_id`, `generation_id`, `model`, `hook_event_name`,
  `cursor_version`, `workspace_roots`, `user_email` and `transcript_path`. The process gets
  `CURSOR_PROJECT_DIR`, "Workspace root directory". `subagentStop` is the same for a subagent.
- `followup_message`: "When provided and non-empty, Cursor will automatically submit it as the next
  user message." The loop has already ended; the message starts another. Exit code 2 blocks an
  action on the permission hooks, not here.
- `loop_count` "indicates how many times the stop hook has already triggered an automatic follow-up
  for this conversation (starts at 0). The default limit is 5 auto follow-ups per script,
  configurable via the `loop_limit` option. Set `loop_limit` to `null` to remove the cap."
- `timeout` in seconds, default "platform default", no number given.
- **Failure mode.** Hook failures "fail open by default" unless `failClosed: true`.
- **Configuration.** `<project-root>/.cursor/hooks.json`: "Project hooks run in any trusted
  workspace and are checked into version control with your project"; `~/.cursor/hooks.json`; team
  and enterprise layers above the project. "Cloud agents run command-based hooks from your
  repository."
- **The CLI.** Whether the CLI agent runs `stop` is not stated: the hooks page names the editor, Tab
  and cloud agents, and the headless CLI page does not mention hooks. robot-council/cli#72 and #83
  (2026-09) set out to measure it and record it as unsettled (report).

### 4.2 Claude Code's hooks run in Cursor

Third-party hooks page, <https://cursor.com/docs/reference/third-party-hooks>, read 2026-10-01. L.

- With "Include Third-Party Plugins, Skills, and Other Configs" on, which it is by default, Cursor
  loads hooks from `.claude/settings.local.json`, `.claude/settings.json` and
  `~/.claude/settings.json`, below its own enterprise, team, project and user hooks; all matching
  hooks from every source run.
- It maps `Stop` to `stop` and treats a Claude Code `decision: "block"` with a `reason` as an
  automatic follow-up message; exit 2 blocks, other non-zero exits fail open.
- The hooks page gives `loop_limit` a default of 5 for Cursor hooks and `null`, no limit, for Claude
  Code hooks, and the third-party hooks page lists loop-limit configuration among the features
  available only in Cursor's native format. So a Claude Code finish hook that relies on Claude
  Code's 8-continuation cap has no cap in Cursor unless it checks its own guard or moves to
  `.cursor/hooks.json`. Whether that default loops in practice is unsettled.
- How Claude Code itself runs these hooks is in [claude-code.md](claude-code.md#71-the-finish-hook).

## 5. Settings that run code or widen permissions

Read 2026-09-27 (MCP and CLI permissions pages). "Executes" means the key names a command or
program the harness runs.

| Project files | Executes | Tool servers | Enables all servers | Endpoint overrides | Permission bypass | Deny rules |
| --- | --- | --- | --- | --- | --- | --- |
| `.cursor/hooks.json`, `.cursor/mcp.json`, `.cursor/cli.json` | `hooks` | `mcpServers` | not settled | not settled | not settled | `permissions.deny` (in `.cursor/cli.json`) |

Cursor also runs the hooks in Claude Code's settings files (§4.2), so a repository's
`.claude/settings.json` is executable configuration for Cursor users too.

## 6. Trust and readers that load nothing

- Project hooks run "in any trusted workspace"; cloud agents run a repository's command hooks
  (§4.1).
- Tab completion, Inline Edit and Bugbot pull-request reviews load no rules (§1), so a brief or a
  review there carries its own bounds.

## 7. Sessions, worktrees and models

- Cursor manages its own worktrees per machine, keeping at most 25 per machine and cleaning up
  every 6 hours ([agent-workspace.md](../practices/agent-workspace.md#2-worktrees-and-working-files-w1-volatile)).
  Where it keeps sessions was not read for this reference.
- Cursor has been a SpaceX subsidiary since 2026-08-14, and with Grok Build is the only place
  serving Grok 4.7 Fast [grok-trend, grok-g12]. Grok 4.5–4.7 were co-trained with Cursor data
  ([cross-harness.md](cross-harness.md#132-the-documented-direction)).
- At-work adoption was 12% in May–July 2026, down from 18% in January, in one vendor-run survey
  ([cross-harness.md](cross-harness.md#12-adoption-monitor)).

## 8. Rendering and surface signals

- Since 2026-02-18 the Cursor CLI renders a reply's Mermaid block inline as ASCII (changelog); for
  Cursor's agent chat it is unknown [as-of 2026-09-23]. Cursor's 2.2 changelog (2025-12-10) says
  Plan Mode supports inline Mermaid diagrams; those are plans, not replies in chat (read
  2026-10-01).
- Cursor sets `CURSOR_AGENT` in the commands its agent runs. As a host editor it also sets its own
  variables for every extension, so a Claude Code extension session inside Cursor carries
  `CURSOR_LAYOUT`, `CURSOR_WORKSPACE_LABEL` and `VSCODE_PID`, and a terminal it opens may inherit
  `CURSOR_AGENT` (A, observed 2026-09-23). Match on the most specific set of variables
  ([cross-harness.md](cross-harness.md#11-rendering-in-harness-surfaces)).

## Sources

- Rules <https://cursor.com/docs/rules> (the earlier `/docs/context/rules` address returned 404 on
  2026-10-01) and rules help <https://cursor.com/help/customization/rules> (2026-09-24,
  2026-10-01); skills page (2026-10-01).
- Hooks <https://cursor.com/docs/hooks> (2026-09-29, 2026-10-01); third-party hooks
  <https://cursor.com/docs/reference/third-party-hooks> (2026-10-01); headless CLI
  <https://cursor.com/docs/cli/headless> (2026-09-29).
- MCP <https://cursor.com/docs/context/mcp> and permissions
  <https://cursor.com/docs/cli/reference/permissions> (2026-09-27).
- 2.2 changelog <https://cursor.com/changelog/2-2> (2026-10-01).
- Reports: robot-council/cli <https://github.com/robot-council/cli/issues/72>,
  <https://github.com/robot-council/cli/issues/83> (2026-09-29).

Evidence ids in brackets resolve in [`../_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl).
