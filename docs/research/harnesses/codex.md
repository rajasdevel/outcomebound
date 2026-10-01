---
last_checked: 2026-09-25
volatility: VOLATILE (Codex CLI releases weekly; loader, hooks, sandbox and app-server change between them)
sources:
  - https://learn.chatgpt.com/docs/agent-configuration/agents-md
  - https://github.com/openai/codex/blob/main/codex-rs/core/src/agents_md.rs
  - https://raw.githubusercontent.com/openai/codex/rust-v0.157.0/codex-rs/models-manager/models.json
  - https://learn.chatgpt.com/docs/hooks
  - https://learn.chatgpt.com/docs/config-file/config-reference
  - https://learn.chatgpt.com/docs/permissions
  - https://learn.chatgpt.com/docs/agent-approvals-security
  - https://learn.chatgpt.com/docs/app-server
  - https://learn.chatgpt.com/docs/cli/reference
---

# Codex (CLI and app)

Re-check when a Codex release changes how it loads `AGENTS.md`, caps the chain, runs hooks, gates
trust or protects paths in its sandbox; before relying on a field name; and by 2026-12-27, the
re-check date `adapters/harnesses.json` carries.

What Codex loads and in what order, its cap, skills, compaction, trust, hooks, the configuration
keys that run code, its sandbox's protected paths, how to isolate a run and how to see what it
loaded. For anyone placing text or hooks where Codex will load them, running Codex as an agent or a
reviewer, or re-checking the `codex` row of `adapters/harnesses.json`. The comparison with other
harnesses, the key findings (H1–H12) and the evidence classes are in
[cross-harness.md](cross-harness.md); Codex's automatic approval review is in
[authority.md §3](../practices/agent-authorization.md#3-codexs-automatic-approval-review-volatile-a3).

The version is 0.157.0 (2026-09-25); the `AGENTS.md` docs and loader source (last commit
2026-09-16) were read 2026-09-25 [openai-harness, harness-loading-coverage-18,
harness-loading-coverage-19]. A claim read on a later day carries its date.

## 1. Instruction files and precedence

- **Files.** Global: `~/.codex/AGENTS.override.md`, otherwise `AGENTS.md`, the first non-empty
  (`CODEX_HOME` relocates it). Project: from the git root down to the working directory, each
  directory contributes at most one of `AGENTS.override.md`, `AGENTS.md` or a
  `project_doc_fallback_filenames` entry. Files are concatenated root-down, so deeper files come
  later and "effectively override" earlier ones. The chain is built once per run or TUI session.
- **Injection.** Each file becomes its own user-role message headed
  `# AGENTS.md instructions for <directory>`, placed near the top of history before the user's
  prompt; OpenAI says the model "has been trained to closely adhere to these instructions".
- **Where the files rank.** They arrive as user-role messages, and the base instructions rank the
  user above skills and external files [openai-harness, openai-f2] (§5).
- **Code review.** Codex code review reads a `## Code Review Rules` section in the nearest
  `AGENTS.md`.
- **Origins.** Codex CLI launched (2025-04-16) merging `~/.codex/instructions.md`, a root `codex.md`
  and a `codex.md` in the working directory; it moved to `AGENTS.md` on 2025-05-10. `AGENTS.md` was
  published as an open format in August 2025 and donated to the Linux Foundation's Agentic AI
  Foundation on 2025-12-09 [openai-harness]. The loader moved from `project_doc.rs` to
  `agents_md.rs`.

## 2. Cap

- Loading stops at a combined `project_doc_max_bytes`, 32 KiB by default; empty files are skipped,
  and the file that crosses the limit is truncated with the warning "project doc exceeds remaining
  budget; truncating" [harness-loading-coverage-19]. The docs' remedy is to raise the cap or split
  content across nested directories [openai-f20].
- Because the file is cut at its end, the most specific file, and a block an installer appends
  after a project's own `AGENTS.md` text, is the first text lost when the chain crosses the cap;
  text that must load sits near the top of the root file, and an installer can report the file's
  size against the cap (inference from the documented truncation). In one adopting repository (A),
  the root `AGENTS.md` with appended blocks came to about half of the 32 KiB; moving procedure and
  state into the guides that own each topic cut it by a third.

## 3. Skills

- Since 2025-12-19, in the Agent Skills format: `.agents/skills` in every directory from the
  working directory up to the repository root, `$HOME/.agents/skills`, `/etc/codex/skills` and
  bundled system skills.
- Name, description and path are listed, capped at 2% of the context window or 8,000 characters,
  with descriptions shortened when there are many [openai-14, openai-f21].
- A skill installed in `.agents/skills` for Codex is installed for Amp, Cursor, Kimi Code, Mistral
  Vibe, Antigravity and Gemini CLI too
  ([cross-harness.md](cross-harness.md#6-skills-discovery-and-listing)).

## 4. Goals, delegation and compaction

- **Goals.** `/goal` (since 0.128.0, 2026-04-30) persists an outcome with a completion check: "what
  should be true, how success should be checked, and what constraints must stay intact"
  [openai-f24].
- **Delegation.** Local Codex delegates to subagents when the user asks or when `AGENTS.md` or a
  skill requests it; Ultra mode enables proactive delegation [openai-f22]. Enter steers the current
  turn; Tab queues a message.
- **Compaction.** After compaction the latest user message steers the task and does not replace the
  objective (base instructions). In OpenAI's RL training runs, compaction summaries included
  instructions "to invent missing data without disclosing it and to hide failures", flagged in
  2.15% of GPT-5.6 Sol and 0.27% of GPT-6 Astra summaries [chk-codex-models, openai-f16].
- **Hooks around compaction.** `PreCompact` and `PostCompact` stop before or after compacting on
  `continue: false`, and ignore plain stdout; a hook can keep each summary but cannot edit it
  (hooks page, read 2026-09-29 and 2026-10-01).

## 5. Per-model base instructions

From `codex-rs/models-manager/models.json` at `rust-v0.157.0` [chk-codex-models, openai-harness].

- GPT-6 Astra: default reasoning low, verbosity low, context window 272,000 (maximum 872,000); Sol
  and Luna: default reasoning medium.
- The instructions rank user instructions above skills and external files; when the model asks
  permission it must say which `SKILL.md`, `AGENTS.md`, memory or auto-review block caused it; after
  compaction the latest user message steers the task without replacing the objective; testing is
  calibrated.
- All three tiers carry "Do not treat exceptions to requirements in local markdown and skill files
  as automatically requiring user approval." Only Astra carries the "can you… / I want to… / help
  me…" line (treat such requests as instructions to act) and "If a skill does not explicitly
  require approval, default to proceeding within the user's authorized scope rather than asking
  for confirmation based on an inferred requirement." A project line repeating any of these
  duplicates what the model already loads.
- **Effort values.** `codex exec --help` lists no reasoning-effort values; the bundled model catalog
  (`codex debug models --bundled`, the catalog that ships with the binary) lists the efforts each
  model accepts, so a runner can check an effort without a model call (A, read locally 2026-09-27,
  version not recorded; the subcommand documented in the CLI reference, read 2026-10-01).

## 6. Trust

- In an untrusted project only user instructions load [harness-loading-coverage-19].
- Marking a project untrusted also makes commands need approval unless an execution-policy rule
  allows them, and disables project-local configuration [instruction-file-security-authority-20].
- Project configuration loads only in a trusted project and ignores the provider, notification,
  approval and sandbox keys (config reference) [as-of 2026-09-27].
- Project hooks additionally need per-hook review, by hash (§7).

## 7. Hooks

### 7.1 The finish hook

Source: <https://learn.chatgpt.com/docs/hooks> (<https://developers.openai.com/codex/hooks>
redirects there with HTTP 308), read 2026-09-29 from the page source and re-read 2026-10-01 from
its Markdown source. Marks: *doc* (in the documentation on the read date), *report* (a third-party
record, named), `UNVERIFIED`.

| Finish event | Holds the finish and returns a reason | Loop guard | Time limit | Project configuration |
| --- | --- | --- | --- | --- |
| `Stop` (doc) | `decision: "block"` + `reason` becomes a new user prompt, or exit 2 with stderr (doc) | `stop_hook_active`; no cap documented (`UNVERIFIED`) | `timeout`, seconds, default 600 (doc) | `.codex/hooks.json` or inline `[hooks]` in `.codex/config.toml`, after project trust and per-hook review (doc); an open report says project hooks do not fire (report) |

- `Stop`: "When a turn is active on the main thread and a model finishes responding, before the turn
  ends." Also `SubagentStop`.
- `Stop` "expects JSON on `stdout` when it exits `0`. Plain text output is invalid for this event."
  `{"decision": "block", "reason": ...}` "tells Codex to continue and automatically creates a new
  continuation prompt that acts as a new user prompt, using your `reason` as that prompt text." "You
  can also use exit code `2` and write the continuation reason to `stderr`." `continue: false` from
  any matching hook takes precedence.
- `stop_hook_active`: "Whether this turn was already continued by `Stop`". No cap on consecutive
  continuations is documented.
- "`timeout` is measured in seconds and defaults to `600`." "Multiple matching command hooks for the
  same event are launched concurrently."
- `systemMessage` is "Surfaced as a warning in the UI or event stream". Hooks run in the session's
  working directory, which the input's `cwd` names; no project-root environment variable is
  documented.
- **Output limit.** Codex limits each model-visible hook-output message to roughly 2,500 tokens;
  past it, the full text is saved under `<temp_dir>/hook_outputs/<session_id>/<uuid>.txt` and the
  model receives a head-and-tail preview with that path ("spilling"). A handler's
  `additionalContextLimit` changes the threshold for `additionalContext` only (`0` passes it whole),
  while "tool feedback and continuation prompts keep the default limit", so a `Stop` hook's `reason`
  reaches the model as about 2,500 tokens at most. Because oversized output is written to disk, the
  page advises against returning secrets in hook output [as-of 2026-10-01].
- **Configuration.** `~/.codex/hooks.json`, `<repo>/.codex/hooks.json`, or an inline `[hooks]` table
  in the `config.toml` of the same layer; plugins. "Project-local hooks load only when the project
  `.codex/` layer is trusted." "Before a non-managed hook can run, Codex requires you to review and
  trust the exact hook definition. Codex records trust against the hook's current hash, so new or
  changed hooks are marked for review and skipped until trusted." `/hooks` reviews them. "For
  one-off automation that already vets hook sources outside Codex",
  `--dangerously-bypass-hook-trust` runs enabled hooks without persisted hook trust for that
  invocation (read 2026-09-29 and 2026-10-01). The `hooks` feature is on by default; `codex_hooks`
  is a deprecated alias. A Codex maintainer's comment (2026-04-15) says a custom `hooks.json` path
  through a top-level `hooks` key in `config.toml` is not supported (report).
- **Possibly unusable.** openai/codex#17532, "codex_hooks do not fire in interactive sessions when
  configured via repo-local .codex/config.toml", opened 2026-04-12, still open on 2026-10-01 with
  eight comments, the last on 2026-05-21. A Codex maintainer could not reproduce it on 2026-04-15
  with `.codex/hooks.json` and a blocking `Stop` hook; later reporters say it holds on 0.128.0 and,
  on 2026-05-21, on 0.132.0 in both `codex exec` and the interactive TUI with trust granted. One
  reporter's `codex exec` run used `--dangerously-bypass-hook-trust`, the documented flag above, with
  a project trust level pre-seeded in `config.toml`. Which account is right is `UNVERIFIED`.

### 7.2 The hook runtime

Hooks page, read 2026-09-24, 2026-09-29 and 2026-10-01. Lab-guidance.

- **Events.** `SessionStart`, `SessionEnd` (main thread only), `SubagentStart`, `SubagentStop`,
  `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`,
  `PostCompact`, `Stop` and `Interrupt` (main thread only; one-second default timeout, configurable
  from one to three seconds; it cannot prevent the interruption).
- **Layers add up.** "If more than one hook source exists, Codex loads all matching hooks.
  Higher-precedence config layers don't replace lower-precedence hooks", so a project's entry runs
  beside the user's, never instead of it, and a layer holding both `hooks.json` and an inline
  `[hooks]` table is merged with a startup warning. Managed hooks (system, MDM, cloud,
  `requirements.toml`) are trusted by policy and cannot be disabled from `/hooks`.
- **Async hooks.** A command hook with `async: true` runs in the background, up to eight at once per
  session (more wait), finishing in any order; it cannot block, approve or rewrite what triggered
  it, its output arrives at the next safe point, and unfinished ones are cancelled when the session
  ends.
- **What tool hooks see.** Shell commands, `apply_patch`, MCP tools and most local function tools,
  but not hosted tools such as web search, and "some specialized tool paths can opt out": "Treat
  tool hooks as a useful guardrail, not a complete enforcement boundary." A blocking `PostToolUse`
  "doesn't undo the completed Bash command"; Codex replaces the tool's result with the hook's
  feedback, so the model sees the hook's text, not the output.
- **Attribution.** "Subagent hooks use the parent session id", and only `SubagentStart` and
  `SubagentStop` carry an `agent_id`, so a tool event cannot be attributed to one subagent;
  `transcript_path`'s format "isn't a stable interface".
- **Concurrency and format.** Matching hooks launch concurrently, `Stop` accepts only JSON on
  stdout, and model-visible output past about 2,500 tokens is cut to a preview with the full text
  written to disk, so a hook returns no secrets (§7.1).
- What makes any harness's hook unsafe is in
  [cross-harness.md](cross-harness.md#92-what-makes-a-hook-unsafe-or-unusable); trust by hash covers
  the entry, not the program it calls.

## 8. Settings that run code or widen permissions

Read 2026-09-27 from the config reference. "Executes" means the key names a command or program the
harness runs.

| Project files | Executes | Tool servers | Enables all servers | Endpoint overrides | Permission bypass | Deny rules |
| --- | --- | --- | --- | --- | --- | --- |
| `.codex/config.toml`, `.codex/hooks.json` | `hooks` | `mcp_servers` | — | — (project config ignores provider keys) | — (project config ignores approval and sandbox keys) | not settled |

Codex's TOML configuration can hold an inline table or a multi-line string that a line-by-line
reader cannot settle; a lexical scan reports those as `UNVERIFIED`.

## 9. Sandbox, permissions and isolated runs

- **Protected paths.** "In the default `workspace-write` sandbox policy, writable roots still include
  protected paths": `<writable_root>/.git` is read-only "whether it appears as a directory or file",
  and where `.git` is a pointer file (`gitdir: …`, as in a linked worktree) the resolved Git
  directory is read-only too; `<writable_root>/.agents` and `<writable_root>/.codex` are read-only
  when they exist as directories; and "Protection is recursive, so everything under those paths is
  read-only" (approvals and security page, read 2026-10-01; no version is stated). The built-in
  `:workspace` permission profile likewise keeps `.codex/` and `.git/` read-only (permissions page,
  same day).
- **What follows.** Under `workspace-write` an agent cannot commit unless the repository's `.git` is
  added as a writable directory, and cannot write anything a project keeps under `.agents/`
  (skills, working files, handoffs, worktrees nested there) unless that folder is added too.
- **Observed (O).** With `--add-dir <repository>/.git`, a probe's `git commit` exited 0 (codex-cli
  0.156.1, gpt-6-sol at low effort, 2026-09-24); without it, a run cannot commit, so an evaluation
  fixture that needs commits measures the sandbox rather than the agent. Under codex-cli 0.159.2's
  default `workspace-write` sandbox, writing `.agents/work` failed with "Operation not permitted";
  started with `--add-dir <repository>/.agents`, the same write succeeded (gpt-6.1-sol at medium
  effort, 2026-10-01, one probe each way).
- **Automatic approval review.** `approvals_reviewer = "auto_review"` sends eligible approval
  requests to a reviewer agent instead of the person; how it decides, its circuit breaker and how
  often it approves are in [authority.md §3](../practices/agent-authorization.md#3-codexs-automatic-approval-review-volatile-a3).
- **As a read-only reviewer.** `codex exec -s read-only` against an isolated worktree reviews
  without writing; set the model with `-m` and the effort with `-c model_reasoning_effort=<level>`,
  since `-p` is `--profile`, a named configuration profile (CLI reference, read 2026-10-01). In that
  mode a review cannot run tests or create fixtures (no writable temporary directory, no package
  cache), so its acceptance re-runs read `UNVERIFIED` and its findings rest on reading the source
  (O, codex-cli 0.154.0, gpt-6-astra at high effort, 2026-09-11). A reviewer that must run checks
  needs a disposable writable copy.
- **Environment signals.** Codex sets `CODEX_SANDBOX` (seen as `seatbelt`, beside
  `CODEX_SANDBOX_NETWORK_DISABLED=1`) only on a command it runs under a sandbox, so it does not tell
  the Codex app, IDE extension and CLI apart (O, observed 2026-09-23).

## 10. Session storage and isolating a run

- `--ephemeral` persists no session files, `--ignore-user-config` skips `$CODEX_HOME/config.toml`
  (authentication still uses `CODEX_HOME`), `--ignore-rules` skips user and project
  execution-policy `.rules` files, and `-c features.memories=false` turns memories off (CLI
  reference, read 2026-10-01).
- They do not keep out everything under `$CODEX_HOME`: Codex still read a user-level agent role
  definition from `~/.codex/agents/` in runs made with all four flags (O, codex-cli 0.158.0 and
  0.159.0, 2026-09-29 and 2026-09-30). Whether a well-formed role there reaches the model is
  `UNVERIFIED`; keep that directory empty for a run that must be isolated.
- Where Codex keeps threads and memory on disk, and how they behave when a repository moves, are in
  [agent-workspace.md §4](../practices/agent-workspace.md#4-memory-and-session-history-on-one-machine-w3).

## 11. Observing what loaded

- **Loading.** The app-server documents a loading channel: "`thread/start`, `thread/resume`, and
  `thread/fork` return `instructionSources`, an array of loaded instruction-file paths", each in
  "its source environment's native absolute syntax" (app-server page, read 2026-09-24 and
  2026-10-01). It reaches a client that drives Codex through the app-server, not a hook or a plain
  CLI session. `codex debug prompt-input` renders "the exact model-visible prompt input list as
  JSON", which the CLI reference suggests for "debugging instruction discovery" (read 2026-10-01;
  not tried). Lab-guidance. These two show loading.
- **Discovery.** `skills/list` on the app-server lists skills for one or more working directories,
  and `/skills` lists them in a session; a listing shows that Codex found a skill, not that any text
  reached the model.
- Which Codex version first returns `instructionSources` is `UNVERIFIED`: probes of Codex CLI
  0.153.4's app-server ended before `initialize` returned (O, 2026-09-09) and settle nothing.
- **Rendering.** A reply's Mermaid block is drawn in the Codex desktop app (observed) and shown as
  source in the Codex CLI, where a text renderer merged upstream on 2026-09-16 is not yet called;
  unknown for the Codex IDE extension [as-of 2026-09-23].

## Sources

- `AGENTS.md` <https://learn.chatgpt.com/docs/agent-configuration/agents-md>; loader source
  <https://github.com/openai/codex/blob/main/codex-rs/core/src/agents_md.rs> (last commit
  2026-09-16); `models.json` at `rust-v0.157.0`
  <https://raw.githubusercontent.com/openai/codex/rust-v0.157.0/codex-rs/models-manager/models.json>
  [chk-codex-models]; goals
  <https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex.md>.
- Config reference <https://learn.chatgpt.com/docs/config-file/config-reference> and permissions
  <https://learn.chatgpt.com/docs/permissions> (2026-09-27, 2026-10-01); hooks
  <https://learn.chatgpt.com/docs/hooks> (2026-09-29, 2026-10-01); issue
  <https://github.com/openai/codex/issues/17532> (2026-09-29, 2026-10-01); app-server
  <https://learn.chatgpt.com/docs/app-server> (2026-09-24, 2026-10-01); CLI reference
  <https://learn.chatgpt.com/docs/cli/reference> (2026-10-01); approvals and security
  <https://learn.chatgpt.com/docs/agent-approvals-security> (2026-09-25, 2026-10-01; the
  developers.openai.com address redirects there).

Checks defined here (verdict PASS, read 2026-09-25):
- [chk-codex-models] Codex `models.json` at `rust-v0.157.0`: the GPT-6 base-instruction lines in §5.

Evidence ids in brackets resolve in [`../_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl).
Own observations (O) are this project's probe and run records: the sandbox probes (2026-09-24,
2026-10-01), the read-only review (2026-09-11), the isolation runs (2026-09-29, 2026-09-30), the
app-server probes (2026-09-09) and one session's environment (2026-09-23).
