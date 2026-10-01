---
last_checked: 2026-10-01
volatility: MONITOR (memory research is mostly 2026 preprints and moves fast) / VOLATILE (§1, where each harness keeps memory)
sources:
  - https://code.claude.com/docs/en/memory
  - https://developers.openai.com/codex/memories
  - https://docs.devin.ai/desktop/cascade/memories
  - https://help.getzep.com/mem0-to-zep
  - https://a2a-protocol.org/latest/specification/
  - https://modelcontextprotocol.io/specification/2026-07-28/changelog
  - https://www.w3.org/community/ai-agent-memory-interop/
  - https://unit42.paloaltonetworks.com/indirect-prompt-injection-poisons-ai-longterm-memory/
  - https://docs.mem0.ai/core-concepts/memory-operations/delete
  - https://www.letta.com/blog/benchmarking-ai-agent-memory
  - https://arxiv.org/abs/2606.04329
  - https://arxiv.org/abs/2605.29463
  - https://arxiv.org/abs/2507.05257
  - https://arxiv.org/abs/2410.10813
  - https://arxiv.org/abs/2501.13956
---

# Agent memory

Re-check when a harness changes where or how it keeps memory, a memory product changes what it
stores or deletes, or a new memory benchmark or poisoning study appears; in any case by 2027-01-01.

Where coding agents' memory lives, whether it moves between tools, how it is poisoned, confabulated,
goes stale or fails to forget, why long context is not memory, what memory benchmarks show, and how
labs say to write memory. For anyone who designs memory or handoffs for agents, or chooses a memory
system. The rules for memory shared in a repository are in [agent-workspace.md](agent-workspace.md)
§4; summaries and their faithfulness in [summarization-layers.md](summarization-layers.md); long
context and compaction in [long-context-and-compaction.md](long-context-and-compaction.md).

