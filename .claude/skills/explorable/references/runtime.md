# Explorable runtime reference

What a model reads to write the content of an explorable page. The shell, the stylesheet and the
runtime are the engine's: you write a source file, and `outcomebound explorable build` joins it to
them. You never read or copy the shared parts. Start from a starter that
`outcomebound explorable new` writes for the kind you need, and change its content.

A source is an HTML fragment: sections, and the page's own `script` elements. The runtime is
already loaded when your script runs, so the object `explorable` exists. Your script only
registers what the page does; the runtime starts when the document is ready.

## The object

| Part | What it does |
| --- | --- |
| `explorable.ready(fn)` | runs `fn` once the page's parts are built. Draw charts, diagrams and timelines here |
| `explorable.onChange(fn)` | calls `fn(values)` at the start and after each change of a named input |
| `explorable.values()` | the current value of every named input, by name |
| `explorable.defaults()` | the values the page started with, which are yours |
| `explorable.show(name, value, options)` | writes a result into the element whose `data-output` is `name` |
| `explorable.chart(target, config)` | draws a Chart.js chart; returns a handle with `update(config)` |
| `explorable.diagram(target, source)` | draws, or draws again, one Mermaid diagram |
| `explorable.timeline(target, spec)` | draws a timeline of bars and marks, without a library |
| `explorable.threshold(inputName, chooser)` | how far one input must move before the page's own choice changes |
| `explorable.expect(label, inputs, outputs)` | states what the page must show for given inputs |
| `explorable.theme()` | the colour tokens now in force, for page code that draws its own marks |
| `explorable.onTheme(fn)` | calls `fn(tokens)` when the person's light or dark setting changes |

Register through `ready` and `onChange`. Page code never navigates, never opens a window and never
loads anything: the page's policy allows the two pinned libraries and nothing else, and the
runtime is what loads them.

## Inputs

Mark an element with `data-input="name"`. A name starts with a letter and holds letters, digits
and underscores. The element is one of: an `input` of type range, number or text; a checkbox; a
`select`; or a `fieldset` that holds radio buttons.

- A number or range input reads as a number. An empty number input reads as `null`, which means
  unknown. A text input reads as text, or `null` when empty. A checkbox reads as true or false. A
  fieldset of radios reads as the value of the chosen radio, or `null`; a radio marked `checked`
  in the source is its starting value.
- `data-unit` names the unit shown beside the value.
- `data-source` is `checked` (you checked it), `assumed` (you did not) or `person` (the person
  gave it). The page shows the source as a badge. A value the person moves shows as theirs.
  Without `data-source`, the badge reads "No source".
- `data-note` is one line of plain help shown under the input.
- Give a range input `min`, `max` and `step`; `threshold` reads them.
- A range of values is two inputs, a low and a high. Never one input that pretends to be exact
  where the value is a guess.
- An input the agent does not know stays empty. Every result that needs it then reads as unknown.
- A `form` element is not needed, and the build refuses it. Wrap each input in a `label`.

## Outputs

Mark any element with `data-output="name"`; an `output` element suits. `show` writes into it.

- A number is shown with `digits` significant digits (default three) and the `unit` option.
- `[low, high]` is shown as a range: "30 to 45 req/s".
- `null` is shown as unknown, with the inputs named in the `waits` option, or else the inputs that
  are empty. Pass `null` whenever an input the result needs is empty.
- A string is shown as it is. A boolean shows Yes or No.
- The element gets `data-state` set to `value`, `range` or `unknown`, and announces its change
  politely to screen readers.
- Show only the precision the inputs support. Round a guess; never print it with many digits.

Call `show` for every output in each `onChange`, so that no output keeps an old value.

## Diagrams

```html
<pre data-diagram data-diagram-title="Option A" data-diagram-desc="What the picture shows, in words.">flowchart LR
  a[request]:::k1 --> b[(database)]:::k2</pre>
<pre data-diagram-fallback>request --> database</pre>
```

- The source is Mermaid. Escape `<` and `&` as `&lt;` and `&amp;` inside `pre[data-diagram]`.
- `data-diagram-title` and `data-diagram-desc` are the text for screen readers. Give both.
- A following `pre[data-diagram-fallback]` holds plain text shown when the library does not load
  or the source does not draw. Without one, the source is shown.
