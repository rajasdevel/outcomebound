"""The HTML drawing of decision briefs, for a decision explorable.

What this module decides: how the briefs `decision_brief.read_document` accepts are drawn as
HTML: the marks, the line names and the line order of the markdown drawing in its emoji form, with
classes the shared stylesheet styles; each brief's own diagram, and the order among the briefs,
as `data-diagram` blocks (Mermaid source) with the ASCII chain form as their fallback text; every
text escaped; and a `code` element for each backtick span. It also fixes the shape of each brief
in the page's configuration, which is what the runtime builds the reply from.

What it does not decide: which brief is accepted, which is `decision_brief`'s reading and
refusals, or what the page around the drawing holds. The markdown drawing stays the one way a
decision is put to a person; this drawing is the page's copy.
"""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from typing import Any

from outcomebound_tools import decision_brief
from outcomebound_tools.decision_brief import MARKS, SEPARATORS, Brief

__all__ = ["config_briefs", "render_html"]

_SYMBOLS = "emoji"
_CODE_SPAN = re.compile(r"`([^`]+)`")


def _escape(text: str) -> str:
    """`text` for an element's content or a double-quoted attribute value."""

    return html.escape(text, quote=False).replace('"', "&quot;")


def _inline(text: str) -> str:
    """`text` escaped, a backtick span as a `code` element."""

    return _CODE_SPAN.sub(r"<code>\1</code>", _escape(text))


def _fence(markdown: str, language: str) -> str:
    """The text inside the first fence of `language` in `markdown`."""

    found = re.search(rf"```{language}\n(.*?)\n```", markdown, re.DOTALL)
    return found.group(1) if found else ""


def _diagram_pair(mermaid: str, fallback: str) -> str:
    """The `pre` elements the runtime draws, and shows where a diagram cannot be drawn."""

    return (
        f"<pre data-diagram>{html.escape(mermaid, quote=False)}</pre>\n"
        f"<pre data-diagram-fallback>{html.escape(fallback, quote=False)}</pre>"
    )


def _figure(caption: str, mermaid: str, fallback: str, note: str = "", extra: str = "") -> str:
    title = f"<figcaption>{_inline(caption)}</figcaption>\n" if caption else ""
    tail = f'\n<p class="xp-note">{_inline(note)}</p>' if note else ""
    return (
        f'<figure class="xp-figure{extra}">{title}{_diagram_pair(mermaid, fallback)}{tail}</figure>'
    )


def _brief_figure(brief: Brief) -> str:
    drawn = brief.diagram
    if drawn is None:
        return ""
    stub = Brief(heading="x", diagram=drawn)
    mermaid = _fence(decision_brief.render([stub], _SYMBOLS, (), "mermaid"), "mermaid")
    fallback = _fence(decision_brief.render([stub], _SYMBOLS, (), "ascii"), "text")
    return _figure(drawn.caption, mermaid, fallback)


def _heading_text(brief_id: str, brief: Brief) -> str:
    """The brief's heading without its id and the separator the drawing joined to it."""

    sep, _ = SEPARATORS[_SYMBOLS]
    return brief.heading[len(brief_id) + len(sep) :]


def _recommend(brief: Brief, ways: Sequence[str]) -> str:
    sep, dash = SEPARATORS[_SYMBOLS]
    letter = ""
    if brief.recommend_way:
        letter = f"{decision_brief.letter(ways.index(brief.recommend_way))}{dash}"
    confidence = f"{sep}confidence {brief.confidence}" if brief.confidence else ""
    mark = MARKS[_SYMBOLS]["recommend"]
    return (
        f'<li class="xp-line xp-recommend"><span class="xp-mark">{mark}</span> '
        f"Recommend: {_escape(letter)}{_inline(brief.recommend)}{_escape(confidence)}</li>"
    )


def _options(brief: Brief) -> str:
    _, dash = SEPARATORS[_SYMBOLS]
    items = []
    for index, (way, leads_to, *downside) in enumerate(brief.options):
        letter = decision_brief.letter(index)
        risk = "".join(
            '\n    <p class="xp-downside"><span class="xp-mark">'
            f"{MARKS[_SYMBOLS]['downside']}</span> Downside: {_inline(text)}</p>"
            for text in downside
        )
        items.append(
            f'  <li class="xp-option" data-letter="{letter}"><span class="xp-letter">{letter}'
            f'</span> <span class="xp-way">{_inline(way)}</span>{_escape(dash)}'
            f"{_inline(leads_to)}{risk}</li>"
        )
    return (
        '<li class="xp-line xp-options">Options:\n<ol class="xp-option-list">\n'
        + "\n".join(items)
        + "\n</ol></li>"
    )


