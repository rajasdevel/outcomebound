---
name: explorable
status: draft
---

# Explorable — design

This draft lands with the change that adds `outcomebound explorable` and the `explorable` skill.
Before it lands: an independent review of this design and of the skill text (the `review`
mechanism, since the change alters what a skill tells a model to do), and the release canary
(`make canary`), because the change adds a verb and a default skill.

## Outcome

When a person must decide, learn or answer something that text alone shows badly, the agent gives
them an explorable: one HTML file, opened from disk, in which the person changes values, steps
through flows, reads charts and answers questions, and then copies a reply back to the agent. The
person makes the decision, or learns the subject, with evidence they can try for themselves, and
the agent gets their answer in words it can act on.

An explorable has three kinds:

- a **decision** explorable puts one or more decision briefs in a form the person can explore:
  each option's mechanism, the measures the choice turns on, the values the person may judge
  differently, and how far each value must move before the answer changes;
- a **learning** explorable teaches a mechanism by asking the person to predict, try and recall;
- an **interview** explorable asks the person the questions whose answers the work waits on.

The name comes from the essay "Explorable Explanations" (2011,
<https://worrydream.com/ExplorableExplanations/>): a document that the reader changes and explores.

How: the `explorable` skill (when to make one, what each kind holds, and the guards); the verb
`outcomebound explorable` (`outcomebound_tools/explorable.py`), which writes a starter source,
joins the source to the shared shell, and checks the page; the shell under
`templates/explorable/` (the page frame, the shared stylesheet, the runtime script and the library
pins); the source header schema `schemas/explorable-source.schema.json`; and the HTML drawing of a
brief in `outcomebound_tools/decision_brief.py`.

The completion bar for one explorable: `outcomebound explorable check` passes on the page; where a
Chromium-family browser is on the machine, `check --browser` runs the page, and every expectation
the page declares passes; the decision brief is in the text the person reads, as the decision-brief
design requires; and the agent names the page's path. Where no such browser exists, the run of the
page is `UNVERIFIED`, and the agent says so.

## Requirements

- R1 A portable, self-contained HTML file helps a person make a complex decision with confidence:
  interactive diagrams, calculators like a spreadsheet, sliders, charts, timelines and animations,
  whatever the decision needs (maintainer, 2026-10-06).
- R2 Libraries come from a CDN where a page opened from disk can load them, to keep the file small
  and to save tokens (maintainer, 2026-10-06).
- R3 The same machinery makes pages for learning and for grilling (maintainer, 2026-10-06).
- R4 The name is not "artifact", which Claude uses for its own feature (maintainer, 2026-10-06);
  the name is "explorable" (maintainer, 2026-10-07).
- R5 The page follows the browser's dark or light setting by itself (maintainer, 2026-10-06).
- R6 Every page uses one shared stylesheet (maintainer, 2026-10-06).
- R7 The model writes the page's HTML and script from a starter file; the engine ships the shell
  (shared CSS, theme, CDN tags) and a check verb (maintainer, 2026-10-07).
- R8 Decision, learning and interview explorables all ship in 1.4.0 (maintainer, 2026-10-07).
- R9 Each option's mechanism is clear on its own, and the page holds only what changes the decision
  (field: a model-built decision page had to be redone because each option's data flow was not
  clear and the page carried material the decision did not need).

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| The page type is called an explorable, with three kinds: decision, learning and interview; the skill is `explorable` and the verb `outcomebound explorable` (maintainer, 2026-10-07) | workbench; sheet; artifact, which collides with Claude's own feature and with this engine's install artifacts | user | decided |
| The model writes the page's content and script; the engine ships the shell and the check (maintainer, 2026-10-07). The engine does not compute the page's numbers | the engine builds the whole page from a JSON document with a formula language, which checks the arithmetic but limits what a page can show; guidance alone, with no shell and no check | user | decided |
| All three kinds ship together in 1.4.0, as one slice of the 1.4.0 work (maintainer, 2026-10-07) | decision explorables first and the other kinds in a later release; all three in 1.5.0 | user | decided |
| An agent makes an explorable only where text serves the person badly: a decision whose answer turns on values the person may judge differently from the agent, or on how options work in ways that text compares poorly; a mechanism the person must learn, where trying it teaches more than reading; a set of questions that is easier to answer on a page than in a chat; or a request from the person. A choice that the brief settles alone gets no page | an explorable for every brief, which adds work that changes no decision; an explorable only on request, which misses the case the request described | agent | decided |
| A decision explorable holds, in this order: the briefs; each option's mechanism, drawn so that what differs between options shows first, with one colour and label for each kind of work; the measures the choice turns on, each with its value for each option and its source; what-if inputs for the values the person may judge differently or that are unknown; for each input that decides the choice, how far it must move before the answer changes; a timeline where time or reversibility differs between options, with the point after which an option cannot be undone; and the reply. It holds nothing that does not change the decision | a general report on the area with the decision at its end, which the field example showed hides the options' differences | agent | decided |
| A learning explorable starts from what the person already knows and lets them skip it; it asks for a prediction before each reveal, lets the person step through a flow at their own pace, gives a model they can change where quantities matter, and asks recall questions on earlier parts later. Its reply carries the person's answers; the agent reports what the person answered and never that they understand, as `explain-spec` says | a page to read, with no question; a quiz with no explanation | agent | decided |
| An interview explorable asks the questions the work waits on, drawn from the open forks (`gather-requirements`) or from a spec's rows (`explain-spec`): one idea in each question, the most important first, the options of equal length, the agent's recommended answer marked and never preselected, and "I don't know" always offered; the reply carries each answer, and the agent records it where the work is recorded | questions in the chat one at a time, which suits a few questions but not a long set; a form that preselects the recommendation, which anchors the answer | agent | decided |
| An explorable adds to a decision brief and never replaces it: the brief is in the text the person reads (the message, the handoff, the ticket comment), and the page is named beside it. A decision explorable shows the same brief at its top | a page that holds the brief, linked from the message, which the decision-brief design refuses | user | decided |
| The model writes a source file, and `outcomebound explorable build` joins it to the shell: the frame, the security policy, the shared stylesheet, the runtime script, the brief and the reply section. The model never reads or copies the shared parts, so they cost it no tokens and every page gets the same ones | a starter file that holds the whole shell, which the model reads again at every edit; a page that links the shared files from a CDN at a release tag, which fails for an engine ahead of its last tag and for a page opened offline | agent | decided |
| A source is an HTML fragment: content sections and the page's own scripts. Its first element is a JSON header, `<script type="application/json" data-explorable>`, with `kind`, `title`, an `id` and, for a decision, the path of the brief document; `schemas/explorable-source.schema.json` defines it. The source names `.source.html`; the page is the same name without `.source` | the kind and title as command flags, which an agent must repeat at every build; a source that is a whole document, whose head and policy the agent could change | agent | decided |
| The source may not hold what the shell owns: a doctype, `html`, `head` or `body` element, a `meta` element, a `link` element, a `base` element, an `iframe`, `object` or `embed` element, a `form` with an action, or a `src` or `href` that is not a fragment (`#…`) or a `data:` URL. `build` refuses such a source and names the line | accepting them and relying on the policy alone, which a later edit to the shell could weaken without a test | agent | decided |
| Libraries: Chart.js for charts and Mermaid for diagrams, flows and Gantt timelines, both from jsDelivr at exact versions that one file, `templates/explorable/libraries.json`, pins. Every other need uses what the browser has: range and number inputs, tables, SVG, CSS transitions, `details`. No CSS framework, no reactive framework, no formula engine, no math typesetting. A library loads only when the page calls for it | ECharts, Vega-Lite and Observable Plot, each larger for this use; HyperFormula and Handsontable, whose licences restrict use; GSAP, whose licence is not open source; Pico.css, archived on 2026-10-04 | agent | decided |
| Mermaid is pinned at 11.17.2, not 12.1.0: in a test on 2026-10-06, 12.1.0 loaded a 494 KB layout chunk for a plain flowchart and 11.17.2 did not, and the cause is `UNVERIFIED` | the newest release, four days old when checked | agent | assumed |
| Chart.js loads as one script with an integrity hash (SRI) and `crossorigin="anonymous"`. Mermaid loads as an ES module whose chunks cannot carry an integrity hash, so the exact version and the host rule below hold it instead | Mermaid's one-file build, which carries a hash but is about 1.5 MB; no hashes at all | agent | decided |
| The page's first head element is a Content-Security-Policy `meta` tag: `default-src 'none'`, scripts only inline and from `https://cdn.jsdelivr.net`, styles inline, images and fonts only `data:` and `blob:`, `form-action 'none'`, `base-uri 'none'`. The page reaches no host except the library host, and sends nothing that the person enters; it cannot fetch live data either, so its data is in the page | no policy, so that page code could call any host; `connect-src 'none'` alone, which leaves images and styles open | agent | decided |
| Without the network the page still works: inputs, results, tables, the brief, the questions and the reply need no library. A chart or diagram whose library does not load shows its fallback text, and a banner says which parts need the network | a page that is blank offline; libraries copied into each page, which makes a large file | agent | decided |
| Every page follows `prefers-color-scheme`. The stylesheet defines its colours as tokens for light and dark; charts and diagrams take their colours from those tokens and draw again when the setting changes; print uses the light tokens. The palette is safe for colour-blind readers, and colour never carries meaning alone: a label, a mark or a shape goes with it | a light page only; a theme switch on the page, which the person must find | user | decided |
| One shared stylesheet, `templates/explorable/explorable.css`, styles every kind; page code adds no stylesheet of its own, and a `style` attribute only where a value is computed | a stylesheet in each page that the model writes | user | decided |
| The runtime script, `templates/explorable/explorable.js`, gives page code one object, `explorable`, with the parts that pages need again and again and that are easy to get wrong: named inputs and their outputs, with an empty input read as unknown; formatting with a stated precision; charts and diagrams that load their library and follow the theme; flows per option with one colour and label per kind of work; tabs; step-through with controls the person drives; a timeline; questions with an "I don't know" answer; the threshold at which an input changes the answer; expectations; saved state; and the reply. `skills/explorable/references/runtime.md` describes it | no runtime, so that each page writes these parts again; a runtime that draws the whole page from data, which the maintainer's ruling rejects | agent | decided |
| The page's arithmetic is checked by expectations: page code declares `explorable.expect(label, compute, expected)` for each number the recommendation rests on, with an expected value the agent worked out outside the page's code. `check --browser` opens the page in a headless Chromium-family browser with the `#explorable-check` fragment, and the runtime runs every expectation and writes the results into the page for the check to read. Where no such browser exists, the arithmetic is `UNVERIFIED` | trusting the page code; an engine formula language, which the maintainer's ruling rejects | agent | decided |
| The browser check uses a Chromium-family browser only (Chrome, Chromium, Edge or Brave, found on the usual paths or named by `OUTCOMEBOUND_BROWSER`), with a new profile folder that the check makes and removes, and a time limit after which it stops only the process it started. Headless Firefox cannot print the page's document, so on a machine with only Firefox the run is `UNVERIFIED`, and so is Safari | a screenshot read by eye; a browser driver such as Playwright, which is not in the standard library | agent | decided |
| `check` reads the page alone and reports separate verdicts: the shell (policy first and unchanged, generator and kind, library pins equal to the engine's), the hosts (no reference outside the policy), the parts each kind needs (decision: a brief and the reply; learning and interview: at least one question and the reply), and, with `--browser`, the run (no script error, every expectation passes). A page with inputs and no expectation reads its arithmetic as `UNVERIFIED`. Exit 1 on any `FAIL` | one verdict for the page, which hides which part failed | agent | decided |
| A decision explorable draws its briefs from the same JSON document that `outcomebound brief` reads, with the same refusals, through an HTML drawing in `decision_brief.py`; the reply offers each brief's options by letter and way | a brief that the page code writes by hand, which can disagree with the brief in the message | agent | decided |
| The reply is one block of text that the runtime builds and shows at all times: the page's id and build time, the choice for each brief, each input the person moved (the agent's value, then theirs, with the unit), each answer (with "I don't know" kept as an answer), and a note. A copy button writes it to the clipboard after a click and falls back to selecting the text | answers sent from the page, which the policy forbids and which needs a server; a downloaded file, whose folder the agent does not know | agent | decided |
| The page saves the person's values and answers in the browser's local storage under the page's id and build time, wrapped so that a browser that refuses storage still works, with a button that restores the agent's values. Chrome shares one storage area across every file opened from disk, so the key carries the page's id | no saved state, so that a reload loses the person's work; state in the address, which a reload in some browsers loses | agent | decided |
| Guards against misleading the person: every value the agent supplies is labelled with its source (checked, assumed, or the person's); an unknown value stays empty and every result that needs it says so; an uncertain value is a range, never one exact number; results show only the precision the inputs support; the reply lists each input the person moved and in which direction; the decision explorable shows, for each input that decides the choice, how far it must move before the answer changes; animation moves only when the person starts it, and stops under `prefers-reduced-motion` | showing the recommendation's numbers as fact; pairwise comparison matrices, whose rankings can reverse when an option is added | agent | decided |
| One skill, `explorable`, serves all three kinds and is a default skill in every install. `decision-brief`, `explain-spec` and `gather-requirements` each point to it in one line, for the case where their work needs a page | a skill for each kind, which would repeat the shell, the checks and the guards three times | agent | decided |
| An explorable is a working file: its source, its brief document and its page go in the project's working area (`.agents/work/<task>/` where the workspace fragment applies), never into a design folder or a commit unless the person asks, since a page can hold private facts. The agent opens the page for the person only when the person asks or is at the machine and the work waits on them, with the system's opener (`open`, `xdg-open`, `start ""`), and otherwise names its path | pages committed beside the design; a page opened in every run, unattended ones included | agent | decided |
| The shell, stylesheet, runtime and pins live under `templates/explorable/`, which ships in the package and which the verb reads from the engine's home; the skill folder holds only markdown, which the instruction audit reads | the shell in the skill folder, which `adopt` copies into every adopter's tree and which the audit, reading only markdown there, would not read | agent | decided |
| The idea of a document whose numbers the reader changes is credited: the README's acknowledgements link `worrydream/Tangle`, the reactive-document library by the essay's author, and the research record names the essay. No text or code is taken from either | no credit; a link to the essay in the README, which links GitHub repositories only | agent | decided |
| The skill's diagram guidance, in OutcomeBound's own words, takes its ideas from `cathrynlavery/diagram-design`, which the README already credits: choose the diagram by what the reader must learn, and use a table where a table says the same; every node is one idea and every line carries information; one or two elements carry the accent; a diagram that needs a guide to read becomes an overview and a detail; an option's change from today is drawn as a change (added, removed, changed) against the current state; the page holds its meaning with motion off; every diagram has a text title and description for screen readers | that skill's own layout system and hand-drawn SVG, which cost many tokens for each diagram; Mermaid's layout is the trade the maintainer's token goal makes | agent | decided |

## Shape

A source, as `outcomebound explorable new` writes the start of one:

```html
<script type="application/json" data-explorable>
{"kind": "decision", "id": "cache-choice", "title": "Which cache for the reports API?",
 "brief": "briefs.json"}
</script>

<section>
  <h2>How each option works</h2>
  <div data-tabs>
    <section data-tab="A in-process cache"><pre data-diagram>flowchart LR
  req[request] -->|on request| cache[in-process cache]:::k1
  cache -->|miss| db[(database)]:::k2</pre></section>
  </div>
</section>

<section>
  <h2>What if</h2>
  <label>Requests per second <input type="range" data-input="rps" data-unit="req/s"
    data-source="checked" min="10" max="500" step="10" value="120"></label>
  <label>Hit rate <input type="number" data-input="hit" data-unit="%" data-source="assumed"
    value=""></label>
  <p>Database load: <output data-output="dbLoad"></output></p>
</section>

<script>
  const model = (v) => ({ dbLoad: v.hit === null ? null : v.rps * (1 - v.hit / 100) });
  explorable.onChange((v) => explorable.show("dbLoad", model(v).dbLoad, { unit: "req/s" }));
  explorable.expect("120 req/s at a 75% hit rate gives 30 req/s",
    () => model({ rps: 120, hit: 75 }).dbLoad, 30);
</script>
```

The page that `build` writes, from top to bottom: the policy, the shared stylesheet, a header
with the title, kind and build time, the network banner (hidden until a library fails), the
briefs, the source's content, the reply section, and the runtime and the source's scripts.
The source above has an empty hit rate, so the database load reads as unknown until the person
sets it.

## Edges

`build` refuses a source whose header does not match the schema, a decision source with no brief
document, a brief document that `outcomebound brief` would refuse, and any element or reference
that the shell owns (the rows above); it refuses to write over a file that is not a page it built.
`check` cannot tell whether the page's content is right, whether its options are the real ones,
or whether its code computes what its labels say beyond the expectations it declares; it says so
in its report. A custom chart, layout or animation that page code draws itself is checked only
for script errors in the run. The policy stops page code from reaching any host but the library
host, so a page cannot load live data: the agent puts the data in the page. A Chromium-family
browser on the machine is the only way the check runs the page; Firefox-only and Safari-only
machines read `UNVERIFIED`. A page opened through a harness's preview server on the loopback
address behaves as it does from disk, except that it could then read a file beside it, which no
page relies on. Local storage is per browser and per machine: a page sent to a colleague opens
with the agent's values.

## Other designs this change edits

- `decision-brief`: the Outcome names the explorable as an addition for a brief whose answer
  turns on values or mechanisms, and a row records the HTML drawing of a brief in
  `decision_brief.py`, with the same refusals as the markdown drawing.
- `skills`: the set gains `explorable`, installed in every install, with its pain (a decision,
  lesson or interview that text serves badly) and its fixture row.
- `install`: the count of working skills; `templates/explorable/` ships with the engine and is
  never copied into an adopter's tree.

## Validation

- `tests/test_explorable.py`: `new` writes a starter source for each kind that `build` accepts
  and `check` passes; `build` refuses each element and reference the shell owns, a bad header,
  and a decision source with no brief; the page's first head element is the policy, unchanged;
  every library reference is a pin from `libraries.json`; brief text with HTML characters is
  escaped; `check` fails a page whose policy, pins or required parts were changed.
- `tests/test_explorable_browser.py`: where a Chromium-family browser is found, the starter page
  of each kind runs with no script error and its expectations pass, and a page with a wrong
  expectation fails; elsewhere the test is skipped with its reason.
- `tests/test_decision_brief.py`: the HTML drawing of the example brief, its escaping, and the
  same refusals as the markdown drawing.
- The skill: `tests/test_skill_frontmatter.py`, `tests/test_skill_paths_resolve.py`,
  `outcomebound instructions check`, and one eval fixture with a case where a page helps (a choice
  that turns on values the person judges) and a case where it must add no work (a yes-or-no
  choice with one clear downside). Until the fixture runs, what the skill does for an adopter is
  `UNVERIFIED`.
- Before landing: the library pins load from a page opened from disk in a headless browser, with
  the policy in place; Mermaid and Chart.js under the policy were not yet run on 2026-10-06.

