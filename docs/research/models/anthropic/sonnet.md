---
last_checked: 2026-10-01
volatility: MONITOR (Sonnet 5.5 shipped 2026-09-28; its defaults and removed controls are new)
sources:
  - https://platform.claude.com/docs/en/models/sonnet-5-5/overview
  - https://platform.claude.com/docs/en/models/sonnet-5-5/whats-new-sonnet-5-5
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5
  - https://www.anthropic.com/claude-sonnet-5-5
  - https://platform.claude.com/docs/en/release-notes/overview
---

# Claude Sonnet 5 and 5.5

What Anthropic's current Sonnet models are, what their API accepts, how they behave and how
Anthropic says to prompt them. For anyone running Sonnet as a main or subagent model, or writing
text it will read. Shared Claude 5 behaviour is in
[claude-5-family-prompting.md](claude-5-family-prompting.md); Sonnet 4.x is in
[earlier-generations.md](earlier-generations.md). Labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations).

## Identity and availability (VOLATILE)

| | Sonnet 5.5 | Sonnet 5 |
| --- | --- | --- |
| API id | `claude-sonnet-5-5` | `claude-sonnet-5` |
| Status | Latest; released 2026-09-28; retirement not sooner than 2027-09-28 | Legacy; released 2026-06-30 |
| Positioning | "The best combination of speed and intelligence"; comparative latency "Fast" | Coding and agentic tasks |
| Context / output | 1M / 128K; 300K on Message Batches (beta) | 1M / 128K |
| Price per MTok | $2 / $10 (Sonnet 5's prices, caching and batch included) | $2 / $10, introductory from launch and made standard on 2026-08-10 (the scheduled rise to $3 / $15 was cancelled) |
| Thinking | Adaptive by default; lowest setting `between_tools` | Adaptive by default; `disabled` accepted |
| Default effort | `high`, levels recalibrated | `high` |
| Tokenizer | Sonnet 5's | New tokenizer, about 30% more tokens than Sonnet 4.6 |
| Knowledge cutoff | Jun 2026 | — |

- Sonnet 5.5 is on the Claude API, Bedrock (`anthropic.claude-sonnet-5-5`), Google Cloud, Microsoft
  Foundry and Claude Platform on AWS; generally available on all of them from 2026-09-28, which
  settled forecast A1a early ([../cross-family.md](../cross-family.md#8-forecasts)).
- Sonnet 5.5 and Sonnet 5 each have their own rate limit, outside the combined Sonnet 4.x bucket.
- Anthropic reports Sonnet 5.5 costing up to 30% less per task than Sonnet 5 at the same token
  prices [lab; chk-sonnet-55], and gives it 70.6% on Terminal-Bench 4.0 against 10.3% for Sonnet 5
  [chk-sonnet-55]. On Scale's SWE-Bench Pro V2, Sonnet 5 scored 88.2 [measured-g22].
- Priority Tier is not available on Sonnet 5.

## API surface (STABLE)

Sonnet 5 (from Sonnet 4.6): adaptive thinking on by default, where 4.6 ran without thinking;
manual extended thinking (`budget_tokens`) returns 400 (deprecated on 4.6); non-default
`temperature`, `top_p` or `top_k` returns 400, new for Sonnet-class models; `thinking: {"type":
"disabled"}` turns thinking off; `max_tokens` covers thinking plus reply, so revisit it for
workloads that ran without thinking [claude-g10].

Sonnet 5.5, five breaking changes from Sonnet 5 [chk-sonnet-55]:
1. **`between_tools` replaces `disabled`.** `{"type": "disabled"}` returns 400 pointing to
   `between_tools`, the lowest setting, which turns off thinking before the first reply. It is
   accepted at `low`, `medium` and `high` (400 at `xhigh` or `max`); takes no other field
   (`display`, `budget_tokens` or `block_binding` with it return 400); and fixes effort for the
   conversation (a differing per-message effort returns 400). Progress updates between tool calls
   still come back as `thinking` blocks to pass back unchanged; in a request without tools the
   response is text only, "as with `disabled` on Claude Sonnet 5".
2. **Forced tool use** (`tool_choice` `any` or `tool`) returns 400, also on the token-counting
   endpoint; for a tool that must be called, "say in the prompt when the tool applies".
3. **Thinking blocks are tied to model and conversation.** Sonnet 5.5 reads blocks from Sonnet 5,
   Opus 4.8, Haiku 4.5 and earlier, but not from Opus 5, Opus 5.5, Fable or Mythos; on the Claude
   API Opus 5.5 reads Sonnet 5.5's blocks and no other model does. The API silently drops a block
   the target model cannot read. The prefix check (400 on a replayed block after an edit to the
   system prompt, tools or an earlier message) is enforced for accounts created on or after
   2026-08-31 on the Claude API, Bedrock and Google Cloud; `block_binding` works only with adaptive
   thinking. Blocks also work only in the account that produced them or a linked one; another
   account's are dropped.
4. **Computer use:** on the Claude API and Google Cloud only the `computer_toolset_20260801`
   toolset; `computer_20251124` still works on Bedrock.
5. **Advisor tool:** a Sonnet 5.5 executor needs an advisor from Mythos 5.1, Fable 5.1, Mythos 5,
   Fable 5, Opus 5.5, Opus 5 or Sonnet 5.5; Opus 4.8, Opus 4.7 and Sonnet 5 advisors return 400, and
   accepted advisors return their advice encrypted.

Also on Sonnet 5.5: text between tool calls longer than a sentence or two arrives as progress-update
`thinking` blocks, empty at the default display (with `between_tools` the text comes back);
per-message effort (beta), mid-conversation system messages and tool changes (beta), which Sonnet 5
lacks; minimum cacheable prompt 512 tokens (Sonnet 5: 1,024); compaction on demand and tools
defined in a message (beta). Safeguards can decline in five categories (`cyber`, `bio`,
`frontier_llm`, `reasoning_extraction`, `general_harms`); server-side fallback (`fallbacks:
"default"`, beta, Claude API) retries `cyber` and `frontier_llm` declines on Sonnet 5 and does not
retry `bio`, `reasoning_extraction` or `general_harms`. When a `between_tools` request falls back to
Sonnet 5, the fallback runs with `disabled` and `display: "omitted"`.

## Behaviour (MONITOR)

Sonnet 5 (its guide; it "performs well out of the box on existing Claude Sonnet 4.6 prompts"):
- Calibrates length to the task rather than a fixed verbosity.
- **Literal:** "does not infer requests you didn't make" and does not generalize an instruction from
  one item to another, particularly at lower effort; state each instruction's scope [claude-g10,
  capability-tier-readers-7].
- Respects effort strictly, especially at the low end: at `low` and `medium` it scopes its work to
  what was asked, with some risk of under-thinking on moderately complex tasks at `low`.
- **Filter words in review prompts:** it may investigate as thoroughly, find the bugs, then not
  report those below a stated bar ("only report high-severity issues", "be conservative", "don't
  nitpick"); precision rises and measured recall can fall, a harness effect rather than a capability
  loss [claude-f13, capability-tier-readers-8].
- May settle into a default visual style on open-ended frontend briefs; generic counter-instructions
  shift it to another fixed palette.
- Tracks its remaining context through API-injected tags (as Sonnet 4.5 and 4.6 do; Sonnet 5.5 does
  not; see [practices/long-context-and-compaction.md](../../practices/long-context-and-compaction.md#3-context-awareness-countdowns-and-early-wrap-up-volatile)).

Sonnet 5.5, compared with Sonnet 5 [chk-sonnet-55]:
- **Effort recalibrated:** a level does not produce the thinking it did on Sonnet 5.
- At `low` and `medium` it sometimes checks in before a coding task is done.
- At every effort level it adds tests, documentation and small supporting files nobody asked for,
  more at higher effort, while the requested change itself stays close to the request.
- At `xhigh` and `max` it starts its own review rounds, sometimes with reviewer subagents.
- Generally checks its work before reporting a change done, but at `low` sometimes reports it done
  without running a check that exercises it.
- Trained to resist instructions planted in tool results, it sometimes treats a genuine user message
  as one: a mid-task message delivered right after, or inside, a tool result, or a harness countdown
  or instructions appended after every tool result.
- For reasoning tasks answered in JSON it often answers without thinking.

## Prompting (MONITOR)

Sonnet 5 (its guide):
- **Effort first.** If reasoning is shallow, raise effort rather than prompt around it; where effort
  must stay `low`, Anthropic gives a targeted "think carefully" line. Thinking frequency is
  steerable; measure the effect.
- **Review harnesses:** say the finding stage is for coverage and filter in a separate step; where
  the model must filter in one pass, give a concrete bar ("report any bugs that could cause
  incorrect behavior, a test failure, or a misleading result; only omit nits like pure style or
  naming preferences") [measured-f14].
- **Design variety:** give a concrete alternative spec, or have it propose options before building
  (the way to vary output now that `temperature` is rejected).
- **Interactive coding products:** give the task, intent and constraints in the first turn;
  requirements revealed over several turns lower token efficiency and sometimes performance.
- Positive examples of the wanted concision work better than prohibitions.

Sonnet 5.5 (its guide) [chk-sonnet-55]. Existing Sonnet 5 prompts "should perform well without
changes"; the guide also tells readers to remove instructions such as "hold all findings for the
final response", wording that discourages tool use, and instructions not to think (which settled
forecast A4a).
- **Finishing and scope:** keep working until everything asked for is done, and stop to ask only
  "when you can't go on without the user or before a risky step"; once the requested work is done
  and checked, stop and report, mentioning a possible addition instead of making it; at `xhigh` and
  `max`, start no extra review rounds or reviewer subagents unasked. In Anthropic's testing at
  `max`, that last line stopped the reviewer subagents and cut a session's spend by about a third
  with no change in quality [lab]. The carry-through line lengthens sessions. These lines do not
  replace a project's own rules about risky or irreversible actions.
- **Verification at `low`:** a line requiring a check that exercises the change made skipped or
  superficial checks rare, with no measurable change in quality and slightly higher cost [lab].
- **Messages after tool results:** deliver mid-turn user input as a user turn after the last
  `tool_result`; keep harness notices in a separate mid-conversation system message; in interactive
  sessions add no countdown of your own after tool results. Task budgets (beta) add a similar
  countdown but have not been seen to cause the misread; an occasional reminder after several
  silent tool steps is far less likely to.
- **Progress updates:** at `high` with a send-to-user tool available, a reminder made the model
  update more often and shortened its longest silent stretches, with no measurable change in
  quality [lab].
- **JSON answers:** for reasoning tasks answered in JSON, use adaptive thinking and end the system
  prompt with "Think the problem through before you answer."; at `high` that line brought accuracy
  close to `xhigh` in Anthropic's testing. Where JSON is asked for in the prompt rather than through
  structured outputs, parse the last JSON value and treat a response stopped at `max_tokens` as
  failed. With `between_tools`, remove any instruction not to think, which makes internal tags in
  the output likelier.

## Effort and thinking (MONITOR)

- Sonnet 5: `max` for absolute capability; `xhigh` for the hardest coding and agentic work; `high`
  the default; `medium` for cost-sensitive work; `low` for short, scoped, latency-sensitive tasks.
  Sonnet 5 at `medium` is comparable to Sonnet 4.6 at `high`, and at `high` to Sonnet 4.6 at `max`;
  benchmark by observed thinking length, not effort name. Leave headroom in `max_tokens` at `high`
  and above, or a response can be almost all thinking and stop at `max_tokens` [claude-g10].
- Sonnet 5.5: re-run the sweep. Start at `high` unless the work is agentic or latency-sensitive; for
  agentic coding and multistep tool use, `medium` for well-specified tasks and `high` for harder or
  longer ones; for chat, `medium` or `low`; `xhigh` and `max` only with a measured gain. Asking the
  model in the system prompt to think less does not reliably reduce its thinking: lower the effort.
  A top-level effort change invalidates the prompt cache; a per-message change (beta) keeps it.
- "Think carefully" lines: Anthropic still suggests one for Sonnet 5 at low effort, and for Sonnet
  5.5 gives "Think the problem through before you answer." for JSON reasoning tasks, while telling
  Opus 5.5 users to delete such lines [claude-f2, forward-16]. Each holds for its own model.

## Caching and pricing (VOLATILE)

- $2 / $10 per MTok; 5-minute cache write $2.50, 1-hour write $4, cache read $0.20; batch 50% off.
- Minimum cacheable prompt 512 tokens on Sonnet 5.5, 1,024 on Sonnet 5. A mid-conversation system
  message keeps the cache on Sonnet 5.5, not on Sonnet 5. Details in
  [practices/prompt-caching.md](../../practices/prompt-caching.md#2-anthropic-volatile).

## Lineage (VOLATILE)

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| Sonnet 5 | 2026-06-30 | Adaptive thinking on by default. `budget_tokens` and non-default sampling return 400. About 30% more tokens (new tokenizer). Literal: "does not infer requests you didn't make". Medium effort comparable to Sonnet 4.6 at high | claude-g10 |
| Sonnet 5.5 | 2026-09-28 | $2/$10 per 1M tokens (Sonnet 5's prices), 1M context, Sonnet 5's tokenizer; Anthropic reports it up to 30% cheaper per task than Sonnet 5. Adaptive thinking on by default; `disabled` returns 400 and `between_tools`, accepted at `high` or below, turns off thinking before the first reply; forced `tool_choice`, `budget_tokens` and non-default sampling return 400. Default effort `high`, levels recalibrated: re-run the effort sweep, start agentic coding at `medium`. At `low` and `medium` it may check in before a task is done; it adds unrequested tests and docs at every level; at `xhigh` and `max` it starts its own review rounds. Text between tool calls returns as thinking blocks. User text placed after tool results, and a countdown after every tool result, can read to it as prompt injection. For reasoning tasks answered in JSON, a "think the problem through" line. Haiku 5.5 is to follow "in the coming weeks" | chk-sonnet-55 |

Forecasts settled by Sonnet 5.5's release (scored in
[../cross-family.md](../cross-family.md#8-forecasts)): A1a held, A2 held, A4a held, and the Sonnet
half of A3 was falsified in effect, since `between_tools` answers without thinking in a request
without tools.

## Sources

- [chk-sonnet-55] Claude Sonnet 5.5, read 2026-10-01: model page
  <https://platform.claude.com/docs/en/models/sonnet-5-5/overview>, what's new
  <https://platform.claude.com/docs/en/models/sonnet-5-5/whats-new-sonnet-5-5>, prompting guide
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5>,
  announcement, 2026-09-28 <https://www.anthropic.com/claude-sonnet-5-5>.
- Prompting Claude Sonnet 5, read 2026-10-01
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5>.
- Claude Platform release notes (Sonnet 5 launch 2026-06-30, pricing 2026-08-10, Sonnet 5.5 launch
  2026-09-28), read 2026-10-01 <https://platform.claude.com/docs/en/release-notes/overview>.
- Refusals and fallback, rate limits, read 2026-10-01 (URLs in
  [claude-5-family-prompting.md](claude-5-family-prompting.md#sources)).