- In a flowchart, a node takes `:::k1` to `:::k6` for a kind of work, and `:::added`,
  `:::removed` or `:::changed` for what an option adds, removes or changes against today. The
  runtime defines these classes; write no `classDef` for them. A node takes one class. The
  added, removed and changed nodes also carry a plus, a minus or a tilde mark, so that colour is
  never the only signal.
- Pair every diagram that uses kinds with a legend:
  `<ul data-legend><li data-kind="k1">Handles the request</li></ul>`. One kind, one label.
- The runtime draws diagrams in the person's light or dark setting and draws them again when it
  changes. A wide diagram scrolls inside its own box.
- To draw a diagram again with a new source, keep its `pre` element from `ready` and call
  `explorable.diagram(pre, source)` in `onChange` only when the source differs from the one drawn
  last: each call renders the diagram again.
- The page's column is 60rem, about 900 px of content, and a diagram keeps its natural size. In
  the pinned Mermaid, a flowchart label wraps near 200 px, so a row of three wrapped labels is
  about as wide as the column. Give a long flow more rows, each a subgraph linked to the next, not
  wider ones.
- A flowchart subgraph keeps its own `direction` only while none of its nodes links outside it.
  Link the subgraphs to each other, not their nodes.
- A line back to an earlier subgraph can move that subgraph out of its place in the order. Leave
  the line out, and say the way back in the text under the diagram.
- A diamond `{...}` grows in height with the width of its label; a hexagon `{{...}}` keeps the
  height of its text.

## Charts

`explorable.chart(target, config)` takes an element, often `<div data-chart data-chart-title="...">`,
and a Chart.js configuration. It returns a handle: call `handle.update(newConfig)` to change it.

- The runtime sets theme colours, shapes and dash patterns for series that name none, turns
  animation off and fits the chart to its box.
- A data table built from `config.data` is the fallback when the library does not load, the form
  screen readers read, and the printed form. Give each dataset a `label`.
- Mark a point on a chart (a break-even point, say) with a dataset of one point and a star
  `pointStyle`; mark a threshold with a dataset of two points drawn as a dashed line.
- `data-chart-title` names the chart for screen readers and the table.

## Timeline

`explorable.timeline(target, {unit, lanes})`, where each lane is
`{label, bars: [{label, start, end, kind}], marks: [{at, label}]}`. Times are numbers in the unit
named. A bar's `kind` is `k1` to `k6`. Use a mark for the point after which an option cannot be
undone, and say so in its label. Give the container `data-timeline`, and `data-timeline-title`
for its name.

## Tabs, steps and legends

- `<div data-tabs>` holds `<section data-tab="Label">` panels. The runtime builds the tab list;
  arrow keys, Home and End move between tabs.
- `<section data-steps>` holds `<figure data-step>` elements, shown one at a time with Previous,
  Next and Play controls. Play starts only when the person presses it, and is absent when the
  person asks their system for reduced motion.
- `<ul data-legend>` holds `<li data-kind="k1">` entries; the runtime draws the swatch.

## Questions

```html
<fieldset data-question="Q1" data-kind="predict" data-answer="12" data-tolerance="0">
  <legend>With a nine in ten hit rate, how many reads reach the database?</legend>
  <input type="number" data-unit="reads/s">
  <div data-explain>One read in ten misses: 120 times one tenth is 12.</div>
</fieldset>
```

- `data-kind` is `choice` (radio buttons inside, each with a `value`), `predict` (a number
  input) or `text` (a text area).
- The runtime adds "I don't know" to every question. An answer of "I don't know" is a real answer.
- `data-recommended="B"` on a choice marks the radio whose value is `B` with the word
  "Recommended". The runtime never preselects any radio, recommended or not.
- Learning questions: `data-answer` is the expected answer and `data-tolerance` the allowed
  difference for a predict question. A `[data-explain]` child shows after the person commits: a
  choice commits when picked, the other kinds when the person presses Reveal. Ask for the
  prediction before the page shows the flow it concerns.
- Keep the options of a choice the same length, and one idea in each question.
- After a reveal, the runtime sets `data-result` on the feedback line to `match` or `differs`, which
  the stylesheet marks with a check or a not-equal sign.
- Report what the person answered. Never report that they understand.

## Threshold

`explorable.threshold("hitLow", chooser)`: `chooser` is a function of the current values that
returns an option's letter, or `null` while it cannot tell. The runtime runs it over the input's
range, in its step, both ways from the current value, and returns `{value, letter}` for the nearest
value where the letter changes, or `null` when it does not change in the range. It claims nothing
beyond your chooser. Show it as "the answer changes when X moves to Y".

