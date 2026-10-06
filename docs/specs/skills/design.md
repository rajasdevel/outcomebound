---
name: skills
status: ratified
---

# Skills — design

## Outcome

An adopting project's agent loads a skill exactly when the task calls for it, and the skill
changes what the agent does in the way the project wants: it serves a pain adopters have, says
nothing the co-loaded text already says, and is true of the engine it names. This design decides
which skills OutcomeBound ships, what a skill must earn to ship and to stay, and how one reaches a
project. The rules for the text are `docs/prompt-standard.md`'s; how a skill is written into a
project is the [install design](../install/design.md)'s. The pains and the comparison with public
skill sets are in the [skills
research](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/skills.md).

## The set

| Skill | The pain it serves | Installed |
| --- | --- | --- |
| `using-outcomebound` | process that outweighs the change; "done" that is not evidence | every install |
| `decision-brief` | too many questions, asked badly; authority the harness cannot read | every install |
| `gather-requirements` | an unclear outcome: guessing, or asking too much too late | every install |
| `tests-worth-keeping` | tests that cannot fail for the reason they name; a project that starts red | every install |
| `explain-spec` | a person who must act on a spec they did not write and does not follow it; a spec whose gaps only a reader's questions show. It explains and asks, and never claims the person understands | every install (proposed; the open row below) |
| `slice-tickets` | work cut to the wrong size | with the `tickets` fragment |
| `hand-off-tickets` | one ticket shape for every implementer: detail that narrows a capable model, too little for a small one. It says what an implementer is given, never how it works the ticket | with the `tickets` fragment |
| `adopt-outcomebound` | installing OutcomeBound | never: an agent asked to adopt reads it from the engine checkout |

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| A skill ships only for a pain adopters have, observed in this repository's research or an adopter's history, that the kernel and the text loaded beside it leave unserved (maintainer, 2026-10-06: a requirements-import capability and a teaching step are also wanted; import is the `outcomebound sources` verbs and a paragraph in `gather-requirements`, not a skill of its own, and teaching is `explain-spec`) | a skill per mechanism or per habit, such as a test-first skill or a lesson-contributing skill; a skill prescribing the turn of working a ticket, which strong models take unasked and which measured no better than no skill; a skill for choosing an approach, whose pains the core skill, `gather-requirements` and `slice-tickets` serve | user | decided |
| Every skill is in OutcomeBound's own words. An idea taken from a public skill set is credited by a link to its GitHub repository in the README's Acknowledgements, and in detail in the research record; its text is not copied (maintainer, 2026-10-06: the README links the GitHub repositories whose ideas are adopted, and nothing else) | adapting a public skill's text under its license notice; credit in the research record alone | user | decided |
| A skill reaches another only by the name or installed path of a skill OutcomeBound ships; it never sends the agent to a third-party skill | invoking a public skill, whose rules (approval gates, files it writes) come with it, and whose text changes upstream unreviewed | user | decided |
| What the person asks for outranks a skill's default: a request to be interviewed grants the questions, whichever skill runs the interview | a skill that holds to ask-once against the person's request | agent | decided |
| `hand-off-tickets` names a default for an edge that holds only on a condition the implementer may be unable to settle: the smaller change inside `bounds`, reported in its handover (field: a conditional edge left the implementer to guess or stop) | leaving it to the implementer, who then asks or stalls | agent | decided |
| `using-outcomebound` says that a change that is only text for people, or mechanical, meets no row by its size and needs no independent review and no full suite unless a row's condition holds or the project requires them. The existing sentence on a project's suggested process covered a project's suggestion, not the change's size | leaving the sentence as it was; a rule in the kernel, the most expensive text | agent | decided |
| Fragment text for field failures lives in the fragment that the failing work loads, not in the kernel: `workspace` (a shared machine's budget: disk, memory, CPU, cleanup of only what the task made), `multi-agent` (wait once for a running delegate and never poll; one role at a time and the tickets of one landing per worker), `commands` (a probe that fails where the sandbox may have denied it is `UNVERIFIED`; a job still running when the task ends needs the person's grant) | the same text in the kernel, which every task loads | agent | decided |
| Shipped guidance that names a POSIX-only command says so, or gives the portable form, once in the file that holds it (`commands` fragment, `gather-requirements`, the `github` store reference, `docs/tickets.md`); text is not duplicated per command. Whether a PowerShell form runs is `UNVERIFIED` until a Windows run settles it | a PowerShell twin of every command | agent | decided |
| A skill states only what the kernel, the core skill, the decision-brief skill and the fragment that installs it do not | restating the kernel for emphasis | agent | decided |
| Every install carries the four default skills; a fragment's `skills:` adds the ones its setup needs; nothing else installs a skill | every shipped skill in every install; skills no install reaches | user | decided |
| Each skill has one eval fixture whose post-checks read the behavior the skill exists for. Until runs of its fixture pass, what a skill does for an adopter is `UNVERIFIED` wherever it is claimed | shipping on reading alone | user | decided |
| Three skills do not yet meet the one-fixture rule above, and what each does is `UNVERIFIED`: `explain-spec` has no fixture yet; the hand-off comparison measures prepared packages on implementers and does not load `hand-off-tickets`; `adopt-outcomebound` has no fixture, since it is never installed in an adopting project, and the engine's tests check the `adopt` verbs it runs, not the skill | a fixture for each built before the release | agent | decided |
| A project's required process binds; what its documents only suggest is sized like any mechanism, and the project facts, the contract and the core skill say so; the kernel stays within its 300 words. The ladder's rungs 2 and 3 measure it, in a project whose documents suggest a design note, a record, the full suite and a second reader for every change | leaving a project's suggestions to outrank the sizing the kernel asks for | agent | decided |
| The kernel keeps its sizing paragraph. On the ladder, the install without it matched the full install within one run on every rung, on one model at three runs a cell, which cannot show its effect absent; and it states the rule the rest of the text applies | cutting it on three runs a cell | agent | decided |
| A skill whose fixture shows no difference between the current and kernel-off arms, over repeated runs, is rewritten or cut | keeping a skill because it reads well | agent | decided |
| Proposal: `explain-spec` installs in every install, as a fifth default skill. The maintainer ruled it an optional skill and did not rule it a default; the engine ships it as one until they settle this at the pull request. Its trigger is narrow (a person must act on a spec they did not write, or says they do not follow it), so an install that never meets that task loads only its description | installed only where a selected fragment's `skills:` names it, which reaches no adopter whose fragments do not | agent | open |
| Frontmatter holds `name` and `description` only, and the description is the trigger, its key use case in the first 250 characters | harness-specific keys, which one harness reads and another rejects | agent | decided |

## Edges

A new skill, or a change to what one tells a model to do, is reviewed once before it ships (the
`review` mechanism, as for the core skill), since no fixture runs in CI.
Removing a shipped skill removes it from adopters' installs on their next upgrade.

## Validation

`tests/test_skill_frontmatter.py` holds the frontmatter and length; `tests/test_skill_paths_resolve.py`
holds every path a skill names; `outcomebound instructions check` reads the installed copies as
it reads any instruction file; the fixtures are listed in `evals/README.md`.
