"""The one place a decision brief is drawn.

What this module decides: the shape a brief put to a person is drawn in — a
`###` heading and a list, so it reads line by line in a terminal and in a
markdown view alike; the seven marks and the two separators under `emoji` and
`ascii`; which of the two marks a `Checked` line carries; the letter each
Option and a recommended way carries; the order in which a brief's lines are
written, each Option's downside nested under it; and how a brief's own diagram
and the order among waiting items are drawn, as Mermaid or as fenced ASCII. A
brief is a floor, not a form: every line but the heading is written only where
its field holds something, so a surface prints what it knows and no
placeholder.

Its command line, `outcomebound brief`, draws the
decisions an agent puts to a person itself: a JSON document in the
shape `schemas/decision-briefs.schema.json` fixes, drawn by `render` in the
symbols the output stream can carry and the diagram form the session's surface
renders, unless a flag names either. It refuses a brief below the floor it can
detect: an Option without its downside, two or more Options and no
recommendation among them, or no line of evidence.

What it does not decide: what a brief says — the surface that asks the
question fills a `Brief` with what it knows, and the presenting agent writes
the rest in its own words — nor whether the checking behind it was done well;
which form the session's surface renders, which is `surfaces`'; or which
symbols a surface uses, beyond `symbols_for`'s reading of what a stream can
encode. Its drawing imports nothing from the engine, so any surface can draw a
brief without depending on another's module; the command line reads
`schemacheck` and `surfaces` only when it runs.
"""

from __future__ import annotations

import argparse
import json
import os
import string
import sys
import textwrap
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, TextIO

from outcomebound_tools import home, textio

__all__ = [
    "MARKS",
    "NOTHING_WAITS",
    "SEPARATORS",
    "Brief",
    "Diagram",
    "checked_mark",
    "diagram",
    "main",
    "render",
    "symbols_for",
]

# The seven marks, in the design's own order, as `emoji` and as `ascii`; each is
# followed by its word wherever it is written. No `ascii` mark is `[ ]`, `[x]`
# or `[X]`, which a markdown view draws at a list item's head as a checkbox.
MARKS: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        "emoji": MappingProxyType(
            {
                "recommend": "👉",
                "checked": "✅",
                "unchecked": "⚠️",
                "downside": "🔻",
                "debt": "🧱",
                "undo": "↩️",
                "cannot_be_undone": "⛔",
            }
        ),
        "ascii": MappingProxyType(
            {
                "recommend": "[>]",
                "checked": "[ok]",
                "unchecked": "[!]",
                "downside": "[-]",
                "debt": "[debt]",
                "undo": "[undo]",
                "cannot_be_undone": "[!!]",
            }
        ),
    }
)

# The two separators, `(sep, dash)`, plain under `ascii` because a surface that
# cannot show a mark cannot be trusted with these either.
SEPARATORS: Mapping[str, tuple[str, str]] = MappingProxyType(
    {"emoji": (" · ", " — "), "ascii": (" | ", " - ")}
)

# The one line an empty rundown prints: never a blank a reader cannot tell from
# a crash.
NOTHING_WAITS = "nothing waits on a person\n"


@dataclass(frozen=True, slots=True)
class Diagram:
    """A brief's own diagram, drawn after its list where order, dependency, flow
    or before/after is the point.

    `edges` hold `(from, to, label)` in the order they are drawn, an empty label
    drawing an unlabelled edge; every edge is drawn, and none is reduced away.
    `caption`, where set, is the line written above the fence.
    """

    edges: tuple[tuple[str, str, str], ...]
    caption: str = ""


@dataclass(frozen=True, slots=True)
class Brief:
    """One decision brief, holding only what its surface knows.

    Only `heading` is required; an empty field writes no line. Each of `options`
    is `(way, leads_to)` or `(way, leads_to, downside)`, a downside written on a
    line of its own under its Option, behind the `downside` mark. `checked` and
    `undo` pair a `MARKS` key with the line's text: `checked` or `unchecked`,
    and `undo` or `cannot_be_undone`. A surface reaches the key `checked` only
    through `checked_mark`. `recommend_way` names the Option the surface
    recommends, by its way, and the renderer writes that Option's letter and the
    dash at the head of the `Recommend` line; unset, the line is written as
    given. `facts` holds `(label, text)` pairs, each a fact the surface knows
    that bears on the answer, written `- <label>: <text>` after `Not checked`
    and before `Debt`. `diagram`, where set, is drawn after the brief's list as
    a block of its own.
    """

    heading: str
    recommend: str = ""
    confidence: str = ""
    options: tuple[tuple[str, str] | tuple[str, str, str], ...] = ()
    why_now: str = ""
    asked: tuple[str, ...] = ()
    checked: tuple[str, str] | None = None
    not_checked: str = ""
    debt: str = ""
    undo: tuple[str, str] | None = None
    recommend_way: str = ""
    facts: tuple[tuple[str, str], ...] = ()
    diagram: Diagram | None = None


