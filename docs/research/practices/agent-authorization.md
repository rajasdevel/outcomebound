---
last_checked: 2026-10-01
volatility: MONITOR (standards, measured studies, authorization patterns and engines) / VOLATILE (§2 and §3, Claude Code's and Codex's permission layers)
sources:
  - https://code.claude.com/docs/en/permission-modes
  - https://code.claude.com/docs/en/auto-mode-config
  - https://www.anthropic.com/engineering/claude-code-auto-mode
  - https://learn.chatgpt.com/docs/sandboxing/auto-review
  - https://alignment.openai.com/auto-review/
  - https://arxiv.org/abs/2608.01710
  - https://arxiv.org/abs/2606.28679
  - https://arxiv.org/abs/2605.27766
  - https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
  - https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
  - https://www.microsoft.com/en-us/security/blog/2026/07/16/least-privilege-for-ai-agents-identity-access-and-tool-binding/
  - https://www.rfc-editor.org/rfc/rfc8693
  - https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization
  - https://docs.cerbos.dev/cerbos/latest/api/index.html
  - https://openfga.dev/docs/authorization-concepts
  - https://cube.dev/articles/semantic-layer-for-ai-agents-2026
---

# Agent authorization: what lets an agent act

Which mechanisms decide whether an agent may take an action, how far each can be trusted, how a
person's grant should be recorded so that the layer that enforces it can read it, and how an agent
system decides what data and calls an agent may reach.

Re-check when Claude Code or Codex changes its permission modes, classifier rules or reviewer; a
vendor publishes new figures for its classifier or reviewer; a study tests a recorded grant for one
named act; or OWASP, the MCP authorization specification or a named authorization engine publishes
a new revision. Evidence ledger records are as verified on 2026-09-25.

This reference answers who or what decides that an agent may act, and how far each answer holds: a
person approving each action, a permission rule, a model classifier or reviewer, a recorded grant,
a sandbox, a policy engine. It covers how approval by a person decays, how the permission layers of
Claude Code and Codex work and what they read, what a grant for one irreversible act needs, what the
field's authorization guidance asks for (agents as principals, delegation, per-call checks, durable
consumption of an approval), which authorization engines decide where, and how untrusted content
and secrets cross the boundary. It is for anyone setting up a repository where agents run with less
supervision, writing a grant, building an agent system that acts or reads data for people, or
deciding what to enforce in configuration rather than in prose. Where agents keep their work and
what stalls long runs is in [agent-workspace.md](agent-workspace.md); which files, hooks and
configuration keys each harness loads is in [harnesses.md](../harnesses/cross-harness.md); the security of
instruction files and skills is in [writing-for-models.md](writing-for-models.md).

