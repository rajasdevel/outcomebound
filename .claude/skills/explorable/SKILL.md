---
name: explorable
description: Use when the person wants to understand something, or wants it explained to others, where trying it teaches more than reading, asks for an interactive page, or wants to try options with their own numbers. A decision page goes beside the decision brief, never in its place.
---

# Explorable

An explorable is one HTML file that the person opens from disk: they change values, step through
flows and read charts. It is of one of four kinds. You write its source; the engine joins it to a
shared shell and checks it. A page that teaches comes first: **learning** teaches the person in this
session, **explain** teaches readers who are not in it, **decision** helps the person decide, and
**interview** asks the questions the work waits on. You are done when the person can open the page
and use it: `outcomebound explorable check` passes on the page (with `--browser` where a
Chromium-family browser exists, else the run is `UNVERIFIED` and your report says so; where the
browser printed nothing, the run's line names the browser and the likely sandbox: report it as
`UNVERIFIED`, try another browser only where evidence shows a different failure, and never work
around a sandbox refusal), every
number the page's lesson or answer rests on has an expectation, your report names each output that
reads `UNVERIFIED`, and the page's path is in the text the person reads, beside the decision brief
when there is one. You have looked at the page, and it shows what the person asked for, with data
that supports that meaning, not only a matching label; where the data cannot, your report says so.

## When a page earns its place

Make one only where text serves the person badly:

- something to understand, or to explain to others, where seeing it move or trying it teaches more
  than reading;
- a decision whose answer turns on values the person may judge differently from you (rates, sizes,
  dates, weights, risk), or on how the options work in ways text compares poorly;
- a set of questions that is easier to answer on a page than in the chat;
- the person asks for one.

A request to understand or to explain something gets a learning or explain page, never a decision
page. Do not turn an explanation into a request to choose, a recommendation, or a quiz unless the
person asked for it. A report, survey or comparison with controls is an explain page, whatever word
the person used; it holds a recommendation only where the person asked for one.

A choice the brief settles alone gets no page. A decision page never replaces the brief: draw the
brief as the `decision-brief` skill says and put it in the text, then name the page beside it. A
page holds only the work that waits on the person; the rest goes on while they read it.

## What each kind holds

**Learning.** Teaches the person in this session. Start from what they say they know and let them
skip it. Start with a concrete case, then state the rule it shows. Use numbers where quantities
matter, a model where changing inputs helps, and step-through where order matters. Show each result
beside the input that caused it. Invite them to try something (`set the rate to zero and watch`)
before you explain what happens. Questions are optional: add a prediction before a reveal, or a
recall question later, only where the person wants to test themselves. A page with a question has the reply; one with none has no reply. Report what they
answered, never that they understand (`explain-spec` holds the same rule).

**Explain.** Teaches readers who are not in this session, who cannot ask you and may open the page
later. Teach as a learning page does, and also: say at the top who it is for and what they can do
after reading; define each term where it first appears; assume nothing from the session; give each
value its source. It has no reply, no brief and no recommendation unless the person asked for one,
and it needs no question. Before you call it shareable, read it for private facts (names, paths,
customer data, credentials, internal ids, unreleased plans), remove or generalise them, and say
what you removed. Sharing the file is the person's act.

**Decision.** In this order: the briefs (`build` draws them from the brief document);
each option's mechanism, drawn so that what differs between options shows first; the measures the
choice turns on, each with its value for each option and where the value came from; what-if inputs
for the values the person may judge differently or that are unknown; for each input that decides
the choice, how far it must move before the answer changes (`explorable.threshold`); a timeline
where time or reversibility differs between options, with the point after which an option cannot
be undone; a question that asks the person to imagine the leading option has failed and say why;
and the reply. Leave out everything that does not change the decision, however true: background,
history and parts no option touches.

**Interview.** Ask the questions the work waits on, drawn from the open forks (`gather-requirements`)
or from a spec's rows (`explain-spec`): one idea in each, the most important first, options of equal
length, your recommended answer marked and never preselected. The runtime adds "I don't know" to
every question; keep it, since such an answer marks a gap.

## Guards

A page can mislead as well as inform. Hold these:

