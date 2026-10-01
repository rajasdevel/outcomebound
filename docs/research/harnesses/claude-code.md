---
last_checked: 2026-09-25
volatility: VOLATILE (Claude Code ships several releases a week; loading, hooks and settings keys change between them)
sources:
  - https://code.claude.com/docs/en/memory
  - https://code.claude.com/docs/en/context-window
  - https://code.claude.com/docs/en/skills
  - https://code.claude.com/docs/en/sub-agents
  - https://code.claude.com/docs/en/hooks
  - https://code.claude.com/docs/en/settings
  - https://code.claude.com/docs/en/settings-reference
  - https://code.claude.com/docs/en/security
  - https://code.claude.com/docs/en/checkpointing
  - https://code.claude.com/docs/en/headless
  - https://code.claude.com/docs/en/cli-reference
  - https://code.claude.com/docs/en/plugins-reference
  - https://code.claude.com/docs/en/agent-sdk/claude-code-features
  - https://code.claude.com/docs/en/mcp
  - https://code.claude.com/docs/en/sandboxing
  - https://code.claude.com/docs/en/permission-modes
  - https://code.claude.com/docs/en/agent-sdk/structured-outputs
  - https://code.claude.com/docs/en/agent-sdk/session-storage
---

# Claude Code

Re-check when a Claude Code release changes how it loads `CLAUDE.md` or `AGENTS.md`, caps or
compacts them, runs hooks or gates trust; before relying on a field name; and by 2026-12-27, the
re-check date `adapters/harnesses.json` carries.