def checked_mark(verdicts: Sequence[str]) -> str:
    """The `MARKS` key a `Checked` line holding `verdicts` carries.

    `checked`, the mark that means a check passed, only where `verdicts` is not
    empty and every item is exactly `PASS`; `unchecked` otherwise, so no verdict
    at all, `FAIL`, `UNVERIFIED`, `RUN_UNVERIFIED`, `pass` and any other word are
    not passed.
    """

    return "checked" if verdicts and all(item == "PASS" for item in verdicts) else "unchecked"


def _ways(brief: Brief) -> list[str]:
    """The way of each Option, in order."""

    return [option[0] for option in brief.options]


def _refused(brief: Brief) -> str:
    """Why `brief` cannot be drawn, or the empty string where it can."""

    if len(brief.options) == 1:
        return (
            "a brief lays out Options only where there are two or more ways forward; "
            f"this one lays out {len(brief.options)}"
        )
    if len(brief.options) > len(string.ascii_uppercase):
        return (
            "a brief letters its Options from A to Z, so it lays out at most "
            f"{len(string.ascii_uppercase)}; this one lays out {len(brief.options)}"
        )
    if brief.confidence and not brief.recommend:
        return "a brief's confidence belongs to its Recommend line, and this one has none"
    if brief.recommend_way and not brief.recommend:
        return "a brief's recommended way belongs to its Recommend line, and this one has none"
    if brief.recommend_way and brief.recommend_way not in _ways(brief):
        return (
            f"a brief letters only a way it lays out, and {brief.recommend_way!r} "
            "is not among its Options"
        )
    return ""


def _below_floor(brief: Brief) -> str:
    """Why `brief` falls below the floor the command holds an agent's own decisions
    to, or the empty string where it does not: two or more Options and no
    recommendation among them, or no line of evidence. `render` does not ask this,
    so a surface drawing only what it knows is not refused for what it does not."""

    count = len(brief.options)
    if count >= 2 and not brief.recommend:
        return (
            f"a brief that lays out {count} Options recommends one of them, "
            "and this one has no Recommend line"
        )
    if count >= 2 and not brief.recommend_way:
        return (
            f"a brief that lays out {count} Options names the one it recommends "
            "in recommend_way, and this one names none"
        )
    if brief.checked is None and not brief.not_checked and not brief.facts:
        return (
            "a brief carries at least one line of evidence, checked, not_checked or facts, "
            "and this one has none"
        )
    return ""


def _recommend_line(brief: Brief, marks: Mapping[str, str], sep: str, dash: str) -> str:
    """The `Recommend` line: the recommended Option's letter and the dash, where a way
    is named, then the text as given and its confidence."""

    confidence = f"{sep}confidence {brief.confidence}" if brief.confidence else ""
    letter = ""
    if brief.recommend_way:
        letter = f"{string.ascii_uppercase[_ways(brief).index(brief.recommend_way)]}{dash}"
    return f"- {marks['recommend']} Recommend: {letter}{brief.recommend}{confidence}"


def _option_lines(brief: Brief, marks: Mapping[str, str], dash: str) -> list[str]:
    """The `Options` line and each lettered Option, its downside nested under it."""

    lines = ["- Options:"]
    for index, (way, leads_to, *downside) in enumerate(brief.options):
        lines.append(f"  - {string.ascii_uppercase[index]} {way}{dash}{leads_to}")
        lines.extend(f"    - {marks['downside']} Downside: {text}" for text in downside)
    return lines


