"""The one place a decision brief is drawn.

What this module decides: the shape a brief put to a person is drawn in — a
`###` heading, then blocks a person reads in the order they decide, each block a
paragraph, a list or a fence, every block separated from the next by exactly one
blank line, so it reads line by line in a terminal and in a markdown view alike;
the twelve marks and the two separators under `emoji` and `ascii`; which of the
two marks a `Checked` line carries; the letter each Option and a recommended way
carries; the order in which a brief's blocks are written (what waits on the
answer, the context, the terms, the picture, the offer to explore, the Options
with the recommendation on the Option it names, the evidence); and how a brief's
own diagram and the order among waiting items are drawn, as Mermaid or as fenced
ASCII. A brief is a floor, not a form: every block but the heading is written
only where its field holds something, so a surface prints what it knows and no
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
import re
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
    "Picture",
    "checked_mark",
    "confidence_words",
    "diagram",
    "letter",
    "main",
    "option_parts",
    "read_document",
    "render",
    "symbols_for",
]

# The twelve marks, in the order a brief writes them, as `emoji` and as `ascii`; each is
# followed by its word wherever it is written. No `ascii` mark is `[ ]`, `[x]` or `[X]`,
# which a markdown view draws at a list item's head as a checkbox, and each is a word, so
# ordinary text in brackets is not mistaken for one.
MARKS: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        "emoji": MappingProxyType(
            {
                "waiting": "⏳",
                "term": "📖",
                "picture": "🗺️",
                "explore": "🧪",
                "recommended": "⭐",
                "choose_if": "⚖️",
                "downside": "🔻",
                "checked": "✅",
                "unchecked": "⚠️",
                "debt": "🧱",
                "undo": "↩️",
                "cannot_be_undone": "⛔",
            }
        ),
        "ascii": MappingProxyType(
            {
                "waiting": "[wait]",
                "term": "[term]",
                "picture": "[pic]",
                "explore": "[explore]",
                "recommended": "[rec]",
                "choose_if": "[choose]",
                "downside": "[-]",
                "checked": "[ok]",
                "unchecked": "[!]",
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
    """A brief's own diagram, drawn after its context and terms where order,
    dependency, flow or before/after is the point.

    `edges` hold `(from, to, label)` in the order they are drawn, an empty label
    drawing an unlabelled edge; every edge is drawn, and none is reduced away.
    `caption`, where set, is the line written above the fence, behind the picture
    mark; without one the fence stands alone.
    """

    edges: tuple[tuple[str, str, str], ...]
    caption: str = ""


@dataclass(frozen=True, slots=True)
class Picture:
    """A small fixed-width figure the agent gives line by line, drawn in a `text` fence
    under its caption, for a before and after that edges show badly. `lines` may hold
    an empty line but not only empty lines."""

    caption: str
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Brief:
    """One decision brief, holding only what its surface knows.

    Only `heading` is required; an empty field writes nothing. Each of `options`
    is `(way, leads_to)`, `(way, leads_to, downside)` or `(way, leads_to, downside,
    choose_if)`: the downside and the condition under which a reasonable person picks
    the Option are each written on a line of their own under it. `context` holds
    blocks, each a string (a paragraph) or a tuple of strings (a list); `terms` holds
    `(term, meaning)` pairs, each a paragraph of its own. `checked` and `undo` pair a
    `MARKS` key with the line's text: `checked` or `unchecked`, and `undo` or
    `cannot_be_undone`. A surface reaches the key `checked` only through
    `checked_mark`. `recommend_way` names the Option the surface recommends, by its
    way, and the renderer writes `recommend` under that Option, behind the
    recommended mark, and ends it with `confidence` in words; unset, the
    recommendation is a paragraph of its own after the Options. `facts` holds
    `(label, text)` pairs, each a fact the surface knows that bears on the answer,
    written as a paragraph `<label>: <text>` after `Not checked` and before `Debt`.
    `diagram`, where set, is drawn after the terms and `picture` after it. `why_now`
    is written first, as what waits on the answer, and `explore` right before the
    Options; where `id` is set, the offer ends by naming the reply that asks for the page.
    """

    heading: str
    recommend: str = ""
    confidence: str = ""
    options: tuple[tuple[str, ...], ...] = ()
    why_now: str = ""
    asked: tuple[str, ...] = ()
    checked: tuple[str, str] | None = None
    not_checked: str = ""
    debt: str = ""
    undo: tuple[str, str] | None = None
    recommend_way: str = ""
    facts: tuple[tuple[str, str], ...] = ()
    diagram: Diagram | None = None
    context: tuple[str | tuple[str, ...], ...] = ()
    terms: tuple[tuple[str, str], ...] = ()
    picture: Picture | None = None
    explore: str = ""
    id: str = ""


def checked_mark(verdicts: Sequence[str]) -> str:
    """The `MARKS` key a `Checked` line holding `verdicts` carries.

    `checked`, the mark that means a check passed, only where `verdicts` is not
    empty and every item is exactly `PASS`; `unchecked` otherwise, so no verdict
    at all, `FAIL`, `UNVERIFIED`, `RUN_UNVERIFIED`, `pass` and any other word are
    not passed.
    """

    return "checked" if verdicts and all(item == "PASS" for item in verdicts) else "unchecked"


def letter(index: int) -> str:
    """The letter of the Option at `index`, from A."""

    return string.ascii_uppercase[index]


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
        return "a brief's confidence belongs to its recommendation, and this one has none"
    if brief.recommend_way and not brief.recommend:
        return "a brief's recommended way belongs to its recommendation, and this one has none"
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
            "and this one has no recommendation"
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


# What the `confidence` field is drawn as: the two values the skill names, in words; any
# other value, such as an older document's percentage, as given.
_CONFIDENCE_WORDS = MappingProxyType({"fact": "a check shows this", "inferred": "my judgment"})


def confidence_words(confidence: str) -> str:
    """`confidence` as the brief draws it: `fact` and `inferred` in words, else as given."""

    return _CONFIDENCE_WORDS.get(confidence, confidence)


def _recommendation(brief: Brief, marks: Mapping[str, str], sep: str) -> str:
    """The recommended mark, its word, the reason as given and the confidence in words."""

    confidence = confidence_words(brief.confidence)
    tail = f"{sep}{confidence}" if confidence else ""
    return f"{marks['recommended']} Recommended: {brief.recommend}{tail}"


def option_parts(option: Sequence[str]) -> tuple[str, str, str, str]:
    """An Option as `(way, leads_to, downside, choose_if)`, an empty string for each it lacks."""

    way, leads_to, *rest = option
    return way, leads_to, rest[0] if rest else "", rest[1] if len(rest) > 1 else ""


def _option_list(brief: Brief, marks: Mapping[str, str], sep: str, dash: str) -> str:
    """The Options as one list: each Option's letter, way and what it leads to, then, nested
    under it, the recommendation where it names this Option, the condition for choosing it
    and its downside."""

    ways = _ways(brief)
    recommended = ways.index(brief.recommend_way) if brief.recommend and brief.recommend_way else -1
    lines: list[str] = []
    for index, option in enumerate(brief.options):
        way, leads_to, downside, choose_if = option_parts(option)
        lines.append(f"- **{string.ascii_uppercase[index]}{sep}{way}**{dash}{leads_to}")
        if index == recommended:
            lines.append(f"  - {_recommendation(brief, marks, sep)}")
        if choose_if:
            lines.append(f"  - {marks['choose_if']} Choose if: {choose_if}")
        if downside:
            lines.append(f"  - {marks['downside']} Downside: {downside}")
    return "\n".join(lines)


def _fence(lines: Sequence[str]) -> str:
    return "\n".join(["```text", *lines, "```"])


def _lead_blocks(brief: Brief, symbols: str, form: str) -> list[str]:
    """What waits on the answer, the context, the terms, the picture and the offer to explore."""

    marks = MARKS[symbols]
    blocks: list[str] = []
    if brief.why_now:
        blocks.append(f"{marks['waiting']} Waiting on this: {brief.why_now}")
    blocks.extend(
        block if isinstance(block, str) else "\n".join(f"- {item}" for item in block)
        for block in brief.context
    )
    blocks.extend(f"{marks['term']} *{term}*: {meaning}" for term, meaning in brief.terms)
    if brief.diagram is not None:
        if brief.diagram.caption:
            blocks.append(f"{marks['picture']} {brief.diagram.caption}")
        blocks.append(_drawing(brief.diagram, form))
    if brief.picture is not None:
        blocks.append(f"{marks['picture']} {brief.picture.caption}")
        blocks.append(_fence(brief.picture.lines))
    if brief.explore:
        ask = f"{SEPARATORS[symbols][0]}reply `explore {brief.id}` for an interactive page"
        blocks.append(f"{marks['explore']} Explore: {brief.explore}{ask if brief.id else ''}")
    return blocks


def _evidence_blocks(brief: Brief, symbols: str) -> list[str]:
    """The evidence, one paragraph each, in the order `Asked`, `Checked`, `Not checked`, the
    facts, `Debt`, `Undo`."""

    marks = MARKS[symbols]
    blocks = [f"Asked: {text}" for text in brief.asked]
    if brief.checked:
        blocks.append(f"{marks[brief.checked[0]]} Checked: {brief.checked[1]}")
    if brief.not_checked:
        blocks.append(f"{marks['unchecked']} Not checked: {brief.not_checked}")
    blocks.extend(f"{label}: {text}" for label, text in brief.facts)
    if brief.debt:
        blocks.append(f"{marks['debt']} Debt: {brief.debt}")
    if brief.undo:
        blocks.append(f"{marks[brief.undo[0]]} Undo: {brief.undo[1]}")
    return blocks


def _blocks(brief: Brief, symbols: str, form: str) -> list[str]:
    """One brief's blocks, in the order a person decides, each written only where its field
    is set; the caller separates them by one blank line."""

    marks = MARKS[symbols]
    sep, dash = SEPARATORS[symbols]
    blocks = [f"### {brief.heading}", *_lead_blocks(brief, symbols, form)]
    if brief.options:
        blocks.extend(["**Options**", _option_list(brief, marks, sep, dash)])
    if brief.recommend and not (brief.options and brief.recommend_way):
        blocks.append(_recommendation(brief, marks, sep))
    return [*blocks, *_evidence_blocks(brief, symbols)]


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
    """A brief's own diagram's fence, without a trailing newline: every edge in the order
    given, none reduced, as a Mermaid flowchart under `mermaid` and as ASCII chains in a
    `text` fence under any other form."""

    if form == "mermaid":
        return "\n".join(_mermaid(drawn.edges, _labels(drawn.edges)))
    return _fence(_chains(drawn.edges))


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
    """Every brief as a `###` heading and the blocks of its fields, in the order a person
    decides, and, where `order` is given, the order's diagram after the last brief; every
    diagram in `form`.

    Every block is separated from the next by exactly one blank line, so no markdown view
    runs two lines into one paragraph or two lists into one. Nothing is padded or wrapped,
    and nothing is fenced but a diagram and a picture; an empty `briefs` is
    `NOTHING_WAITS`. A brief with one option or more than there are letters, with a
    confidence and no recommendation, or with a recommended way it has no recommendation
    for or does not lay out, is refused by `ValueError` before anything is drawn.
    """

    if not briefs:
        return NOTHING_WAITS
    for brief in briefs:
        refused = _refused(brief)
        if refused:
            raise ValueError(refused)
    blocks: list[str] = []
    for brief in briefs:
        blocks.extend(_blocks(brief, symbols, form))
    if order:
        blocks.append(diagram(order, symbols, form))
    return "\n\n".join(blocks) + "\n"


# The longest header a harness's question tool shows: Codex's request_user_input describes its
# header as 12 or fewer characters (request_user_input_spec.rs, read 2026-10-05), and Claude Code's
# AskUserQuestion tool describes its header parameter as "max 12 chars" (the tool's own parameter
# description, read 2026-10-16); a longer id is left to the question text.
_HEADER = 12


def questions(briefs: Sequence[Brief], ids: Sequence[str], symbols: str) -> dict[str, Any]:
    """Every brief as one question for a harness's question tool, each field on one line.

    A question holds `id`, the brief's id; `header`, the id where it fits a tool's short header,
    else empty; `question` and `title`, the same text, the heading and then the recommended
    Option's letter and why, behind `Recommended:`; and `options`, the recommended Option first,
    as the tools ask, then the rest in letter order, and, for a brief with `explore`, a last
    choice, `Explore it first`. Each option holds `label`, its letter and way, with
    " (Recommended)" on the recommended one; `description`, what it leads to, then `choose if:`
    its condition and `downside:` its downside, each where given; and `line`, the label and what
    it leads to, for a tool whose options are plain strings. A brief with no Options has an empty
    `options`. The drawn brief, with its context and evidence, goes in the message before the
    question. A brief `render` refuses is refused here by the same `ValueError`.
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
            text += f"{sep}Recommended: {letter}{brief.recommend}"
        options = []
        for index, option in enumerate(brief.options):
            way, leads_to, downside, choose_if = option_parts(option)
            label = f"{string.ascii_uppercase[index]} {way}"
            if index == recommended:
                label += " (Recommended)"
            description = leads_to
            if choose_if:
                description += f"; choose if: {choose_if}"
            if downside:
                description += f"; downside: {downside}"
            options.append(
                {"label": label, "description": description, "line": f"{label}{dash}{leads_to}"}
            )
        if recommended is not None:
            options.insert(0, options.pop(recommended))
        if brief.explore and options:
            options.append(
                {
                    "label": "Explore it first",
                    "description": brief.explore,
                    "line": f"Explore it first{dash}{brief.explore}",
                }
            )
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
      "heading": "Should the old flag stay for one more release?",
      "why_now": "the release notes for 2.0; until you answer, the flag stays",
      "context": [
        "The old `--legacy` flag switches the parser back to its 1.x behaviour.",
        "Two adopters still set it.",
        ["Keeping it: those adopters see a warning for one release before it goes.",
         "Dropping it: the code path goes in 2.0."]
      ],
      "terms": [["code path", "the branch of the parser that runs only when the flag is set"]],
      "recommend": "two adopters still set it",
      "recommend_way": "keep it",
      "confidence": "fact",
      "options": [
        {"way": "keep it", "leads_to": "adopters get a warning first",
         "choose_if": "no adopter should break on upgrade",
         "downside": "one more release carries the old code path"},
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
`outcomebound brief lookup TERM... [--in PATH]... [--json]` finds a brief by id or words and
prints the `Decided:` answer recorded for it (`lookup --help`). `outcomebound brief open
[PATH]... [--json]` lists the briefs with no recorded answer (`open --help`).

The document is one JSON object (schemas/decision-briefs.schema.json):
  briefs   the briefs, in the order they are put to the person; each holds
           id (required: the id the person answers by, joined to the heading
           with the separator of the symbols drawn), heading (required, the
           question in one line), undo (required: {{"can_be_undone": true or
           false, "text": ...}}), at least one line of evidence: checked
           ({{"verdicts": [...], "text": ...}}), not_checked (what could not
           be checked, why, and what would settle it) or facts ([label, text]
           pairs, no label naming a line the renderer writes); and, where it
           changes the answer: why_now (what waits on the answer and what
           happens if none comes; drawn first, after the question),
           context (blocks, each a string, drawn as a paragraph, or a list of
           strings, drawn as a list; two lists never in a row; no block or
           item starts with a markdown opener such as - * + # > 1. | ``` ---),
           terms ([term, meaning] pairs, each drawn as a paragraph after the
           context; no term starts or ends with * or _), diagram
           ({{"caption": ..., "edges": [[from, to] or [from, to, label],
           ...]}}, drawn where order, dependency, flow or before/after is the
           point), picture ({{"caption": ..., "lines": [...]}}: a small
           fixed-width figure drawn in a text fence; the caption is required,
           a line may be empty but not all of them; no line holds three
           backticks, a wide East Asian character, U+FE0F or U+20E3),
           explore (one line: what an interactive page would let the person
           try, for a decision that is not simple; the person can ask for it
           by the brief's id), options (two or more: [way, what it leads to,
           its downside] triples, or {{"way", "leads_to", "downside",
           "choose_if"}} objects, choose_if optional: when a reasonable person
           picks it; no way starts or ends with * or _), recommend (why;
           required with options), recommend_way (the way of options
           recommended, required with options; the recommendation is drawn
           under that option), confidence (`fact` where a command you ran
           shows it, drawn as "a check shows this", else `inferred`, drawn as
           "my judgment"), asked (a list), debt (what the choice leaves owed)
  order    optional [before, after] pairs of brief ids: after waits on
           before; drawn after the last brief

A brief reads in the order a person decides: the question, what waits on it,
the context, the terms, the picture, the offer to explore, each option with
its recommendation, when to choose it and its downside, then the evidence.
Every block is separated from the next by one blank line.

Every string is one line. The command writes marks only from these fields:
the passed mark where every verdict given is PASS. It refuses a string
holding a line break, a control or format character, or a mark's own glyph;
an id that is not a letter followed by letters, digits and hyphens; a
diagram label holding a double quote, or an edge label holding a |, which
would break a Mermaid diagram; and the context, term, option and picture
rules above. It does not vouch for what your text says:
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
as title) is the heading and the recommendation, behind Recommended:; the recommended
option comes first, its label ending (Recommended); a description is what the option
leads to, then choose if: and downside:; a brief with explore gets a last option,
Explore it first; line is the label and what it leads to, for a tool whose options
are plain strings; header is the id where it has 12 characters or fewer. The order is
not printed. Fill the tool's fields by name, after the drawn brief in the message.
Posting to a GitHub issue, discussion or pull request, or from the Codex app, pass
--form mermaid: those surfaces set no variable. Show the output as markdown, never
inside a code block. Exit 0 when drawn; exit 1 when a brief is refused, naming
which: one option or more than 26, two or more options with no recommend or
recommend_way, a confidence or a recommended way with no recommendation, a
recommended way it does not lay out, or no checked, not_checked or facts; exit 2 when
the document cannot be read or breaks a rule above (an option object missing its way,
what it leads to or its downside; an empty context block or list; two context lists in
a row; a context block or item starting with a markdown opener; a term or a way
starting or ending with * or _; a terms pair that is not exactly two; a picture with no
caption or only empty lines, or a picture line holding what is refused above), naming
why, and on a usage error.
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


