# Model and harness adapter notes

What one model family's maker, or one harness's own documentation, advises for that model or
harness alone.

- **Checked:** 2026-09-25 to 2026-10-01; each note's Checked line gives the day its own source was
  read.
- **Volatility:** volatile: defaults, API controls and model behaviour change with each release.
- **Re-check when:** a model or harness a note names ships a new version or changes its guide, and
  in any case a quarter after a note's Checked date.

Each note below is advice that one model family's maker, or one harness's own documentation,
gives for that model or that harness. Its heading names the family (as `family` in
`docs/research/_evidence/`) or the harness key (as in `adapters/harnesses.json`) it is for, and
the line under the heading gives the date its source was last read and the source, an evidence
id under `docs/research/_evidence/` or a URL. Read a note when you choose a model, an effort
level or a harness setting, or tune text for a model you run. A note holds for the model or
harness its source names and no other: it is a starting point to test on your own scenarios,
not OutcomeBound doctrine. The notes review official documentation; how an adapter behaves
natively, and what a note gains over its absence, remain unverified.

The portable rules for text a model reads are the prompt standard's, S1 to S22
(`docs/prompt-standard.md`), and the operating contract is
`OutcomeBound.md`; a note overrides neither. Adopt copies none of them into an adopting project.
These notes and the contract ship with the engine, under `outcomebound home`, where the core skill
points for a model, effort, harness or prompting decision; the prompt standard and the evidence
records the notes cite stay in the OutcomeBound repository, at the tag of the release you installed.

Re-read a note's source before you act on it. When you change a note, move its Checked date. Add,
change or retire a note when its source changes, when a harness gains or loses a control a note
names, or when the project's own scenarios show a repeated failure that a note would fix. A
portable rule changes only through a revision of the standard, never here.

## For the standard's next revision

These lines are portable: a method for choosing a model, an effort level or a role, which no rule
of the standard carries. They stand as advice, as the notes below do, until a revision of the
standard takes them in or drops them ("Revising the standard" in `docs/prompt-standard.md`).

Do not assign a model or an effort level to an orchestrator, implementer, reviewer or mechanical
role by prose alone. First fix representative tasks and their success criteria, then compare the
configurations the actual harness offers on them, reading at least:

- outcome completion and the evidence it requires;
- underengineering, and machinery that changes no decision;
- preservation of unrelated work and behaviour at the authority boundary;
- tool correctness and recovery from ordinary failure;
- latency, token use and money spent; and
- whether status reports are accurate and say what the handoff must contain.

Of the configurations that meet the completion bar for that workload, choose the one with the
least total spend of time, tokens and money together. Raise effort, use a more capable model, or
add a separate role only where the comparison shows a material gain. Run the same comparison again
after a model, the harness, the tool surface or the prompt changes.

## Models

### openai: GPT-6, reasoning effort when migrating
Checked: 2026-10-01; source: https://developers.openai.com/api/docs/guides/latest-model

OpenAI's GPT-6 guidance recommends keeping the current effective reasoning effort when migrating,
where the model supports it: GPT-6 Astra and GPT-6.1 Sol have no `none`, and it says to use `low`
instead. To change effort between responses on a GPT-6 model, it says to add a
`configuration_update` item and leave the request-level effort unchanged, which keeps the prompt
prefix for caching.

### openai: GPT-6 Astra, instructions in skills and AGENTS.md
Checked: 2026-09-27; source: https://developers.openai.com/api/docs/guides/latest-model

Because GPT-6 Astra can be more sensitive to instructions in skills and files such as
`AGENTS.md`, the guide recommends auditing them for instructions that could influence its
behavior, and says unclear or conflicting guidance in a skill file may make the model pause and
block work early [openai-8].

### openai: GPT-6 Astra, instructions to run tests
Checked: 2026-09-25; source: openai-10

OpenAI's Astra post says earlier models needed encouragement to run tests and check their work,
and that GPT-6 Astra does this on its own, so the same instructions can lead to unnecessary
testing. The same post warns that guidance for GPT-6 Sol or Luna may differ [openai-f10].

### openai: GPT-6 Astra, boundary language written for earlier models
Checked: 2026-09-25; source: openai-12

