"""`reads` sections: which one section an anchor names, and how far it runs.

What this module decides: which heading of a markdown file an anchor names, how
far that section runs, and when a citation resolves to no one section. It reads
the working tree, since that is where a citation has to resolve, and answers
with a value or a `LinksError`; which level that reads at, and which ticket it
lands on, is the caller's. `brief` names a section by its `heading`.

What it does not decide: anything about a closed ticket, whose links are history
and are not resolved. It builds no message, renders nothing, writes nothing and
runs no subprocess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from outcomebound_tools import paths, textio
from outcomebound_tools.tickets_model import fenced_spans
from outcomebound_tools.tickets_report import EngineError

__all__ = ["LinksError", "Section", "anchor_of", "section"]

# The heading grammar, spelled once.
_HEADING = re.compile(r" {0,3}(?P<hashes>#{1,6})(?:[ \t]+(?P<text>.*))?")
# The heading marker, and the kept characters beyond a letter and a digit.
_MARKER = "#"
_KEPT = " -_"


class LinksError(EngineError):
    """A citation this module will not resolve, carrying the report code it becomes.

    `code` is `READS_UNRESOLVED` or `READS_AMBIGUOUS`, and the message names the
    file and the remedy.
    """

    def __init__(self, code: str, text: str) -> None:
        super().__init__(text)
        self.code = code


@dataclass(frozen=True, slots=True)
class Section:
    """One `reads` target: the heading an anchor names, and its extent.

    `heading` is the heading's text, with its `#` markers and any closing run of
    them dropped; `level` is how many markers it carried. `text` is the section's
    lines as written, fenced content included: what an implementer reads. A
    citation of a path alone names the whole file: its `anchor` and `heading` are
    empty, its `level` is 0, and `text` is the file.
    """

    path: str
    anchor: str
    heading: str
    level: int
    text: str


@dataclass(frozen=True, slots=True)
class _Heading:
    """One `#`-style heading: where it is, how deep, and what it anchors."""

    index: int
    level: int
    text: str
    line: str
    anchor: str


def _read(target: Path | str, relative: str) -> str | None:
    """The file's text with CRLF folded to LF, or None where it is not there.

    Only the two errors that mean "no such file" read as absence; a file that is
    there and cannot be read raises, because reporting it as missing would turn a
    damaged checkout into a clean answer.
    """

    try:
        resolved = paths.resolve_bounded(target, relative)
        return textio.decode(resolved.read_bytes()).replace("\r\n", "\n")
    except (FileNotFoundError, NotADirectoryError):
        return None
    except (OSError, UnicodeDecodeError, paths.PathError) as error:
        raise LinksError(
            "READS_UNRESOLVED",
            f"{relative} is in this checkout but could not be read ({error}); "
            "repair the file before a ticket citing it can be judged",
        ) from error


def _heading_text(raw: str) -> str:
    """A heading's text, with its closing run of `#` removed.

    The trailing whitespace goes before the run does, so `## Reports ## ` and
    `## Reports ##` are one heading. A `#` the text itself ends on is
    indistinguishable from that run and goes with it.
    """

    return raw.rstrip().rstrip("#").strip()


def _kept(character: str) -> bool:
    """The kept set: a letter, a digit, a space, a hyphen or an underscore,
    letters and digits read as Unicode."""

    return character.isalpha() or character.isdigit() or character in _KEPT


def _anchor(text: str) -> str:
    """The anchor of a heading's text: lowercase, remove, then hyphenate."""

    return "".join(
        "-" if character == " " else character for character in text.lower() if _kept(character)
    )


def anchor_of(heading: str) -> str:
    """The anchor of one heading, or the empty string where it has none.

    Takes the heading with its `#` markers or without them. Removal can leave
    neighbouring hyphens and nothing collapses them, so `# Tickets — contracts`
    anchors at `tickets--contracts`. A line that reaches for the `#` marker and
    misses it — `#no-space`, a run of seven, a marker indented four spaces — has
    no anchor, as `section` reads no heading there.
    """

    match = _HEADING.fullmatch(heading)
    if match is not None:
        return _anchor(_heading_text(match.group("text") or ""))
    if heading.lstrip().startswith(_MARKER):
        return ""
    return _anchor(_heading_text(heading))


def _headings(lines: list[str], fenced: list[bool]) -> list[_Heading]:
    """Every `#`-style heading outside a code fence, in document order.

    An underlined heading is not one here: a spec's frontmatter
    fence would otherwise read as a heading over the line above it.
    """

    found: list[_Heading] = []
    for index, line in enumerate(lines):
        match = None if fenced[index] else _HEADING.fullmatch(line)
        if match is None:
            continue
        text = _heading_text(match.group("text") or "")
        found.append(_Heading(index, len(match.group("hashes")), text, line, _anchor(text)))
    return found


def _fenced(text: str, lines: list[str]) -> list[bool]:
    """Which of the file's lines a code fence swallows."""

    spans = fenced_spans(text)
    flags: list[bool] = []
    position = 0
    span = 0
    for line in lines:
        while span < len(spans) and spans[span][1] <= position:
            span += 1
        flags.append(span < len(spans) and spans[span][0] <= position)
        position += len(line) + 1
    return flags


def section(target: Path | str, path: str, anchor: str) -> Section:
    """The one section `path#anchor` names, or the `LinksError` saying why not.

    An empty `anchor` names the whole file, which resolves wherever the file can
    be read as text.

    `READS_UNRESOLVED` where the path is not one this engine reads, the file is
    not there, or no heading carries the anchor; `READS_AMBIGUOUS` where two
    headings share it. A section runs from its heading to the line before the
    next heading of the same or a higher level; a heading of only removed
    characters has no anchor, and still ends the section above it.
    """

    try:
        relative = paths.bounded_relative(path)
    except paths.PathError as error:
        raise LinksError(
            "READS_UNRESOLVED",
            f"{path!r} is not a repository-relative path this engine will read ({error}); "
            "cite a path inside the repository, written without a leading separator and "
            "without `..`",
        ) from error
    text = _read(target, relative)
    if text is None:
        resolves = f"the anchor {anchor!r}" if anchor else "the whole-file citation"
        raise LinksError(
            "READS_UNRESOLVED",
            f"no file {relative} is in this checkout, so {resolves} resolves to "
            "nothing; cite a file the repository holds",
        )
    if not anchor:
        return Section(path=relative, anchor="", heading="", level=0, text=text)
    lines = text.split("\n")
    headings = _headings(lines, _fenced(text, lines))
    found = [at for at, heading in enumerate(headings) if heading.anchor == anchor != ""]
    if not found:
        raise LinksError(
            "READS_UNRESOLVED",
            f"no heading in {relative} has the anchor {anchor!r}; the anchor of a heading is "
            "its text lowercased with every character that is not a letter, a digit, a "
            "space, a hyphen or an underscore removed and each space replaced by a hyphen, "
            "so cite it as that spells it",
        )
    if len(found) > 1:
        named = " and ".join(headings[at].line.strip() for at in found)
        raise LinksError(
            "READS_AMBIGUOUS",
            f"{len(found)} headings in {relative} share the anchor {anchor!r} — {named}; "
            "rename one of them so that the citation names one section",
        )
    heading = headings[found[0]]
    stop = next(
        (later.index for later in headings[found[0] + 1 :] if later.level <= heading.level),
        len(lines),
    )
    return Section(
        path=relative,
        anchor=anchor,
        heading=heading.text,
        level=heading.level,
        text="\n".join(lines[heading.index : stop]),
    )
