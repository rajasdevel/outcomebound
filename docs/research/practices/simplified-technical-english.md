---
last_checked: 2026-10-03
volatility: STABLE (the standard is revised every few years; Issue 10 is due January 2028) / MONITOR (§4, LLMs and STE)
sources:
  - https://asd-ste100.org/about_STE.html
  - https://asd-ste100.org/STE_faq.html
  - https://asd-ste100.org/index.html
  - https://asd-ste100.org/STEsoftware.html
  - https://www.asd-ste100.org/assets/files/WhitePaper-ASD-STE100_and_AI.pdf
  - https://researchconnect.buffalo.edu/en/publications/simplified-english-for-aircraft-workcards/
  - https://arxiv.org/pdf/1507.01701
  - https://arxiv.org/abs/2406.19898
  - https://arxiv.org/abs/2310.11324
  - https://allaboutcoding.ghinda.com/explain-to-me-in-simple-technical-english
---

# ASD-STE100 Simplified Technical English and text for coding agents

Re-check when ASD publishes Issue 10, or when a measured study of STE or another controlled
language in prompts for models appears.

Whether OutcomeBound, or the projects that adopt it, should write in ASD-STE100 Simplified
Technical English (STE): what the standard is, what it may be used for, what is measured for human
readers and for models, and how it compares with OutcomeBound's own writing rules. Strength tags:
M measured, L lab or owner guidance, A practitioner, O opinion or own observation.

## Key findings

1. **STE is a controlled language for human non-native readers of maintenance text.** Its owner
   says it is "not intended for general-purpose writing" (L, FAQ). OutcomeBound's readers are
   models and developers.
2. **The measured gain is for people, against ordinary aerospace prose.** 175 aircraft
   technicians on 16 workcards understood Simplified English better, most for difficult cards and
   non-native readers (M, Chervak, Drury and Ouellette 1996; Shubert 1995 agrees; both cited by
   Kuhn 2014). No study found compares STE with plain English.
3. **No measured study shows STE improves how a model follows instructions.** That is an absence
   of evidence, not evidence of no effect (searched 2026-10-03).
4. **Naming the standard in a prompt lost facts in the one direct test found.** Claude explaining
   code kept 11–14 of 24 facts under "ASD-STE100", 21–22 under "Simple Technical English" and 23–24
   with no style instruction (A, 4 samples × 2 runs; the author calls it not rigorous).
5. **Prompt wording matters more for small models, but not through simplicity.** Paraphrase gains
   were larger for an 8B model than a 70B one, with "no significant correlation" with prompt
   complexity or length (M, arXiv 2406.19898); formatting alone moved accuracy by up to 76 points
   (M, arXiv 2310.11324).
6. **The standard is free to read, not free to reuse.** "Simplified Technical English, ASD-STE100,
   is a Copyright and a Trademark of ASD" (EU trade mark 017966390). The PDF is free on request; no
   grant to restate the rules or ship the dictionary under Apache-2.0 was found, and ASD authorizes
   no tool to claim conformance. Only a written answer from ASD settles reuse.
7. **OutcomeBound already carries STE's meaning rules, not its form rules.** One decision per
   sentence, one term per meaning and plain defined terms are in the prompt standard (S9) and the
   ticket and brief guidance; there is no sentence limit, voice rule or dictionary (O, mapped
   2026-10-03).

## 1. The standard

- Issue 9, 15 January 2025, now called an "international standard"; Issue 10 is due January 2028.
  Maintained by ASD through its STEMG working group since 1983 (about_STE.html, FAQ).
- 53 writing rules in 9 sections, and a dictionary of about 900 approved words, each with one
  meaning and one part of speech ("start" replaces begin, commence and initiate; "check" is a noun
  only). Companies add their own technical nouns and technical verbs.
- Headline limits, from secondary sources (the rule text was not read): at most 20 words in a
  procedural sentence and 25 in a descriptive one; noun clusters of at most three words; one
  instruction per sentence; one topic per paragraph and at most six sentences in it; active voice;
  imperative procedures with the condition first.
- Required in ATA iSpec 2200 and by EASA, FAA and CAAC for continued airworthiness; recommended in
  S1000D. The owner reports 64% of requests come from outside aerospace and defence.

## 2. Reuse

The standard's text, its dictionary and its name are ASD's. Practitioner skills under MIT ship rule
summaries and not the dictionary, which is practice, not permission. The plain-writing principles
STE shares with every style guide (short sentences, active voice, one instruction per sentence)
need no licence; a claim of STE conformance, or a bundled dictionary, does.

## 3. Human readers

Measured gains are in comprehension of maintenance procedures, largest for complex text and
non-native readers (M, two studies). Translation and cost benefits are owner or vendor claims (L);
one German–English study found controlled-language rules helped older machine translation but not
neural (M, Marzouk 2019). The owner calls writing STE "a demanding task" needing trained writers
(L). Critics report wordiness ("do a check of") and loss of nuance (O).

## 4. Models

- **Writing STE.** A skill cut lint-detected STE violations by 72.9% across six Claude models
  (L/A, n=96, no comprehension measure). ASD's June 2026 white paper warns that AI text "can appear
  clear... even when it does not correctly apply the rules", and that checkers vary in accuracy
  (L). No checker's accuracy is independently measured.
- **Reading STE.** Nothing measured. The nearest evidence on text for coding agents: context files
  raised cost by over 20% without raising success (M, arXiv 2602.11988); small readers drop
  instructions under load (M, IFScale); a contradiction stopped a small model and not a larger one
  (O, evaluations.md E13). These point at contradiction, load and missing detail, not sentence form.
- **Rewriting is a risk.** In OutcomeBound's own rewrite of its text to a standard, six of eight
  fresh reviews found changes of meaning (O, writing-for-models.md finding 14). Two sample rewrites
  of shipped text into STE style split well, grew 8–20% in words and each lost one nuance (O).

## 5. Against OutcomeBound's rules

| STE | OutcomeBound | Fit |
| --- | --- | --- |
| One instruction per sentence | One decision per sentence (work-breakdown.md §5); spec-tier packages, one instruction to a sentence (`hand-off-tickets`) | Carried |
| One word, one meaning | S9, one vocabulary; terms defined at first use | Carried, without a dictionary |
| 20/25-word sentence limits | No length limit drives a ticket or its text; "short sentences are not readable text" (writing-for-models.md) | Conflicts as a rule or check |
| Imperative procedures | Strong readers do worse with skills written as itineraries (model-guidance.md) | Fits the spec tier only |
| Approved dictionary | Verbatim names, domain terms, the contract's own verbs | Conflicts |

## How to apply

1. Use STE for what it was built for, human readers, and nowhere else: text a model writes for a
   person (reports, decision briefs, handovers, pull request descriptions, questions, documents
   written for people). Text a model reads (instructions, skills, tickets' implementer sections,
   hand-off packages) is out of scope.
2. Refer to the standard by name and copy none of its text: no rules restated, no dictionary, no
   claim of conformance. Naming it is enough for a capable model to write in its manner; ASD warns
   that such text can look like STE without applying its rules, which matters only for a
   conformance claim.
3. No length limit: STE's sentence limits are not adopted as a rule or a check.
4. Guard the facts: the one direct test found (finding 4) lost about half of a code explanation's
   facts when the prompt named "ASD-STE100". Say that every fact, number and caveat is kept and
   that the project's own terms stay as they are, and read the first outputs for loss.

## Limits

The rule text and the PDF's licence notice were not read; limits come from secondary sources. The
human studies date from 1995–1996 and test aerospace procedures. No source tests STE in software
documentation or in prompts for coding agents.