def _lines(brief: Brief) -> list[str]:
    """The brief's list items, in the order the markdown drawing writes them."""

    marks = MARKS[_SYMBOLS]
    ways = [option[0] for option in brief.options]
    lines: list[str] = []
    if brief.recommend:
        lines.append(_recommend(brief, ways))
    if brief.options:
        lines.append(_options(brief))
    if brief.why_now:
        lines.append(f'<li class="xp-line xp-why">Why now: {_inline(brief.why_now)}</li>')
    lines.extend(
        f'<li class="xp-line xp-asked">Asked: {_inline(text)}</li>' for text in brief.asked
    )
    if brief.checked:
        lines.append(
            f'<li class="xp-line xp-checked"><span class="xp-mark">{marks[brief.checked[0]]}'
            f"</span> Checked: {_inline(brief.checked[1])}</li>"
        )
    if brief.not_checked:
        lines.append(
            f'<li class="xp-line xp-not-checked"><span class="xp-mark">{marks["unchecked"]}'
            f"</span> Not checked: {_inline(brief.not_checked)}</li>"
        )
    lines.extend(
        f'<li class="xp-line xp-fact"><span class="xp-label">{_escape(label)}</span>: '
        f"{_inline(text)}</li>"
        for label, text in brief.facts
    )
    if brief.debt:
        lines.append(
            f'<li class="xp-line xp-debt"><span class="xp-mark">{marks["debt"]}</span> '
            f"Debt: {_inline(brief.debt)}</li>"
        )
    if brief.undo:
        lines.append(
            f'<li class="xp-line xp-undo"><span class="xp-mark">{marks[brief.undo[0]]}</span> '
            f"Undo: {_inline(brief.undo[1])}</li>"
        )
    return lines


def _article(brief_id: str, brief: Brief) -> str:
    sep, _ = SEPARATORS[_SYMBOLS]
    head = (
        f'<h2><span class="xp-brief-id">{_escape(brief_id)}</span>{_escape(sep)}'
        f"{_inline(_heading_text(brief_id, brief))}</h2>"
    )
    figure = _brief_figure(brief)
    body = "\n".join([head, '<ul class="xp-lines">', *_lines(brief), "</ul>"])
    if figure:
        body += "\n" + figure
    return (
        f'<article class="xp-brief" id="brief-{_escape(brief_id)}" '
        f'data-brief="{_escape(brief_id)}">\n{body}\n</article>'
    )


def _order_figure(order: Sequence[tuple[str, str]]) -> str:
    _, dash = SEPARATORS[_SYMBOLS]
    mermaid = _fence(decision_brief.diagram(order, _SYMBOLS, "mermaid"), "mermaid")
    ascii_form = decision_brief.diagram(order, _SYMBOLS, "ascii")
    note = ""
    for line in ascii_form.splitlines():
        if line.startswith("- "):
            note = line[2:]
    return _figure(
        f"Order{dash}an arrow points at what waits on it",
        mermaid,
        _fence(ascii_form, "text"),
        note,
        " xp-order",
    )


def render_html(briefs: Sequence[tuple[str, Brief]], order: Sequence[tuple[str, str]] = ()) -> str:
    """The briefs, each beside its id, and the order among them, as one `section`; the empty
    string for no brief. Every text is escaped."""

    if not briefs:
        return ""
    parts = [_article(brief_id, brief) for brief_id, brief in briefs]
    if order:
        parts.append(_order_figure(order))
    return (
        '<section class="xp-briefs" id="explorable-briefs" aria-label="Decision briefs">\n'
        + "\n".join(parts)
        + "\n</section>"
    )


def config_briefs(briefs: Sequence[tuple[str, Brief]]) -> list[dict[str, Any]]:
    """Each brief as the page's configuration holds it: its id, its heading, the letter it
    recommends or None, and each option's letter and way."""

    shaped: list[dict[str, Any]] = []
    for brief_id, brief in briefs:
        ways = [option[0] for option in brief.options]
        letter = (
            decision_brief.letter(ways.index(brief.recommend_way)) if brief.recommend_way else None
        )
        shaped.append(
            {
                "id": brief_id,
                "heading": _heading_text(brief_id, brief),
                "recommend": letter,
                "options": [
                    {"letter": decision_brief.letter(index), "way": way}
                    for index, way in enumerate(ways)
                ],
            }
        )
    return shaped
