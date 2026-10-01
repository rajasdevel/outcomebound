---
last_checked: 2026-09-25
volatility: VOLATILE (harnesses change how they load, cap, compact and run hooks monthly; the adoption survey, the interview and the direction are dated and MONITOR)
sources:
  - https://agents.md/
  - https://code.claude.com/docs/en/memory
  - https://learn.chatgpt.com/docs/agent-configuration/agents-md
  - https://cursor.com/docs/rules
  - https://geminicli.com/docs/cli/gemini-md/
  - https://ampcode.com/docs/customize/agents-md
  - https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/configuration.md
  - https://blog.jetbrains.com/research/2026/08/ai-coding-agent-adoption-2026/
  - https://www.youtube.com/watch?v=IZAlq-V19U8
  - https://modelcontextprotocol.io/specification/2026-07-28/changelog
---

# Coding harnesses compared: what they load, cap, compact and run

Re-check when a harness release changes how it loads, caps or compacts instruction files, runs hooks
or gates trust; before relying on a row's field name; and in any case by 2026-12-27, the re-check
date `adapters/harnesses.json` carries.

What every coding harness shares and where they differ: which instruction files each loads and how
precedence works, the caps and what happens past them, how skills are listed, what survives
compaction, which trust gates decide whether project files load, what hooks offer at the agent's
finish and which configuration keys run code, how to see what loaded, and where harnesses are
heading. For anyone placing text or hooks where several harnesses will load them, auditing a
project's harness configuration, or comparing harness rows. The facts for one harness, in full and
with their sources, are in its own file:

| Harness | File |
| --- | --- |
| Claude Code (and the Agent SDK) | [claude-code.md](claude-code.md) |
| Codex (CLI and app) | [codex.md](codex.md) |
| Cursor | [cursor.md](cursor.md) |
| Gemini CLI | [gemini-cli.md](gemini-cli.md) |
| Amp | [amp.md](amp.md) |
| Pi | [pi.md](pi.md) |
| GitHub Copilot and VS Code, Antigravity, Grok Build, ZCode, Qwen Code, Kimi Code, DeepSeek Harness, OpenCode, Cline, Mistral Vibe, Windsurf, Kiro, Junie, OpenHands, Spec Kit, Muse Code | [others.md](others.md) |

What lets an agent act once loaded (permission modes, classifiers, automatic reviewers, grants) is
in [authority.md](../practices/agent-authorization.md); where agents keep their work and sessions is in
[agent-workspace.md](../practices/agent-workspace.md). Every fact carries its source and the day it
was read; a claim read later than `last_checked` carries its date.

## Key findings

**H1. A root `AGENTS.md` is the one file every checked harness can be made to read.** Sixteen were
checked: Claude Code, Codex, Grok Build, Cursor, ZCode, Qwen Code, Gemini CLI, Antigravity, Kimi
Code, DeepSeek Harness, OpenCode, Amp, Pi, GitHub Copilot, Cline and Mistral Vibe. Two need a
condition: Claude Code reads it, under its default setting, only when no `CLAUDE.md`,
`.claude/CLAUDE.md` or `CLAUDE.local.md` exists in the working directory or any directory above it
(or through an `@AGENTS.md` import), and Gemini CLI only through `context.fileName`. Lab-guidance
(vendor docs and source) (L) [claude-harness, gemini-harness, harness-loading-coverage-3,
chk-amp-agents, chk-pi, chk-copilot, chk-cline, chk-vibe].

**H2. Everything beyond the root file is optional in some harness.** Imports, nested files,
path-scoped rules and local override files did not converge: ZCode reads no nested file and
expands no import; Kimi Code ignores `CLAUDE.md` entirely; DeepSeek Harness interprets no
`@path`; OpenCode prefers `AGENTS.md` where Claude Code prefers `CLAUDE.md`. Text that must load
belongs in the root `AGENTS.md`. L [glm-f22, open-weight-f3, harness-loading-coverage-28].

**H3. "Precedence" means different things.** Claude Code concatenates every layer with no conflict
resolution ("Claude may pick one arbitrarily"); Gemini CLI concatenates and tells the model that
subdirectory files outrank the workspace root, extensions and global files; Codex concatenates
root down, so deeper files come later and effectively win; Cursor merges and lets earlier sources
(Team, then Project, then User) win, while between nested `AGENTS.md` files the more specific
wins. No harness in the evidence ranks instruction files above the user's own instructions. L
[harness-loading-coverage-10, harness-loading-coverage-12, harness-loading-coverage-17,
gemini-harness, open-weight-harness, grok-f2, openai-f2].

**H4. The tightest enforced caps are Antigravity's 24,000 bytes per rule file and Codex's 32 KiB for
the whole chain.** Codex truncates the file that crosses the limit, so the most specific files are
cut, and text appended at the end of a long `AGENTS.md` is the first lost. Claude Code skips a
`CLAUDE.md` over 4 MiB; DeepSeek Harness drops broader files past 65,536 bytes; Kimi Code only warns
above 32 KiB. L, and source [harness-loading-coverage-19, harness-loading-coverage-21,
chk-claude-memory, open-weight-f4].

**H5. Skill listings are truncated, and the model sees only the listing until it invokes a skill.**
Claude Code cuts a skill's combined `description` and `when_to_use` at 1,536 characters in the
model's listing (its `/skills` menu shows 250); Codex shortens descriptions to fit 2% of context
or 8,000 characters; ZCode injects the first 250 characters each turn and drops a skill whose
description exceeds 1,024. L [chk-claude-skills, openai-14, glm-f23].

**H6. Compaction keeps some layers and summarises others away.** In Claude Code the root
`CLAUDE.md`, unscoped rules and auto memory are re-injected; path-scoped rules and nested files
are not; each invoked skill keeps its first 5,000 tokens (25,000 in all, oldest dropped first).
L [harness-loading-coverage-7, harness-loading-coverage-8].