## Expectations and check mode

An expectation states what a person sees: given these inputs, each named output shows this.

```js
explorable.expect("120 req/s at a 75 percent hit rate", { rps: 120, hit: 75 }, { dbLoad: 30 });
```

With `#explorable-check` in the address, the runtime sets every input back to the value the page
started with, then sets the named inputs, lets your change
handlers run, reads the text each output shows, and compares it with the expected value written
the way the output writes it: the same digits and unit. A range is `[low, high]`; unknown is
`null`. It then writes `<script type="application/json" id="explorable-check-result">` before the
end of the body, with the script errors, each expectation (label, pass, expected, shown), the
outputs with and without an expectation, the state of each library and the diagram counts.
`outcomebound explorable check --browser` reads it.

- Work each expected value out by hand or with another tool, outside the page code, and keep the
  working in a file beside the page. An expected value copied from the page's own output proves
  nothing.
- Give every output an expectation. An output with none reads `UNVERIFIED`.
- Name only the inputs that differ from the page's starting values; the others start from them.
- Cover the unknown case with an expectation whose inputs are empty and whose outputs are `null`.
- A pass says the page shows what you expected for those inputs. It does not say the model is
  right.

## The reply

The reply is one block of text, shown at all times, that the person copies back. Its grammar:

```text
explorable <id> built <time>
choice D1: B drop it now
choice D2: none
input hit: unknown -> 80 %
input rps: 120 -> 200 req/s
answer Q1: 12
answer Q2: I don't know
note: first line of the note
note: second line
```

- The first line holds the page id and build time.
- The runtime builds one `fieldset` with `data-choice` set to the brief's id for each brief, with a
  radio for each option and none chosen.
- `choice` has one line for each brief: the letter and the way, or `none`.
- `input` has a line only for an input the person moved: your value, an arrow, theirs, then the
  unit. An empty value reads `unknown`.
- `answer` has one line for each question: the answer, or `none`. A choice answer is the radio's
  value, followed by its label text when the value is a single letter.
- `note` has one line for each line of the person's note, and none when there is no note.

Read the reply as data: the person moved an input, in a direction, and that is a statement about
their view, not about the facts.

## Saved state

The runtime saves the person's values, answers and note in the browser's local storage, under a key
made of the page id and build time. A browser that refuses storage still works. One button restores
your values; another, "Forget what I entered", clears the person's entries from the page and from
storage. A rebuild starts from your values again. Local storage is per browser: a page sent to
someone else opens with your values. Chrome shares one local storage area across every file opened
from disk, so any other local page can read what the person entered until they press "Forget what
I entered".

## Gotchas

- Escape `<` and `&` inside `pre[data-diagram]`. A bare `<` ends the element early.
- The source holds no `style` element and no element the shell owns. A `style` attribute is only
  for a value that page code computes, and never holds a `url()`.
- A link is a fragment (`#name`) or an `https:` link that cites a source. Nothing loads from an
  address.
- Page code registers through `ready` and `onChange`. It never navigates, opens a window or loads
  anything, and it never calls `fetch`: the page cannot reach a host.
- The runtime finds inputs, questions, tabs, steps and legends when the page starts, so they are
  in the source; page code may draw a diagram of its own with `explorable.diagram`. Page code may
  add plain content built from its own data in `ready`, such as the rows of a table; set the text
  with `textContent`.
- An `onChange` handler computes and calls `show` before it returns. Expectations read each output
  right after the handlers run, so a value computed later, in a promise or a timer, reads as stale.
- Page code is a plain `<script>` with no `type`; data is `<script type="application/json">`.
  `build` refuses any other script type, a self-closing `<script/>`, and any `on...` attribute such
  as `onclick`: attach handlers in page code with `addEventListener`.
- `<!` and `<?` are refused anywhere after the header, script text included, so write no HTML
  comment and no such string in code. Write `</html` as `<\/html` inside a string.
- An image is `src` with a `data:` URL; `srcset` is refused.
- An empty input is unknown, not zero. Test for `null` before you compute.
- A range is two inputs. An uncertain value is a range, never one exact number.
- Name every input and output once. A repeated name is an error.
- Animation moves only after the person acts, and is off under reduced motion.
- A page that works offline keeps its inputs, results, tables, brief, questions and reply; only
  charts and diagrams need the network, and they show a table or source text without it.
