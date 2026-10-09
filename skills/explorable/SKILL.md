---
name: explorable
description: Use when the person asks for an interactive page, wants to try options with their own numbers, or must learn a mechanism by trying it. Builds a single-file HTML page the engine checks, beside the decision brief and never in place of it; the decision-brief, gather-requirements and explain-spec skills send a decision, an interview or a lesson here where text serves it badly.
---

# Explorable

An explorable is a single HTML file the person opens from disk: they change values, step through
flows, read charts and answer questions, then copy a reply back to you. You write its source; the
engine joins it to a shared shell and checks it. You are done when `outcomebound explorable check`
passes on the page (with `--browser` where a Chromium-family browser exists, else the run is
`UNVERIFIED` and your report says so), every number the page's answer rests on has an expectation,
your report names each output that reads `UNVERIFIED`, and the page's path is in the text the person
reads, beside the decision brief when there is one.

## When a page earns its place

Make one only where text serves the person badly:

- a decision whose answer turns on values the person may judge differently from you (rates, sizes,
  dates, weights, risk), or on how the options work in ways text compares poorly;
- a mechanism the person must learn, where trying it teaches more than reading;
- a set of questions that is easier to answer on a page than in the chat;
- the person asks for one.

A choice the brief settles alone gets no page. A page never replaces the brief: draw the brief as
the `decision-brief` skill says and put it in the text, then name the page beside it. A page holds
only the work that waits on the person; the rest goes on while they read it.

## What each kind holds

**Decision.** In this order: the briefs (`build` draws them from the brief document);
each option's mechanism, drawn so that what differs between options shows first; the measures the
choice turns on, each with its value for each option and where the value came from; what-if inputs
for the values the person may judge differently or that are unknown; for each input that decides
the choice, how far it must move before the answer changes (`explorable.threshold`); a timeline
where time or reversibility differs between options, with the point after which an option cannot
be undone; a question that asks the person to imagine the leading option has failed and say why;
and the reply. Leave out everything that does not change the decision, however true: background,
history and parts no option touches.

**Learning.** Start from what the person says they know and let them skip it. Before each reveal,
ask for a prediction. After the reveal, explain the outcome and any difference from their
prediction; let them try again where that helps. Let them step through a flow at their own
pace; give them a model to change where quantities matter; later, ask them to recall what an
earlier part showed. Report what they answered, never that they understand (`explain-spec`
holds the same rule).

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
- Your recommendation is already in the brief, so the page shows what would change it, not more
  reasons for it.
- Motion starts only when the person starts it.
- Colour never carries meaning alone: a label, mark or shape goes with it.
- Page code never navigates, opens a window, fetches, or loads anything; the page's data is in the
  page. The policy stops loads and sends but not navigation, so this one is yours to hold.
- What the person enters stays in the browser, where Chrome lets any page opened from disk read
  it. Where the answers are private, tell the person to press "Forget what I entered" once the
  reply is copied.

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

## Build and check

1. Work in the project's working area (`.agents/work/<task>/` where the workspace fragment
   applies), never in a design folder or a commit unless the person asks: a page can hold private
   facts.
2. `outcomebound explorable new <name>.source.html --kind decision` (or `learning`, `interview`)
   writes a starter source; for a decision it also writes `briefs.json` beside it when that file is
   missing. The brief document is the one `outcomebound brief` reads: fill it, and draw it with
   `outcomebound brief briefs.json` for your message.
3. Write the content and the page code over the starter. `references/runtime.md` names the
   `explorable` object, the attributes and the reply's form.
4. For each number the recommendation rests on, add `explorable.expect` with input values and the
   output each must show. Work the expected value out by hand or with another tool, never by
   running the page's code, and keep that working in a file beside the source.
5. `outcomebound explorable build <name>.source.html` writes `<name>.html`. When it refuses the
   source, fix the source and build again; never edit the built page, which the next build
   replaces.
6. `outcomebound explorable check <name>.html --browser` runs the page and its expectations.
7. Put the brief in your message and name the page's path. Open the page for the person with the
   system's opener (`open` on macOS, `xdg-open` on Linux, `wslview` under WSL; on Windows
   `Invoke-Item` or `start ""`, which have not been run) only when they ask, or when they are at
   the machine and the work waits on them.

## The reply

The person pastes a block that `references/runtime.md` describes. Read each `choice` line as their
answer to that brief, by its id. Read each `input` line as their value: where it changes the
answer, work the answer out again with it and say what changed. Record each `answer` where the work
is recorded; an "I don't know" is a gap to settle, not a blank. A reply grants only what the chosen
option names; an act a permission check guards still needs the person's own words for it.