What Claude Code loads and in what order, what it caps and keeps after compaction, which trust
gates, hooks and settings run code, where it keeps sessions, and how to see what it loaded. For
anyone placing text or hooks where Claude Code will load them, or re-checking the `claude-code` row
of `adapters/harnesses.json`. The comparison with other harnesses, the key findings (H1–H12) and
the evidence classes are in [cross-harness.md](cross-harness.md); permission modes, the auto-mode
classifier and the sandbox are in [authority.md](../practices/agent-authorization.md#2-claude-codes-permission-layers-volatile-a2-a4).

The pages were read at version 2.1.282 (2026-09-24); npm listed 2.1.286 on 2026-10-01. The memory,
skills, context-window and sub-agents pages were read 2026-09-25, settings 2026-09-27, hooks
2026-09-29; the memory, hooks, sub-agents, worktrees, checkpointing, plugins, SDK, headless,
CLI-reference, commands and debugging pages were re-read 2026-10-01, and the MCP, sandboxing,
permission-modes, structured-outputs and session-storage pages read that day [claude-harness]. A
claim read on a later day than `last_checked` carries its date.

## 1. Instruction files and precedence

- **Files.** Managed policy (plus a `claudeMd` key in managed settings), `~/.claude/CLAUDE.md`,
  `./CLAUDE.md` or `./.claude/CLAUDE.md`, and `./CLAUDE.local.md`. Every file from the filesystem
  root down to the working directory loads at launch and is concatenated, not overridden; files
  nearer the working directory are read last, and `CLAUDE.local.md` follows `CLAUDE.md` at each
  level. Subdirectory `CLAUDE.md` files load on demand when Claude reads files there.
- **Imports.** `@path` imports (since v0.2.107, 2025-05-09) up to four hops; an import resolving
  outside the working directory needs a one-time approval. Block-level HTML comments are stripped
  before injection (v2.1.72).
- **`AGENTS.md`** (memory page, "When Claude Code reads AGENTS.md") [as-of 2026-10-01]. Claude Code
  started reading it directly in v2.1.277 (2026-09-18), and v2.1.281 extended that to every session
  type (before it, some sessions, such as Bedrock or telemetry off, could not read it at all);
  OutcomeBound's harness table records 2.1.281 for that reason. In every version, under the default
  setting, it is read only when none of the files that count exists: a `CLAUDE.md`,
  `.claude/CLAUDE.md` or `CLAUDE.local.md` in the working directory or any directory above it. The
  person's `~/.claude/CLAUDE.md`, the organisation's managed `CLAUDE.md` and `.claude/rules/` files
  do not count and keep loading beside `AGENTS.md`. The reading is done by the built-in `agents-md`
  plugin, which can be turned off. When none counts, every `AGENTS.md` and `.claude/AGENTS.md` from
  the working directory upward loads at session start (an interactive session prints "no CLAUDE.md
  found; AGENTS.md loaded: …"), a subdirectory's `AGENTS.md` loads when Claude reads a file there
  and that subdirectory has no `CLAUDE.md` of its own, `@path` imports and `claudeMdExcludes` apply
  inside it, and subagents that skip project instructions skip it too. `AGENTS.local.md`,
  `AGENTS.override.md` and anything under a `.agents/` directory are never read. A `CLAUDE.local.md`
  counts, so adding one suppresses `AGENTS.md` [harness-loading-coverage-3]. Under the default
  setting no session reads `AGENTS.md` unless that condition holds; only the setting below, or an
  `@AGENTS.md` import, changes that.
- **The "Project instructions" setting** takes four values: `claude-md-or-agents-md` (the default,
  as above); `claude-md-and-agents-md` (both, each directory's `CLAUDE.md` first, an `AGENTS.md`
  already loaded through an import or symlink not read twice); `claude-md`; and `managed-only` (only
  the managed `CLAUDE.md` and auto memory at launch). It is set in `/config`, or under
  `pluginConfigs` → `agents-md@builtin` → `options.instructionFiles` in user, `--settings` or managed
  settings; project and local settings are ignored for it. Sessions read `CLAUDE.md` files only, and
  the setting is absent from `/config`, before v2.1.277, with the built-in `agents-md` plugin
  disabled, and in some first sessions after an upgrade from v2.1.276 or earlier. Lab-guidance
  [as-of 2026-10-01].
- **Where an `AGENTS.md` read through the setting differs.** It fires no `InstructionsLoaded` hook
  (one reached through a `CLAUDE.md` import or symlink does), does not load from directories added
  with `--add-dir`, and loads an import from outside the working directory only if external imports
  were already approved for the project. A `CLAUDE.md` that tells Claude in prose to read
  `AGENTS.md` loads it only if Claude decides to open it; a `CLAUDE.md` holding `@AGENTS.md` never
  double-loads, works on older versions, with a `CLAUDE.local.md` present and in sessions that
  cannot read `AGENTS.md`, and the page says it can be removed if it holds nothing else or kept for
  those sessions [harness-loading-coverage-4]. Lab-guidance [as-of 2026-10-01].
- **A symbolic link.** A `CLAUDE.md` that is a symbolic link to `AGENTS.md` gives Claude Code
  `AGENTS.md`'s text with no import, so anything appended to `AGENTS.md` reaches it too; the Edit and
  Write tools refuse to write through the link and point Claude at `AGENTS.md`. It does not survive
  every checkout: on Windows, creating a link needs Administrator rights or Developer Mode, and Git
  checks a committed link out as a plain text file unless `core.symlinks` is enabled, leaving a
  one-line `CLAUDE.md` in place of the instructions, so the page advises the `@AGENTS.md` import
  wherever anyone works on Windows. Lab-guidance [as-of 2026-10-01]. An automated audit that skips
  symlinked files ([writing-for-models.md](../practices/writing-for-models.md#71-scope)) does not read such a `CLAUDE.md`.
- **Rules.** `.claude/rules/*.md` (since v2.0.64, 2025-12-10), path-scoped with `paths:`
  frontmatter, the only field read; also `~/.claude/rules/`.
- **Auto memory.** `MEMORY.md` plus topic files (since v2.1.59, 2026-02-25); the first 200 lines or
  25 KB of `MEMORY.md`, whichever comes first, load at every session start
  [harness-loading-coverage-6].
- **Conflicts.** Layers are concatenated with no conflict resolution: "if two rules contradict each
  other, Claude may pick one arbitrarily" [harness-loading-coverage-10]. Instruction files are
  "context, not enforced configuration"; to block an action whatever Claude decides, use a
  `PreToolUse` hook [harness-loading-coverage-9]. `CLAUDE.md` "is delivered as a user message after
  the system prompt", with "no guarantee of strict compliance, especially for vague or conflicting
  instructions" (memory page, from the detail of [agent-files-12]).
- **One file pointing at another.** A `CLAUDE.md` holding `@AGENTS.md` is the robust form for
  Claude Code; how other harnesses read the same file is in
  [cross-harness.md](cross-harness.md#4-precedence-and-authority).

## 2. Caps

| Cap | Scope | Past the cap | Source |
| --- | --- | --- | --- |
| 4 MiB | per `CLAUDE.md` | file skipped | chk-claude-memory |
| 200 lines or 25 KB | `MEMORY.md` | the rest not loaded at start | harness-loading-coverage-6 |
| 5,000 tokens per skill, 25,000 total | invoked skills after compaction | start of each skill kept; oldest skills dropped | harness-loading-coverage-8 |
| 1,536 characters | a skill's `description` plus `when_to_use` in the model's listing | truncated (the `/skills` menu shows 250) | chk-claude-skills |

**Advisory, not enforced.** Keep each `CLAUDE.md` under about 200 lines, because "longer files
consume more context and reduce adherence"; imports organise content but do not shrink what loads
[harness-loading-coverage-5]. A `CLAUDE.md` of up to 4 MiB loads in full and a larger one is
skipped [chk-claude-memory].

## 3. Skills and deferred tools

- Agent Skills `SKILL.md` format, from `.claude/skills` and `~/.claude/skills`; only the listing is
  preloaded and the body loads on use [claude-harness].
- The listing cuts a skill's combined `description` and `when_to_use` at 1,536 characters; the
  `/skills` menu shows 250 [chk-claude-skills]. The model decides from the listing alone, so a
  description carries its trigger early.
- After compaction each invoked skill keeps its first 5,000 tokens, 25,000 in all, oldest dropped
  first (§4).
- Cursor and Amp also read `.claude/skills`, and OpenCode reads `~/.claude/skills`
  ([cross-harness.md](cross-harness.md#6-skills-discovery-and-listing)).
- **Tool definitions load the same way** (MCP page) [as-of 2026-10-01]. Tool search is on by
  default, in `-p` and Agent SDK runs too: only tool names and MCP server instructions load at
  session start, and definitions are fetched on demand, so a server's instructions field is its
  discovery text, much as a skill's description is. `ENABLE_TOOL_SEARCH` sets it: unset defers every
  MCP tool; `auto` (or `auto:N`) loads them up front while their definitions stay under 10% (or N%)
  of the context window and defers all of them past it; `false` loads all up front. It falls back to
  up-front loading when `ANTHROPIC_BASE_URL` names a non-first-party host, on a Microsoft Foundry
  deployment hosted on Azure, and on Google Cloud Agent Platform models older than the Claude 4.5
  generation; it needs a model that supports `tool_reference` blocks (Sonnet 4.5, Haiku 4.5, Opus
  4.5 and later). With tool search, a server that failed to connect or needs sign-in is named to
  Claude; without it, it is not. L.

## 4. Compaction, checkpoints and long sessions

- **What is re-injected.** The root `CLAUDE.md`, unscoped rules and auto memory are re-injected
  after compaction; path-scoped rules and nested `CLAUDE.md` files "load into message history when
  their trigger file is read, so compaction summarizes them away"; invoked skills are re-injected up
  to 5,000 tokens each and 25,000 in all, keeping the start of each file, so "put the most important
  instructions near the top of SKILL.md". Up to five recently modified files are re-read, and a
  file over 5,000 tokens comes back as a path reference only (from the record's detail). Whether an
  `AGENTS.md` read directly (with no `CLAUDE.md`) is re-injected is `UNVERIFIED`
  [harness-loading-coverage-7, harness-loading-coverage-8].
- **Hooks around compaction.** `PreCompact` (matcher `manual` or `auto`) blocks compaction on exit 2
  or `decision: "block"`: a proactive automatic compaction is then skipped and the conversation
  continues uncompacted, while one triggered to recover from a context-limit error lets that error
  surface and the request fails. `PostCompact` receives the generated `compact_summary` and has no
  decision control. A hook can therefore keep each summary for checking against the files a run
  relies on, but cannot edit it. Lab-guidance (hooks page, read 2026-09-29 and 2026-10-01).
- **Checkpoints.** Claude Code checkpoints the files before every prompt that starts a turn, keeps
  snapshots for the 100 most recent checkpoints, and lets `/rewind` restore code and conversation or
  summarize part of it ("Summarize from here" compresses from a chosen message on, "Summarize up to
  here" compresses what came before it); the snapshots go in the retention sweep, by default about 30
  days after the session last saved one (checkpointing page) [as-of 2026-10-01].
- **Effort mid-session.** Changing effort mid-session no longer breaks the prompt cache on Opus 5.5
  and Fable 5.1 (v2.1.280 and later, as reported by Latent Space on 2026-09-28; A) [claude-harness].
- How context windows degrade, prompt caching and compaction as a mechanism are in
  [context-and-memory.md](../practices/long-context-and-compaction.md#5-compaction-monitor).

## 5. Subagents, delegation and the Agent SDK

- **Which subagents load the instruction files.** The built-in Explore and Plan subagents skip
  `CLAUDE.md` and the git status snapshot; every other built-in and custom subagent loads both
  unless its definition sets `omitClaudeMd` [capability-tier-readers-13]. Since v2.1.198 Explore
  inherits the main conversation's model instead of always running on Haiku, capped at Opus on the
  Claude API [chk-claude-subagents]. A delegate's brief must carry the bounds itself.
- **Limits.** A subagent may spawn subagents up to three layers below the main conversation
  (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`), at most 20 may run at once
  (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`, v2.1.217 and later), and there is no limit on the total
  over a session; the Agent SDK adds a spending cap (`max_budget_usd`) [claude-f21; sub-agents page,
  as-of 2026-10-01].
- **Contracts per subagent.** A definition's frontmatter sets `description`, `tools`,
  `disallowedTools`, `model`, `permissionMode`, `mcpServers`, `hooks`, `maxTurns`, `skills`,
  `initialPrompt`, `memory` (a persistent `user`, `project` or `local` scope), `effort`,
  `background`, `omitClaudeMd` and `isolation`. A subagent can be resumed or sent a follow-up; one
  that reaches `maxTurns` returns output marked partial (v2.1.246 and later) and can be resumed to
  continue. Sub-agents page [as-of 2026-10-01]. L.
- **Foreground or background.** Background is the default in an interactive session, where fork
  mode is on: every subagent Claude spawns runs in the background. With fork mode off, which is the
  default under `-p` and in the Agent SDK, Claude runs a subagent in the background unless it needs
  the result before continuing; `background: true` keeps one in the background regardless, and
  `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` forces the foreground. A background subagent keeps every
  MCP tool but only a fixed set of built-in tools (file, shell, search, web and worktree tools among
  them), so one definition can resolve to different tools in the two modes; its permission prompts
  surface in the main session, naming it. Same page [as-of 2026-10-01]. L.
- **Hooks inside subagents.** Hooks from settings, managed policy and plugins also fire inside
  subagents, with `agent_id` and `agent_type` in their input (§7.1).
- **Text a subagent returns.** Claude Code scans each subagent's final report before the parent
  reads it: it inserts a backslash into text that imitates its own control tags (such as
  `<system-reminder>`, or a line starting `Human:` or `Assistant:`) so the imitation reads as plain
  text, and prepends a line beginning `[harness: subagent output matched instruction-shaped
  pattern(s):` when the report imitates a tag or names a permission setting such as
  `bypassPermissions`. The scan removes nothing and judges nothing, and a report arrives under a
  header saying its instructions or approval claims carry no authority (sub-agents page)
  [as-of 2026-10-01]. It was seen working on a report that described `.claude/settings.json` as an
  attack surface (O, sessions run through the Agent SDK, 2026-09-25 and 2026-10-01).
- **Agent SDK.** With `settingSources` omitted, an SDK `query()` reads the same filesystem settings
  as the CLI: user, project and local settings, `CLAUDE.md` files, and `.claude/` skills, agents and
  commands; `settingSources: []` limits it to what the program configures, and some inputs (such as
  user-level sandbox credential rules) are read whatever its value. Write-ups from 2025 describe the
  opposite default. `--bare` skips hooks, skills, plugins, MCP servers, auto memory and `CLAUDE.md`
  for scripted calls, so the same call gives the same result on every machine. The SDK's
  `total_cost_usd` and `costUSD` are client-side estimates from a bundled price table, not billing.
  Lab-guidance, SDK, headless and cost pages [as-of 2026-10-01]. Whether an SDK session reads
  `AGENTS.md` by the rules in §1 is `UNVERIFIED`.
- **More of the Agent SDK** (read at TypeScript 0.3.286 and Python 0.2.163, the registries' latest
  on 2026-10-01). The headless page calls `--bare` "the recommended mode for scripted and SDK
  calls", which "will become the default for `-p` in a future release"; without it a `-p` session
  runs a project's hooks and connects its `.mcp.json` servers in a folder never trusted, and bare
  mode reads no OAuth credentials or keychain, so it needs `ANTHROPIC_API_KEY` or an
  `apiKeyHelper`. Structured outputs validate the final answer against a JSON Schema (draft-07) and
  re-prompt on a mismatch; when no valid output remains after the retries the result's subtype is
  `error_max_structured_output_retries`, and a `success` result with no `structured_output` is also
  a failure. A `SessionStore` mirrors session transcripts to an object store, key-value store or
  database so another host can resume them from a matching working directory; the mirror is
  best-effort (three attempts, then a `mirror_error` message and the batch dropped), a run resumed
  from the store deletes its local copy at the end, and the SDK never deletes from the store, so
  retention is the adapter's. Its page carries no alpha or beta label. Headless, structured-outputs
  and session-storage pages [as-of 2026-10-01]. L.

## 6. Trust

- The trust check for first-time codebases and new MCP servers "is disabled when running
  non-interactively with the `-p` flag" [instruction-file-security-authority-19].
- Hooks from settings files are held back until the workspace trust dialog is accepted, but in a
  `-p` or SDK session the folder is treated as trusted, so committed hooks run in a folder never
  trusted (§7.1).
- A project-scope plugin, checked into the repository, loads only after the workspace trust check
  that guards project allow rules ("Trusting a parent folder or running with `-p` isn't enough")
  (§10) [as-of 2026-10-01].
- The trust Claude Code documents is per workspace; no review of individual hook entries like
  Codex's is documented, so a later change to a committed entry is not prompted again (as read, not
  tested).

## 7. Hooks

### 7.1 The finish hook

Source: <https://code.claude.com/docs/en/hooks>, read 2026-09-29 from the page source and re-read
2026-10-01 from its Markdown source. Marks: *doc* (in the documentation on the read date).

| Finish event | Holds the finish and returns a reason | Loop guard | Time limit | Project configuration |
| --- | --- | --- | --- | --- |
| `Stop` (doc) | `decision: "block"` + `reason`, or exit 2 with stderr; or a `prompt` or `agent` handler's `ok: false` (doc) | `stop_hook_active`; cap of 8 consecutive continuations (doc) | `timeout`, seconds, default 600 (doc) | `.claude/settings.json`, committable (doc); runs untrusted under `-p` (doc) |

- `Stop` fires "When Claude finishes responding"; `SubagentStop` is the same for a subagent.
- Exit code 2 on `Stop` "Prevents Claude from stopping, continues the conversation". JSON on
  stdout: top-level `"decision": "block"` with `reason`. `hookSpecificOutput.additionalContext`
  also keeps the conversation going "through the same loop protections as `decision: "block"`",
  labelled "Stop hook feedback" with no error notice.
- "The `stop_hook_active` field is `true` when Claude Code is already continuing as a result of a
  stop hook. Check this value or process the transcript to avoid blocking on a condition that will
  never resolve. Claude Code applies an 8-consecutive-continuation cap: after stop hooks have
  continued the turn eight times in a row, Claude Code overrides the next block and ends the turn."
  `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` raises it.
- `timeout`: "Seconds before canceling", default 600 for `command`, `http` and `mcp_tool` hooks.
- A model can judge the finish without a script: on `Stop` and `SubagentStop` a `prompt` handler
  (one model call that returns `{"ok", "reason", "impossible"}`, 30 s default) or an experimental
  `agent` handler (a subagent with Read, Grep and Glob, up to 50 turns, 60 s default) feeds an
  `ok: false` reason back as Claude's next instruction, and a prompt handler's `impossible: true`
  lets the turn end instead [as-of 2026-10-01].
- Configuration: `~/.claude/settings.json`; `.claude/settings.json`, which "can be committed to the
  repo"; `.claude/settings.local.json`; managed policy; a plugin's `hooks/hooks.json`; skill and
  subagent frontmatter. Entries merge across settings levels rather than replacing each other;
  `disableAllHooks` set outside managed settings cannot turn managed hooks off, and
  `allowManagedHooksOnly` blocks user, project, local and plugin hooks. Hooks from settings files,
  managed policy and plugins also fire inside subagents, with `agent_id` and `agent_type` in their
  input. Cloud sessions do not read the person's `~/.claude/settings.json` [as-of 2026-10-01].
- Input: `background_tasks` and `session_crons` "let hooks distinguish 'session is done' from
  'session is paused waiting for background work to wake it back up'". The working directory moves
  during a session (`CwdChanged` fires "When the working directory changes, for example when Claude
  executes a `cd` command"), so a hook's `cwd` need not be the project root: the input's `cwd`
  follows the agent into a worktree while `CLAUDE_PROJECT_DIR`, exported to the hook process, stays
  where the session started. `systemMessage` is a "Warning message shown to the user" and does not
  reach the model.
- Trust: "Claude Code checks workspace trust before it runs any hook from a settings file."
  Interactively, hooks from every settings file are held back "until you accept the workspace trust
  dialog". "`-p` or SDK session: Claude Code never shows the dialog and treats the folder as
  trusted, so hooks committed in a repository's `.claude/settings.json` run in a folder you've
  never trusted". `--settings '{"disableAllHooks": true}'` turns hooks off for a run. Frontmatter
  hooks in a project subagent run only after the trust dialog for the folder the agent file came
  from, and a `-p` session does not count (before v2.1.218 they could run untrusted); frontmatter
  hooks in a project skill follow the settings-file rule, so they register in an untrusted `-p` run.
  Before scripting `claude -p` over a repository someone else wrote, the page advises reviewing its
  `.claude/` settings, starting with `--bare`, or disabling hooks for the run.
- Where a handler runs: in the current directory; if that directory was deleted mid-session (a
  removed worktree, for example), command hooks run from the first that still exists of the
  session's start directory, the project root, the home directory and the temporary directory
  [as-of 2026-10-01].
- **Observed (O, one project, 2026-09-30).** A `Stop` hook committed to `.claude/settings.json` ran
  at the end of a turn and its message reached the transcript, including in a session started
  before the entry was added. A harness launched from a desktop app without the hook's command on
  its `PATH` shows a named hook error and holds nothing, and a hook that never fires fails silently.
  A hook also inherits no activated virtual environment, so a command that works in a developer's
  shell can fail inside the hook.
- **Cursor runs these hooks too.** With its third-party setting on, which is the default, Cursor
  loads the hooks in `.claude/settings.local.json`, `.claude/settings.json` and
  `~/.claude/settings.json` and runs a `Stop` hook as a follow-up message with no loop limit, which
  only Cursor's own format can set ([cursor.md](cursor.md#4-hooks)).

### 7.2 How a hook fails or blocks

- **Only exit 2 blocks by its code.** Exit 1, the usual Unix failure, is a non-blocking error: the
  action proceeds and the transcript shows a `<hook name> hook error` notice, so a hook that
  enforces a policy exits 2. A script that is missing or not executable exits 127 into the same
  non-blocking bucket ("a mistyped path in `settings.json` leaves the gate silently disabled").
  Stdout is parsed as JSON only when it starts with `{` and ends with `}`; an object that fails
  schema validation is a non-blocking error on every exit code but 2. Stderr from a hook that exits
  0 goes to the debug log only. A hook that reaches its `timeout` is cancelled and its output
  discarded, so a timed-out `PreToolUse` command hook lets the tool call continue ("don't count on a
  stalled hook to act as a gate"), while a timed-out `PreModelSwitch` hook blocks the switch;
  `WorktreeCreate` fails on any non-zero exit. Lab-guidance, hooks reference read 2026-09-29 and
  2026-10-01.
- A hook whose command is missing holds nothing (§7.1).
- What makes any harness's hook unsafe (privileges, trust once, environment, loops, fighting a
  legitimate stop) is in [cross-harness.md](cross-harness.md#92-what-makes-a-hook-unsafe-or-unusable).

### 7.3 The hook catalogue

- **Events** (hooks reference, read 2026-09-29 and 2026-10-01). 33 events: per session
  `SessionStart`, `SessionEnd` and `Setup` (for `--init-only`, or `--init` or `--maintenance` under
  `-p`); per turn `UserPromptSubmit`, `Stop` and `StopFailure`; on every tool call `PreToolUse` and
  `PostToolUse`; and `UserPromptExpansion`, `PermissionRequest`, `PermissionDenied`,
  `PostToolUseFailure`, `PostToolBatch`, `Notification`, `MessageDisplay`, `SubagentStart`,
  `SubagentStop`, `TaskCreated`, `TaskCompleted`, `TeammateIdle`, `InstructionsLoaded`,
  `ConfigChange`, `CwdChanged`, `DirectoryAdded`, `FileChanged`, `WorktreeCreate`,
  `WorktreeRemove`, `PreCompact`, `PostCompact`, `PreModelSwitch`, `PostModelSwitch`, `Elicitation`
  and `ElicitationResult`.
- **Handlers.** One of five types: `command`, `http`, `mcp_tool`, `prompt` or `agent`; twelve
  events take all five, including `Stop`, `SubagentStop` and `PreToolUse`. A `PreToolUse` hook can
  rewrite a tool call's input (`updatedInput`), not only allow or deny it.
- **Timeouts.** 600 s for `command`, `http` and `mcp_tool` (30 s on `UserPromptSubmit` and
  `PreModelSwitch`, 10 s on `MessageDisplay`), 30 s for `prompt`, 60 s for `agent`; `SessionEnd`
  hooks get 1.5 s, raised to the largest per-hook `timeout` in the settings files up to 60 s. All
  matching handlers run in parallel; a handler defined in several settings files runs once.
  Lab-guidance.
- **Enforcement.** A `PreToolUse` hook blocks an action whatever the model decides; instruction
  files cannot [harness-loading-coverage-9]. Hooks that touch the auto-mode classifier
  (`PermissionDenied`, `classifierContext`) are in
  [authority.md](../practices/agent-authorization.md#2-claude-codes-permission-layers-volatile-a2-a4).

## 8. Settings that run code or widen permissions

Read 2026-09-27 from the settings reference (2026-09-30 for `enabledPlugins` and
`extraKnownMarketplaces`, settable in any settings file). "Executes" means the key names a command
or program the harness runs.

| Project files | Executes | Tool servers | Enables all servers | Endpoint overrides | Permission bypass | Deny rules |
| --- | --- | --- | --- | --- | --- | --- |
| `.claude/settings.json`, `.mcp.json` | `hooks`, `statusLine`, `apiKeyHelper`, `awsAuthRefresh`, `awsCredentialExport`, `gcpAuthRefresh`, `otelHeadersHelper`, `fileSuggestion`, `enabledPlugins` | `mcpServers` | `enableAllProjectMcpServers`, `enabledMcpjsonServers` | `env.ANTHROPIC_BASE_URL`, `env.ANTHROPIC_BEDROCK_BASE_URL`, `env.ANTHROPIC_VERTEX_BASE_URL`, `forceLoginGatewayUrl`, `extraKnownMarketplaces` | `permissions.defaultMode`, `skipDangerousModePermissionPrompt`, `sandbox.filesystem.disabled` | `permissions.deny` |

- **Where a key counts.** The table lists keys the settings reference allows in settings files.
  Some are ignored from a project's own files: `sandbox.filesystem.disabled` and the sandbox's
  credential-mask keys are honored only from user, managed and `--settings` sources, and auto mode
  ignores `autoMode` and `defaultMode: "auto"` from project settings (§9) [as-of 2026-10-01]. Whether
  `skipDangerousModePermissionPrompt` and other `permissions.defaultMode` values take effect from a
  project's files was not checked (`UNVERIFIED`); review them in a change as if they do.
- **Personal files a project should never depend on:** `CLAUDE.local.md` and
  `.claude/settings.local.json`.
- **Exploited as CVEs.** Hooks, `.mcp.json` and base-URL overrides in `.claude/settings.json` were
  exploited as CVE-2025-59536 and CVE-2026-21852 ("The line between configuration and execution
  continues to blur"): the first let a project's `.mcp.json` servers start without the person's
  consent through `enableAllProjectMcpServers` and `enabledMcpjsonServers`, the second sent the API
  key to an attacker through `ANTHROPIC_BASE_URL`; a hook-based remote code execution was fixed
  before them under a GitHub advisory [instruction-file-security-authority-17; Check Point page
  re-read 2026-10-01]. Anecdote (incident reports).
- **The same files in published skills.** A study of published skills found one that shipped a
  `.mcp.json` with hard-coded credentials pointing at the attacker's workspace, another that used
  `PreToolUse` and `PostToolUse` hooks to watch every action and send results out, and others that
  told the platform to run with `--dangerously-skip-permissions` (arXiv 2602.06547, body read
  2026-10-01).
- Cursor reads these same files' hooks (§7.1). How the keys compare across harnesses is in
  [cross-harness.md](cross-harness.md#94-configuration-keys-that-execute-code-or-widen-permissions).

## 9. Sandbox and permissions

The classifier's decision order, its rules, how well it does and the hooks that touch it are in
[authority.md](../practices/agent-authorization.md#2-claude-codes-permission-layers-volatile-a2-a4); containment
and credentials across tools in [authority.md](../practices/agent-authorization.md#5-containment-a1). This
section holds what a harness row needs. Permission-modes and sandboxing pages [as-of 2026-10-01]. L.

- **Permission modes.** `default` (shown as Manual; reads only), `acceptEdits` (reads, file edits
  and common filesystem commands), `plan` (reads, plus classifier-approved commands where auto mode
  is available), `auto` (everything, with a background classifier reviewing commands and
  protected-directory writes), `dontAsk` (reads and pre-approved tools; anything that would prompt
  is denied, for locked-down CI) and `bypassPermissions` (everything; for isolated containers and
  VMs only). Deny rules block in every mode, `bypassPermissions` included. Writes to protected
  paths are never auto-approved outside `bypassPermissions`.
- **Auto mode** is the starting mode for interactive terminal and VS Code sessions from v2.1.283,
  on every plan and provider; under `-p` and in the Agent SDK a session starts in `default` where it
  fetches feature flags, and in `auto` (v2.1.285 and later) where it does not, such as on a
  third-party provider or with telemetry off. It returns to prompting after 3 blocks in a row or 20
  in a session; a boundary stated in conversation can be lost at compaction, so a deny rule is the
  hard guarantee. The classifier ignores `autoMode` and `defaultMode: "auto"` from project settings.
- **The sandbox** covers every Bash, PowerShell and Monitor command and its child processes, on
  macOS (the built-in Seatbelt framework), Linux and WSL2 (bubblewrap and socat, with an optional
  seccomp filter; on Ubuntu 24.04 and later an AppArmor profile must let `bwrap` create user
  namespaces); native Windows is not supported. Filesystem isolation and network isolation are
  separate layers; outbound traffic passes a proxy outside the sandbox with an allowlist of
  domains. A command that fails in the sandbox can retry unsandboxed through
  `dangerouslyDisableSandbox`; `allowUnsandboxedCommands: false` ("Strict sandbox mode" in
  `/sandbox`) removes that escape hatch, leaving only `excludedCommands` outside.
- **Turning isolation off.** `sandbox.filesystem.disabled: true` drops filesystem isolation while
  keeping the network layer; it is honored only from user settings, managed settings and
  `--settings`, never from a project's `.claude/settings.json` or `.claude/settings.local.json`,
  and once managed settings configure `sandbox.filesystem` only they can set it. With isolation off
  and commands auto-allowed, a command can write shell startup files, executables on `$PATH` or
  `~/.claude/settings.json` and widen its own access on the next run.
- **Credentials.** A `sandbox.credentials` entry with `"mode": "deny"` blocks a credential file or
  unsets a variable for sandboxed commands; `"mode": "mask"` (environment variables from v2.1.199)
  shows the command a per-session placeholder, the sentinel, and the proxy substitutes the real
  value on requests to the hosts in `injectHosts`, which requires `network.tlsTerminate` so the
  proxy sees request contents. AWS requests are signed over their contents, so the access key and
  secret are masked together and the proxy re-signs a detected SigV4 request; `decode: "jwt"`
  replaces a token with a structurally valid fake. File masking substitutes on Linux and WSL2; on
  macOS the file is blocked instead. Mask entries, `tlsTerminate` and plaintext injection are
  honored only from user, managed and `--settings` sources, never from a repository's settings
  files.

## 10. Session storage, plugins, models and routes

- **Session storage.** Checkpoint snapshots are kept for the 100 most recent checkpoints and go in
  the retention sweep about 30 days after the session last saved one (§4); `--bare` keeps hooks,
  skills, plugins, MCP servers, auto memory and `CLAUDE.md` out of a scripted call (§5). Where
  sessions, transcripts and memory live on disk, and what the retention sweep removes, are in
  [agent-workspace.md](../practices/agent-workspace.md#4-memory-and-session-history-on-one-machine-w3).
- **Plugins.** A plugin whose manifest and marketplace entry set no `version` is versioned by its
  source's commit (12 characters) for GitHub, URL and git-subdirectory sources. A project-scope
  plugin, checked into the repository, loads only after the workspace trust check that guards
  project allow rules ("Trusting a parent folder or running with `-p` isn't enough"); a project
  skills-directory plugin loads only from the `.claude/skills/` of the session's primary working
  directory and does not search parent directories, so a session launched from a subdirectory does
  not load a plugin at the repository root. Lab-guidance, plugins reference and loading pages
  [as-of 2026-10-01].
- **Claude 5 generation changes (2026-07-24).** More than 80% of Claude Code's own system prompt was
  removed; verification and code review moved into skills; tools are deferred and loaded through
  tool search; the Opus 5 delegation instruction is added only under the `claude_code` system-prompt
  preset; history stays append-only, as preserved thinking on Fable 5.1 and Opus 5.5 requires
  [claude-harness].
- **Other models through Claude Code.** Z.ai, DeepSeek, Moonshot, MiniMax and Alibaba document
  running their models inside Claude Code by setting `ANTHROPIC_BASE_URL`, the per-tier model
  variables, `CLAUDE_CODE_SUBAGENT_MODEL`, `CLAUDE_CODE_EFFORT_LEVEL` and
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW`. The model then receives Claude Code's system prompt,
  `CLAUDE.md` with its imports, rules, skills, memory and hooks exactly as Claude Code loads them.
  Moonshot warns that unset tier variables make subagent or summarisation calls fail silently. Z.ai
  maps `/effort` onto GLM effort: `none` becomes low, medium or high becomes high, xhigh and above
  become max (the default) [glm-harness, open-weight-harness, qwen-harness].
- **A gateway or cloud route changes what reaches the model.** LiteLLM forwards no client headers
  by default, so an `anthropic-beta` header reaches the provider only when
  `forward_client_headers_to_llm_api` is enabled, and `drop_params` drops OpenAI parameters a
  provider does not support instead of failing [as-of 2026-10-01]; one LiteLLM release refused
  `effort="max"` for Opus 4.7 on the client side before the request reached Anthropic's API
  (issue #25957, opened 2026-04-17 and closed as not planned on 2026-07-25, read through issue metadata on 2026-10-01). Claude on Microsoft Foundry has
  two hostings: models hosted on Azure return 400 by design for code execution, newer web search
  and fetch tool versions, Agent Skills, programmatic tool calling and the Files API, the Fable
  models are hosted only by Anthropic, and on either hosting Message Batches, the Models and Admin
  APIs, the advisor tool, Managed Agents and server-side fallback are unsupported; Claude Code
  detects an Azure-hosted deployment and adapts its feature set (Foundry page) [as-of 2026-10-01].
  Probe each feature on the actual route before relying on it. Lab-guidance and anecdote.

## 11. Observing what loaded, and surface signals

- `/context` and `/memory` show the loaded context; an interactive session prints when it reads
  `AGENTS.md` directly [harness-loading-coverage-3].
- The `InstructionsLoaded` hook logs which files loaded and why (memory page, from the detail of
  [agent-files-12]), except an `AGENTS.md` read through the "Project instructions" setting (§1).
- `claude doctor`, run from the shell, prints read-only installation and settings diagnostics
  without starting a session, settings-file validation errors and dropped keys among them; `/doctor`
  inside a session also lists unused skills, MCP servers and plugins against their context cost and
  flags slow hooks, and proposes fixes it applies only after confirmation (CLI reference, commands
  and debugging pages) [as-of 2026-10-01].
- **Rendering.** A reply's Mermaid block is shown as source in Claude Code's editor extension
  (observed), its desktop app and its CLI (open issues anthropics/claude-code#52517 and #14375)
  [as-of 2026-09-23].
- **Environment signals.** The editor extension sets `CLAUDECODE=1` and
  `CLAUDE_CODE_ENTRYPOINT=claude-vscode`. `AI_AGENT` carries the harness version
  (`claude-code_2-1-280_agent` was observed), so an exact match breaks on every release. A Claude
  Code extension session inside Cursor also carries Cursor's `CURSOR_LAYOUT`,
  `CURSOR_WORKSPACE_LABEL` and `VSCODE_PID`, and a terminal it opens may inherit `CURSOR_AGENT` (O,
  observed 2026-09-23). How to choose a surface from these is in
  [cross-harness.md](cross-harness.md#11-rendering-in-harness-surfaces).

## Sources

- Memory <https://code.claude.com/docs/en/memory> (2026-09-25, 2026-10-01); context window
  <https://code.claude.com/docs/en/context-window>; skills <https://code.claude.com/docs/en/skills>;
  sub-agents <https://code.claude.com/docs/en/sub-agents> (2026-09-25, 2026-10-01); security
  <https://code.claude.com/docs/en/security>; settings <https://code.claude.com/docs/en/settings>
  and <https://code.claude.com/docs/en/settings-reference> (2026-09-27, 2026-09-30); hooks
  <https://code.claude.com/docs/en/hooks> (2026-09-29, 2026-10-01).
- Read 2026-10-01 from their Markdown sources: worktrees <https://code.claude.com/docs/en/worktrees>,
  checkpointing <https://code.claude.com/docs/en/checkpointing>, headless
  <https://code.claude.com/docs/en/headless>, CLI reference
  <https://code.claude.com/docs/en/cli-reference>, commands <https://code.claude.com/docs/en/commands>,
  debugging your configuration <https://code.claude.com/docs/en/debug-your-config>, plugins
  reference <https://code.claude.com/docs/en/plugins-reference> and loading
  <https://code.claude.com/docs/en/plugins/loading>, Agent SDK features, Python reference and cost
  tracking <https://code.claude.com/docs/en/agent-sdk/claude-code-features>.
- Routes (2026-10-01): LiteLLM drop unsupported params
  <https://docs.litellm.ai/docs/completion/drop_params> and forwarding client headers
  <https://docs.litellm.ai/docs/proxy/forward_client_headers>; LiteLLM issue
  <https://github.com/BerriAI/litellm/issues/25957>; Claude in Microsoft Foundry
  <https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry>.
- Read 2026-10-01: MCP <https://code.claude.com/docs/en/mcp> (tool search); sandboxing
  <https://code.claude.com/docs/en/sandboxing>; permission modes
  <https://code.claude.com/docs/en/permission-modes>; Agent SDK structured outputs
  <https://code.claude.com/docs/en/agent-sdk/structured-outputs> and session storage
  <https://code.claude.com/docs/en/agent-sdk/session-storage>; npm and PyPI registries for
  `@anthropic-ai/claude-code`, `@anthropic-ai/claude-agent-sdk` and `claude-agent-sdk`.
- Security: Check Point, CVE-2025-59536
  <https://research.checkpoint.com/2026/rce-and-api-token-exfiltration-through-claude-code-project-files-cve-2025-59536/>
  (2026-02-25, re-read 2026-10-01); malicious skills, arXiv 2602.06547 (2026-10-01).
- Rendering issues <https://github.com/anthropics/claude-code/issues/52517> and
  <https://github.com/anthropics/claude-code/issues/14375> (2026-09-23).

Checks defined here (verdict PASS, read 2026-09-25):
- [chk-claude-skills] Skills page: "the combined `description` and `when_to_use` text is
  truncated at 1,536 characters in the skill listing", the model-facing listing; 250 characters is
  the `/skills` menu.
- [chk-claude-memory] Memory page: "Claude Code loads a CLAUDE.md file of up to 4 MiB in full and
  skips a larger file."
- [chk-claude-subagents] Sub-agents page: "As of v2.1.198, Explore inherits the main conversation's
  model instead of always running on Haiku", capped at Opus on the Claude API.

Evidence ids in brackets resolve in [`../_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl).