def _lines(brief: Brief, marks: Mapping[str, str], sep: str, dash: str) -> list[str]:
    """One brief's lines, in order, each written only where its field is set."""

    lines = [f"### {brief.heading}"]
    if brief.recommend:
        lines.append(_recommend_line(brief, marks, sep, dash))
    if brief.options:
        lines.extend(_option_lines(brief, marks, dash))
    if brief.why_now:
        lines.append(f"- Why now: {brief.why_now}")
    lines.extend(f"- Asked: {text}" for text in brief.asked)
    if brief.checked:
        lines.append(f"- {marks[brief.checked[0]]} Checked: {brief.checked[1]}")
    if brief.not_checked:
        lines.append(f"- {marks['unchecked']} Not checked: {brief.not_checked}")
    lines.extend(f"- {label}: {text}" for label, text in brief.facts)
    if brief.debt:
        lines.append(f"- {marks['debt']} Debt: {brief.debt}")
    if brief.undo:
        lines.append(f"- {marks[brief.undo[0]]} Undo: {brief.undo[1]}")
    return lines


# The list item after the fence of an order holding a circle; `{circles}` names
# each circle's entries, and `{dash}` is the second of `SEPARATORS[symbols]`.
_CIRCLE_ITEM = (
    "- In a circle: {circles}{dash}these wait on each other, so no order exists among them"
    " and every edge is drawn on its own line"
)


def _reach(successors: Mapping[str, Sequence[str]], start: str) -> frozenset[str]:
    """Every label reachable from `start` by one edge or more; a visited set keeps
    a circle from looping."""

    seen: set[str] = set()
    stack = list(successors.get(start, ()))
    while stack:
        label = stack.pop()
        if label not in seen:
            seen.add(label)
            stack.extend(successors.get(label, ()))
    return frozenset(seen)


def _circles(ranked: Sequence[str], reach: Mapping[str, frozenset[str]]) -> list[list[str]]:
    """Each circle's labels by rank, the circles by the rank of their first label;
    a label is in a circle when it reaches itself, and two labels share one when
    each reaches the other."""

    cyclic = [label for label in ranked if label in reach[label]]
    circles: list[list[str]] = []
    placed: set[str] = set()
    for label in cyclic:
        if label not in placed:
            circle = [
                other
                for other in cyclic
                if other == label or (other in reach[label] and label in reach[other])
            ]
            placed.update(circle)
            circles.append(circle)
    return circles


def _reduced(
    edges: Sequence[tuple[str, str]],
    successors: Mapping[str, Sequence[str]],
    reach: Mapping[str, frozenset[str]],
) -> list[tuple[str, str]]:
    """`edges` in the order given, less every edge a longer path already shows:
    `(a, c)` is dropped where another successor of `a` reaches `c`."""

    return [
        (before, after)
        for before, after in edges
        if not any(other != after and after in reach[other] for other in successors[before])
    ]


def _chains(edges: Sequence[tuple[str, str, str]]) -> list[str]:
    """`edges` as ASCII lines of one chain each, `a --label--> b --> c`: a chain
    starts at the first remaining edge whose source no remaining edge points at,
    or, where each is pointed at, as around a loop, at the first remaining edge,
    and follows the first remaining edge from its last label, so every edge
    stands as two neighbours on exactly one line."""

    remaining = list(edges)
    lines: list[str] = []
    while remaining:
        pointed_at = {target for _, target, _ in remaining}
        head = next((edge for edge in remaining if edge[0] not in pointed_at), remaining[0])
        remaining.remove(head)
        chain = [head]
        while (step := next((e for e in remaining if e[0] == chain[-1][1]), None)) is not None:
            remaining.remove(step)
            chain.append(step)
        steps = (f" --{label}--> {to}" if label else f" --> {to}" for _, to, label in chain)
        lines.append(head[0] + "".join(steps))
    return lines


def _mermaid(edges: Sequence[tuple[str, str, str]], labels: Sequence[str]) -> list[str]:
    """`edges` as a fenced Mermaid flowchart, one edge per line in the order given,
    each label under the id `n1`, `n2`, … of its place in `labels`, since a label
    such as `new flag` or `CT-0007` is not a safe Mermaid node id."""

    ids = {label: f"n{number}" for number, label in enumerate(labels, start=1)}
    lines = ["```mermaid", "flowchart LR"]
    for source, target, label in edges:
        link = f"-->|{label}|" if label else "-->"
        lines.append(f'  {ids[source]}["{source}"] {link} {ids[target]}["{target}"]')
    return [*lines, "```"]