**Evidence classes.** M measured; L lab or vendor report or documentation; S standard; P
practitioner consensus; A anecdote or one uncontrolled report; O a result recorded in one
repository's own runs. **Citations.** Bracketed ids resolve in
[`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl); other sources are linked inline with
their date and listed under Sources. "One repository's runs" means the unattended runs and
multi-day sessions described in [agent-workspace.md](agent-workspace.md), read afterwards from
file times, harness transcripts and permission denials.

## Key findings

**A1. Approval by a person decays; containment is the primary control.** Claude Code's users
approve 93% of permission prompts, and the more approvals a person sees, the less attention each
gets; sandboxing cut prompts by 84% in Anthropic's own use. Limit what an agent can reach before
asking anyone to approve what it does. M (vendor telemetry).

**A2. A permission classifier reads what the person said and what the agent does, not what the
actions returned, and it misses some actions.** Claude Code's auto-mode classifier let 17% of 52
real overeager actions through, at 0.4% false positives on 10,000 real tool calls. It clears a
blocked action only when the person's own message names that action and its specifics, and a
boundary stated once in conversation can be lost at compaction. M (vendor, own product), L.

**A3. An automatic approval reviewer rarely stops work, and is not a gate.** OpenAI's Codex
reviewer approved about 99% of escalated actions in OpenAI's deployment, and in one repository's
runs it allowed 295 of 296 requests. Its documentation calls it "not a deterministic security
guarantee". M (vendor), O, L.

**A4. Authority must be recorded where the enforcing layer reads it.** A goal file, a memory, a
relayed decision or a hook's note does not establish the person's intent to Claude Code's
classifier; a content-scoped `ask` or `deny` rule in user or managed settings holds even in auto
mode, for the command spellings it matches. L, O.

**A5. A grant must be consumed, not only checked.** After an uncertain outcome (a timeout, a lost
acknowledgement, a restart), agents re-proposed an already-approved action in 39.8% of 10,152
trajectories; single-use tokens did not stop a fresh reissuance, and durable state over the action,
the person's confirmation and the remaining budget did. M (one paper).

**A6. Exposing a tool is not authorizing a call.** Three agent frameworks gate on whether a tool is
exposed and do not re-authorize each call with its argument values; standards and vendor guidance
converge on binding an approval to the exact action, re-checking every call, and narrowing
authority at each delegation hop. M, S, L.

**A7. Untrusted content and secrets cross the boundary through rendering, delegation and social
exposure, and are stopped in code, not in prose.** Markdown-image exfiltration is fixed where output
is rendered; a researcher reported every AI browser he tested at Black Hat 2026 injectable; in a
simulation, an agent's reply leaked private information about eight times as often after a peer's
reply leaked (12.8% against 1.6%; the paper's abstract states 5.1×), and privacy instructions left
leakage above 37.8%. P, A, M.

**A8. Keep data the person may not see out of the model's context by deciding where the data is
selected.** Compiling the permission into the query or retrieval scope (a policy engine's query
plan, a semantic layer that generates the SQL, row-level security on the table) means rows the
person may not see never reach the model. A filter applied after retrieval has to check every item
before the model reads it and cannot correct an aggregate already computed over rows the person may
not see. L, P — §8.

## 1. Approval by a person, and why it decays (A1)

- Claude Code's users approve 93% of permission prompts ("approval fatigue"). M (vendor
  telemetry), 2026-03-25, [Anthropic, Claude Code auto mode](https://www.anthropic.com/engineering/claude-code-auto-mode);
  the more approvals a person sees, the less attention each gets, so per-action approval decays
  into rubber-stamping [anthropic-17]. M.
- Sandboxing with filesystem and network boundaries reduced permission prompts by 84% in
  Anthropic's internal use; new network domains still prompt [deterministic-12]. M, vendor,
  2025-10-20. Containment (sandboxes, filesystem boundaries, egress controls, credentials out of
  reach) is the primary control, not per-action approval [anthropic-17]. L.
- A rule that must hold is enforced by a hook, a permission rule or managed settings, not stated in
  prose, because prompted rules fail under pressure [anthropic-16]. L.
- User-written standing policies blocked 20.1 percentage points less overreach than approving each
  action (95% CI −32.1 to −8.1) and 14.5 less than automated per-action review (95% CI −25.8 to
  −3.2); prompts fell from 18.0 to 10.9 with no net time saved; 114 of 140 rules defaulted to "ask".
  M (one author), 2026-08-27, [arXiv 2608.27443](https://arxiv.org/abs/2608.27443)
- Coding agents that wrote their own permission policies succeeded 52.6% of the time against 83.3%
  unrestricted, and still over-granted. M, 2026-05-15, [arXiv 2605.14859](https://arxiv.org/html/2605.14859)
- Habituation to security warnings grows over weeks, and less with varied warnings; a three-week
  field experiment. M, MIS Quarterly 42(2), 2018-06,
  [abstract](https://misq.umn.edu/tuning-out-security-warnings-a-longitudinal-examination-of-habituation-through-fmri-eye-tracking-and-field-experiments.html)
  (abstract only; exact percentages `UNVERIFIED`).
- Keep the approval policy in one place and state each rule once: repeating "ask first", "do not
  mutate" or "wait for approval" causes unnecessary approval stops for safe, expected actions
  [forward-6, capability-tier-readers-5, openai-f4]. L.

## 2. Claude Code's permission layers (VOLATILE) (A2, A4)

Read 2026-10-01 from the permission-modes, auto-mode configuration and hooks pages, unless dated
otherwise.

**The decision order.** Each action resolves at the first step that matches. (1) Allow, ask and
deny rules resolve immediately, with exceptions: writes to protected paths still go to the
classifier, no allow rule approves removing a critical path, and an ask rule that matches on a
command's content (such as `Bash(git push *)`) falls back to a permission prompt. (2) Read-only
actions and file edits in the working directory are approved. (3) Everything else goes to the
classifier. (4) A blocked action returns its reason to the model, in most sessions the matched
rule's name in brackets, such as `[Data Exfiltration]`. L.

**Allow rules auto mode sets aside.** On entering auto mode, broad rules that grant arbitrary code
execution are dropped: `Bash(*)`, wildcarded interpreters such as `Bash(python*)`, package-manager
run commands, `Agent` rules and `Monitor` rules. Narrow rules such as `Bash(npm test)` stay in force
and are resolved before the classifier, so a narrow rule can let a destructive argument through
unseen; `autoMode.classifyAllShell: true` sends every shell command to the classifier. L. An allowed
`Bash(curl:*)` is kept in auto mode, so every `curl` skips the classifier (O) [as-of 2026-09-28].

**What the classifier reads.** "The classifier reads your messages and the commands Claude runs,
not their output": evidence has to be something it can read, such as the person's own message
naming a repository as public, while the output of `gh repo view` does not reach it. Anthropic
reports that adding assistant messages and tool results lowered its performance on an
overeagerness test set [deterministic-11]. It also reviews each message Claude sends to another
agent with `SendMessage` (v2.1.222 and later). L.

**How well it does.** Anthropic's evaluation of the deployed two-stage pipeline: 0.4% false
positives on 10,000 real tool calls from employees, 17% false negatives on 52 real overeager
actions curated from sessions where an employee denied the action or it was flagged afterwards,
and 5.7% false negatives on 1,000 synthetic data-exfiltration attempts; the first stage alone
runs 8.5%, 6.6% and 1.8%. The post calls the 17% "the honest number" and says the classifier "is
not a drop-in replacement for careful human review on high-stakes infrastructure". M (vendor, own
product), 2026-03-25, read 2026-10-01, [Anthropic](https://www.anthropic.com/engineering/claude-code-auto-mode).

**Rules and the person's intent.** Inside the classifier four tiers apply: `hard_deny` rules block
unconditionally; `soft_deny` rules block next; `allow` rules are exceptions to soft blocks; and the
person's intent clears the remaining soft blocks "if the user's message directly and specifically
describes the exact action Claude is about to take". "General requests don't count as explicit
intent": "clean up the repo" does not authorize a force push. An approval stated in conversation
must name the action and the specific thing that makes it dangerous (naming the verb alone clears
nothing), and covers that one action unless the person granted it as standing. L.

**Boundaries stated in conversation.** A boundary such as "don't push" blocks matching actions
until the person lifts it, and Claude's own judgment that a condition was met does not lift it.
Boundaries "are not stored as rules": the classifier re-reads them from the transcript on each
check, so a boundary "can be lost if context compaction removes the message that stated it"; a
deny rule is the hard guarantee [deterministic-10]. L. In one repository's runs a single session
lasted nine days through 47 compactions (O), so a boundary stated once does not last.

**What the classifier trusts by default.** The working directory and the remotes configured when
the session started; a remote added or repointed during the session is not trusted (before
v2.1.200 it was), and everything else is external until listed in `autoMode.environment`. Pushes
to any branch of the working repository, the default branch included, and pull-request creation
are allowed by default; a push to a branch whose name marks it as a deploy or publication target
(`production`, `release`, `gh-pages`) is judged on its own terms. L.

**When it falls back.** Three blocks in a row or twenty in a session (neither configurable) pause
auto mode and return to prompting; a non-interactive `-p` run with no prompt tool skips the action
and keeps working. Codex's reviewer has a similar breaker (§3). L.

**Where its configuration counts.** The classifier does not read `autoMode` from the project's
`.claude/settings.json` or `.claude/settings.local.json`, "so a checked-in repo or a build step"
cannot inject its own allow rules; it reads user, `--settings` and managed settings, and entries
from each scope combine. `defaultMode: "auto"` likewise does not take effect from project
settings. A list that includes the literal `"$defaults"` extends the built-in entries; one without
it replaces that section's built-ins. `claude auto-mode defaults` prints the built-in rules,
`claude auto-mode config` the effective ones, and `/auto-mode-setup` (Pro, Max and Team plans,
v2.1.228 and later) drafts `environment` entries from the project and recent sessions and offers
to remove allow rules auto mode ignores or that auto-approve destructive commands. L.

**A checkpoint the person keeps.** Content-scoped ask rules "are evaluated before the classifier
and always force a permission prompt, even in auto mode". `"permissions": {"ask": ["Bash(git push
*)"]}` matches commands that begin with `git push`; a push written as `git -C <dir> push` or
`git -c <key>=<value> push` does not match, and a `PreToolUse` hook that reads the whole command
covers those spellings. L.

**When it is on.** From v2.1.283 auto mode is the starting permission mode for interactive terminal
and VS Code sessions on every plan and provider; on earlier versions only on Pro, Max and Team
plans. Administrators turn it off with `permissions.disableAutoMode`. On Bedrock, Google Cloud's
Agent Platform and Foundry it supports only Sonnet 5 or later, Opus 4.7 or later and the Fable
models. L.

**Blocks worth knowing in advance.** Among the built-in blocks (v2.1.198 to v2.1.257 extended the
list): force pushes and `git reset --hard`-style discards; amending a commit the session did not
create; printing a live credential into the transcript or a file; content from a sensitive local
store entering a commit, push, issue or package unless the person named both source and
destination; writing to Claude Code's own session transcripts under `~/.claude/projects/`;
repointing an API base URL, proxy or registry at a third-party host; changing where pushes go;
launching an agent loop with approvals or the sandbox disabled. As read from `claude auto-mode
defaults` on 2026-09-28 (v2.1.283), the external-system-writes rule covered "deleting, resolving,
closing, or mass-modifying items in … GitHub Issues/PRs … that the agent did not create in this
session", so tracker upkeep an agent does on others' issues needs an `autoMode.allow` entry. L.

**Hooks that touch the classifier.** `PermissionDenied` fires only when auto mode denies a tool
call; its `reason` names the matched rule in brackets (for example `[Data Exfiltration]` or
`[Irreversible Local Destruction]`), and returning `hookSpecificOutput.retry: true` tells the model
it may retry, without reversing the denial; `retry` is ignored for a denial with no classifier
verdict. A `PostToolUse` hook may return `classifierContext` (v2.1.236 and later), a note about a
call's result for the classifier, which never sees results itself. From a settings, plugin, skill
or agent hook the note is unverified application context that "never establishes user intent", and
a claimed approval in it is checked against the person's own messages; the notes for one call are
capped at 2,000 characters across hooks; the field is ignored from background hooks and on
read-only calls the classifier does not record. So no hook can carry a goal file's grant into the
classifier. L, hooks reference read 2026-09-29 and 2026-10-01.

**Observed in one repository's runs** (O). The built-in rules that fired
were instruction poisoning (recording a decision the agent had relayed from files), external system
writes (editing, labelling, commenting on or closing tracker issues the agent had not created),
modifying shared resources (a write into another repository) and destructive git (deleting old
worktrees and branches); a release commit, and an authorization record the agent had drafted without
the person's words, were also refused. Each followed a reply that named only an option's label or
approved the work in general words, which the classifier does not read as the person describing the
act. Reads drew false positives: a read-only `sed -n` denied with no reason given, and a re-read of
a file in another worktree.

## 3. Codex's automatic approval review (VOLATILE) (A3)

Read 2026-10-01 from Codex's approvals and auto-review pages and OpenAI's post.

- **What it reviews.** With `approvals_reviewer = "auto_review"`, eligible approval requests go to
  a reviewer agent instead of the person. It sees only actions that already need approval (sandbox
  escalations, blocked network requests, permission requests, side-effecting app and tool calls),
  and only under an interactive approval policy (`on-request` or granular). Its policy checks for
  data exfiltration, credential probing, persistent security weakening and destructive actions:
  low- and medium-risk actions proceed when policy allows, critical-risk actions are denied, and
  high-risk ones need enough user authorization. Prompt-build, review-session and parse failures
  fail closed; a timeout is reported apart, and the action still does not run. L.
- **After a denial.** The rationale goes back to the main agent with an instruction not to reach
  the same outcome by a workaround. A per-turn breaker interrupts the turn after 3 consecutive
  denials or 10 among the last 50 reviews. `/approve` lets the person approve one recent denied
  action for one retry; the approval covers that exact action, and the retry is reviewed again. L.
- **How often it approves.** OpenAI (2026-04-30): sessions in auto-review stop for a person about
  200 times less often than with manual approval; 99.1% of real escalated actions were approved,
  and 99.93% of all actions, counting those that stayed inside the sandbox, ran without a person;
  recall was 90.3% on synthetic overeager actions,
  99.3% on synthetic prompt injections aimed at remote code execution, secret exfiltration and
  external upload (90.2% across all injection categories, including destructive deletion and data
  tampering), and 96.1% on MonitoringBench hard. M (vendor, own product),
  [OpenAI Alignment](https://alignment.openai.com/auto-review/).
- **In one repository's runs** (O): across 38 reviewer sessions, recorded as `codex-auto-review`
  at low effort, the reviewer allowed 295 of 296 requests; the one denial was deleting the only
  copy of evidence the task had asked for. The main session separately reported a network-enabled
  probe rejected because its destinations and its credential or telemetry transmission were not
  authorized.
- **Limits, in its own words.** It "is not a deterministic security guarantee", evaluates only
  actions that ask to cross a boundary, "can still make mistakes, especially in adversarial or
  unusual contexts", and complements sandbox design, monitoring and policy. L.

## 4. Grants and authorization patterns (A4–A6)

**A grant for one irreversible act.** Weakly supported: approval fatigue is well measured, and
standing policies written by users let more overreach through than per-action approval (§1), but no
study tests a narrow, dated, expiring grant for one named act. The nearest evidence (structural
authorization in [agent-workspace.md](agent-workspace.md) §4, durable consumption below) favours a
grant a tool checks over one a model reads. A grant that holds up is the person's own words naming
the kinds of act it covers, with an end (a version line or a date). It never covers an irreversible
edge beyond the one named, new authority, a scope change, a stale requirement link, a gap in intent,
a confirmation only the person can give, or an acceptance. Each act taken under it is recorded with
its undo, and the end-of-run digest keeps what needs the person apart from what was done on the
grant. Where the harness offers it, a permission rule enforces the edge whatever files say; in
Claude Code that is an `ask` or `deny` rule in user or managed settings (§2), which a file, a memory
or a hook note cannot replace.

- **Consume a grant durably.** Agents that replan, retry, delegate or resume after a crash can
  request and execute one approval more than once under fresh token identifiers ("semantic
  replay"): "rejecting a consumed token does not prevent issuing a fresh token for the same
  authorization". Across 10,152 trajectories (three model families, 282 high-risk actions, four
  uncertain outcomes, three seeds), agents re-proposed a semantically equivalent action in 39.8%:
  58.0% after a lost acknowledgement, 46.0% after a timeout, 31.0% after an ambiguous result and
  24.0% after delegation or restart. Progent, PACT and AIRGuard reduced invalid initial
  authorization but permitted every tested fresh reissuance; SUDP refused replay of the same grant
  but accepted a fresh grant derived from the same approval. What held (CapLease) was a durable
  authorization instance binding the canonical action (user, operation, arguments, resource), the
  person's authenticated confirmation and an execution budget *b*, consumed slot by slot through
  issued, prepared and committed states, with a compare-and-swap at prepare so only one executor
  wins a slot and a stable idempotency key against duplicate effects; it bounds issuance, admission
  and effects each at *b* (N_issue ≤ b, N_admit ≤ b, N_effect ≤ b). A server-side ledger with the
  same records and transitions gave identical protection, so the guarantee comes from durable state
  and transactional execution, not from what token is sent; a transition took 0.92 ms on average
  (p95 1.41 ms). M, 2026-08-03, [arXiv 2608.01710](https://arxiv.org/abs/2608.01710)
  (abstract and body read 2026-10-01). For a recorded grant: name the act and how many times it may
  be used, and record each use where the next use is checked.
- **Bind an approval to the exact action.** OWASP's AI Agent Security Cheat Sheet: separate
  deciding from executing, so a policy service validates scope, privilege and approval state before
  execution; bind each approval to "the actor, tool name, target resource, normalized parameters,
  timestamp, and expiry"; use short-lived authorization artifacts and replay protection for
  irreversible operations; make high-impact actions idempotent or require an explicit duplicate
  confirmation; show the person a sanitized preview of the parameters; set autonomy by each
  action's risk level, so low-risk tools proceed and the rest wait for review; and fail closed when
  risk classification, approval validation, policy lookup or audit logging fails. Its example maps
  each tool to low, medium, high or critical risk and lets only the mapped low-risk tools skip
  review: medium, high, critical and unmapped tools all wait for a person, and the classification
  "does not grant permission to run a tool": the execution component still checks the actor's
  authorization and the approval for the exact action. Step-up authentication is asked for critical
  acts such as payment initiation, privilege changes, bulk deletion or production deployment. S,
  read 2026-10-01. Microsoft's guidance adds that "downstream tools and services must re-check
  claims, roles, and scope on each call rather than trusting the orchestrator implicitly", and that
  elevated entitlements, tokens and approvals are temporary and scoped to one workflow, dropping
  "back to baseline when workflow completes". L, 2026-07-16, [Microsoft Security](https://www.microsoft.com/en-us/security/blog/2026/07/16/least-privilege-for-ai-agents-identity-access-and-tool-binding/),
  read 2026-10-01.
- **A standing grant is a different object.** A grant for background or recurring work records who
  granted it, for what purpose, a snapshot of its scope and an expiry or review date, and can be
  revoked apart from any session. Expiry and revocation fail differently: an expired grant may be
  renewed as routine; a revoked one stops the work and needs the person again, and no automatic
  retry crosses a revocation. OWASP names the failure this prevents: permissions validated at the
  start of a workflow change or expire before execution and the agent "continues with outdated
  authorization" (ASI03, time-of-check to time-of-use), and it asks for "automated revocation on
  idle or anomaly". P (a reading of vendor identity designs, 2026-08-13, and OWASP ASI03). AWS
  AgentCore Identity, for one, binds stored credentials to one agent and user,
  [AWS](https://aws.amazon.com/blogs/machine-learning/introducing-amazon-bedrock-agentcore-identity-securing-agentic-ai-at-scale/);
  its SDK handles token expiry and a needed user consent by producing an authorization URL, and
  its token vault refreshes credentials automatically (§5). Microsoft Entra Agent ID's on-behalf-of
  flow supports refresh tokens "for asynchronous scenarios and background processes" (page updated
  2026-08-10). L, read 2026-10-01.
- **Decide outside the model, enforce at every call.** The model chooses what to attempt; a
  deterministic layer decides whether it is allowed. Microsoft: "Relying on prompts or 'the agent
  will only do X' narratives instead of hard authorization boundaries invites prompt injection and
  workflow drift" (L, 2026-07-16). OWASP's agentic list asks to "treat LLM or planner outputs as
  untrusted", with a pre-execution policy enforcement point ("Intent Gate") that validates intent
  and arguments, enforces schemas and rate limits and issues short-lived credentials (ASI02), and
  to "re-verify each privileged step with a centralized policy engine" (ASI03). S. The split is the
  one XACML 3.0 named (OASIS Standard, 2013-01-22): a policy decision point "evaluates applicable
  policy and renders an authorization decision", a policy enforcement point performs access control
  "by making decision requests and enforcing authorization decisions"; policy then lives outside
  application code and can be tested and analyzed on its own (§8). S.
- **Exposing a tool is not authorizing a call.** An audit of LangChain/LangGraph, LlamaIndex and the
  Stripe Agent Toolkit at pinned commits found that all three gate on capability by default and none
  re-authorizes each model-emitted call with its concrete argument values before execution, which
  leaves confused-deputy failures open when the agent also reads untrusted content; the identical
  unauthorized payout call ran under LangChain's default dispatch. The proposed gate (ScopeGate, "a
  five-stage PDP/PEP for agent tool calls") checks scope, authorization, a money ceiling and
  idempotency on every call and denies by default (0 of 48 static bypasses, 0 of 29 adaptive
  attempts). M, 2026-06-27, [arXiv 2606.28679](https://arxiv.org/abs/2606.28679)
  (abstract read 2026-10-01). OWASP lists the same failure among agents: a compromised
  low-privilege agent relays valid-looking instructions to a high-privilege one that "executes them
  without re-checking the original user's intent" (ASI03, confused deputy). S.
- **Delegation narrows authority at each hop.** OAuth 2.0 Token Exchange
  ([RFC 8693](https://www.rfc-editor.org/rfc/rfc8693), 2020) lets each hop trade its token for
  another; it separates impersonation, where the acting party becomes indistinguishable from the
  subject, from delegation, where an `act` claim records the actor (nested for earlier actors) and
  `may_act` names who may act for the subject. The RFC lets the client ask for a narrower audience
  and scope but does not require the issued token to be narrower: narrowing is the authorization
  server's policy. Resource Indicators ([RFC 8707](https://www.rfc-editor.org/rfc/rfc8707), 2020)
  bind a token to one audience: the server "SHOULD audience-restrict issued access tokens to the
  resource(s) indicated". The MCP authorization specification of 2026-07-28 requires clients to
  implement RFC 8707 with the server's canonical URI in both the authorization and the token
  request, on OAuth 2.1 with PKCE; servers must check that a token was issued for them and "MUST
  NOT accept or transit any other tokens", so a server cannot pass a client's token through to the
  next service. S, read 2026-10-01. AWS AgentCore
  Identity added on-behalf-of token exchange on 2026-04-30, trading a user's access token for a
  scoped-down one that carries both the user's and the agent's identity, and Uber's published design
  (2026-05-21) mints a token for each hop, "conceptually based on OAuth 2.0 Token Exchange (RFC
  8693)", with one audience and a lifetime of minutes, carrying "the fully attested actor chain" so
  a policy can evaluate the human initiator and the agent together; its token-exchange service's
  P99 latency stays under 40 ms. L, both read 2026-10-01. A worked RFC 8693 example states the
  choice plainly: send an `actor_token` and the issued token records who acted for whom (`sub` the
  person, `act.sub` the agent); omit it and the agent becomes the user; all six agent-delegation
  Internet-Drafts it surveyed cite RFC 8693. P, 2026-08-03,
  [MojoAuth](https://mojoauth.com/blog/oauth-2-0-token-exchange-rfc-8693-for-agent-delegation-a-worked-example),
  read 2026-10-01. Inherit and narrow, never inherit and keep: a delegate gets the bounds its part
  needs and never more than the delegator holds; OWASP calls the opposite "un-scoped privilege
  inheritance" and asks to flag a low-privilege agent handed higher-privilege scopes through a
  delegation chain (ASI03). P, S.
- **Agents as principals.** Workload identity (SPIFFE, with SPIRE as its implementation) can attest
  an agent and federate it to a governed agent identity such as Microsoft Entra Agent ID. L/P, read
  2026-10-01 through practitioner write-ups. Google Cloud's agent identity gives each agent a SPIFFE
  ID; unlike service accounts, agent identities "are not shared by multiple workloads by default,
  can't be impersonated", and their access tokens are bound to the agent's X.509 certificate. L, IAM
  page updated 2026-09-24, read 2026-10-01. Each agent is a principal with its own identity, a named
  human owner and a stated purpose, never a shared secret: Microsoft's guidance asks for "a
  dedicated agent identity (not a shared secret or reused service account)", "clear human ownership
  for approvals and incident response" and a purpose statement ("what it is allowed to do and why"),
  because "shared secrets across multiple agents erase accountability and make revocation slow and
  incomplete". L, 2026-07-16, read 2026-10-01. OWASP traces the risk to "the architectural mismatch
  between user-centric identity systems and agentic design": without a governed identity of its own
  an agent "operates in an attribution gap that makes enforcing true least privilege impossible",
  and it points to platforms that manage agents as non-human identities with scoped credentials,
  audit trails and lifecycle controls (ASI03). S. A request carries both principals, the agent and
  the person it acts for: Microsoft asks that logs capture "the agent identity, role used ... 'on
  behalf of' user (if applicable)", and token exchange with an actor token puts both in the token
  (above). L, S. Least privilege has several dimensions at once. Microsoft: "Constrain permissions
  by resource boundary (tenant/subscription/workspace/site), by data boundary (collection, label,
  sensitivity), and by operation boundary (read/write/export/admin)"; where a workflow both gathers
  evidence and remediates, "use different roles (or different tools) for read versus write, and gate
  high-impact actions like delete, export, or privilege changes behind step-up approvals"; and time
  is a dimension too: "keep the baseline role minimal, use time-limited entitlements (temporary role
  activation, short-lived tokens, or per-action approvals)", so elevation is just in time and
  reverts by itself. L, 2026-07-16. Practice the field names as anti-patterns, each in Microsoft's
  words where it gave them: broad roles granted to unblock a pilot and never refactored ("temporary
  access that lacks an expiry mechanism becomes permanent access in practice"); one service account
  acting for every user (ambient authority; OWASP's "identity sharing", where an agent lets other
  users act through the identity it holds for one); "you may not access X" in a prompt as the
  control; logging only the model's response, which "creates an audit trail that looks present but
  is useless for forensics", where decisions and enforcement outcomes (tool invocations, scopes,
  authorization result, approval identifier, policy version) are what forensics needs; and grants
  that are each reasonable but compose into a high-impact chain ("the real risk often emerges when
  multiple 'reasonable' roles combine to enable a high-impact chain of actions", so analyze
  aggregate permissions). P (Microsoft and OWASP guidance, read 2026-10-01; the structured audit
  fields from OWASP's cheat sheet, S).
- **Authorize before data reaches the model.** Compile the permission into the query or retrieval
  scope (a policy engine's query plan, such as Cerbos's `PlanResources`, a semantic layer,
  row-level security) rather than filtering results afterwards; the engines and the trade-off are
  in §8 (A8). P, read 2026-10-01.
- **OWASP's agentic list** (OWASP Top 10 for Agentic Applications 2026, published 2025-12-09) names
  ASI01 agent goal hijack, ASI02 tool misuse and exploitation, ASI03 identity and privilege abuse
  (un-scoped privilege inheritance, credentials cached in memory and reused, confused deputies,
  time-of-check to time-of-use drift, escalation through delegation), ASI04 agentic supply chain
  vulnerabilities, ASI05 unexpected code execution, ASI06 memory and context poisoning, ASI07
  insecure inter-agent communication, ASI08 cascading failures, ASI09 human-agent trust
  exploitation, where persuasive output steers a person into an unsafe approval, and ASI10 rogue
  agents. Its controls that bear on authorization: issue short-lived, narrowly scoped tokens per
  task, isolate agent identities and memory per session and wipe state between tasks, and require
  a person's approval for high-privilege or irreversible actions (ASI03); show a dry-run or diff
  before a high-impact action is approved (ASI02); segment memory by user session and domain, scan
  each memory write before commit and expire unverified memory (ASI06); separate preview from
  effect, so a "read-only" preview cannot trigger side effects, and give the person a
  plain-language risk summary rather than a model-generated rationale (ASI09). S, primary document
  read 2026-10-01. OWASP's cheat sheet adds memory isolated between users and sessions with a
  time-to-live, a structured record of each high-risk decision (classification, authorization
  outcome, approval identifier, result, policy version) and of each tool call (agent, session, user,
  tool), cost tracked per session and user, and alerts on abnormal tool-call frequency, cost spikes
  or a rise in high-risk actions (its example thresholds: 30 tool calls a minute, 10 US dollars a
  session). S, read 2026-10-01.
- **Open.** No study of a narrow, dated, expiring grant for one named act; no study of whether a
  goal record that states the authorized acts reduces stops or overreach.

## 5. Containment (A1)

- **Layers.** Claude Code's sandbox has two independent layers: filesystem isolation (which paths
  sandboxed commands can read and write) and network isolation, enforced by a proxy running outside
  the sandbox that pre-allows no domains. `strictAllowlist` denies hosts outside the allowlist
  instead of prompting; `allowUnsandboxedCommands: false` removes the escape hatch by which a failed
  command retries outside the sandbox. L, read 2026-10-01.
- **Credentials out of reach.** A `sandbox.credentials` entry with `"mode": "deny"` blocks a
  credential file and unsets an environment variable for sandboxed commands; `"mode": "mask"` shows
  the command a per-session placeholder and has the proxy substitute the real value on outbound
  requests to the hosts the entry names, so the command and its logs never hold it (the proxy must
  terminate TLS; without it authentication fails and nothing leaks). Credential entries in project
  or local settings are ignored (v2.1.246 and later). L, read 2026-10-01. A token vault does the same
  for delegated access: AWS AgentCore Identity stores OAuth tokens and API keys encrypted, bound to
  one agent and user; its documentation adds that the vault holds OAuth 2.0 tokens, client
  credentials and API keys encrypted with KMS keys, releases them only to an agent that presents
  "verifiable proof of workload identity", validates every access request independently "even from
  callers within the same trust domain", and refreshes credentials automatically, so no secret is
  embedded in agent code or configuration. L, read 2026-10-01. No production credential belongs
  inside an agent's sandbox. P.
- **Non-interactive runs.** A Claude Code `-p` or SDK session treats the folder as trusted, so hooks
  and tool servers a repository commits run without a prompt; `--bare` skips them
  ([harnesses.md](../harnesses/cross-harness.md#8-trust-gates-and-readers-that-load-nothing) §8, §9). L.

## 6. Untrusted content crossing the boundary (A7)

- **A helper's report.** Claude Code scans each subagent's final report before the parent reads it:
  it inserts a backslash into text that imitates its own control tags (such as `<system-reminder>`
  or a line starting `Human:`) and prepends a marker line when the report imitates a tag or names a
  permission setting such as `bypassPermissions`; the report arrives under a header saying that
  instructions or approval claims inside it "carry no authority". The scan judges nothing and does
  not change what an instruction in the report can do. L, read 2026-10-01. It was seen working on a
  report that described `.claude/settings.json` as an attack surface (A, sessions run through the
  Agent SDK, 2026-09-25 and 2026-10-01).
- **What hooks do not see.** Codex's tool hooks miss hosted tools such as web search, and "some
  specialized tool paths can opt out": "Treat tool hooks as a useful guardrail, not a complete
  enforcement boundary". A hook after a tool cannot undo its effect. L, read 2026-10-01.
- **Rendering.** An injected Markdown image whose URL carries data in its query string is stopped
  where output is rendered, by restricting which hosts images and links may reference, not by the
  model: GitLab fixed Duo that way in 2025. P, [Simon Willison](https://simonwillison.net/2025/May/23/remote-prompt-injection-in-gitlab-duo/),
  read 2026-10-01. The "lethal trifecta" of private data, untrusted content and a way to send data
  out is avoided as a combination [practitioners-19]; adaptive attackers bypassed all 12 recent
  injection defenses one study tested [instruction-file-security-authority-27]. P, M.
- **Browsing agents.** At Black Hat USA 2026 a researcher reported that every AI browser he
  analyzed, including Perplexity's Comet and OpenAI's ChatGPT Atlas, was prompt-injectable despite
  system prompts, content tagging and approval steps. A, 2026-08, [Dark Reading](https://www.darkreading.com/application-security/no-perfect-fix-ai-browser-prompt-injection-flaws)
  (read through a search summary, 2026-10-01).

## 7. Secrets (A7)

- In a simulated month of thousands of agents interacting across communities, privacy violations
  rose from 19.95% in single-turn evaluation to 45.30% in multi-turn social settings (OpenAI
  models), and several frontier models leaked in about 50–60% of interactions by 50 tool calls,
  stronger ones in about 20–30%. Leakage spread: a reply that followed a leaking reply leaked 12.8%
  of the time against 1.6% after a clean one, about eight times as often, as the paper's body and
  introduction say (its abstract states 5.1×). Explicit privacy instructions reduced leakage but
  left it above 37.8%; only some models dropped sharply (gpt-5 from 2,296 to 482 leaking replies).
  M, 2026-05-26, [arXiv 2605.27766](https://arxiv.org/abs/2605.27766) (abstract and body read
  2026-10-01). A secret is kept out of what an agent can read or write by a deterministic control (a
  scan before a write, a masked credential, a denied path), not by an instruction.
- Codex saves hook output over about 2,500 tokens to a file under the temporary directory, so its
  documentation advises "avoid returning secrets or other sensitive data in hook output". L, read
  2026-10-01.
- Claude Code's auto mode blocks by default printing a live credential into the transcript or a
  file, and content from a credential store, session transcript or other sensitive file entering a
  commit, push, issue or package unless the person named both source and destination (§2). L.

## 8. Authorization engines and data scope (A8)

Read 2026-10-01. Four families decide at different places; the choice follows the shape of the
permission (relationships, attributes, rows, governed metrics) and where the data is selected.

- **Relationship-based (ReBAC, after Google's Zanzibar): SpiceDB, OpenFGA.** Access follows
  relationships between users and objects and between objects, for example "a user can view a
  document if they have access to its parent folder"; Zanzibar "stores object-relation-user tuples
  and answers checks and reverse queries against the resulting graph", and ReBAC is described as a
  superset of role-based access. It fits hierarchies and sharing that change quickly, "like Google
  Drive's per-document and per-folder sharing". L,
  [OpenFGA](https://openfga.dev/docs/authorization-concepts). Listing every object a user may
  reach has a limit: OpenFGA recommends `ListObjects` when the objects of a type a user can access
  are few (about 1,000) and a small share of the total, and beyond that a local index built from
  its changes endpoint, searched and then checked. L,
  [OpenFGA search with permissions](https://openfga.dev/docs/interacting/search-with-permissions).
  AuthZed reports that OpenAI uses its SpiceDB-based service to keep source permissions for
  enterprise knowledge connected to ChatGPT (Google Drive, OneDrive and Box among the sources), for
  over 5 million business users and over 37 billion documents with fine-grained access control. L
  (vendor customer story, undated), [AuthZed](https://authzed.com/customers/openai).
- **Policy as code, as a decision point: Cerbos, OPA with Rego, Cedar (and Amazon Verified
  Permissions, which uses Cedar 4.7).** Declarative policies over the attributes of principal and
  resource, kept outside application code and tested on their own (`cerbos compile` validates and
  tests policies). Cedar is implemented in Rust, modelled in Lean with its properties proved, and
  designed for "a sound and complete logical encoding, which enables precise policy analysis", for
  example proving that a refactor leaves the authorized permissions unchanged. On its authors'
  three benchmarks Cedar was 28.7–35.2× faster than OpenFGA and 42.8–80.8× faster than Rego. M
  (the language's own authors), 2024-03, [arXiv 2403.04651](https://arxiv.org/abs/2403.04651).
  OPA's core maintainers and part of Styra's engineering team joined Apple in August 2025; OPA
  "remains a CNCF graduated open source project" with no change to governance or licensing, and
  Styra's products pass to the community. L, 2025-08-20,
  [OPA blog](https://openpolicyagent.org/blog/note-from-teemu-tim-and-torin-to-the-open-policy-agent-community-2dbbfe494371).
  Cerbos's `PlanResources` turns a policy into a filter before any data is read: it returns
  always-allowed, always-denied, or a condition as an abstract syntax tree that adapters translate
  into an ORM's or database's query filter (Prisma, SQL, MongoDB), so the query fetches only
  permitted resources. L, [Cerbos API](https://docs.cerbos.dev/cerbos/latest/api/index.html);
  [Cerbos, query plans](https://www.cerbos.dev/blog/filtering-database-results-with-cerbos-query-plans),
  2025-09-25.
- **In the database: PostgreSQL row-level security, SQL authorizers.** A row security policy is
  attached to the table, and "all normal access to the table for selecting rows or modifying rows
  must be allowed by a row security policy", so it holds whatever shape the query takes; with row
  security enabled and no policy, nothing is visible ("default-deny"). Superusers and roles with
  `BYPASSRLS` always bypass it, and table owners do unless the table is set to `FORCE ROW LEVEL
  SECURITY`. L, [PostgreSQL 18](https://www.postgresql.org/docs/current/ddl-rowsecurity.html). A
  policy that reads the caller's identity from a session setting needs that setting bound per
  transaction when connections are pooled (`SET LOCAL` lasts "only till the end of the current
  transaction"), and because policies and the row-security switch belong to the table, a pipeline
  that drops and rebuilds a table has to recreate them. P,
  [PostgreSQL SET](https://www.postgresql.org/docs/current/sql-set.html). A SQL authorizer outside
  the database does the same by rewriting each query: PlainID's authorizer for SQL databases
  sits at the data layer inside the applications or microservices and "dynamically changes the query
  at runtime to return only the data the user is authorized to view", down to rows, columns and
  cells. L, 2023-12-12, [PlainID](https://www.plainid.com/news/plainid-announces-dynamic-security-capabilities-with-sql-databases/).
- **A semantic layer: Cube, often fed by dbt models.** The agent picks governed metrics and
  dimensions by name and the layer generates the SQL; "row-level and role-based rules are evaluated
  when the query is generated", so "the agent can't query data the user isn't allowed to see" and
  an agent acting for one tenant cannot build a query for another tenant's rows; a layer that ships
  an MCP server lets the agent discover and call those definitions instead of writing SQL. Its fit
  is analytics agents. L (vendor), 2026-08-28,
  [Cube](https://cube.dev/articles/semantic-layer-for-ai-agents-2026).
- **Before or after retrieval.** Authorization applied before retrieval or execution, compiled into
  the query or the retrieval scope, keeps unauthorized data out of the model's context and out of
  every result row. A filter applied afterwards is a trade-off, not a fix: AuthZed's guide to
  access control for retrieval treats pre-filtering (look up the documents the user may see, then
  search only those) and post-filtering (check every returned document before the model reads it)
  as a choice by hit rate, post-filtering when most retrieved documents are permitted and
  pre-filtering for a large corpus with few. P, 2026-01-08,
  [Pinecone, RAG access control](https://www.pinecone.io/learn/rag-access-control/). What a
  post-filter cannot do: correct an aggregate or summary already computed over rows the person may
  not see, or help when a loose filter let another tenant's chunk into the candidates (OWASP's
  "cross-tenant vector bleed", ASI06). P, S.

## How to apply

1. Contain before you approve: run agents in a sandbox with network egress through a proxy, keep
   credentials masked or out of reach, and keep production credentials out entirely (A1).
2. Put every boundary that must hold in a permission rule or hook the harness enforces, in a
   settings layer the project cannot override; state each approval rule once (A1, A4).
3. In Claude Code's auto mode, tell the classifier about trusted infrastructure in
   `autoMode.environment`, allow recurring routine acts in `autoMode.allow` with `"$defaults"`, and
   keep a person's checkpoint with a content-scoped `ask` rule plus a hook for the spellings it
   misses (A2, A4).
4. When a goal starts, make its text the session's first message, and approve an action by naming
   it and its target; do not count on a boundary stated once surviving compaction (A2).
5. Treat an automatic reviewer's approval as one more check, not the project's gate (A3).
6. Record a grant as the person's words naming the acts, how many uses, and an end; consume it where
   the next use is checked; make the act idempotent or confirm a duplicate (A5).
7. Re-authorize every tool call with its arguments at a decision point outside the model, bind
   approvals to the exact action, give each agent its own identity and owner, and narrow authority
   at each delegation (A6).
8. Stop exfiltration where output renders and leaves the machine, and keep secrets out by
   deterministic controls (A7).
9. Where an agent reads data for a person, decide the permission where the data is selected (query
   plan, semantic layer, row-level security) and check every item a post-filter passes (A8).

## Limits and open questions

- The classifier and reviewer figures are each vendor's evaluation of its own product; the 52-case
  overeager set is small, and no independent replication was found.
- The observed denials, the reviewer's tally and the 47 compactions come from one repository's
  runs; whether the suggested allow entries clear those denials was not tested.
- The grant patterns (standing grants, delegation, anti-patterns) are practice and vendor guidance,
  not measured; the one measured study of consuming an approval (CapLease) is a single paper.
- The engine comparisons are vendor documentation and, for Cedar's speed, its authors' own
  benchmarks; no independent comparison of the four families for agent workloads was found. The
  OpenAI scale figures are AuthZed's customer story.
- The Black Hat browser report was read through a search summary, not the page itself.

## Sources

Read 2026-10-01 unless dated otherwise.

- Claude Code: permission modes <https://code.claude.com/docs/en/permission-modes>; auto-mode
  configuration <https://code.claude.com/docs/en/auto-mode-config>; hooks
  <https://code.claude.com/docs/en/hooks> (also 2026-09-29); sandboxing
  <https://code.claude.com/docs/en/sandboxing>; sub-agents
  <https://code.claude.com/docs/en/sub-agents>; `claude auto-mode defaults` output, v2.1.283
  (2026-09-28, local record).
- Anthropic: Claude Code auto mode <https://www.anthropic.com/engineering/claude-code-auto-mode>
  (2026-03-25); How we contain Claude (2026-05-25) [anthropic-17]; Claude Code sandboxing
  (2025-10-20) [deterministic-12]; steering Claude Code [anthropic-16].
- Codex: approvals and security <https://learn.chatgpt.com/docs/agent-approvals-security>;
  auto-review <https://learn.chatgpt.com/docs/sandboxing/auto-review>; hooks
  <https://learn.chatgpt.com/docs/hooks>; OpenAI Alignment, Auto-review
  <https://alignment.openai.com/auto-review/> (2026-04-30).
- Papers: arXiv 2608.01710 (CapLease, 2026-08-03), 2606.28679 (capability gates, ScopeGate,
  2026-06-27), 2605.27766 (privacy in multi-agent systems, 2026-05-26), 2608.27443, 2605.14859,
  2403.04651 (Cedar, 2024-03); MIS Quarterly 42(2), 2018 (abstract).
- Standards and guidance: OWASP AI Agent Security Cheat Sheet
  <https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html>; OWASP Top 10
  for Agentic Applications 2026 (2025-12-09; the document downloaded from
  <https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/>); OASIS XACML
  3.0 core specification (2013-01-22)
  <https://docs.oasis-open.org/xacml/3.0/xacml-3.0-core-spec-os-en.html>; RFC 8693
  <https://www.rfc-editor.org/rfc/rfc8693>; RFC 8707 <https://www.rfc-editor.org/rfc/rfc8707>; MCP
  authorization, revision 2026-07-28
  <https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization>; Microsoft, Least
  privilege for AI agents (2026-07-16)
  <https://www.microsoft.com/en-us/security/blog/2026/07/16/least-privilege-for-ai-agents-identity-access-and-tool-binding/>;
  Microsoft Entra Agent ID, agent on-behalf-of flow (updated 2026-08-10)
  <https://learn.microsoft.com/en-us/entra/agent-id/agent-on-behalf-of-oauth-flow>; AWS, AgentCore
  Identity
  <https://aws.amazon.com/blogs/machine-learning/introducing-amazon-bedrock-agentcore-identity-securing-agentic-ai-at-scale/>,
  its features page <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/key-features-and-benefits.html>,
  and its on-behalf-of token exchange announcement (2026-04-30)
  <https://aws.amazon.com/about-aws/whats-new/2026/04/amazon-bedrock-agentcore/>; Uber, Solving the
  agent identity crisis (2026-05-21) <https://www.uber.com/blog/solving-the-agent-identity-crisis/>;
  MojoAuth, RFC 8693 for agent delegation (2026-08-03)
  <https://mojoauth.com/blog/oauth-2-0-token-exchange-rfc-8693-for-agent-delegation-a-worked-example>;
  Google Cloud IAM, agent identity overview
  <https://docs.cloud.google.com/iam/docs/agent-identity-overview>; [forward-6],
  [capability-tier-readers-5], [openai-f4].
- Authorization engines and data scope: OpenFGA concepts
  <https://openfga.dev/docs/authorization-concepts> and search with permissions
  <https://openfga.dev/docs/interacting/search-with-permissions>; SpiceDB
  <https://authzed.com/spicedb>; AuthZed, OpenAI customer story
  <https://authzed.com/customers/openai>; Cerbos API
  <https://docs.cerbos.dev/cerbos/latest/api/index.html> and query plans (2025-09-25)
  <https://www.cerbos.dev/blog/filtering-database-results-with-cerbos-query-plans>; Amazon Verified
  Permissions <https://docs.aws.amazon.com/verifiedpermissions/latest/userguide/what-is-avp.html>;
  OPA, note on the maintainers joining Apple (2025-08-20)
  <https://openpolicyagent.org/blog/note-from-teemu-tim-and-torin-to-the-open-policy-agent-community-2dbbfe494371>;
  PostgreSQL 18 row security policies <https://www.postgresql.org/docs/current/ddl-rowsecurity.html>
  and SET <https://www.postgresql.org/docs/current/sql-set.html>; PlainID SQL database authorizer (2023-12-12)
  <https://www.plainid.com/news/plainid-announces-dynamic-security-capabilities-with-sql-databases/>; Cube,
  semantic layer for AI agents (2026-08-28)
  <https://cube.dev/articles/semantic-layer-for-ai-agents-2026>; AuthZed on Pinecone, RAG access
  control (2026-01-08) <https://www.pinecone.io/learn/rag-access-control/>.
- Injection and exfiltration: Simon Willison on GitLab Duo (2025-05-23) and the lethal trifecta
  [practitioners-19]; [instruction-file-security-authority-27]; Dark Reading on AI browsers at Black
  Hat USA 2026.
- One repository's records: session transcripts, permission denials and Codex approval-reviewer
  rollouts (August and September 2026).