def _options(values: Sequence[Any], where: str) -> tuple[tuple[str, ...], ...]:
    """Each Option as `(way, leads_to, downside)`, with `choose_if` after them where given.

    An Option given as a list holding other than three strings is refused by its path,
    naming the downside it lacks; one given as an object has been checked by the schema
    for its way, what it leads to and its downside.
    """

    options: list[tuple[str, ...]] = []
    for index, value in enumerate(values):
        if isinstance(value, Mapping):
            parts = (value["way"], value["leads_to"], value["downside"])
            options.append(parts + ((value["choose_if"],) if "choose_if" in value else ()))
        elif len(value) != 3:
            raise _Unreadable(
                f"{where}[{index}] must hold exactly three strings: the way, what it leads to, "
                "and its downside"
            )
        else:
            options.append((value[0], value[1], value[2]))
    return tuple(options)


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
        "Recommended",
        "Options",
        "Downside",
        "Choose if",
        "Explore",
        "Why now",
        "Waiting on this",
        "Asked",
        "Checked",
        "Not checked",
        "Debt",
        "Undo",
        "Confidence",
    )
)

# The start of a one-line context paragraph or list item that a CommonMark view would read as a
# block of its own: a bullet or an ordered-list number followed by a space or the end, a heading
# mark followed by a space or the end, a quote, a fence, or a whole line that is a rule. Text such
# as `3.12 is the minimum`, `#3 needs` or `-5 degrees` opens no block and is not refused; a table
# or a setext underline needs a second line, which a one-line block never has.
_BLOCK_OPENER = re.compile(
    r"(?:[-*+]|\d{1,9}[.)]|#{1,6})(?:[ \t]|$)|>|```|~~~|(?:[-*_][ \t]*){3,}$"
)