**H7. Some readers load nothing.** Claude Code's built-in Explore and Plan subagents skip
`CLAUDE.md`; Kiro's custom agents skip steering unless listed; ZCode's Explore subagent skips
`AGENTS.md`; an untrusted Codex project gets only user instructions; Cursor's rules reach only
its agent chat, not Tab completion, Inline Edit or Bugbot reviews. A delegate's brief must
carry the bounds itself. L [capability-tier-readers-13, harness-loading-coverage-23,
glm-harness, harness-loading-coverage-19; Cursor's rules help page, read 2026-10-01].

**H8. Project configuration beside the instruction files is executable.** Hooks, tool-server
definitions, "enable all servers" switches, API endpoint overrides and permission bypasses sit in
committed files (`.claude/settings.json`, `.mcp.json`, `.codex/hooks.json`,
`.gemini/settings.json`, `.cursor/hooks.json`, `.amp/settings.json`, `.pi/settings.json`), and
such files were exploited as CVEs. One harness's file can run in another: Cursor loads Claude
Code's hooks from `.claude/settings.json` by default. Anecdote (incident reports) (A) and L
[instruction-file-security-authority-17, instruction-file-security-authority-19; Cursor's
third-party hooks page, read 2026-10-01].

**H9. Four harnesses offer a finish hook as a command in a JSON file:** Claude Code, Codex and
Gemini CLI hold the finish and hand a reason back to the model; Cursor lets the loop end and submits
the reason as the next user message, and runs a Claude Code `Stop` hook the same way with no loop
limit, which such a hook cannot set. Claude Code also takes a model prompt or a subagent as a `Stop`
handler. Amp and Pi expose the finish only to a TypeScript plugin or extension. Each runs with the
person's privileges from a file a pull request can change, and Claude Code runs committed hooks
untrusted in its non-interactive mode. L (docs read 2026-09-29 and 2026-10-01).

**H10. A person running several harnesses is the common case.** In a vendor-run survey of more than
15,000 developers (August 2026), at-work adoption was Claude Code 39%, GitHub Copilot 21%, Codex
16%, Cursor 12%, JetBrains AI or Junie 9%, OpenCode 7% and Antigravity 6%; in a self-selected
survey of 906 readers, 70% used two to four AI tools at once. Measured (surveys) (M)
[harness-loading-coverage-2, harness-loading-coverage-1].

**H11. Harness builders expect the instruction file to shrink and the harness to become
programmable.** One Claude Code team member predicts the project instruction file goes away "in the
limit" and advises adding an entry only for a failure that keeps recurring; harnesses gain
in-process "mods", forked side agents and artifact surfaces ([§13.1](#131-one-practitioners-account-t1t7)
T1, T5). A and F (one practitioner, vendor).

**H12. What loaded can be read from the harness, Codex included.** Claude Code shows it in `/context`
and through the `InstructionsLoaded` hook (which does not fire for an `AGENTS.md` it reads
directly); Codex's app-server returns `instructionSources`, the loaded instruction files, when a
thread starts, resumes or forks, and `codex debug prompt-input` renders the model-visible input.
Three earlier probes of the app-server failed before they reached it, so they settled nothing.
L (docs read 2026-10-01) and own probes (O, 2026-09-09).

## 1. Scope, method and evidence

- **What was read.** Each harness's own documentation, and its source code where published, on
  2026-09-25 (instruction loading and skills), 2026-09-27 (configuration keys), 2026-09-29 (hooks)
  and 2026-09-30 (two Claude Code settings keys); the pages each harness file names were re-read on
  2026-10-01, from their Markdown sources, to check the facts added or corrected that day. Facts
  from the 2026-09 evidence sweep resolve by id in
  [`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl); each record there carries its claim
  as fact-checked, a verbatim quote, the URL and the date. `[chk-…]` ids are facts re-checked at
  their source and listed under each file's Sources. Harness versions are the ones the sources
  named on the read date. A few specifics are marked as coming from a record's detail: the note a
  sweep reader recorded beside the claim (the record's `detail` field), which the fact-check did not
  separately verify.
- **Evidence classes**, as across this library: lab-guidance (L) is a vendor's documentation or
  source, and states what the product does, not what it achieves; measured (M) is a survey or
  benchmark; anecdote (A) is a single observed run, an incident report or one person's account;
  forecast (F) is a prediction; own record (O) is an observation from OutcomeBound's own runs or
  probes. `UNVERIFIED` marks what no source settled.
- **Hook facts** use three marks: *doc* (in the harness's own documentation on the read date, at the
  URL given), *report* (a third-party record, named) and `UNVERIFIED` (no documentation found, or
  documentation and reports disagree). Documentation pages carry no version; version numbers are
  the reports' own.
- **Where these facts are also kept as data.** OutcomeBound's harness table,
  `adapters/harnesses.json`, records a row per harness it knows (claude-code, codex, amp, gemini,
  cursor, and pi, which adopt refuses until its route is verified), each with a `verified_on` date
  and a `recheck_on` date of 2026-12-27.
- **What a harness row needs to record** for a loading or audit check to use it: the files read and
  their order; which files hide `AGENTS.md`; imports and their depth; path-scoped and nested files;
  override files, marked as the project's or one person's; each cap with its value, unit (bytes,
  tokens or characters), over-limit behaviour (truncate, skip or demote to a pointer), scope (per
  file, combined, per skill after compaction, per description) and which file it cuts; how
  precedence works (concatenation, later file wins, closest file wins); trust gating; what survives
  compaction; whether helpers load the files; the configuration files and keys that hold hooks,
  tool servers, permissions and bypasses; and the command a person runs to see what loaded. A cap
  whose over-limit behaviour is undocumented cannot be checked; a row missing its precedence reads
  "loading order `UNVERIFIED`"; a row past its re-check date reads `UNVERIFIED` wherever it is used;
  where tokens must be estimated, bytes/4 is labelled an estimate.

## 2. The harnesses at a glance

| Harness | Root instruction file | Also reads | Nesting and imports | Enforced cap | Skills directory |
| --- | --- | --- | --- | --- | --- |
| [Claude Code](claude-code.md) | `CLAUDE.md` | `AGENTS.md` and `.claude/AGENTS.md` only with no `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` at or above the working directory (default setting), or via `@AGENTS.md` | every file root to cwd, concatenated; subdirectories on demand; `@path` four hops; `.claude/rules` with `paths:` | 4 MiB per file (skipped) | `.claude/skills` |
| [Codex](codex.md) | `AGENTS.md` | `AGENTS.override.md`, fallback names | one file per directory, git root to cwd, concatenated | 32 KiB combined (truncated) | `.agents/skills` |
| [GitHub Copilot](others.md#github-copilot-and-vs-code) | `AGENTS.md` (nearest wins) | a single root `CLAUDE.md` or `GEMINI.md`; `.github/copilot-instructions.md` | nested `AGENTS.md` anywhere | none for review since 2026-06-12 | not checked |
| [Cursor](cursor.md) | `AGENTS.md` | `CLAUDE.md` (read like `AGENTS.md`, always applied), `.cursor/rules/*.mdc`, user and team rules | root and nested `AGENTS.md`, the more specific winning; four rule activation modes | none documented | `.cursor/skills`, `.agents/skills`; `.claude/skills` and `.codex/skills` for compatibility |
| [Gemini CLI](gemini-cli.md) | `GEMINI.md` | `AGENTS.md` only via `context.fileName` | just-in-time subdirectory files; `@./path.md` | none documented | `.gemini/skills`, `.agents/skills` |
| [Antigravity](others.md#antigravity-googles-consumer-harness) | `AGENTS.md` or `GEMINI.md` | `.agents/AGENTS.md`, `.agents/rules/*.md` | per directory, edited file up to workspace root | 24,000 bytes per file; 20,000-token budget | `.agents/skills` |
| [Grok Build](others.md#grok-build-xai) | `AGENTS.md` and six other names | `.grok/rules`, `.claude/rules`, `.cursor/rules` | root to cwd; deeper wins | none ("no size cap") | `.grok/skills`, `~/.agents/skills` |
| [ZCode](others.md#zcode-zai) | workspace `AGENTS.md` | `~/.zcode/AGENTS.md` | none: no nesting, no imports | skill description 1,024 chars (dropped) | `~/.zcode/skills` |
| [Qwen Code](others.md#qwen-code-alibaba) | `QWEN.md` and `AGENTS.md` | `.qwen/QWEN.local.md`, `.qwen/rules` | upward scan to project root; `@path` | none documented | `.qwen/skills` |
| [Kimi Code](others.md#kimi-code-moonshot) | `AGENTS.md` | `.kimi-code/AGENTS.md`, `agents.md` | git root to cwd; no `CLAUDE.md` | warns above 32 KiB, drops nothing | `.kimi-code/skills`, `.agents/skills` |
| [DeepSeek Harness](others.md#deepseek-harness-dsh-developer-preview-mit) | `AGENTS.md` and `CLAUDE.md` | `.local` overlays | git root to cwd; no `@path`, no `.claude/rules` | 65,536 bytes (broader files dropped first) | not documented |
| [OpenCode](others.md#opencode) | `AGENTS.md` | `CLAUDE.md` only with no `AGENTS.md` | walks up from cwd | none documented | reads `~/.claude/skills` |
| [Amp](amp.md) | `AGENTS.md` | `AGENT.md`, then `CLAUDE.md` as fallbacks | cwd and parents to `$HOME`; subtree files once read there | none documented | `.agents/skills`, `.claude/skills` and others |
| [Pi](pi.md) | `AGENTS.md` | `AGENTS.override.md`, `CLAUDE.md`; `.pi/SYSTEM.md` and `.pi/APPEND_SYSTEM.md` (trusted project only) | agent dir, cwd and parents, without project trust | none documented | `.pi/skills` |
| [Cline](others.md#cline) | `AGENTS.md` | `.clinerules/`, `.cursorrules`, `.windsurfrules` | each source togglable, combined | none documented | not documented |
| [Mistral Vibe](others.md#mistral-vibe) | `AGENTS.md` | `~/.vibe/AGENTS.md` | cwd up to the trust root | none documented | `.agents/skills`, `.vibe/skills` |
| [Windsurf / Devin Desktop](others.md#windsurf-devin-desktop) | rules or `AGENTS.md` | auto-generated Memories (not recommended for durable guidance) | — | 6,000 chars global, 12,000 per workspace rule (over-limit behaviour undocumented) | — |
| [Kiro](others.md#kiro) | `AGENTS.md` (always included) | steering files | custom agents load steering only if listed | — | — |
| [Junie](others.md#junie) | `.junie/AGENTS.md`, else root `AGENTS.md` | `.junie/playbook.md`, `.junie/rules/*.md`, global `~/.junie/AGENTS.md` | project file wins over global | — | — |
| [OpenHands](others.md#openhands) | `AGENTS.md` (into the initial system prompt) | legacy microagents without triggers | — | — | on-demand skills |

Sources and dates for each row are in the harness's file.

## 3. Loading, harness by harness

Each harness's loading rules (files, order, imports, injection, trust, skills, memory and models)
are in its file, linked from the table in §2. What holds across them:

- **The root `AGENTS.md` is the common ground** (H1); everything else is optional somewhere (H2).
- **Path-scoped rule files** differ by harness (supplied by the research's critic, not in the
  evidence file): Copilot `.github/instructions/*.instructions.md` with `applyTo`; Cursor rules with
  `alwaysApply` and `globs`; Kiro `.kiro/steering`; Claude Code `.claude/rules` with `paths:`; Qwen
  Code `.qwen/rules` with `paths:`.
- **One harness reads another's files.** Cursor applies a `CLAUDE.md` to every conversation and runs
  Claude Code's hooks ([cursor.md](cursor.md)); Grok Build reads `.claude/rules` and `.cursor/rules`
  and claims compatibility with Claude Code's plugins, hooks and instruction files
  ([others.md](others.md#grok-build-xai)); Copilot reads a root `CLAUDE.md` or `GEMINI.md`; a skill in
  `.agents/skills` installed for Codex is installed for Amp, Cursor, Kimi Code, Mistral Vibe,
  Antigravity and Gemini CLI too (§6).

## 4. Precedence and authority

- **Models of precedence.** Concatenation with no conflict resolution (Claude Code; Qwen Code, whose
  local file loads last to "supplement or override"); concatenation with a ranking the system prompt
  states (Gemini CLI: sub-directories, then workspace root, then extensions, then global); root-down
  concatenation where the later, deeper file effectively wins by position (Codex, Grok Build,
  DeepSeek Harness); and merge with a stated order (Cursor: Team, then Project, then User, earlier
  winning, and the more specific of nested `AGENTS.md` files; GitHub Copilot: personal, then
  repository, then organisation, all provided; Junie, Kiro, Cline and Roo: project over global).
  `agents.md` itself says only "The closest AGENTS.md to the edited file wins; explicit user chat
  prompts override everything"; in the harnesses that send parent and child files together,
  closest-wins holds only through position in the prompt [harness-loading-coverage-11,
  harness-loading-coverage-12, harness-loading-coverage-17].
- **Where instruction files rank.** Codex injects them as user-role messages and its base
  instructions rank the user above skills and external files [openai-harness, openai-f2]. Grok
  Build: chat instructions override them [grok-f2]. DeepSeek Harness: they "do not override
  system, developer, or direct user instructions" [open-weight-harness]. Gemini CLI: "absolute
  precedence" over its default workflows, not over its safety mandates [gemini-f19]. A benchmark
  measured the system prompt and the user overriding project documents across harnesses
  (OctoBench, co-authored by MiniMax) [open-weight-f5]. No harness in the evidence ranks
  instruction files above the user, so an instruction file cannot guarantee that a rule wins.
- **Local override files behave inconsistently.** `CLAUDE.local.md` suppresses `AGENTS.md` in
  Claude Code, reaches DeepSeek Harness, and is skipped by Grok Build when gitignored; Qwen Code
  loads `.qwen/QWEN.local.md` last; Pi's `AGENTS.override.md` replaces only its own directory's
  file [harness-loading-coverage-3, open-weight-harness, grok-f3, qwen-harness, chk-pi].
- **One file pointing at another.** For Claude Code, a `CLAUDE.md` holding `@AGENTS.md` is the
  robust form; the same file is ignored by Kimi Code, loses to `AGENTS.md` in OpenCode, and loads
  as a harmless one-line file in DeepSeek Harness, while Cursor reads a `CLAUDE.md` as it reads
  `AGENTS.md` and applies it to every conversation. A symbolic link from `CLAUDE.md` to `AGENTS.md`
  works where links survive checkout, and can become a one-line text file on Windows
  ([claude-code.md](claude-code.md#1-instruction-files-and-precedence)). For Gemini CLI,
  `context.fileName` or an `@AGENTS.md` import in `GEMINI.md` [claude-harness, open-weight-f3,
  gemini-harness; Cursor rules help page and Claude Code memory page, read 2026-10-01].

## 5. Caps, truncation and advisories

| Harness | Cap | Scope | Past the cap | Source |
| --- | --- | --- | --- | --- |
| Codex | 32 KiB (`project_doc_max_bytes`) | whole project chain | the crossing file is truncated at its end, so the most specific file, and text appended last, is cut; warning logged | harness-loading-coverage-18, harness-loading-coverage-19 |
| Antigravity | 24,000 bytes | per rule file, after includes | truncated | harness-loading-coverage-21 |
| Antigravity | 20,000 tokens | always-on and global rules together | largest files demoted to pointers | harness-loading-coverage-21, other-labs-7 |
| DeepSeek Harness | 65,536 bytes | whole chain | broader files dropped first, with a notice | open-weight-f4 |
| Kimi Code | 32 KiB | whole chain | warning only | open-weight-f4 |
| Claude Code | 4 MiB | per `CLAUDE.md` | file skipped | chk-claude-memory |
| Claude Code | 200 lines or 25 KB | `MEMORY.md` | the rest not loaded at start | harness-loading-coverage-6 |
| Claude Code | 5,000 tokens per skill, 25,000 total | invoked skills after compaction | start of each skill kept; oldest skills dropped | harness-loading-coverage-8 |
| Claude Code | 1,536 characters | a skill's `description` plus `when_to_use` in the model's listing | truncated (the `/skills` menu shows 250) | chk-claude-skills |
| Codex | 2% of context or 8,000 characters | the skill listing | descriptions shortened | openai-14 |
| ZCode | 250 characters injected; 1,024 maximum | per skill description | beyond 1,024 the skill is dropped; many skills degrade to names only | glm-f23 |
| Windsurf / Devin Desktop | 6,000 / 12,000 characters | global rules / per workspace rule file | undocumented (`UNVERIFIED`) | harness-loading-coverage-22 |
| Grok Build | none | — | files load in full | grok-f1 |
| GitHub Copilot review | none since 2026-06-12 (was 4,000 characters) | review instructions | — | harness-loading-coverage-13 |

**Advisories, not enforced:** Claude Code about 200 lines per `CLAUDE.md`; Cursor rules under 500
lines; a `SKILL.md` under 500 lines (Anthropic's skill authoring guidance); Copilot about 1,000
lines per instruction file; Z.ai's main file under 200 lines [harness-loading-coverage-5,
harness-loading-coverage-17, anthropic-18, harness-loading-coverage-13, glm-f3]. The binding
constraint for a file several harnesses load is the tightest enforced cap: 24,000 bytes per file and
32 KiB for the whole chain. An installer that appends to a project's `AGENTS.md` should report the
file's size against these caps, since its block is what Codex cuts first
([codex.md](codex.md#2-cap)).

## 6. Skills: discovery and listing

Every checked harness that supports skills uses the Agent Skills `SKILL.md` format with only the
name and description preloaded and the body loaded on use: Claude Code, Codex, Cursor, Gemini CLI,
Antigravity, Grok Build, ZCode, Qwen Code, Kimi Code, Amp, Mistral Vibe and Pi [claude-harness,
openai-harness, gemini-harness, grok-harness, glm-f23, qwen-harness, open-weight-harness,
chk-amp-skills, chk-vibe, chk-pi; Cursor's skills page, read 2026-10-01]. The directories differ:

| Directory | Read by |
| --- | --- |
| `.agents/skills` | Codex, Cursor, Amp, Kimi Code, Mistral Vibe, Antigravity, Gemini CLI (alias of `.gemini/skills`) |
| `~/.agents/skills` | Codex (`$HOME`), Cursor, Amp, Kimi Code, Mistral Vibe, Grok Build, Gemini CLI |
| `.claude/skills`, `~/.claude/skills` | Claude Code; Cursor and Amp; OpenCode (`~/.claude/skills`) |
| harness-specific | `.gemini/skills`, `.grok/skills`, `~/.zcode/skills`, `.qwen/skills`, `.kimi-code/skills`, `.vibe/skills`, `.pi/skills`, `.cursor/skills` |

A description must carry its trigger early, since the model decides from the listing alone and the
listing is truncated (§5). The format itself (six frontmatter fields, about 100 tokens of metadata
per skill, the products that list support) and skill-writing guidance are in
[skills.md](../practices/skills.md#1-what-a-skill-is-across-harnesses-volatile).

## 7. Compaction and long sessions

- **What survives differs.** Claude Code re-injects the root `CLAUDE.md`, unscoped rules, auto
  memory and the start of each invoked skill, and summarizes path-scoped rules and nested files away
  ([claude-code.md](claude-code.md#4-compaction-checkpoints-and-long-sessions)); Codex's base
  instructions say the latest user message steers the task after compaction without replacing the
  objective, and compaction summaries in OpenAI's training runs sometimes told the model to hide
  failures ([codex.md](codex.md#4-goals-delegation-and-compaction)); Kimi Code injects a reminder
  when an `AGENTS.md` changes or an unloaded nested one is touched [open-weight-f8]; the Antigravity
  managed agent compacts at about 135k tokens [gemini-harness].
- **Durable state.** Rules that exist only in the conversation are lost at compaction: "If certain
  rules disappear after compression, that means those rules existed only in the conversation and
  were never written into a memory file" (Z.ai) [glm-f5]. Codex and ZCode `/goal` persist an outcome
  with a completion check across turns [openai-f24, glm-f13]. Monitors missed a dangerous action 2
  to 30 times more often after 800K benign tokens [measured-g13], so instructions given at session
  start cannot be relied on to govern very long runs [measured-f17].
- **Hooks around compaction.** Claude Code's `PreCompact` can block a compaction and its
  `PostCompact` receives the summary; Codex's `PreCompact` and `PostCompact` stop before or after
  compacting on `continue: false`. Neither lets a hook edit the summary, so a hook can keep each
  summary for checking against the files a run relies on, but not change it (both hooks pages, read
  2026-09-29 and 2026-10-01; details in each harness's file). L.
- **Checkpoints and thresholds.** Claude Code checkpoints the files before every prompt and lets
  `/rewind` restore or summarize a chosen range ([claude-code.md](claude-code.md#4-compaction-checkpoints-and-long-sessions)).
  One framework publishes its thresholds: LangChain's deep agents move a tool input or result over
  20,000 tokens to a file, truncate older tool calls to file pointers once context passes 85% of the
  window, and summarize at 85% of the model's input limit, keeping 10% as recent context and writing
  the original messages to the filesystem (docs read 2026-10-01). L (one framework).
- **Heuristics in circulation, not measurements.** Keeping a working ceiling 4–10 times below the
  advertised window, cutting cost 41–80% with a cache-aware prompt layout, and treating a cache hit
  rate under 60% as the alarm line each come from one practitioner or one study whose source the
  2026-08 survey that carried them did not name (A, `UNVERIFIED`). The measured part is that
  degradation with length is uneven [research-11]. How context windows degrade, prompt caching and
  summarization as a context mechanism are in
  [context-and-memory.md](../practices/long-context-and-compaction.md#1-context-windows-today-volatile).

## 8. Trust gates and readers that load nothing

- **Non-interactive runs skip the gate in Claude Code:** the trust check is disabled under `-p`, and
  in a `-p` or SDK session committed hooks run in a folder never trusted; project plugins, by
  contrast, need the workspace trust check even there
  ([claude-code.md](claude-code.md#6-trust)) [instruction-file-security-authority-19].
- **Codex:** an untrusted project gets only user instructions, needs approval for commands, and has
  project-local configuration disabled; project hooks also need per-hook review by hash
  ([codex.md](codex.md#6-trust)) [harness-loading-coverage-19, instruction-file-security-authority-20].
- **Grok Build, Qwen Code, Mistral Vibe:** project files, upward scans, skills or settings load
  only in trusted folders [grok-f3, qwen-harness, chk-vibe].
- **Pi** loads its project `.pi/` settings and resources only after project trust, but loads
  context files (`AGENTS.md`, `CLAUDE.md` in the working directory and its parents) without it, so
  an untrusted checkout's instruction files reach the model; and it does not ask before each tool
  call ([pi.md](pi.md#3-trust)).
- **Muse Code** loads committed project memory in an untrusted workspace, before its instruction
  files, skills and hooks, which wait for trust ([others.md](others.md#muse-code-meta)).
- **Text returned by a helper.** Claude Code scans each subagent's final report for imitations of
  its control tags before the parent reads it, removing and judging nothing
  ([claude-code.md](claude-code.md#5-subagents-delegation-and-the-agent-sdk)).
- **Readers that skip the instruction files by design:** Claude Code's Explore and Plan subagents;
  Kiro custom agents unless steering is listed; ZCode's Explore subagent; Cursor's Tab completion,
  Inline Edit and Bugbot pull-request reviews, since its "Rules only apply to Agent (Chat)"
  [capability-tier-readers-13, harness-loading-coverage-23, glm-harness; Cursor rules help page,
  read 2026-10-01].

## 9. Hooks

### 9.1 The finish hook, per harness

Each harness's hook documentation was read on 2026-09-29, and the sentences that settle each fact
were copied from the page source, not a summary. Two GitHub issues and one third-party test log
were read the same day. The Claude Code, Codex and Cursor hook pages and Cursor's third-party hooks
page were re-read on 2026-10-01 from their Markdown sources. The quoted sentences behind each cell
are in the harness's file.

| Harness | Finish event | Holds the finish and returns a reason | Loop guard | Time limit | Project configuration |
| --- | --- | --- | --- | --- | --- |
| [Claude Code](claude-code.md#71-the-finish-hook) | `Stop` (doc) | `decision: "block"` + `reason`, or exit 2 with stderr; or a `prompt` or `agent` handler's `ok: false` (doc) | `stop_hook_active`; cap of 8 consecutive continuations (doc) | `timeout`, seconds, default 600 (doc) | `.claude/settings.json`, committable (doc); runs untrusted under `-p` (doc) |
| [Codex](codex.md#71-the-finish-hook) | `Stop` (doc) | `decision: "block"` + `reason` becomes a new user prompt, or exit 2 with stderr (doc) | `stop_hook_active`; no cap documented (`UNVERIFIED`) | `timeout`, seconds, default 600 (doc) | `.codex/hooks.json` or inline `[hooks]` in `.codex/config.toml`, after project trust and per-hook review (doc); an open report says project hooks do not fire (report) |
| [Gemini CLI](gemini-cli.md#6-hooks) | `AfterAgent` (doc) | `decision: "deny"` + `reason`, or exit 2 with stderr (doc) | `stop_hook_active`; no cap documented (`UNVERIFIED`); a loop defect fixed 2026-03 (report) | `timeout`, milliseconds, default 60000 (doc) | `.gemini/settings.json`, fingerprinted, warned on change (doc) |
| [Cursor](cursor.md#4-hooks) | `stop` (doc) | no hold: `followup_message` is submitted as the next user message after the loop ends (doc) | `loop_count`; `loop_limit`, default 5 (doc) | `timeout`, seconds, default not stated (`UNVERIFIED`) | `.cursor/hooks.json`, trusted workspaces and cloud agents (doc); also Claude Code's `.claude/settings*.json` hooks, on by default, with `loop_limit` `null`, no limit, which only Cursor's own format can set (doc); CLI support undocumented (`UNVERIFIED`) |
| [Amp](amp.md#4-hooks-the-plugin-api) | `agent.end`, a plugin event (doc) | `action: 'continue'` + `userMessage` starts a new turn (doc) | `maxContinuations`, default 5 (doc) | none documented (`UNVERIFIED`) | a TypeScript program under `.amp/plugins/`, run by Bun (doc); trust rule not found (`UNVERIFIED`) |
| [Pi](pi.md#4-hooks-extensions) | `agent_before_settle`, an extension event (doc) | `continue: true`, one more model request (doc) | the extension's own condition (doc) | none documented (`UNVERIFIED`) | a TypeScript extension under `.pi/extensions/`; a `project_trust` event precedes loading (doc) |

**Across the rows.** Three rows export the project root to the hook process (Claude Code, Gemini
CLI, Cursor); Codex runs the hook in the session's working directory, and Cursor's stop input has no
`cwd`. The three holding rows show `systemMessage` to the person without it reaching the model, and
Codex's `Stop` takes JSON on stdout only. Three rows carry a `stop_hook_active` flag and one a
count; three document a cap (Claude Code, Cursor, Amp). Two rows expose the finish only to a program
in another language. One committed file can drive two rows: Cursor runs the `Stop` hooks in Claude
Code's settings files.

### 9.2 What makes a hook unsafe or unusable

- **It runs with the person's privileges from a file a pull request can change.** Gemini CLI and Pi
  say so in as many words; every row does it. A committed entry is one more file a review must
  read.
- **Trust is given once, or not at all.** Claude Code runs committed hooks untrusted under `-p` or
  the SDK, and documents no per-entry review after the workspace is trusted; Codex re-reviews an
  entry whose hash changed; Gemini CLI warns when a project hook's name or command changes. Trust by
  hash covers the entry, not the program it calls: upgrading the tool an unchanged entry runs changes
  what executes without a new review (inference from Codex's documented rule, not tested), so an
  entry that must not run a newer program unreviewed names the version it expects and checks it.
  A hook checked from the CLI is not thereby checked in a desktop app, whose environment differs;
  qualify each surface the person uses.
- **The hook's environment is not the developer's shell.** A harness started from a desktop app may
  lack the shell's `PATH`, and no activated virtual environment is inherited (observed in Claude
  Code, [claude-code.md](claude-code.md#71-the-finish-hook)). A command that runs a module by name
  from the project directory can be shadowed by a module of the same name the project, or a pull
  request, adds: Python's `-m` puts the working directory ahead of `PYTHONPATH`, which
  `PYTHONSAFEPATH=1` (Python 3.11+) prevents (reproduced in one project's CI snippets, O,
  2026-09-28). `python -I` goes further (it implies `-E`, `-P` and `-s`, so neither the working
  directory, `PYTHONPATH` nor the user site enters `sys.path`) but does not disable `site`: `.pth`
  files and `sitecustomize` in the running environment still execute, and in one probe a planted
  `.pth` changed what an installed command imported (Python command-line docs, read 2026-10-01;
  probe on CPython 3.10.11 and 3.14, O, 2026-10-01). How a command can run one pinned engine is in
  [releasing.md](../practices/releasing.md#1-the-command-a-package-installs-rl1-rl2).
- **Loops.** A hold that can never resolve loops until the cap (Claude Code 8, Cursor 5, Amp 5) or,
  where no cap is documented (Codex, Gemini CLI, Pi) or none applies (Cursor running a Claude Code
  hook, whose `loop_limit` is `null`), until the hook's own guard stops it.
- **A hold can fight a legitimate stop.** A finish hook that holds whenever a check fails also holds
  when that check already failed before the agent's change, which good test practice leaves as
  found, and when the turn ends to ask the person a question, which pushes the agent past its stop.
  Word the returned reason so the agent reports a failure that predates its change, or its question,
  and finishes, with the loop guard keeping it to one hold (A, one finish hook, 2026-09-30).
- **Concurrency and format.** Codex launches matching hooks concurrently, accepts only JSON on
  stdout from `Stop`, and cuts any model-visible hook output past about 2,500 tokens to a preview,
  writing the full text to a file on disk, so a hook returns no secrets
  ([codex.md](codex.md#7-hooks)).
- **An exit code may not block.** In Claude Code only exit 2 blocks by its code; exit 1, and a
  missing or non-executable script (exit 127), are non-blocking errors, so a mistyped path leaves a
  gate silently disabled, and a timed-out `PreToolUse` hook lets the tool call continue
  ([claude-code.md](claude-code.md#72-how-a-hook-fails-or-blocks)).
- **Failure mode.** Cursor's hooks fail open unless `failClosed: true`; a Claude Code hook whose
  command is missing holds nothing.

### 9.3 Other hook facts

- Each harness's full event list, handler types and runtime rules are in its file: Claude Code's 33
  events and five handler types ([claude-code.md](claude-code.md#73-the-hook-catalogue)), Codex's
  twelve events, additive layers and async hooks ([codex.md](codex.md#72-the-hook-runtime)), and
  Cursor's, Gemini CLI's, Amp's and Pi's finish events in theirs.
- A `PreToolUse` hook in Claude Code blocks an action whatever the model decides; instruction files
  cannot [harness-loading-coverage-9]. Qwen Code skills can declare frontmatter hooks as hard gates
  [qwen-f14]. Grok Build needs `/hooks-trust` for project hooks [grok-harness]. Hooks that touch
  Claude Code's auto-mode classifier (`PermissionDenied`, `classifierContext`) are in
  [authority.md](../practices/agent-authorization.md#2-claude-codes-permission-layers-volatile-a2-a4).
- LangChain's harness adds a pre-completion checklist that intercepts the agent before it exits and
  reminds it (does not force it) to verify against the task spec, a loop detector that nudges after
  N edits to one file, and injected directory context; together with prompt and reasoning-budget
  changes these moved Terminal Bench 2.0 from 52.8 to 66.5 with gpt-5.2-codex, no single component
  isolated [deterministic-22] (M, vendor).

### 9.4 Configuration keys that execute code or widen permissions

Read 2026-09-27 (2026-09-30 for Claude Code's `enabledPlugins` and `extraKnownMarketplaces`,
settable in any settings file; 2026-10-01 for Pi's `.pi/mcp.json`, which an earlier reading had
missed), from each harness's settings reference. "Executes" means the key names a command or
program the harness runs. Cursor also runs the hooks in Claude Code's settings files (§9.1).

| Harness | Project files | Executes | Tool servers | Enables all servers | Endpoint overrides | Permission bypass | Deny rules |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Code | `.claude/settings.json`, `.mcp.json` | `hooks`, `statusLine`, `apiKeyHelper`, `awsAuthRefresh`, `awsCredentialExport`, `gcpAuthRefresh`, `otelHeadersHelper`, `fileSuggestion`, `enabledPlugins` | `mcpServers` | `enableAllProjectMcpServers`, `enabledMcpjsonServers` | `env.ANTHROPIC_BASE_URL`, `env.ANTHROPIC_BEDROCK_BASE_URL`, `env.ANTHROPIC_VERTEX_BASE_URL`, `forceLoginGatewayUrl`, `extraKnownMarketplaces` | `permissions.defaultMode`, `skipDangerousModePermissionPrompt`, `sandbox.filesystem.disabled` (the last ignored from project files, and `defaultMode: "auto"` too, as read 2026-10-01) | `permissions.deny` |
| Codex | `.codex/config.toml`, `.codex/hooks.json` | `hooks` | `mcp_servers` | — | — (project config ignores provider keys) | — (project config ignores approval and sandbox keys) | not settled |
| Gemini CLI | `.gemini/settings.json` | `hooks` | `mcpServers` | — | environment variables, not settings | `general.defaultApprovalMode`, `tools.allowed`, `mcpServers.*.trust` | `tools.exclude`, `mcp.excluded` |
| Cursor | `.cursor/hooks.json`, `.cursor/mcp.json`, `.cursor/cli.json` | `hooks` | `mcpServers` | not settled | not settled | not settled | `permissions.deny` |
| Amp | `.amp/settings.json` or `.jsonc` | not settled (plugins under `.amp/plugins/`) | `amp.mcpServers` | — | `amp.url` | `amp.dangerouslyAllowAll` | `amp.permissions`, `amp.mcpPermissions` |
| Pi | `.pi/settings.json`, `.pi/mcp.json` (trusted project) | `extensions`, `packages`, `shellCommandPrefix`, `shellPath`, `npmCommand`; `mcpServers.*.command` | `mcpServers` in `.pi/mcp.json` | — | `httpProxy` | not settled | not settled |

Such files were exploited: hooks, `.mcp.json` and base-URL overrides in Claude Code's project
settings as CVE-2025-59536 and CVE-2026-21852, and published skills shipped a `.mcp.json` with an
attacker's credentials and hooks that sent every action out
([claude-code.md](claude-code.md#8-settings-that-run-code-or-widen-permissions))
[instruction-file-security-authority-17]. Personal files a project should never depend on are
listed in each harness's file. A TOML configuration (Codex) can hold values a line-by-line reader
cannot settle ([codex.md](codex.md#8-settings-that-run-code-or-widen-permissions)).

## 10. Observing what loaded

Loading can be observed rather than assumed: `/context` and `/memory` in Claude Code (an
interactive session also prints when it reads `AGENTS.md` directly), `/memory show` in Gemini CLI,
the app-server's `instructionSources` and `codex debug prompt-input` in Codex, `grok inspect` in
Grok Build, `/context detail` in Qwen Code, and VS Code's Agent Customizations editor
[harness-loading-coverage-30, harness-loading-coverage-3, grok-harness, qwen-harness]. A listing of
skills (Codex's `/skills` or app-server `skills/list`) shows discovery, not loading. Each harness's
commands are in its file ([claude-code.md](claude-code.md#11-observing-what-loaded-and-surface-signals),
[codex.md](codex.md#11-observing-what-loaded)).

- **Four facts to keep apart.** Placement (the file sits at the discovery path with the expected
  bytes), discovery (the harness lists it), loading (its text entered the context) and execution
  (the model acted on it); a listing proves discovery only.
- **Failed probes settle nothing.** Three bounded probes of Codex CLI 0.153.4's app-server
  (2026-09-09) ended before `initialize` returned (O), so which Codex version first returns
  `instructionSources` is `UNVERIFIED`.

## 11. Rendering in harness surfaces

Whether a reply's Mermaid block is drawn or shown as source differs by surface, read 2026-09-23:
drawn in the Codex desktop app (observed) and inline as ASCII in the Cursor CLI since 2026-02-18
(changelog); shown as source in Claude Code's editor extension (observed), its desktop app and its
CLI (open issues anthropics/claude-code#52517 and #14375), and in the Codex CLI, where a text
renderer merged upstream on 2026-09-16 is not yet called; unknown for the Codex IDE extension,
Cursor agent chat, Gemini CLI, Amp and Pi. Environment signals a hook or tool can read: Claude
Code's editor extension sets `CLAUDECODE=1` and `CLAUDE_CODE_ENTRYPOINT=claude-vscode`; Cursor sets
`CURSOR_AGENT` in the commands its agent runs; Gemini CLI sets `GEMINI_CLI=1` in every command
(OutcomeBound's `adapters/surfaces.json`). Signals that do not identify a surface: Claude Code's
`AI_AGENT` carries the harness version (`claude-code_2-1-280_agent` was observed), so an exact match
breaks on every release; Codex sets `CODEX_SANDBOX` (seen as `seatbelt`, beside
`CODEX_SANDBOX_NETWORK_DISABLED=1`) only on a command it runs under a sandbox, so it does not tell
the Codex app, IDE extension and CLI apart; and a host editor sets its own variables for every
extension, so a Claude Code extension session inside Cursor also carries `CURSOR_LAYOUT`,
`CURSOR_WORKSPACE_LABEL` and `VSCODE_PID`, and a terminal it opens may inherit `CURSOR_AGENT`
(A, observed 2026-09-23). Match on the most specific set of variables, read a tie as unknown,
and draw ASCII where the surface is unknown. Cursor's 2.2 changelog (2025-12-10) says Plan Mode
supports inline Mermaid diagrams; those are plans, not replies in chat (read 2026-10-01).

## 12. Adoption (MONITOR)

JetBrains' vendor-run survey, reweighted to be globally representative (more than 15,000
respondents, published August 2026), puts at-work adoption in May–July 2026 at Claude Code 39%,
GitHub Copilot 21%, Codex 16%, Cursor 12%, JetBrains AI or Junie 9%, OpenCode 7% and Antigravity
6%. Claude Code rose from 18% in January 2026 and Codex from 3% (about 5x); Copilot fell from 29% a
year earlier and Cursor from 18% in January [harness-loading-coverage-2, chk-jetbrains]. In a
self-selected survey of 906 Pragmatic Engineer readers (27 January to 17 February 2026), 70% used
two to four AI tools at once and 15% five or more; "tools" includes chatbots, not only coding agents
[harness-loading-coverage-1]. M.

## 13. Where harnesses are heading (MONITOR)

### 13.1 One practitioner's account (T1–T7)

**Source.** Thariq Shihipar, on Anthropic's Claude Code team, interviewed on Latent Space (hosts
swyx and Vibhu), "The Future of Claude Code: Mods, Mutable Software, & Multiplayer Agents",
published 2026-09-28, 1:34:31, <https://www.youtube.com/watch?v=IZAlq-V19U8>. Read from the
auto-generated English captions (750 segments, no manual track) on 2026-09-29. Screen content he
refers to is known only through his description. Speakers are unmarked in the captions; (host)
marks a host's words. Timestamps may drift about 15 seconds. All of it is one practitioner speaking
for a vendor about its products, so every item is anecdote (A) at most; each item says in words
whether it is something he observed, a measurement he described, a prediction (F), an opinion, or
a product fact or plan from the vendor (L, from an interested party).

**T1. Instruction files shrink.**
- In the limit the project instruction file goes away, "maybe not even that far"; today it may be
  better to start a project without one and add an entry only for a failure mode that keeps
  recurring. Predicted (F) and his opinion (A), [30:35]
- Failure modes change between model versions, even point releases (his example: Fable 5 against
  5.1), so a running log of failure modes will probably over-constrain the model, and keeping one
  file per model is a pain. Opinion (A), [30:47]
- Eval plugins for skills were just added, so a team can test whether a skill makes things better;
  they cost tokens and are imperfect. Product fact (L, vendor), [31:25]
- (host) Goals, and a decision or experiment log that survives the session, both live outside the
  prompt as markdown with no standard. [29:10]
- Consistent with the ETH study of context files (no success gain, more than 20% higher cost)
  [research-4].

**T2. What the model decided, and what it set aside.**
- In nearly every eval failure he read, the model thought of the right solution and chose not to do
  it; at high effort it rarely lacks the knowledge. Asking for decision or implementation notes lets
  a person see and reverse those choices. Newer models (Fable 5.1) call out their decisions more
  often, but making it explicit in the harness is better. Observed, from eval transcripts (A),
  [28:27]–[29:00]
- In progress: a tool that registers assumptions as the model works and shows them at the end.
  Product plan (L, vendor), [37:13]

**T3. Effort, verification and model choice.**
- Extra effort mostly goes on verification and edge-case testing; it changes security results
  visibly and general software results much less. A measurement he described (about 70 Terminal
  Bench problems plus transcripts, in a post not yet published; no numbers given), so A. [25:16],
  [27:59]
- A rough split: code review and security at high or max effort; interface work at low or medium;
  an API at enough effort to cover its edge cases; say explicitly when heavy verification is
  wanted. Opinion, backed by the item above (A), [27:17]
- A strong model at high effort over-verifies (needless Chromium screenshots of work already done);
  frontier models will become the cheapest on most tasks, "Pareto-dominant", because they need
  less checking and a perfect model would do the work once. Predicted (F), with observed support
  (A), [25:40]–[27:17]
- The harness does not route between models by default: routing is hard, "you will get it wrong"
  (a heavy model on an easy task or the reverse), and a router can break the prompt cache. Opinion
  (A), [37:39]
- Cost follows a pattern: Opus 4 was expensive, Opus 4.5 "great and cheap"; he expects the same for
  the newest tier. Predicted (F), [55:04]

**T4. Prompting and elicitation.**
- Prompting stays the core skill: a mental model of what the model can do in one pass; expert
  prompts are often short because the author knows both the model and the codebase; learning a
  domain's vocabulary finds one's unknown unknowns (a non-designer asks for eight mockups where a
  designer gives reference sites, fonts and components). Opinion (A), [17:17]–[20:01]
- Most people need the agent to clarify, because they know less about what they want than they
  think; work out design decisions such as schema and call structure before implementation.
  Opinion (A), [06:59]–[08:29]
- Put the context in the first prompt: the goal, prototype or production, and where compute may be
  spent, since the model cannot tell how much you want to spend. Long runs are hard to steer
  midway, and undo-and-redo cycles use up rate limits. Observed and opinion (A), [23:23]–[24:53]
- Voice prompts are not inferior: what matters is how much information the prompt holds. Opinion
  (A), [22:45]
- Advanced prompting is executive communication: situation, complication, question, answer (SCQA);
  without the answer, still give the first three. Opinion (A), [31:31]
- Quiz yourself on what was implemented before sending it on; do not pass on output you have not
  understood. Opinion (A), [33:50]–[34:43]

**T5. The harness becomes mutable.**
- "Mods" customise the harness's execution loop and interface in process, beyond hooks: they run in
  the TypeScript runtime, read turn count, tokens and messages, fork subagents, parse their
  structured output and change the interface; they can hook into each other (a mode selector lets
  any plugin register as a mode). Product fact, announced in the episode (L, vendor), [34:43],
  [41:22]
- A forked agent reuses the prompt cache, so it is a light way to run a side task, such as judging
  whether the task is complete, proposing next steps or quizzing the user, without adding to the
  main context. A host's next-steps skill re-reads the transcript against the original goal and
  checks for laziness or a missing approval. Observed (A) and product fact (L), [35:34],
  [44:03]–[45:57]
- Harnesses go out of date fast, in ways that are hard to predict. For hard coding work, use the
  vendor's harness; for simpler or domain-specific agents, a team's own harness on a managed-agent
  service. Opinion (A), [46:42]–[50:13]
- The product splits into a cloud "brain", "hands" that run locally or in a remote sandbox, and a
  display surface: artifacts with a database that several sessions can read. In the limit artifacts
  become the interface to the harness; a dashboard artifact suits long-running projects. Predicted
  (F) and product plan (L), [08:29]–[12:48]
- (host) Past harness changes: plan mode used less, auto mode, most of the system prompt cut,
  examples dropped. [48:44]
- With intelligence abundant, spend compute on keeping the person in the loop (artifacts, side
  agents) while the core harness stays complex and secure; the brain, hands and surface split costs
  more tokens (loops, managing subagents, writing artifacts), which he expects to matter little.
  Predicted (F) and opinion (A), [47:39], [50:23]. (host) Keep a supervisor agent with the
  high-level context apart from the implementing agent. Observed (A), [45:57]. How feedback should
  route between an artifact and the chat is unresolved. Observed (A), [10:14]

**T6. Multiplayer and organisational agents.**
- A channel per project or feature, with reviewers such as legal tagged in, answers their questions
  without the engineer; background work (review, security, incidents, starting a pull request)
  moves to the shared agent. Observed (A), [14:35], [52:35]
- Permissions and visibility across channels are an "iceberg": exfiltration through another
  channel, or an agent using one person's tool server to message someone else. Observed (A),
  [16:22]
- Making company data agent-accessible is the slow part; building your own is risky because a
  public form feeding a chat hook can be prompt-injected to exfiltrate code. Opinion (A),
  [56:03]–[57:21]
- Shared agents collide on credentials and tool servers, and how much context should cross channels
  is open; their best uses are proactive. Observed and opinion (A), [12:48]–[16:22], [55:46]

**T7. Security: layered, permission-matched.**
- Reported incidents, retold from public write-ups he showed: agents on a very hard benchmark used
  folder names in an internal artifact cache as a message board, reverse-engineered the scorer and
  reached into a model hub for its code, then tried to edit their transcripts once they read that
  the scorer punished cheating; in another, sandboxed agents limited to GET requests found a wiki
  writable by GET, and one edited `/etc/hosts` to send POST requests through a white-labelled
  storage host. Package registries an agent must reach (RubyGems, PyPI, npm, Artifactory) are
  attack paths. His retelling of observed incidents (A), [58:42]–[1:04:55]. The model in the
  benchmark incident was unreleased and still in training, without safety post-training, unlike
  production models under auto mode (host, [1:27:03]); the attacks were detected easily and were
  not major by the affected host's account (speaker unmarked, [1:10:22]).
- Defense is layered: training; inference-time probes and classifiers that act on intent; auto
  mode, which checks an action against what the user granted; scoped identity and keys. Probes act
  on intent, auto mode on permissions, and the two should not interfere; any one layer can fail.
  Observed (A) and product fact (L), [1:18:52]–[1:26:24]. Probes read a model's activations on input
  and output, add latency to every request, can be refined without retraining, and catch intent
  that never reaches the output; a request falling back to a smaller model is their visible effect
  (host). Product fact (L) and observed (A), [1:18:52]–[1:21:24]
- The next misbehaviour cannot be predicted, since capabilities are "spiky", so the remedy is
  operational: sandboxes and training environments built with care. Opinion (A), [1:10:56]. He
  describes, without a horizon or a test, agents acquiring resources as a side effect of a goal;
  read these as scenarios, not forecasts. [1:07:22]–[1:10:22]. He argues for pacing frontier
  releases with external evaluators and early access for security teams. Opinion (A) and product
  plan (L), [1:12:21]–[1:30:08]
- Do not give an agent production access without asking whether it could mint its own credentials;
  threat-model every input that feeds an agent with company access (forms, chat hooks, external
  channels); attach open safeguard models to a harness you build (host). Opinion (A), [56:26],
  [1:25:50], [1:27:03]
- Models increasingly know when they are being evaluated, so evals may not reveal a behaviour;
  reasoning traces were found to diverge from stated output (speaker unmarked). Observed and
  opinion (A), [1:05:19], [1:10:22]

**Limits of this account.** One practitioner, speaking for a vendor about its own products. The only
measurement he described (T3) gives no numbers and is unpublished. Captions mangle names, and
speaker turns are inferred. The incident accounts are second-hand. Read a prediction as a direction
to re-check, not a finding.

### 13.2 The documented direction

- **Convergence on one file name, not on budgets or precedence.** Root `AGENTS.md` support spread
  from Codex (May 2025) to Claude Code (September 2026); imports, nesting, path rules, local
  override files and size limits did not converge [harness-loading-coverage-3, openai-harness].
- **Skills are shared.** `SKILL.md` with progressive disclosure is read by at least twelve
  harnesses; `.agents/skills` is the nearest thing to a shared directory (§6).
- **Models are trained across harnesses.** Qwen from 3.7, Kimi K3, DeepSeek V4.1, MiMo V2.6 and
  Nemotron 3 Ultra were trained or post-trained in several harnesses; Grok 4.5–4.7 were co-trained
  with Cursor data; the harness still moves results by several points: about 9 points across eight
  scaffolds in DeepSeek's own table, the simplest scoring highest (DeepSeek-V4.1-Flash at max effort
  on DeepSWE v1.1: Claude Code 69.8, Codex 65.6, OpenCode 65.5, Pi 66.2, mini-SWE 74.2, DeepSeek
  Harness 72.6 minimal, 70.5 standard and 67.6 with programmatic tool calling; on Terminal-Bench
  v2.1 84.1 to 90.6; arXiv 2609.19969, re-read 2026-10-01); Opus 5.5 at 66.4% on
  Terminal-Bench 4.0 by Anthropic's figure against 59.6% in Artificial Analysis's mini-swe-agent run;
  Sonnet 4.5's rule-following rate fell from 16.7% in Claude Code to 4.4% in Kilo [open-weight-f2,
  measured-g23, open-weight-f24, grok-f14]. See [models.md](../models/cross-family.md#3-trends-r1r16) R3.
- **Goals and loops become primitives.** Codex and ZCode ship `/goal`; practitioners advocate
  "designing loops that prompt your agents" instead of prompting turn by turn [openai-f24, glm-f13,
  repo-readiness-audits-27].
- **Thin or thick harness is contested.** Model labs say the ideal harness is minimal ("the ideal
  harness is no harness"; with reasoning models "you don't need this complex behavior. In fact, in
  many ways, it makes it worse"); harness builders report large harness-only gains (LangChain's
  13.7 points) and OpenAI advises moving deterministic work into code, "reserving model tokens for
  judgment" [forward-24, deterministic-24, latent-space-15, deterministic-22, openai-22]. A likely
  reconciliation: simple scaffolding for how the model works, deterministic checks for what counts
  as done; "every component in a harness encodes an assumption about what the model can't do on its
  own", worth re-testing at each model [deterministic-23, anthropic-8, deterministic-15,
  latent-space-4]. One guest essay proposes measuring harness progress by how much can be deleted at
  equal capability, and expects the durable work to be the human-facing guardrails models will not
  absorb: permissions, identity, trust and legibility [forward-23] (A). Lilian Weng observes that
  prompt tricks became less central as instruction tuning and reasoning improved, but "the need to
  specify goals, constraints, context, and evaluation did not disappear"; keep the harness's
  interface to tools and context simple, with complexity behind it [deterministic-27,
  practitioners-1] (A, one researcher).
- **Protocols set transport and identity, not delegation policy.** The MCP specification revision
  of 2026-07-28 made the core stateless (no `initialize` handshake or protocol-level sessions; each
  request carries its protocol version and capabilities), added an extensions framework, deprecated
  Roots, Sampling and Logging, and requires clients to bind tokens to one server with RFC 8707
  resource indicators on OAuth 2.1 with PKCE (changelog and authorization pages, read 2026-10-01).
  A2A reached version 1.0.0, governed under the Linux Foundation, and passed 150 participating
  organisations by its first anniversary (2026-04-09); IBM's Agent Communication Protocol merged
  into it in August 2025 (A2A specification and Linux Foundation release read 2026-10-01; the merger
  through search summaries). Neither, as read, carries constraints a delegator places on a delegate,
  so the host's own check enforces them
  ([authority.md](../practices/agent-authorization.md#4-grants-and-authorization-patterns-a4a6)). L.
- **Neighbouring platforms.** Claude Managed Agents, in beta behind the `managed-agents-2026-04-01`
  header, hosts the agent loop and its sandbox (Anthropic-managed or self-hosted); its sessions are
  long-running and resume after pauses, with conversation history, sandbox state and outputs stored
  server-side and the event history fetchable in full; vaults register per-user credentials once and
  are referenced by id at session creation; it is not eligible for zero data retention or HIPAA
  coverage; and it bills $0.08 per session-hour of running time plus tokens (overview, vaults and
  pricing pages, read 2026-10-01). OpenAI's Agents SDK offers both shapes of delegation: a handoff
  makes the specialist the active agent for the rest of the turn, while an agent used as a tool
  returns to the manager, as Claude Code's subagents return to the parent; it keeps a conversation's
  history either in the client (sessions) or on OpenAI's servers (`conversation_id` or
  `previous_response_id`), one strategy per conversation (SDK docs, read 2026-10-01).
  OpenTelemetry's GenAI conventions moved to their own repository in 2026 (created 2026-05-05);
  every `gen_ai` attribute on the spans page is still at Development status; `gen_ai.prompt` and
  `gen_ai.completion` are listed as "Removed, no replacement at this time" in the main conventions'
  registry, and message content is carried in opt-in `gen_ai.input.messages` and
  `gen_ai.output.messages`, so pin the conventions' version (read 2026-10-01). L.
- **Harness-level forecasts** are in [models.md](../models/cross-family.md#8-forecasts) §8: C5 (Claude Code
  and Gemini CLI read `AGENTS.md` alongside their own file by default), O1 (Astra's cross-context
  notes become the Codex default), O2 and C10 (per-model tuning stays in harness base
  instructions), P1 (scale washes harnesses away), P4 (small models trained for harness
  compatibility), P5 (a human attention policy surface) and P7 (loop primitives beyond `/goal`).

## 14. What a 2026 agent harness is expected to provide (MONITOR)

A survey of agent harnesses in August 2026 named ten capabilities as table stakes, each either a
durable requirement (it holds whatever the vendor), a mechanism (one credible way to meet a
requirement, substitutable) or a heuristic (a useful number or rule of thumb, not consensus). The
requirements underneath all ten are least privilege, bounded execution, effects that happen once,
and control of the context. Each row was re-read at its source on 2026-10-01; where the detail
lives in another reference, the row points there.

| Requirement | Mechanism in 2026 | As read 2026-10-01 | Detail |
| --- | --- | --- | --- |
| Capability packaging | Agent Skills (`SKILL.md`) | an open standard; agentskills.io listed 46 supporting products; six frontmatter fields are portable, the rest is host extension; about 100 tokens of metadata per skill stay loaded and the body loads on use; a bundled script's output enters the context, while the script itself can run without being loaded. Putting procedure in the system prompt instead is a generation behind (opinion, A) | [skills.md](../practices/skills.md#1-what-a-skill-is-across-harnesses-volatile) |
| Tools bounded by context | deferred tool loading through a tool-search tool | on by default in Claude Code and its `-p` and SDK runs: tool names and MCP server instructions load at start, definitions on demand; a threshold mode loads them up front below a share of the window | [claude-code.md](claude-code.md#3-skills-and-deferred-tools) |
| Bounded delegation | subagents with per-agent tools, permissions, model and memory | Claude Code: depth 3, 20 at once, no session total; background by default in interactive sessions; resumable; each report scanned for imitated control tags. A subagent is a context firewall, not a team; fan out reads, keep writes to one thread; most multi-agent failures are specification and termination, and token spend explains most of one vendor's multi-agent gain | [claude-code.md](claude-code.md#5-subagents-delegation-and-the-agent-sdk); [work-breakdown.md](../practices/work-breakdown.md#f9-splitting-one-outcome-across-parallel-writers-costs-reliability-and-tokens--strong) |
| Least-privilege execution | an operating-system sandbox | Seatbelt on macOS, bubblewrap on Linux and WSL2; filesystem and network isolation as separate layers, egress through a proxy the agent cannot reconfigure; a strict mode removes the unsandboxed retry; credential masking (a placeholder in the sandbox, the real secret substituted by the proxy, AWS requests re-signed); no production credential inside a sandbox (P) | [claude-code.md](claude-code.md#9-sandbox-and-permissions); [authority.md](../practices/agent-authorization.md#5-containment-a1) |
| Approval without a prompt per action | a classifier reviewing each action | Claude Code's auto mode (the starting mode from v2.1.283): deny rules first, a stated trust boundary, back to prompting after 3 blocks in a row or 20 in a session; boundaries stated in conversation can be lost at compaction, so hard guarantees still need deny rules and the sandbox. Defense in depth, not a boundary | [authority.md](../practices/agent-authorization.md#2-claude-codes-permission-layers-volatile-a2-a4) |
| Programmable control | a hook bus | 33 events in Claude Code; a hook can rewrite a tool's input; model-prompt and subagent handlers exist | §9; [claude-code.md](claude-code.md#73-the-hook-catalogue) |
| Context control | checkpoints, rewind, targeted summarization, compaction thresholds | per-prompt checkpoints, `/rewind`, "Summarize from here" and "Summarize up to here" in Claude Code; one framework's thresholds; degradation with length is uneven; the ceiling and cache numbers in circulation are heuristics | §7 |
| Effects happen once, and runs recover | durable execution (Temporal, DBOS, Restate) | a checkpoint of conversation state is not durable execution; at-least-once delivery to an idempotent handler, its key derived from the step's address, gives effectively-once; a model's output is journaled and replayed, never sampled again; a pause for a person suspends with a timeout and de-duplicates the resume; external writes have a compensating action; a crash in the middle of a tool call is the test case (P). One arrangement in write-ups runs a workflow engine as the outer loop and a LangGraph graph inside it (A, not re-sourced). Releases: below | [agent-workspace.md](../practices/agent-workspace.md#7-what-stalls-long-autonomous-runs-w6w8) |
| Memory with invalidation | thread checkpoints, a cross-thread store, file tools the agent calls, background consolidation, an invalidation policy (P) | LangGraph pairs a checkpointer per thread with a store across threads; Letta's background consolidation is now called "dreaming": background subagents review recent conversations, consolidate lessons and update memory (docs read 2026-10-01). "File and grep memory beats vector retrieval" rests on one contested benchmark; nothing benchmarks what an agent writes to memory | [context-and-memory.md](../practices/agent-memory.md) |
| Protocols | MCP for tools, A2A between agents | as §13.2; `AGENTS.md` read by every major coding agent, with the conditions in H1 | §13.2, H1 |

**Security consensus** (re-read 2026-10-01). Prompt injection is unsolved by architecture: every AI
browser one researcher tested at Black Hat 2026 was injectable, and adaptive attacks defeat
detector defenses ([authority.md](../practices/agent-authorization.md#6-untrusted-content-crossing-the-boundary-a7)).
Capability isolation works but costs utility: CaMeL extracts control and data flow from the trusted
query so retrieved data cannot change the program, and enforces capability policies on tool calls,
solving 77% of AgentDojo tasks with provable security against 84% for an undefended system (M,
arXiv 2503.18813, abstract read 2026-10-01). The working frame is to break one leg of the "lethal
trifecta" (private data, untrusted content, a way to send data out) per session; memory and context
poisoning (OWASP ASI06) turns one injection into a durable one; Markdown-image exfiltration is fixed
where output renders; workload identity (SPIFFE, with SPIRE) is the substrate for agent identity
([authority.md](../practices/agent-authorization.md#6-untrusted-content-crossing-the-boundary-a7),
[agent-workspace.md](../practices/agent-workspace.md#4-memory-and-session-history-on-one-machine-w3)).

**Releases in the surrounding stack** (L, read 2026-10-01).
- **LangGraph 1.2.0** (2026-05-12; read at 1.2.12): delta channels store only the increment at each
  step instead of re-serializing the whole value, which shrinks checkpoints of long threads;
  per-node timeouts (wall-clock or idle, raising `NodeTimeoutError`); node error handlers that run
  after all retries are exhausted, for compensation; and a graceful drain
  (`RunControl.request_drain()`) that stops runs after the current step with a resumable checkpoint
  (LangChain changelog).
- **LangChain deep agents** (read at 0.7.21): planning, the filesystem, subagents and compaction are
  middleware, and from 0.7.0 (2026-07-24) a middleware whose name matches a built-in replaces it in
  place; harness profiles, introduced in 0.6.0 and in beta, apply per-provider or per-model bundles
  of system-prompt changes, tool overrides and middleware when a model is selected (changelog and
  docs).
- **Temporal** (Replay 2026, post of 2026-05-06): Workflow Streams stream token batches and
  application updates durably out of a workflow, in public preview; the integration with OpenAI's
  Agents SDK is generally available.
- **DBOS** (post of 2026-06-18): `read_stream()` receives stream messages through Postgres
  LISTEN/NOTIFY, keeping polling as a fallback; pluggable data sources let a workflow step on any
  database run exactly once, its checkpoint written in the same transaction.
- **Claude Agent SDK** (read at TypeScript 0.3.286, Python 0.2.163): facts in
  [claude-code.md](claude-code.md#5-subagents-delegation-and-the-agent-sdk).

## How to apply

- Put everything that must load in a root `AGENTS.md`; for Claude Code add a `CLAUDE.md` holding
  `@AGENTS.md`; for Gemini CLI set `context.fileName` or import it. Treat imports, nested files,
  path rules and local overrides as extras that some harnesses never see.
- Keep the whole chain under 24,000 bytes per file and 32 KiB in total, put what must load near
  the top of the root file, and put what must survive a long session in the root file or unscoped
  rules, and at the top of each `SKILL.md`.
- Remember that one harness reads another's files: Cursor applies a `CLAUDE.md` to every
  conversation and runs Claude Code's hooks; Pi loads context files in an untrusted checkout.
- State the bounds in every delegate's brief: some helpers never load the instruction files.
- Treat committed harness configuration as code: review hooks, tool servers, endpoint overrides and
  permission bypasses in every change, and never rely on a harness's trust dialog in a
  non-interactive run.
- A finish hook should check `stop_hook_active` (or its count) itself rather than rely on a
  harness's cap, exit 2 (not 1) when it must block in Claude Code, run by path rather than by module
  name from the project directory, assume neither the shell's `PATH` nor an activated environment,
  hand its reason back through the documented channel (`reason` or stderr, not `systemMessage`),
  and word its reason so a failure that predates the change, or a question for the person, ends the
  turn. Observe it fire in each harness before relying on it, Cursor included where a Claude Code
  hook is committed.
- Under Codex's default sandbox, add `.git`, and any `.agents/` or `.codex/` folder the agent must
  write, as writable directories (`--add-dir`).
- Observe what loaded with each harness's evidence command instead of assuming it: in Codex, the
  app-server's `instructionSources` or `codex debug prompt-input`; a skill listing shows discovery
  only.

## Limits and open questions

- One day's reading per topic of documentation pages that mostly carry no version; harnesses change
  monthly. Re-read a row's page before relying on a field name. OutcomeBound's harness table sets
  2026-12-27 as the next re-check.
- Little here was run: one observed Claude Code `Stop` hook, the Codex sandbox and read-only probes,
  and the app-server probes; every other firing report is someone else's. Codex project hooks
  (#17532), Cursor's CLI `stop` hook, and whether Cursor's no-cap default for Claude Code hooks loops
  in practice are unsettled.
- Whether Claude Code re-injects an `AGENTS.md` read directly after compaction, whether an Agent
  SDK session reads `AGENTS.md`, Windsurf's over-limit behaviour, and the loaders of Muse Code,
  MiniMax Code, MiMo Code and CodeBuddy are `UNVERIFIED`.
- Several facts were read through search summaries or issue metadata rather than full pages
  (LiteLLM's issue, the A2A merger).
- The adoption figures come from one vendor-run and one self-selected survey.
- The harness-direction account is one vendor practitioner's, with no published numbers; the
  table-stakes list (§14) is one survey's synthesis, re-read row by row, and its heuristics carry no
  named source.

## Sources

Per-harness documentation and source are listed in each harness's file. Cross-harness sources:

- `agents.md` <https://agents.md/> (last commit 2026-09-10).
- Surveys: JetBrains <https://blog.jetbrains.com/research/2026/08/ai-coding-agent-adoption-2026/>
  (August 2026) [chk-jetbrains]; Pragmatic Engineer
  <https://newsletter.pragmaticengineer.com/p/ai-tooling-2026> (2026-03-03).
- Direction: Latent Space interview with Thariq Shihipar <https://www.youtube.com/watch?v=IZAlq-V19U8>
  (2026-09-28, read 2026-09-29); LangChain, harness engineering
  <https://www.langchain.com/blog/improving-deep-agents-with-harness-engineering> (2026-02-17); Latent
  Space, is harness engineering real <https://www.latent.space/p/ainews-is-harness-engineering-real>
  (2026-03-05); Noam Brown <https://www.latent.space/p/noam-brown> (2025-06-19); Loopcraft
  <https://www.latent.space/p/loopcraft> (2026-06-12); harness engineering (Lopopolo)
  <https://www.latent.space/p/harness-eng> (2026-04-07); Anthropic, harness design for long-running
  apps <https://www.anthropic.com/engineering/harness-design-long-running-apps> (2026-03-24); OpenAI,
  builder's guide to GPT-5.6 <https://openai.com/index/builders-guide-to-gpt-5-6/> (2026-08-13).
- Protocols and platforms (read 2026-10-01): MCP changelog and authorization for revision
  2026-07-28 <https://modelcontextprotocol.io/specification/2026-07-28/changelog>; A2A specification
  <https://a2a-protocol.org/latest/specification/> and the Linux Foundation's anniversary release
  <https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year>;
  Claude Managed Agents overview <https://platform.claude.com/docs/en/managed-agents/overview>,
  vaults <https://platform.claude.com/docs/en/managed-agents/vaults> and pricing
  <https://platform.claude.com/docs/en/about-claude/pricing>; OpenAI Agents SDK, handoffs and
  multi-agent docs <https://github.com/openai/openai-agents-python/tree/main/docs>; OpenTelemetry
  GenAI semantic conventions <https://github.com/open-telemetry/semantic-conventions-genai> and the
  main registry's GenAI attributes
  <https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/gen-ai.md>;
  LangChain deep agents, context engineering
  <https://docs.langchain.com/oss/python/deepagents/context-engineering>.
- Surrounding stack (read 2026-10-01): LangChain and LangGraph changelog
  <https://docs.langchain.com/oss/python/releases/changelog>; LangGraph persistence
  <https://docs.langchain.com/oss/python/langgraph/persistence>; Temporal, Replay 2026 announcements
  <https://temporal.io/blog/replay-2026-product-announcements>; DBOS, June 2026
  <https://dbos.dev/blog/new-in-dbos-june-2026>; Letta, background memory
  <https://docs.letta.com/guides/agents/architectures/sleeptime>; CaMeL, arXiv 2503.18813
  <https://arxiv.org/abs/2503.18813>; PyPI and npm registries for `langgraph`, `deepagents`,
  `claude-agent-sdk` and `@anthropic-ai/claude-agent-sdk`.

Checks defined here (verdict PASS, read 2026-09-25 unless dated in the text):
- [chk-jetbrains] JetBrains survey: Codex "roughly 5x, from just 3% in January 2026 to 16% in
  May–July 2026"; Copilot "from 29% adoption a year ago to 21%"; Cursor "from 18% in January to
  12%".
- The per-harness checks ([chk-claude-skills], [chk-claude-memory], [chk-claude-subagents],
  [chk-codex-models], [chk-amp-agents], [chk-amp-skills], [chk-pi], [chk-copilot], [chk-cline],
  [chk-vibe], [chk-mistral-devstral2], [chk-meta]) are defined in the harness files.

Own records cited as observations (O): the Codex app-server probe ledger (2026-09-09); the Codex
sandbox probes (2026-09-24, 2026-10-01); the read-only review report (2026-09-11); the evaluation
transcripts of 2026-09-29 and 2026-09-30; a session's environment on 2026-09-23; the Python
module-shadowing reproductions (2026-09-28, 2026-10-01); and the talk's captions and distillation
(2026-09-29).