Where a project stated boundaries to stop earlier models going too far, the post suggests
reconsidering that language when switching to GPT-6 Astra, which could take it too seriously and
stop where you would be happy for it to continue. As a remedy for its tentativeness, it suggests
giving it permission for a specific workflow you know is safe [openai-f3].

### openai: GPT-6 Astra, pointers in AGENTS.md
Checked: 2026-09-25; source: openai-11

The post advises pointing to documents by condition ("X for schema changes") in `AGENTS.md`,
rather than having the model read a stack of documents or a repository map before every edit,
which spends context and slows the work.

### openai: GPT-6 Astra, skills written as itineraries
Checked: 2026-09-25; source: openai-15

The post says skills written as step-by-step itineraries or recipes can now hinder results where
they once helped. For a skill with several workflows, it makes the root document a short router
to supporting documents and scripts [capability-tier-readers-2]. It adds that guidance which helps
GPT-6 Sol or Luna may overconstrain Astra, so consider which models will read what you leave
[capability-tier-readers-1].

### openai: GPT-6 Sol, Luna and 6.1 Sol, no guide of their own
Checked: 2026-10-01; source: openai-g13; https://developers.openai.com/api/docs/guides/latest-model

OpenAI offers its GPT-6 prompts as a starting point across the family, and says they address
behaviour observed with GPT-6 Astra: evaluate them on Sol or Luna with your own workload
[capability-tier-readers-3]. Codex's base instructions for Sol and Luna already carry "Do not treat
exceptions to requirements in local markdown and skill files as automatically requiring user
approval", so a project line restating it repeats what those models load. At maximum effort in the
Codex harness, Sol and Luna deliverables were measured omitting required rubric elements
[openai-f19]. OpenAI's GPT-5.6 guide gives the matching remedy for over-concision: name what a
deliverable must keep rather than ask for brevity. GPT-6.1 Sol (2026-09-29), offered as near-Astra
performance at a lower price, has no guide of its own either; it accepts `low` to `max` (default
`medium`), and its tool calls go through the Responses API only.

### openai: GPT-5.6, reasoning effort
Checked: 2026-10-01; source: https://developers.openai.com/api/docs/guides/latest-model/gpt-5.6

GPT-5.6 accepts `none`, `low`, `medium` (the default), `high`, `xhigh` and `max`. OpenAI's
reasoning guide maps `none` to latency-critical work such as classification, `low` to
execution-oriented coding, data analysis and tool use, `medium` to planning, complex reasoning and
judgement, `high` to hard reasoning and complex debugging, and `xhigh` to long asynchronous runs,
"only when your evals show a clear benefit"; it says to evaluate `max` against `xhigh`. When
migrating from GPT-5.5 or 5.4, keep the current effort as the baseline and compare one level lower.
Before raising effort, OpenAI's GPT-5.6 prompt guidance says to check whether the prompt lacks a
success criterion, a dependency rule, a tool-routing rule or a verification loop; its GPT-5.5 guide
warns that higher effort with conflicting instructions or weak stopping criteria can overthink
[openai-f18].

### openai: GPT-5.6 and GPT-6, structured outputs and the prompt cache
Checked: 2026-10-01; source: https://developers.openai.com/api/docs/guides/structured-outputs

The first request with a new schema waits while the API processes the schema; later requests with
the same schema do not. In strict mode a refusal arrives in a `refusal` field rather than in the
schema's shape, so the caller handles it. The requested schema is part of the cached prompt
prefix, so a changed schema no longer matches the cached prefix: keep schemas stable and
versioned.

### openai: GPT-5.6, leaner system prompts
Checked: 2026-09-25; source: forward-5

OpenAI's GPT-5.6 guide favours leaner system prompts: remove repeated instructions and examples
and simplify tool descriptions, one group at a time, running the same evaluations again after
each cut. In a sample of its internal coding-agent evaluations, leaner configurations scored
roughly 10 to 15% higher while using 41 to 66% fewer total tokens; the guide calls the ranges
directional [openai-f6].

### claude: Claude 5 models, fewer hard constraints
Checked: 2026-09-25; source: forward-1

Anthropic removed over 80% of Claude Code's system prompt for Claude Opus 5 and Claude Fable 5
with no measurable loss on its coding evaluations. It found it could delete many of the hard
constraints once needed to keep older models from worst cases and let the model use surrounding
context and judgement instead, while still advising constraints in highly important areas
[forward-2].