def _opener(text: str) -> bool:
    return _BLOCK_OPENER.match(text.lstrip()) is not None


def _edge(text: str) -> bool:
    """Whether `*` or `_` stands at either edge of `text`, which would open or close emphasis
    around the mark and the word that bracket it."""

    return text[:1] in ("*", "_") or text[-1:] in ("*", "_")


# Characters a fixed-width figure cannot rely on: the emoji presentation selector and the
# keycap, and the East Asian widths W and F, which a terminal draws two columns wide.
_NO_COMBINING = ("\ufe0f", "\u20e3")
_WIDE = ("W", "F")


def _picture_defect(line: str) -> str:
    """Why a picture line cannot be drawn in a fence at a fixed width, or the empty string."""

    if "```" in line:
        return "holds three backticks, which end its fence"
    for character in line:
        if character in _NO_COMBINING or unicodedata.east_asian_width(character) in _WIDE:
            return (
                f"holds the character U+{ord(character):04X}, which is drawn two columns wide "
                "or changes how its neighbour is drawn"
            )
    return ""


def _checked_context(blocks: Sequence[Any], at: str) -> None:
    """Two lists in a row, and a paragraph or item that starts a block of its own."""

    after_list = False
    for number, block in enumerate(blocks):
        where = f"{at}.context[{number}]"
        items = block if isinstance(block, list) else None
        if items is not None and after_list:
            raise _Unreadable(
                f"{where} is a list directly after another list, which a markdown view joins "
                "into one; put a paragraph between them"
            )
        after_list = items is not None
        for position, text in enumerate(items if items is not None else [block]):
            if _opener(text):
                at_item = where if items is None else f"{where}[{position}]"
                raise _Unreadable(
                    f"{at_item} starts with a markdown block opener, which a markdown view "
                    "reads as a block of its own; start with a word"
                )


