"""The HTML drawing of decision briefs, for a decision explorable.

What this module decides: how the briefs `decision_brief.read_document` accepts are drawn as
HTML: the marks, the line names and the block order of the markdown drawing in its emoji form (what
waits on the answer, the context, the terms, the picture, the offer to explore, the options with
the recommendation on the option it names, the evidence), with classes the shared stylesheet
styles; each brief's own diagram, and the order among the briefs, as `data-diagram` blocks
(Mermaid source) with the ASCII chain form as their fallback text, and a picture as a `figure`
holding a `pre`; every text escaped; and a `code` element for each backtick span. It also fixes
the shape of each brief in the page's configuration, which is what the runtime builds the reply
from.

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


def _mark(key: str) -> str:
    return f'<span class="xp-mark">{MARKS[_SYMBOLS][key]}</span>'


def _figure(
    caption: str, mermaid: str, fallback: str, note: str = "", extra: str = "", mark: str = ""
) -> str:
    title = f"<figcaption>{mark}{_inline(caption)}</figcaption>\n" if caption else ""
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
    mark = _mark("picture") + " " if drawn.caption else ""
    return _figure(drawn.caption, mermaid, fallback, mark=mark)


def _picture_figure(brief: Brief) -> str:
    picture = brief.picture
    if picture is None:
        return ""
    return (
        '<figure class="xp-figure xp-picture">'
        f"<figcaption>{_mark('picture')} {_inline(picture.caption)}</figcaption>\n"
        f'<pre class="xp-picture-lines">{html.escape(chr(10).join(picture.lines), quote=False)}'
        "</pre></figure>"
    )


def _heading_text(brief_id: str, brief: Brief) -> str:
    """The brief's heading without its id and the separator the drawing joined to it."""

    sep, _ = SEPARATORS[_SYMBOLS]
    return brief.heading[len(brief_id) + len(sep) :]


def _recommend(brief: Brief, css: str) -> str:
    """The recommendation: the mark, `Recommended:`, the reason, the confidence in words."""

    sep, _ = SEPARATORS[_SYMBOLS]
    confidence = decision_brief.confidence_words(brief.confidence)
    tail = f"{sep}{confidence}" if confidence else ""
    return (
        f'<p class="{css}">{_mark("recommended")} '
        f"Recommended: {_inline(brief.recommend)}{_escape(tail)}</p>"
    )


def _options(brief: Brief) -> str:
    """The `Options` lead-in and the lettered list; the recommendation sits inside the option it
    names, before its `Choose if` and `Downside` lines."""

    _, dash = SEPARATORS[_SYMBOLS]
    ways = [option[0] for option in brief.options]
    recommended = ways.index(brief.recommend_way) if brief.recommend and brief.recommend_way else -1
    items = []
    for index, option in enumerate(brief.options):
        way, leads_to, downside, choose_if = decision_brief.option_parts(option)
        letter = decision_brief.letter(index)
        nested = []
        if index == recommended:
            nested.append(_recommend(brief, "xp-rec-inline"))
        if choose_if:
            nested.append(
                f'<p class="xp-choose">{_mark("choose_if")} Choose if: {_inline(choose_if)}</p>'
            )
        if downside:
            nested.append(
                f'<p class="xp-downside">{_mark("downside")} Downside: {_inline(downside)}</p>'
            )
        inner = "".join(f"\n    {line}" for line in nested)
        items.append(
            f'  <li class="xp-option" data-letter="{letter}"><span class="xp-letter">{letter}'
            f'</span> <span class="xp-way">{_inline(way)}</span>{_escape(dash)}'
            f"{_inline(leads_to)}{inner}</li>"
        )
    return (
        '<p class="xp-line xp-options"><strong>Options</strong></p>\n'
        '<ol class="xp-option-list">\n' + "\n".join(items) + "\n</ol>"
    )


def _context(brief: Brief) -> list[str]:
    """Each context block: a paragraph for a string, a list for a list of strings."""

    blocks: list[str] = []
    for block in brief.context:
        if isinstance(block, str):
            blocks.append(f'<p class="xp-context">{_inline(block)}</p>')
        else:
            items = "".join(f"<li>{_inline(item)}</li>" for item in block)
            blocks.append(f'<ul class="xp-context-list">{items}</ul>')
    return blocks


def _lead_blocks(brief: Brief) -> list[str]:
    """What waits on the answer, the context, the terms, the pictures and the offer to explore."""

    blocks: list[str] = []
    if brief.why_now:
        blocks.append(
            f'<p class="xp-line xp-why">{_mark("waiting")} Waiting on this: '
            f"{_inline(brief.why_now)}</p>"
        )
    blocks.extend(_context(brief))
    blocks.extend(
        f'<p class="xp-line xp-term">{_mark("term")} <em>{_escape(term)}</em>: '
        f"{_inline(meaning)}</p>"
        for term, meaning in brief.terms
    )
    blocks.extend(figure for figure in (_brief_figure(brief), _picture_figure(brief)) if figure)
    if brief.explore:
        blocks.append(
            f'<p class="xp-line xp-explore">{_mark("explore")} Explore: '
            f"{_inline(brief.explore)}</p>"
        )
    return blocks


def _evidence_blocks(brief: Brief) -> list[str]:
    """The evidence, one paragraph each, in the order the markdown drawing writes it."""

    marks = MARKS[_SYMBOLS]
    blocks = [f'<p class="xp-line xp-asked">Asked: {_inline(text)}</p>' for text in brief.asked]
    if brief.checked:
        blocks.append(
            f'<p class="xp-line xp-checked"><span class="xp-mark">{marks[brief.checked[0]]}'
            f"</span> Checked: {_inline(brief.checked[1])}</p>"
        )
    if brief.not_checked:
        blocks.append(
            f'<p class="xp-line xp-not-checked">{_mark("unchecked")} '
            f"Not checked: {_inline(brief.not_checked)}</p>"
        )
    blocks.extend(
        f'<p class="xp-line xp-fact"><span class="xp-label">{_escape(label)}</span>: '
        f"{_inline(text)}</p>"
        for label, text in brief.facts
    )
    if brief.debt:
        blocks.append(f'<p class="xp-line xp-debt">{_mark("debt")} Debt: {_inline(brief.debt)}</p>')
    if brief.undo:
        blocks.append(
            f'<p class="xp-line xp-undo"><span class="xp-mark">{marks[brief.undo[0]]}</span> '
            f"Undo: {_inline(brief.undo[1])}</p>"
        )
    return blocks


def _blocks(brief: Brief) -> list[str]:
    """The brief's blocks after its heading, in the order the markdown drawing writes them."""

    blocks = _lead_blocks(brief)
    if brief.options:
        blocks.append(_options(brief))
    if brief.recommend and not (brief.options and brief.recommend_way):
        blocks.append(_recommend(brief, "xp-line xp-recommend"))
    return [*blocks, *_evidence_blocks(brief)]


def _article(brief_id: str, brief: Brief) -> str:
    sep, _ = SEPARATORS[_SYMBOLS]
    head = (
        f'<h2><span class="xp-brief-id">{_escape(brief_id)}</span>{_escape(sep)}'
        f"{_inline(_heading_text(brief_id, brief))}</h2>"
    )
    body = "\n".join([head, *_blocks(brief)])
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