**Evidence classes**, as in [the index](../README.md): M measured; L lab or vendor documentation or
guidance; S standard or protocol specification; P practitioner consensus; A anecdote or one
uncontrolled report; F forecast; O own result. **Citations.** Bracketed ids resolve in
[`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl); "[id] detail" is the sweep reader's
note on that record, which the fact-check did not separately verify. `[chk-…]` ids are pages re-read
on 2026-10-01, listed under Sources. Papers are cited by arXiv id and were read on 2026-10-01; a
number taken from a paper's body rather than its abstract is marked "body". Most memory studies are
2026 preprints, several by one author; product claims come from the vendors.

## Key findings

**CM7. Agent memory is local, does not move between tools, and is open to attack.** Harness memory
lives on one machine and is not committed; memory products store different things, and the
documented migration is to re-ingest the raw data; no memory format is standard. The best
prompt-injection defense tested caught 67.7% of memory-poisoning attempts and 42.5% of those with no
syntactic anomaly; false memories reinforce themselves across trials; and selective forgetting fails
(at most 28% on multi-hop cases). M, L.

**CM8. Memory benchmarks are weak evidence for choosing a memory system.** On LoCoMo a full-context
baseline scored about 73% and plain files 74.0%, above a specialised memory product; models
near-perfect there fell to 40–60% on active memory management; and no benchmark found scores the
quality of an agent's ordinary memory writes. M, A.

## 1. Where harness memory lives (VOLATILE)

| Harness | Where | Shared with | Loaded |
| --- | --- | --- | --- |
| Claude Code auto memory | `~/.claude/projects/<project>/memory/`, the project derived from the Git repository | The repository's worktrees on that machine; "not shared across machines or cloud environments" | The first 200 lines or 25KB of `MEMORY.md` each session, topic files on demand; not in subagents except forks; re-read from disk after compaction; kept out of the transcript retention sweep [chk-claude-memory, harness-loading-coverage-6] |
| Codex memories | `~/.codex/memories/`; off by default | One machine | "Treat memories as a helpful recall layer, not as the only source for rules that must always apply"; secrets redacted in generated fields; chats that used outside context can be kept out [chk-codex-memories] |
| Devin Desktop (Windsurf) Cascade | `~/.codeium/windsurf/memories/`, per workspace | One workspace; "not committed to your repository"; the default Devin Local agent keeps none | When Cascade judges them relevant [chk-devin-memories, harness-loading-coverage-22] |
| Qwen Code | `~/.qwen/projects/<project>/memory/` | Private by default; an opt-in team memory is tracked in Git | Cleaned daily [harness-loading-coverage-26] |
| ZCode | Written by the agent; off by default; `AGENTS.md` kept by hand in the repository | One machine | Not documented [glm-f6 detail] |
| GitHub Copilot | GitHub's service, per repository; only users with write access create entries | Copilot's cloud agent, code review and CLI | Cited facts checked against the current branch; deleted after 28 days unused [harness-loading-coverage-16] |
| Muse Code | A committed `MEMORY.md` plus topic files | Every clone | An index of up to 48 paths, even in an untrusted workspace [other-labs-27 detail] |

The only memory every harness and every clone reads is committed files. L.

## 2. Memory does not move between tools

- **Products store different things.** Mem0 distils durable facts with a model extraction pass; Zep,
  built on Graphiti, keeps a temporal knowledge graph whose edges carry validity windows; Letta,
  since March 2026, projects memory into Git-backed files the agent edits with file tools
  [chk-particula] (A, a comparison write-up). Zep's model is bi-temporal: it records when a fact held
  and when it was ingested, and closes a contradicted fact's validity window instead of deleting it
  [arXiv 2501.13956]. L.
- **Migration means re-ingesting.** Zep's guide: "Do not translate each Mem0 memory into a Zep fact.
  Ingest the source messages or records so Zep can build the graph" [chk-zep-migration]. L.
- **Lock-in.** LangChain's Harrison Chase argues that memory held in a closed harness "creates
  incredible lock in", citing Codex's encrypted compaction summary, unusable outside OpenAI's
  ecosystem, and an agent of his, deleted by accident, whose preferences he had to teach again to its
  replacement [chk-chase]. A.
- **No standard.** A2A, at v1.0 under the Linux Foundation with more than 150 organisations by
  2026-04-09, has agents collaborate "without needing access to each other's internal state, memory,
  or tools" and defines no shared memory [chk-a2a]. MCP's 2026-07-28 revision removed protocol-level
  sessions; servers that need state across calls mint handles passed as ordinary arguments
  [chk-mcp]. S.
- **Proposals.** Portable Agent Memory: content-addressed entries in a Merkle-DAG, BLAKE3 hashing,
  Ed25519 signing, scoped capability tokens, a 54-test SDK and a 50-task pilot its author calls
  "directional rather than definitive" [arXiv 2605.11032]. memorywire: a JSON-Schema wire format for
  remember, recall, forget, merge and expire, with a provenance field and signing only on its roadmap
  [arXiv 2606.01138]. A W3C AI Agent Memory Interoperability Community Group, created 2026-06-03 with
  28 participants, which does not speak for W3C [chk-w3c-cg]. M (one-author pilots), L.

## 3. Poisoning

- **Defenses fall short.** On MPBench (3,240 attack cases, 2,997 benign), "no defense achieves both
  high TPR and low FPR simultaneously": the best, PromptArmor, detected 67.67% at 1.00% false
  positives (61.6% after adaptation) and 42.50% of weak-signal attacks, whose payload "carries no
  syntactic anomaly" and reads as legitimate domain knowledge (body) [arXiv 2606.04329]. M.
- **On a shipping product.** Unit 42 showed a malicious web page manipulating an Amazon Bedrock
  agent's session-summarization step so that instructions were stored in memory, persisted into
  later sessions and let the agent exfiltrate conversation history; it calls this prompt injection,
  "not a vulnerability in the Amazon Bedrock platform" (2025-10-09) [chk-unit42]. A (proof of
  concept).
- **Recovery.** memorywire's author reports its provenance field as the strongest lever for
  recovering a poisoned store [arXiv 2606.01138]. M (one author).
- **The rest.** Memory-file attacks on coding agents, poisoning across chains of agents, OWASP's
  ASI06 and the defenses that held are in [agent-workspace.md](agent-workspace.md) §4: poisoning is
  contained (a source per fact, no authority, a way to drop one source's entries), not prevented.

## 4. Confabulation, staleness and forgetting

- **Confabulation.** Reflexion-style agents on ALFWorld and HumanEval stored confident but wrong
  readings of their task and kept acting on them "across trials, even though the environment resets
  to the correct task each time"; one pursued a fabricated task for 14 consecutive trials. Unlike a
  one-off hallucination, the false content "is stored, retrieved, acted upon, and reinforced by later
  reflections", and "A memory system that stores confident, plausible-sounding but wrong beliefs is
  worse than no memory at all for the tasks those beliefs affect" [arXiv 2605.29463]. M. A
  consolidated note that cites only earlier notes inherits their errors (inference): trace each fact
  to its source or to a person's statement.
- **Forgetting.** On MemoryAgentBench every method scored at most 28% on multi-hop selective
  forgetting, and "Selective Forgetting cannot be solved by prompt engineering alone" (body) [arXiv
  2507.05257]. M.
- **Staleness.** Mem0 counts memory staleness among the hardest open problems ("accurate until they
  change jobs, at which point it becomes confidently wrong"), and reports, with no data shown, that
  continuously running agents reach 80,000–120,000-token contexts within two to three weeks, memory
  bloat a main contributor [chk-mem0]. A (vendor). In one benchmark, memory systems still used stale
  items 20% of the time ([agent-workspace.md](agent-workspace.md) §4). M.
- **Concurrent writes.** "Silent last-write-wins is almost never correct—it corrupts shared truth
  without leaving evidence that corruption occurred" [chk-oreilly]. P.
- **Superseded is not deleted.** Graphiti, under Zep, does not delete a contradicted fact: "it
  invalidates the affected edges by setting their t_invalid to the t_valid of the invalidating
  edge", keeping the old fact for history [arXiv 2501.13956]. L (the vendor's paper). Mem0 deletes
  by id, in batches and by filter, and presents this as meeting user-erasure requests
  [chk-mem0-delete]. L. Which a store does decides whether a fact is gone or only marked past, and
  a summary built from a deleted fact keeps it until rebuilt
  ([summarization-layers.md](summarization-layers.md) §1).
- **Dates.** Keep when a fact held apart from when it was recorded, as Zep's bi-temporal model does
  (§2). Claude Code stamps a memory file's write time in a `modified` field (v2.1.214 and later)
  [chk-claude-memory]. L.

## 5. Long context is not memory

- **LongMemEval** (500 questions): long-context models lost 30–60% against answering from the
  evidence sessions alone (GPT-4o 0.870 to 0.606), and ChatGPT and Coze lost 37% and 64% against
  reading the same history offline (body) [arXiv 2410.10813]. M.
- **MemoryArena**, as a 2026 survey relays it: models near-perfect on LoCoMo's passive recall fell to
  40–60%, and replacing an active memory agent with a long-context-only baseline dropped task
  completion from over 80% to about 45% on interdependent multi-session tasks [arXiv 2603.07670]. M.
- **BEAM** (conversations up to 10M tokens; 100 conversations, 2,000 questions): "even LLMs with 1M
  token context windows (with and without retrieval-augmentation) struggle as dialogues lengthen"
  [arXiv 2510.27246]. M.
- **Retrieved memory against the full history.** On LongMemEval conversations of about 115K tokens,
  Zep's retrieved context of about 1.6K tokens scored 71.2% against 60.2% for the full history with
  gpt-4o, at about a tenth of the latency [arXiv 2501.13956]. M (the vendor's own paper).

## 6. What memory benchmarks show

- **LoCoMo is near its ceiling for plain methods.** A full-context baseline scored about 73% in Mem0's
  own paper [arXiv 2504.19413], and Letta's agent, storing conversation histories in files, scored
  74.0% with gpt-4o-mini, above Mem0's reported 68.5% for its graph variant; Letta reads this as
  "current memory benchmarks may not be very meaningful" [chk-letta]. M (vendors). Locomo-Plus
  argues that LoCoMo tests only surface factual recall, with string-matching metrics that misjudge
  answers [arXiv 2602.10715]. M.
- **What to read instead.** Benchmarks of active use, forgetting and length: MemoryArena,
  MemoryAgentBench, LongMemEval and BEAM (§4–§5).
- **Writes.** MPBench scores whether an attack was written into memory, and memorywire's PurgeBench
  scores recovery of a poisoned store; no benchmark found scores the quality of an agent's ordinary
  writes (`UNVERIFIED`).
- **"Files beat vector retrieval."** The claim rests on the LoCoMo result above and is not settled. A.

## 7. How labs say to write memory

- **Anthropic, for Fable 5.** The model "performs particularly well when it can record lessons from
  previous runs and reference them"; the suggested shape is one lesson per file with a one-line
  summary at the top, corrections and confirmed approaches alike with why they mattered, nothing the
  repository or chat history already records, an existing note updated rather than duplicated, and
  notes deleted when they turn out wrong [chk-claude-pages]. L (no measurement). Its Fable 5
  announcement reports that persistent file-based memory improved Fable 5's play of one deck-building
  game three times more than it improved Opus 4.8's [chk-claude-pages]. M (lab, one game).
- **Claude Code.** Auto memory skips what Claude can derive from the codebase and what `CLAUDE.md`
  already says; `MEMORY.md` is an index and details live in topic files [chk-claude-memory]. L. Read
  from leaked source, its design is an index, topic files read on demand, and searchable session
  transcripts [latent-space-7]. A.
- **Meta's Muse Code.** "Facts the agent could get wrong from general knowledge alone are the ones
  worth recording"; load an index and read files on demand; treat a committed `MEMORY.md` as a
  prompt-injection surface [other-labs-27]. L.
- **Z.ai.** Keep human-written instruction memory apart from what the agent accumulates, so
  "experience-driven notes" do not "gradually pollute" the core rules [glm-f6]. L.
- **Codex and Devin Desktop.** Durable or team guidance goes into `AGENTS.md` or rules, not generated
  memory [chk-codex-memories, chk-devin-memories, harness-loading-coverage-22]. L.
- **Structured notes.** Anthropic's context-engineering post describes notes kept outside the window
  (a `NOTES.md`, a to-do list) and read back after a reset [chk-context-engineering]. L.
- **Entries, not one rolling text.** The memory stores above keep per-topic entries: Claude Code's
  topic files, Codex's durable entries, Copilot's cited facts. L.
- These agree with the rules of [agent-workspace.md](agent-workspace.md) §4: a source and a date per
  fact, a check against the source at use, deletion when wrong, no authority, and committed files for
  what every clone needs.

## How to apply

1. Treat agent memory as local, perishable and untrusted: commit what every clone needs, give each
   fact a source and a date, re-check it at use, delete it when wrong, and grant it no authority
   (§1–§4, [agent-workspace.md](agent-workspace.md) §4).
2. Keep human-written rules apart from what the agent accumulates, as per-topic entries rather than
   one rolling text (§7).
3. Do not choose a memory system on LoCoMo scores; test active use and forgetting on your own work
   (§6).

## Limits and open questions

- Memory research is mostly 2026 preprints, several by one author; product claims come from the
  vendors.
- No study compares memory against none on coding-agent outcomes beyond vendor A/B tests; no
  benchmark scores ordinary memory writes.

## Sources

Read 2026-10-01 unless dated otherwise. Ids in brackets resolve in the evidence files.

**Checks defined here:**
- [chk-claude-memory] Claude Code, memory <https://code.claude.com/docs/en/memory> and context
  window <https://code.claude.com/docs/en/context-window>.
- [chk-codex-memories] Codex, memories (now at learn.chatgpt.com)
  <https://developers.openai.com/codex/memories>.
- [chk-devin-memories] Devin Desktop, Cascade memories and rules
  <https://docs.devin.ai/desktop/cascade/memories>.
- [chk-claude-pages] Anthropic, prompting Claude Fable 5
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5>,
  and the Fable 5 announcement, 2026-06-09 <https://www.anthropic.com/news/claude-fable-5-mythos-5>.
- [chk-context-engineering] Anthropic, effective context engineering for AI agents, 2025-09-29
  <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>.
- [chk-particula] Particula, Mem0 vs Zep vs Letta vs Cognee, 2026-09-22
  <https://particula.tech/blog/agent-memory-frameworks-tested-mem0-zep-letta-cognee-2026>.
- [chk-zep-migration] Zep, migrate from Mem0 <https://help.getzep.com/mem0-to-zep>.
- [chk-chase] Harrison Chase, your harness, your memory, 2026-04-11
  <https://langchain.com/blog/your-harness-your-memory>.
- [chk-a2a] A2A specification v1.0 <https://a2a-protocol.org/latest/specification/>; Linux Foundation,
  A2A surpasses 150 organizations, 2026-04-09
  <https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year>.
- [chk-mcp] MCP specification 2026-07-28, changelog
  <https://modelcontextprotocol.io/specification/2026-07-28/changelog>, and its release candidate
  post, 2026-05-21 <https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/>.
- [chk-w3c-cg] W3C AI Agent Memory Interoperability Community Group
  <https://www.w3.org/community/ai-agent-memory-interop/>.
- [chk-unit42] Unit 42, when AI remembers too much, 2025-10-09
  <https://unit42.paloaltonetworks.com/indirect-prompt-injection-poisons-ai-longterm-memory/>.
- [chk-mem0] Mem0, state of AI agent memory 2026 (updated 2026-09-28)
  <https://mem0.ai/blog/state-of-ai-agent-memory-2026>, and the 2026 token optimization playbook
  (updated 2026-09-28)
  <https://mem0.ai/blog/the-2026-token-optimization-playbook-cut-ai-agent-memory-costs-3%E2%80%934x>.
- [chk-mem0-delete] Mem0, delete memories <https://docs.mem0.ai/core-concepts/memory-operations/delete>.
- [chk-oreilly] O'Reilly Radar, why multi-agent systems need memory engineering, 2026-02-25
  <https://www.oreilly.com/radar/why-multi-agent-systems-need-memory-engineering/>.
- [chk-letta] Letta, benchmarking AI agent memory: is a filesystem all you need?, 2025-08-12
  <https://www.letta.com/blog/benchmarking-ai-agent-memory>.

**Papers** (arXiv, read 2026-10-01, each at `https://arxiv.org/abs/<id>`): 2606.04329 (MPBench),
2605.29463 (memory confabulation), 2507.05257 (MemoryAgentBench), 2410.10813 (LongMemEval),
2603.07670 (memory survey), 2510.27246 (BEAM), 2501.13956 (Zep), 2504.19413 (Mem0), 2602.10715
(Locomo-Plus), 2605.11032 (Portable Agent Memory), 2606.01138 (memorywire).