def _labels(edges: Sequence[Sequence[str]]) -> list[str]:
    """Each node label of `edges`, once, in the order it first appears."""

    return list(dict.fromkeys(label for edge in edges for label in edge[:2]))


def _drawing(drawn: Diagram, form: str) -> str:
    """A brief's own diagram, without a trailing newline: its caption line, where it
    has one, then every edge in the order given, none reduced, as a Mermaid
    flowchart under `mermaid` and as ASCII chains in a `text` fence under any
    other form."""

    lines = [drawn.caption] if drawn.caption else []
    if form == "mermaid":
        lines.extend(_mermaid(drawn.edges, _labels(drawn.edges)))
    else:
        lines += ["```text", *_chains(drawn.edges), "```"]
    return "\n".join(lines)


def diagram(order: Sequence[tuple[str, str]], symbols: str, form: str = "ascii") -> str:
    """The order among waiting items, from `(before, after)` pairs — `after` waits
    on `before` — without a trailing newline.

    The order is drawn as its transitive reduction: an edge a longer path between
    its two labels already shows is not drawn, and a pair given twice is read
    once, where it first stands. Under `mermaid` the reduction's edges are drawn
    one per line in the order given, each label under the id `n1`, `n2`, … of its
    first appearance in `order` as given, before anything is reduced. Under any
    other form the edges are ASCII in a `text` fence, one chain per line, each
    chain starting at an entry no undrawn edge points at, so an entry is written
    again only where the order branches or joins at it. Where labels wait on each
    other in a circle no order exists among them: nothing is reduced or chained,
    every edge is drawn on its own line, and one list item after the fence names
    each circle.
    """

    _, dash = SEPARATORS[symbols]
    edges = list(dict.fromkeys(order))
    labels = _labels(edges)
    successors: dict[str, list[str]] = {}
    for before, after in edges:
        successors.setdefault(before, []).append(after)
    reach = {label: _reach(successors, label) for label in labels}
    circles = _circles(labels, reach)
    drawn = [(b, a, "") for b, a in (edges if circles else _reduced(edges, successors, reach))]
    lines = [f"### Order{dash}an arrow points at what waits on it"]
    if form == "mermaid":
        lines.extend(_mermaid(drawn, labels))
    elif circles:
        lines += ["```text", *(f"{before} --> {after}" for before, after, _ in drawn), "```"]
    else:
        lines += ["```text", *_chains(drawn), "```"]
    if circles:
        named = "; ".join(", ".join(circle) for circle in circles)
        lines.append(_CIRCLE_ITEM.format(circles=named, dash=dash))
    return "\n".join(lines)


def render(
    briefs: Sequence[Brief],
    symbols: str,
    order: Sequence[tuple[str, str]] = (),
    form: str = "ascii",
) -> str:
    """Every brief as a `###` heading and a list, its own diagram, where it has one,
    as the next block, one blank line between blocks, and, where `order` is given,
    the order's diagram after the last brief; every diagram in `form`.

    Nothing is padded or wrapped, and nothing is fenced but a diagram; an empty
    `briefs` is `NOTHING_WAITS`. A brief with one option or more than there are
    letters, with a confidence and no recommendation, or with a recommended way
    it has no Recommend line for or does not lay out, is refused by `ValueError`
    before anything is drawn.
    """

    if not briefs:
        return NOTHING_WAITS
    for brief in briefs:
        refused = _refused(brief)
        if refused:
            raise ValueError(refused)
    marks = MARKS[symbols]
    sep, dash = SEPARATORS[symbols]
    blocks: list[str] = []
    for brief in briefs:
        blocks.append("\n".join(_lines(brief, marks, sep, dash)))
        if brief.diagram is not None:
            blocks.append(_drawing(brief.diagram, form))
    if order:
        blocks.append(diagram(order, symbols, form))
    return "\n\n".join(blocks) + "\n"


# The longest header a harness's question tool shows: Codex's request_user_input describes its
# header as 12 or fewer characters (request_user_input_spec.rs, read 2026-10-05), and Claude Code's
# AskUserQuestion as at most 12; a longer id is left to the question text.
_HEADER = 12