### claude: Opus 5, response and document length
Checked: 2026-10-01; source: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5

Opus 5's replies run longer than earlier Opus models', its messages in agentic sessions are often
longer, and the files it writes to disk (reports, Markdown documents, summaries) are often longer
than earlier models'. Effort sets how much it thinks, not how much it says, so lowering effort does
not reliably shorten a reply. Anthropic says a short conciseness instruction is effective; in a
long system prompt it pairs the instruction with a short reminder near the end, and for documents
it adds: "Match the length of written documents to what the task needs: cover the substance, but
do not pad with filler sections, redundant summaries, or boilerplate." The guide gives no measured
reduction. This holds for Opus 5: for GPT-6 Sol and Luna, whose deliverables were measured
omitting required elements, the remedy is to name what a deliverable must keep.

### claude: Opus 5, running with thinking disabled
Checked: 2026-10-01; source: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5

Thinking is on by default on Opus 5 and can be disabled only at effort `high` or below;
`thinking: {"type": "disabled"}` with `xhigh` or `max` returns 400. With thinking disabled the
model occasionally writes a tool call into its visible text instead of a `tool_use` block: the turn
completes, the call never runs, and in an agent loop the leaked text stays in the history for later
turns, most often on tool-heavy work such as search. It can also emit `<thinking>` or other
internal tags, and a system-prompt rule telling it not to think or reason makes that worse.
Anthropic's remedy is to keep thinking on and lower the effort: for most tasks, thinking at `low`
effort performs better than thinking disabled at a similar price. Thinking cannot be disabled on
Opus 5.5 at all.

### claude: Opus 5, explicit verification instructions
Checked: 2026-10-01; source: anthropic-22; https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5