def _checked_picture(picture: Mapping[str, Any], at: str) -> None:
    """A picture of only empty lines, and a line a fence cannot hold at a fixed width."""

    if not any(picture["lines"]):
        raise _Unreadable(f"{at}.picture.lines holds only empty lines")
    for number, line in enumerate(picture["lines"]):
        defect = _picture_defect(line)
        if defect:
            raise _Unreadable(f"{at}.picture.lines[{number}] {defect}")


def _checked_blocks(entry: Mapping[str, Any], index: int) -> None:
    """Refuse what would make a markdown view run the brief's blocks together or draw a
    figure out of line: two context lists in a row, a context paragraph or item that starts a
    block of its own, `*` or `_` at an edge of a way or a term, and a picture of only empty
    lines or with a line a fence cannot hold. An empty block, list or item is the schema's."""

    at = f"$.briefs[{index}]"
    _checked_context(entry.get("context", ()), at)
    for number, term in enumerate(entry.get("terms", ())):
        if _edge(term[0]):
            raise _Unreadable(f"{at}.terms[{number}][0] starts or ends with * or _")
    for number, option in enumerate(entry.get("options", ())):
        way = option["way"] if isinstance(option, Mapping) else option[0]
        if _edge(way):
            raise _Unreadable(f"{at}.options[{number}] has a way that starts or ends with * or _")
    if "picture" in entry:
        _checked_picture(entry["picture"], at)


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
        _checked_blocks(entry, index)
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
        context=tuple(
            block if isinstance(block, str) else tuple(block) for block in entry.get("context", ())
        ),
        terms=_pairs(entry.get("terms", ()), f"$.briefs[{index}].terms"),
        picture=(
            Picture(entry["picture"]["caption"], tuple(entry["picture"]["lines"]))
            if "picture" in entry
            else None
        ),
        explore=entry.get("explore", ""),
        id=entry["id"],
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


def read_document(
    source: str | os.PathLike[str], symbols: str = "emoji"
) -> tuple[list[tuple[str, Brief]], tuple[tuple[str, str], ...]]:
    """The briefs of the JSON document at `source`, each beside its id, and the order among
    them, read and refused exactly as `outcomebound brief` reads and refuses them: a document it
    cannot read or that breaks a rule, and a brief below the floor. A refusal is a `ValueError`
    whose text names the cause. `source` is a file's path; standard input is not read."""

    briefs, order = _read(os.fspath(source), symbols)
    for number, (brief_id, brief) in enumerate(briefs, start=1):
        refused = _refused(brief) or _below_floor(brief)
        if refused:
            raise ValueError(f"brief {number}, {brief_id}, is refused: {refused}")
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

    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["lookup"]:
        # A document named `lookup` is given as `./lookup`.
        from outcomebound_tools import brief_lookup

        return brief_lookup.main(arguments[1:])
    if arguments[:1] == ["open"]:
        # A document named `open` is given as `./open`.
        from outcomebound_tools import brief_open

        return brief_open.main(arguments[1:])
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
    args = parser.parse_args(arguments)
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