def questions(briefs: Sequence[Brief], ids: Sequence[str], symbols: str) -> dict[str, Any]:
    """Every brief as one question for a harness's question tool, each field on one line.

    A question holds `id`, the brief's id; `header`, the id where it fits a tool's short header,
    else empty; `question` and `title`, the same text, the heading and then the recommended
    Option's letter and why; and `options`, the recommended Option first, as the tools ask, then
    the rest in letter order. Each option holds `label`, its letter and way, with
    " (Recommended)" on the recommended one; `description`, what it leads to and its downside;
    and `line`, the label and what it leads to, for a tool whose options are plain strings. A
    brief with no Options has an empty `options`. The drawn brief, with its evidence, goes in the
    message before the question. A brief `render` refuses is refused here by the same
    `ValueError`.
    """

    sep, dash = SEPARATORS[symbols]
    asked: list[dict[str, Any]] = []
    for brief, brief_id in zip(briefs, ids, strict=True):
        refused = _refused(brief)
        if refused:
            raise ValueError(refused)
        text = brief.heading
        recommended = _ways(brief).index(brief.recommend_way) if brief.recommend_way else None
        if brief.recommend:
            letter = "" if recommended is None else f"{string.ascii_uppercase[recommended]}{dash}"
            text += f"{sep}Recommend: {letter}{brief.recommend}"
        options = []
        for index, (way, leads_to, *downside) in enumerate(brief.options):
            label = f"{string.ascii_uppercase[index]} {way}"
            if index == recommended:
                label += " (Recommended)"
            description = leads_to + "".join(f"; downside: {risk}" for risk in downside)
            options.append(
                {"label": label, "description": description, "line": f"{label}{dash}{leads_to}"}
            )
        if recommended is not None:
            options.insert(0, options.pop(recommended))
        asked.append(
            {
                "id": brief_id,
                "header": brief_id if len(brief_id) <= _HEADER else "",
                "question": text,
                "title": text,
                "options": options,
            }
        )
    return {"questions": asked}


def symbols_for(stream: TextIO) -> str:
    """`ascii` where `stream`'s encoding cannot carry every `emoji` mark and
    separator, `emoji` otherwise.

    A stream that names no encoding is read as UTF-8.
    """

    emoji = "".join([*MARKS["emoji"].values(), *SEPARATORS["emoji"]])
    try:
        emoji.encode(getattr(stream, "encoding", None) or "utf-8")
    except (UnicodeEncodeError, LookupError):
        return "ascii"
    return "emoji"


# The command line: an agent's own decisions, drawn by `render`.

_SCHEMA_PATH = home.ROOT / "schemas" / "decision-briefs.schema.json"

# The worked example `--help` carries, and which the command draws as it is.
_EXAMPLE = """\
{
  "briefs": [
    {
      "id": "D1",
      "heading": "Keep the old flag for one release?",
      "recommend": "two adopters still set it",
      "recommend_way": "keep it",
      "confidence": "80% (inferred)",
      "options": [
        ["keep it", "adopters get a warning first",
         "one more release carries the old code path"],
        ["drop it now", "the code path goes today",
         "an adopter who sets it is refused on upgrade"]
      ],
      "checked": {"verdicts": ["PASS"],
                  "text": "`grep -r old_flag` finds two adopter configs"},
      "undo": {"can_be_undone": true, "text": "revert the commit"},
      "diagram": {
        "caption": "How an upgrade reads the flag",
        "edges": [["config", "warning", "old_flag"], ["warning", "new flag"]]
      }
    },
    {
      "id": "D2",
      "heading": "Tag the release once D1 is settled?",
      "recommend": "tag it once the hosted run passes",
      "not_checked": "the hosted run, which needs your login; its result settles it",
      "undo": {"can_be_undone": false, "text": "a pushed tag cannot be taken back"}
    }
  ],
  "order": [["D1", "D2"]]
}"""