Anthropic's Opus 5 guide says the model verifies its own work unasked, and that explicit
verification instructions ("include a final verification step for any non-trivial task", "use a
subagent to verify") cause over-verification on it: remove them from its prompts. The Fable 5
guide's advice to use fresh-context verifier subagents conflicts with this; each holds for its
own model.

### claude: Opus 5.5, effort
Checked: 2026-09-25; source: claude-g13

Start at medium, Opus 5.5's default (Opus 5 defaults to high), set it explicitly, and test several
levels against your own evaluations rather than carrying over the setting used on Opus 5. Thinking
cannot be turned off on Opus 5.5.

### claude: Opus 5.5, lines asking it to think
Checked: 2026-10-01; source: claude-f2; https://claude.dev/blog/getting-the-most-out-of-opus-5-5/

Anthropic's Opus 5.5 guidance removes "think carefully", "think step by step" and similar lines
from prompts and saved instructions, since the model already thinks before every reply; in
Anthropic's testing in a chat product, removing a "think carefully" line made replies start sooner
with no clear drop in quality [forward-16 detail]. This holds for models whose thinking is always
on (Opus 5.5, Fable 5 and 5.1); for Opus 4.8 with thinking off, or Sonnet 5 at low effort,
Anthropic's pages still suggest such a line when effort has to stay low, and its Sonnet 5.5 guide
gives one for reasoning tasks answered in JSON (see that model's notes).

### claude: Opus 5.5, Sonnet 5.5 and Fable 5, reasoning asked for as response text
Checked: 2026-10-01; source: claude-f3; https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5

Prompts, skills or harness instructions that tell Fable 5, Opus 5.5 or Sonnet 5.5 to echo,
transcribe or explain its internal reasoning as response text can trigger the
`reasoning_extraction` refusal; read its summarized thinking blocks instead. Anthropic's server-side
fallback does not retry that refusal, and since 2026-09-24 one that arrives before any output is
billed. This is no concern on a model run with thinking disabled.

### claude: Opus 5.5, stopping to report on long tasks
Checked: 2026-09-25; source: agent-files-20

On long tasks Opus 5.5 sometimes stops to report instead of continuing. Anthropic's Opus 5.5
guidance puts a short rule in `CLAUDE.md` on when to stop and ask and when to keep going, its
example stopping "only when you can't continue without me, or before anything destructive:
deleting data, force-pushing, or changing anything outside this repository."

### claude: Fable 5, refusals and fallback
Checked: 2026-10-01; source: https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback

Fable 5 runs safety classifiers aimed at offensive cybersecurity, biology and life-sciences
content, and extraction of its summarized thinking, and benign work in those areas can trip them;
Fable 5.1, Opus 5, Opus 5.5 and Sonnet 5.5 run them too. A decline is an HTTP 200 response with
`stop_reason: "refusal"` and a `stop_details.category` (`cyber`, `bio`, `frontier_llm`,
`reasoning_extraction`, `general_harms`, or null), so a client branches on the stop reason, and
monitoring built on error rates never sees one. Since 2026-09-24 a decline before any output is
billed in the `bio`, `frontier_llm` and `reasoning_extraction` categories; a decline mid-stream
bills the input and the output already streamed. Server-side fallback (`fallbacks: "default"`, in
beta on the Claude API; not on Message Batches, Bedrock, Google Cloud or Microsoft Foundry, where
the SDK's client-side fallback serves) retries on the model Anthropic recommends for the category,
and does not retry a `reasoning_extraction` decline. The Fable 5 guide names Opus 4.8 as the
fallback; Anthropic's Fable page now routes biology flags to Opus 5. The `fallbacks` parameter does
not reach model calls made inside tool execution, so give those calls their own.

### claude: Fable 5, recording lessons
Checked: 2026-10-01; source: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5

Anthropic's Fable 5 guide says the model "performs particularly well when it can record lessons
from previous runs and reference them", and suggests a place to write them, with this shape: one
lesson per file with a one-line summary at the top; corrections and confirmed approaches alike,
with why they mattered; nothing the repository or chat history already records; an existing note
updated rather than duplicated; notes deleted when they turn out wrong. The guide gives no
measurement. The evidence on agent memory, its benefits and its risks, is in
`docs/research/practices/agent-memory.md`.

### claude: Fable 5, progress audited against tool results
Checked: 2026-09-25; source: forward-15

On long autonomous runs, have Fable 5 audit each progress claim against actual tool results from
the session and report what is not yet verified as unverified. In Anthropic's testing this nearly
eliminated fabricated status reports, even on tasks designed to elicit them [anthropic-21].

### claude: Sonnet 5, literal scope
Checked: 2026-09-25; source: capability-tier-readers-7

Sonnet 5 interprets prompts literally, particularly at lower effort levels: it does not
generalize an instruction from one item to another, and it does not infer requests you did not
make. State each instruction's scope.

### claude: Sonnet 5, filter words in review prompts
Checked: 2026-09-25; source: capability-tier-readers-8

Sonnet 5 may follow phrases such as "only report high-severity issues", "be conservative" or
"don't nitpick" more faithfully than earlier models, so measured recall can fall in a harness
tuned for an earlier model. Ask for coverage and filter in a separate step, or, where the model
filters in one pass, state a concrete bar.

### claude: Sonnet 5.5, effort
Checked: 2026-10-01; source: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5

Sonnet 5.5's effort levels are recalibrated: a level does not produce the thinking it did on Sonnet
5, so run a fresh sweep rather than carry a setting over. Anthropic suggests starting at `high`,
the default; at `medium` for well-specified agentic coding and multistep tool use, moving to `high`
for harder or longer tasks; at `medium` or `low` for chat and other latency-sensitive work; and
keeping `xhigh` and `max` for work where a quality gain was measured. Asking the model in the
system prompt to think less does not reliably reduce its thinking: lower the effort instead.
Changing the top-level effort between requests invalidates the prompt cache, while a per-message
effort change (beta) keeps it.

### claude: Sonnet 5.5, finishing the work and staying in scope
Checked: 2026-10-01; source: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5

At `low` and `medium` effort Sonnet 5.5 sometimes checks in before a coding task is done; at every
level it adds tests, documentation and small supporting files nobody asked for, more at higher
effort; at `xhigh` and `max` it starts its own review rounds, sometimes with reviewer subagents.
Anthropic's guide gives a line for each: keep working until everything asked for is done, and stop
to ask only when the model cannot go on without the user or before a risky step; once the
requested work is done and checked, stop and report, and mention a possible addition instead of
making it; at the two highest levels, start no extra review rounds or reviewer subagents unasked.
In its testing at `max`, the last line stopped the reviewer subagents and cut a session's spend by
about a third with no change in quality. These lines do not replace a project's own rules about
risky or irreversible actions.

### claude: Sonnet 5.5, running without up-front thinking, and answers in JSON
Checked: 2026-10-01; source: https://platform.claude.com/docs/en/models/sonnet-5-5/whats-new-sonnet-5-5

`thinking: {"type": "disabled"}` returns 400 on Sonnet 5.5. Its lowest setting, `between_tools`,
is accepted at `high` effort or below, and in a request without tools the model then answers
without thinking. With `between_tools`, remove any instruction that tells the model not to think,
which makes internal tags in its visible output more likely. For reasoning tasks answered in JSON,
use adaptive thinking and end the system prompt with "Think the problem through before you
answer."; at `high`, that line brought accuracy close to `xhigh` in Anthropic's testing. Where the
JSON is asked for in the prompt rather than through structured outputs, parse the last JSON value
in the response, and treat a response that stopped at `max_tokens` as failed.

### claude: Sonnet 5.5, messages after tool results
Checked: 2026-10-01; source: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5

Sonnet 5.5 is trained to resist instructions planted in tool results, and sometimes treats a
genuine user message as one: when a user's mid-task message arrives directly after a tool result or
inside a `tool_result` block, or when the harness appends a token countdown or instructions after
every tool result. Deliver mid-turn user input as a user turn after the last `tool_result`, keep
harness notices in a separate mid-conversation system message, and in interactive sessions add no
countdown of your own after tool results. An occasional reminder after several silent
tool-calling steps is far less likely to cause the misread; send reminders less often if it does.

### claude: Haiku, no guide of its own
Checked: 2026-10-01; source: capability-tier-readers-9; https://www.anthropic.com/claude-sonnet-5-5

Anthropic's prompting best practices cover models through Haiku 4.5 with no Haiku-specific
guide, and say that where a technique names a specific model, it is measured on that model:
re-check it against your own evaluations before applying it to Haiku. Anthropic measured Haiku
4.5 far behind Opus 5.5 on long coding tasks, and places it for high-volume work with checkable
outputs rather than long agentic loops [capability-tier-readers-11]. On 2026-09-28 Anthropic said
Haiku 5.5 "will join the Claude 5.5 family in the coming weeks"; until its guide appears, Haiku 4.5
is the current Haiku.

### claude: context engineering
Checked: 2026-10-01; source: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

Anthropic's context-engineering guidance for agents aims for the smallest set of information that
fully specifies the expected behaviour, and says that this set need not be short: the agent still
needs enough up front to behave correctly [anthropic-2]. It starts by testing such a prompt on the
most capable model available, and adds instructions and examples in response to the failure modes
that testing finds [anthropic-3]. It organizes a prompt into distinct sections, while saying their
exact formatting is likely becoming less important as models become more capable, and keeps tools
distinct, narrowly described and relevant to the request.

### grok: Grok 4.7, returned reasoning and output length
Checked: 2026-09-25; source: grok-g12

grok-4.7 always returns `reasoning.encrypted_content` on the Responses API; passing reasoning
items back unchanged keeps its reasoning, and cache hits, across turns, though a client that
ignores the field keeps working. At xhigh it used about 81k output tokens per Artificial Analysis
Intelligence Index task, against 38k for Grok 4.6 at xhigh and 36k at high [grok-f12]. xAI says it
self-verifies more effectively [grok-f13]; Artificial Analysis measured a 3.7-point regression on
its long-context benchmark, and xAI's docs recommend context compaction for long agent loops
[grok-f18].

## Harnesses

### claude-code: boundaries that must hold
Checked: 2026-09-25; source: anthropic-16

Anthropic's guidance for Claude Code enforces a rule that must hold ("never do X", "every time X,
always do Y") with hooks and permissions, or managed settings, rather than writing it only in
`CLAUDE.md`, because a prompted rule fails under pressure, in long sessions or under prompt
injection. Name the enforced boundary in the prompt, so the agent can plan around it.

### claude-code: Explore and Plan subagents load no CLAUDE.md
Checked: 2026-09-25; source: capability-tier-readers-13

Claude Code's built-in Explore and Plan subagents skip `CLAUDE.md` files and the git status
snapshot; every other built-in and custom subagent loads both, unless its definition sets
`omitClaudeMd`. What those two must hold reaches them only in the prompt that delegates to them.