- Label every value you supply with its source: checked, assumed, or the person's.
- An unknown value stays empty, and every result that needs it says it is unknown. Never fill a
  gap with a plausible number.
- An uncertain value is a range, two inputs for the low and the high, never one exact number.
- Show only the precision the inputs support.
- Keep the controls to the values that move the answer; the threshold shows which those are.
- On a decision page your recommendation is already in the brief, so the page shows what would
  change it, not more reasons for it.
- Motion starts only when the person starts it.
- Colour never carries meaning alone: a label, mark or shape goes with it.
- Page code never navigates, opens a window, fetches, or loads anything; the page's data is in the
  page. The policy stops loads and sends but not navigation, so this one is yours to hold.
- What the person enters stays in the browser, where Chrome lets any page opened from disk read
  it. Where the answers are private, tell the person to press "Forget what I entered" when they
  finish.

## Diagrams

- Draw a diagram only when the reader must see order, flow, dependency, state or change; a table
  says the same about attributes, and a sentence about one relation.
- For options, draw one flow per option with the same names for the same parts, so the difference
  stands out; give each kind of work (on a schedule, on a change, on a request) its own class and
  a legend. Where an option changes today's system, draw it against today, marking what it adds,
  removes and changes.
- Every node is one idea, and every line carries information the layout does not already show.
- Accent one or two elements, the ones the decision turns on.
- A diagram that needs a guide to read becomes an overview and a detail.
- Give each diagram a title and a one-sentence description for screen readers.

## Write it once

Rework and repeated text take the person's time and add nothing to the page:

- Outline the page's parts and interactions, then write the content straight into the source.
  Drafting the content in full in your reasoning first writes it twice; working out a number or a
  choice there is not drafting.
- Take content from the most condensed document the work already has, with each value's source
  as that document gives it, and open a longer source only for the part a section needs.
- Where many tables or cards share one shape, keep their rows as data in the page's script and
  build them in page code, so that a change edits one row. A citation stays a link in the source:
  `check` refuses an address in a script.
- Ask each question once. A what-if input that restates a brief's choice asks it twice; give
  what-if inputs only to values that no brief chooses.
- Read an explorable through `check`. Where layout matters, such as a diagram's width against the
  column, measure it in a browser you drive; with none, the layout is `UNVERIFIED`.
- Change the source with targeted edits; never write it out again to change one part.

## Build and check

1. Work in the project's working area (`.agents/work/<task>/` where the workspace fragment
   applies), never in a design folder or a commit unless the person asks: a page can hold private
   facts.
2. `outcomebound explorable new <name>.source.html --kind decision` (or `learning`, `explain`,
   `interview`) writes a starter source; for a decision it also writes `briefs.json` beside it when that file is
   missing. For a decision page only, the brief document is the one `outcomebound brief` reads: fill it,
   and draw it with `outcomebound brief briefs.json` for your message.
3. Write the content and the page code over the starter. `references/runtime.md` names the
   `explorable` object, the attributes and the reply's form.
4. For each computed output the lesson or answer relies on, add `explorable.expect` with input values and the
   output each must show. Work the expected value out by hand or with another tool, never by
   running the page's code, and keep that working in a file beside the source.
5. `outcomebound explorable build <name>.source.html` writes `<name>.html`. When it refuses the
   source, fix the source and build again; never edit the built page, which the next build
   replaces.
6. `outcomebound explorable check <name>.html --browser` runs the page and its expectations.
7. Name the page's path in your message, beside the brief where there is one. Open the page for
   the person with the system's opener (`open` on macOS, `xdg-open` on Linux, `wslview` under WSL;
   on Windows `Invoke-Item` or `start ""`, which have not been run) only when they ask, or when they
   are at the machine and the work waits on them.

## The reply

A decision, an interview and a learning page with questions end in a reply; an explain page and a
learning page with no question have none. The person pastes a block that `references/runtime.md` describes. Read each `choice` line as their
answer to that brief, by its id. Read each `input` line as their value: where it changes the
answer, work the answer out again with it and say what changed. Record each `answer` where the work
is recorded; an "I don't know" is a gap to settle, not a blank. A reply grants only what the chosen
option names; an act a permission check guards still needs the person's own words for it.