_EPILOG = f"""\
The document is one JSON object (schemas/decision-briefs.schema.json):
  briefs   the briefs, in the order they are put to the person; each holds
           id (required: the id the person answers by, joined to the heading
           with the separator of the symbols drawn), heading (required, the
           question in one line), undo (required: {{"can_be_undone": true or
           false, "text": ...}}), at least one line of evidence: checked
           ({{"verdicts": [...], "text": ...}}), not_checked (what could not
           be checked, why, and what would settle it) or facts ([label, text]
           pairs, no label naming a line the renderer writes); and, where it
           changes the answer: options ([way, what it leads to, its downside]
           triples, two or more), recommend (why; required with options),
           recommend_way (the way of options recommended, required with
           options; its letter is written), confidence (fact, or NN%
           (inferred)), why_now, asked (a list), debt, and diagram
           ({{"caption": ..., "edges": [[from, to] or [from, to, label],
           ...]}}, drawn after the brief where order, dependency, flow or
           before/after is the point)
  order    optional [before, after] pairs of brief ids: after waits on
           before; drawn after the last brief

Every string is one line. The command writes marks only from these fields:
the passed mark where every verdict given is PASS. It refuses a string
holding a line break, a control or format character, or a mark's own glyph;
an id that is not a letter followed by letters, digits and hyphens; and a
diagram label holding a double quote, or an edge label holding a |, which
would break a Mermaid diagram. It does not vouch for what your text says:
the verdicts are your own report of commands you ran.

Example, drawn as the briefs D1 and D2, D1's diagram and their order:

{textwrap.indent(_EXAMPLE, "  ")}

The marks are emoji where standard output can carry them, and ASCII where it
cannot; --symbols names them. The diagrams are Mermaid where
OUTCOMEBOUND_DIAGRAMS=mermaid, or, where that variable names neither form,
where adapters/surfaces.json records this session's surface as rendering
Mermaid; they are ASCII everywhere else, an unknown surface included; --form
names them. With --ask, the command prints instead one JSON object for a harness's
question tool, {{"questions": [{{"id", "header", "question", "title", "options":
[{{"label", "description", "line"}}]}}]}}, each field on one line: the question (also
as title) is the heading and the recommendation; the recommended option comes first,
its label ending (Recommended); line is the label and what it leads to, for a tool
whose options are plain strings; header is the id where it has 12 characters or
fewer. The order is not printed. Fill the tool's fields by name, after the drawn
brief in the message. Posting to a GitHub issue, discussion or pull request, or from
the Codex app, pass --form mermaid: those surfaces set no variable. Show the output
as markdown, never inside a code block. Exit 0 when drawn; exit 1 when a brief
is refused, naming which: one option or more than 26, two or more options with
no recommend or recommend_way, a confidence or a recommended way with no
Recommend line, a recommended way it does not lay out, or no checked,
not_checked or facts; exit 2 when the document cannot be read or breaks a rule
above, naming why, and on a usage error.
"""

# Every character `str.splitlines` breaks a line at: a string holding one could
# write a line of its own, such as a `Checked` line with a mark nothing passed.
_LINE_BREAKS = "\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029"

# Every mark, in both spellings, and the base character of each emoji mark, so
# no text given can carry a mark only the renderer writes.
_GLYPHS = tuple(
    sorted(
        {mark for marks in MARKS.values() for mark in marks.values()}
        | {mark[0] for mark in MARKS["emoji"].values()}
    )
)


class _Unreadable(ValueError):
    """The document, or the schema it is read against, cannot be read."""


def _pairs(values: Sequence[Sequence[str]], where: str) -> tuple[tuple[str, str], ...]:
    """Each value as a pair; one holding more than two strings is refused by its path."""

    for index, value in enumerate(values):
        if len(value) != 2:
            raise _Unreadable(f"{where}[{index}] must hold exactly two strings")
    return tuple((value[0], value[1]) for value in values)


def _options(values: Sequence[Sequence[str]], where: str) -> tuple[tuple[str, str, str], ...]:
    """Each Option as `(way, leads_to, downside)`; one holding other than three strings
    is refused by its path, naming the downside it lacks."""

    for index, value in enumerate(values):
        if len(value) != 3:
            raise _Unreadable(
                f"{where}[{index}] must hold exactly three strings: the way, what it leads to, "
                "and its downside"
            )
    return tuple((value[0], value[1], value[2]) for value in values)


def _diagram(value: Mapping[str, Any] | None, where: str) -> Diagram | None:
    """The brief's diagram, each edge as `(from, to, label)`, the label empty where
    none is given. An edge of more than three strings is refused by its path, as is
    a label holding what would end it in a Mermaid diagram — a double quote in any
    label, and a `|` in an edge's — or a `-->`, which draws as an ASCII edge."""

    if value is None:
        return None
    edges: list[tuple[str, str, str]] = []
    for index, edge in enumerate(value["edges"]):
        at = f"{where}.edges[{index}]"
        if len(edge) > 3:
            raise _Unreadable(f"{at} must hold two or three strings: from, to and a label")
        quoted = next((place for place, text in enumerate(edge) if '"' in text), None)
        if quoted is not None:
            raise _Unreadable(f"{at}[{quoted}] holds a double quote, which ends a Mermaid label")
        if len(edge) == 3 and "|" in edge[2]:
            raise _Unreadable(f"{at}[2] holds a |, which ends a Mermaid edge's label")
        arrowed = next((place for place, text in enumerate(edge) if "-->" in text), None)
        if arrowed is not None:
            raise _Unreadable(f"{at}[{arrowed}] holds -->, which draws as an ASCII edge")
        edges.append((edge[0], edge[1], edge[2] if len(edge) == 3 else ""))
    return Diagram(edges=tuple(edges), caption=value.get("caption", ""))


def _strings(value: object, where: str) -> list[tuple[str, str]]:
    """Every string in `value`, each beside its path."""

    if isinstance(value, str):
        return [(where, value)]
    if isinstance(value, Mapping):
        return [item for key, inner in value.items() for item in _strings(inner, f"{where}.{key}")]
    if isinstance(value, list):
        return [item for i, inner in enumerate(value) for item in _strings(inner, f"{where}[{i}]")]
    return []


# The names of the lines the renderer writes, which no `facts` label may take, so a
# fact cannot pass for one of them.
_LINE_NAMES = frozenset(
    name.casefold()
    for name in (
        "Recommend",
        "Options",
        "Downside",
        "Why now",
        "Asked",
        "Checked",
        "Not checked",
        "Debt",
        "Undo",
        "Confidence",
    )
)


def _checked_text(document: Mapping[str, Any]) -> None:
    """Refuse a string holding a line break, a control or format character, or a mark's
    own glyph, and a `facts` label that takes the name of a line the renderer writes.

    This keeps the command's own lines and marks its own; it does not vouch for what
    the text says.
    """

    for where, text in _strings(document, "$"):
        if any(character in _LINE_BREAKS for character in text):
            raise _Unreadable(f"{where} holds a line break; every string is one line")
        control = next((ch for ch in text if unicodedata.category(ch) in ("Cc", "Cf")), "")
        if control:
            raise _Unreadable(f"{where} holds the control or format character U+{ord(control):04X}")
        glyph = next((glyph for glyph in _GLYPHS if glyph in text), "")
        if glyph:
            raise _Unreadable(f"{where} holds the mark {glyph!r}, which only the renderer writes")
    for index, entry in enumerate(document["briefs"]):
        for number, fact in enumerate(entry.get("facts", ())):
            if fact and fact[0].strip().casefold() in _LINE_NAMES:
                raise _Unreadable(
                    f"$.briefs[{index}].facts[{number}] is labelled {fact[0]!r}, the name of a"
                    " line the renderer writes"
                )


def _brief(entry: Mapping[str, Any], index: int, sep: str) -> Brief:
    """One brief object the schema accepted, as a `Brief`: the passed mark comes from
    `checked_mark`, and the `id` is joined to the heading with the symbols' separator."""

    checked = entry.get("checked")
    undo = entry.get("undo")
    return Brief(
        heading=f"{entry['id']}{sep}{entry['heading']}",
        recommend=entry.get("recommend", ""),
        confidence=entry.get("confidence", ""),
        options=_options(entry.get("options", ()), f"$.briefs[{index}].options"),
        why_now=entry.get("why_now", ""),
        asked=tuple(entry.get("asked", ())),
        checked=(checked_mark(checked["verdicts"]), checked["text"]) if checked else None,
        not_checked=entry.get("not_checked", ""),
        debt=entry.get("debt", ""),
        undo=(
            ("undo" if undo["can_be_undone"] else "cannot_be_undone", undo["text"])
            if undo
            else None
        ),
        recommend_way=entry.get("recommend_way", ""),
        facts=_pairs(entry.get("facts", ()), f"$.briefs[{index}].facts"),
        diagram=_diagram(entry.get("diagram"), f"$.briefs[{index}].diagram"),
    )


def _read(source: str, symbols: str) -> tuple[list[tuple[str, Brief]], tuple[tuple[str, str], ...]]:
    """The document's briefs, each beside its id, and its order."""

    from outcomebound_tools import schemacheck

    try:
        raw = sys.stdin.buffer.read() if source == "-" else Path(source).read_bytes()
        document = json.loads(textio.decode(raw, utf16=True))
    except OSError as error:
        raise _Unreadable(error.strerror or str(error)) from error
    except UnicodeDecodeError as error:
        raise _Unreadable(f"it is not UTF-8 ({error.reason})") from error
    except json.JSONDecodeError as error:
        raise _Unreadable(f"it is not JSON ({error})") from error
    try:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _Unreadable(
            "the schema schemas/decision-briefs.schema.json in the selected engine cannot be read"
        ) from error
    defects = schemacheck.validate(document, schema)
    if defects:
        raise _Unreadable("; ".join(defects))
    _checked_text(document)
    ids = [entry["id"] for entry in document["briefs"]]
    repeated = sorted({brief_id for brief_id in ids if ids.count(brief_id) > 1})
    if repeated:
        raise _Unreadable(f"the id {repeated[0]!r} names more than one brief")
    order = _pairs(document.get("order", ()), "$.order")
    for index, pair in enumerate(order):
        stray = next((label for label in pair if label not in ids), None)
        if stray is not None:
            raise _Unreadable(f"$.order[{index}] names {stray!r}, which is no brief's id")
    sep, _ = SEPARATORS[symbols]
    briefs = [
        (entry["id"], _brief(entry, index, sep)) for index, entry in enumerate(document["briefs"])
    ]
    return briefs, order


def _session_form() -> str:
    """The diagram form this session's surface renders, or `ascii` where the surface
    table cannot be read: a brief is not lost to a table it only needed for its
    diagram."""

    from outcomebound_tools.surfaces import SurfaceError, diagram_form

    try:
        return diagram_form(os.environ)
    except SurfaceError:
        return "ascii"


def main(argv: Sequence[str] | None = None) -> int:
    """Draw the document's briefs, their diagrams and their order as markdown on
    standard output."""

    parser = argparse.ArgumentParser(
        prog="outcomebound brief",
        description="Draw the decisions an agent puts to a person as decision briefs, "
        "from a JSON document. Writes nothing.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("document", help="the JSON document's path, or - for standard input")
    parser.add_argument(
        "--symbols",
        choices=sorted(MARKS),
        help="the marks drawn; by default emoji where standard output can carry them, "
        "and ascii where it cannot",
    )
    parser.add_argument(
        "--form",
        choices=("ascii", "mermaid"),
        help="the diagrams' form; by default the one OUTCOMEBOUND_DIAGRAMS or "
        "adapters/surfaces.json names for this session, and ascii where neither does",
    )
    parser.add_argument(
        "--ask",
        action="store_true",
        help="print the briefs as JSON questions for a harness's question tool, each field "
        "on one line, instead of drawing them",
    )
    args = parser.parse_args(argv)
    symbols = args.symbols or symbols_for(sys.stdout)
    source = "standard input" if args.document == "-" else args.document
    try:
        briefs, order = _read(args.document, symbols)
    except _Unreadable as error:
        print(f"decision_brief: cannot read {source}: {error}", file=sys.stderr)
        return 2
    for number, (brief_id, brief) in enumerate(briefs, start=1):
        refused = _refused(brief) or _below_floor(brief)
        if refused:
            print(
                f"decision_brief: brief {number}, {brief_id}, is refused: {refused}",
                file=sys.stderr,
            )
            return 1
    if args.ask:
        asked = questions([b for _, b in briefs], [i for i, _ in briefs], symbols)
        text = json.dumps(asked, ensure_ascii=False)
        sys.stdout.write(text + "\n")
        return 0
    drawn = bool(order) or any(brief.diagram is not None for _, brief in briefs)
    form = args.form or (_session_form() if drawn else "ascii")
    text = render([brief for _, brief in briefs], symbols, order, form)
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        sys.stdout.write(text.encode(encoding, "replace").decode(encoding))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
