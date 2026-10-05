"""A draft: a local file, read before anything about it has been published.

What this module decides: what a draft is — a file whose first line is
`# <title>`, its id the file name without the extension, which is how other
drafts name it — what its `blocked-by` and `parent` entries may name, and which
drafts given together claim one id, and which paragraph every draft of a
breakdown repeats. It is the one place a draft is read, so
`check --draft` and `brief --draft` cannot come to differ about what a draft is.

What it does not decide: what a block says (`tickets_model`), whether a relation
closes a knot (`tickets_graph`), or what a message does to a verdict
(`tickets_report`). **It makes no git call, reads no store and reads no claims
plan:** a draft is a file and nothing else (the engine's own issue template is
read too, to know its placeholder text), which is what lets a breakdown be
reviewed before anything is published.

A file this module will not read is a finding about that draft and never the end
of a run, so everything it refuses comes back as a `Message` stamped with the
draft's id. The one exception is a path carrying no file name at all: there is no
id to stamp, and that is `DraftError`.
"""

from __future__ import annotations

import dataclasses
import functools
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType

from outcomebound_tools.home import ROOT
from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_model import (
    STATES,
    Ticket,
    content_identity,
    effective_hold,
    parse_block,
)
from outcomebound_tools.tickets_report import EngineError, Message, message

__all__ = ["DraftError", "draft_relations", "read_draft", "repeated_guidance"]

_OPEN = STATES[0]

# A draft's heading: `# <title>`, and no id.
_DRAFT_HEADING = re.compile(r"#[ \t]+(?P<title>\S.*)")

# Every spelling of an existing ticket a draft's relation may name: `#<n>`, and
# `owner/project#n` for an issue of another repository. `?#n` is not among them:
# the export reader writes it where an export named no repository, and no person
# writes it into a draft.
_TICKET_ID = re.compile(r"(?:[A-Za-z0-9._-]+/[A-Za-z0-9._-]+)?#[0-9]+")

# A byte-order mark is a filesystem artefact and not content: one leading U+FEFF
# is dropped so a marked draft reads as the draft it is.
_BOM = "\ufeff"

_RELATION_KEYS: tuple[str, str] = ("blocked-by", "parent")
# The remedy for a heading that is an id.
_NO_ID = (
    "give a draft the heading `# <title>`: a draft's heading carries no id, which is "
    "assigned when the ticket is published"
)


class DraftError(EngineError):
    """A draft this module cannot even name: the message says what to pass instead."""


# --- files this module will not read -----------------------------------------------


def _absent(id: str, path: str) -> Message:
    return message(
        "TICKET_UNREADABLE",
        id,
        f"no file is at {path}, so there is no draft to lint there",
        "name a draft file this checkout holds; `--draft` takes the paths as they are typed",
    )


def _unreadable(id: str, path: str, error: Exception) -> Message:
    return message(
        "TICKET_UNREADABLE",
        id,
        f"{path} could not be read as UTF-8 text: {error}",
        "restore the file as UTF-8 text before it can be linted as a draft",
    )


def _first_line(text: str) -> tuple[str, int]:
    """The first line that is not blank, trimmed, and where that line ends.

    The offset is what the brief starts from, so the brief is never found by
    searching for a heading a second time.
    """

    offset = 0
    for line in text.split("\n"):
        stop = offset + len(line)
        if line.strip():
            return line.rstrip(), stop
        offset = stop + 1
    return "", 0


def _heading(id: str, path: str, text: str) -> tuple[str, int, list[Message]]:
    """The draft's title, where its heading line ends, and what is wrong with it.

    A heading that is only an id names no work: a draft's id is assigned when the
    ticket is published.
    """

    written, stop = _first_line(text)
    drafted = _DRAFT_HEADING.fullmatch(written)
    if drafted is None:
        headless = message(
            "VALUE_INVALID",
            id,
            f"{path} does not begin with the heading `# <title>` a draft opens with, so it "
            "carries no title",
            "give the file that heading; a draft's id is its file name and its title is its "
            "heading",
        )
        return "", 0, [headless]
    title = drafted.group("title").strip()
    if _TICKET_ID.fullmatch(title) is not None:
        refused = message(
            "VALUE_INVALID",
            id,
            f"{path} begins with the heading `# {title}`, which is an id and no title",
            _NO_ID,
        )
        return "", stop, [refused]
    return title, stop, []


# --- the seam ----------------------------------------------------------------------


def read_draft(
    path: Path | str, declaration: Declaration
) -> tuple[Ticket | None, tuple[Message, ...]]:
    """One local file as the normalised ticket a draft compiles to.

    The id is the file name without its extension; the state is open, and the
    effective hold the block's own value, whatever store is declared. The path
    is taken as given, not resolved against any checkout: a draft is not yet a
    file of any store. The ticket is None only where there is no ticket to talk
    about — the file is not there, or its bytes are not text. A draft may carry
    `blocked-by` and `parent` in its block, since it has no tracker to hold them
    yet.
    """

    given = Path(path)
    id = given.stem
    if not id:
        raise DraftError(
            f"{str(path)!r} carries no file name, so this draft has no id and nothing "
            "reported about it could be acted on; name a file, not a directory"
        )
    shown = given.as_posix()
    try:
        text = given.read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
        return None, (_absent(id, shown),)
    except (OSError, UnicodeDecodeError) as error:
        return None, (_unreadable(id, shown, error),)
    if text.startswith(_BOM):
        text = text[1:]
    title, stop, messages = _heading(id, shown, text)
    fields, block = parse_block(text)
    messages.extend(dataclasses.replace(item, ticket=id) for item in block)
    brief = text[stop : fields.begin if fields.begin >= 0 else len(text)].strip()
    ticket = Ticket(
        id=id,
        title=title,
        state=_OPEN,
        block_version=fields.version,
        path=shown,
        brief=brief,
        reads=fields.reads,
        bounds=fields.bounds,
        human_only=fields.human_only,
        hold=effective_hold(fields.human_only, (), declaration),
        done_when=fields.done_when,
        blocked_by=fields.blocked_by,
        parent=fields.parent,
        discovered_from=fields.discovered_from,
        waits_on=fields.waits_on,
        content=content_identity(title, brief, fields),
    )
    return ticket, tuple(messages)


def _duplicate(id: str, where: Sequence[str]) -> Message:
    return message(
        "ID_DUPLICATE",
        id,
        f"{id} is the name of {' and '.join(where)}; a draft's id is its file name, so "
        "two files of one name claim one id",
        "rename one of them, because a relation naming that id cannot say which is meant",
    )


def _refused(ticket: Ticket, key: str, entry: str) -> Message:
    return message(
        "VALUE_INVALID",
        ticket.id,
        f"{ticket.path} names {entry!r} in `{key}`, which is neither one of the drafts this "
        "run was given nor a ticket id",
        "name another draft by its file name without the extension, or an existing ticket by id",
    )


def _unchecked(ticket: Ticket, key: str, entry: str) -> Message:
    return message(
        "RELATION_UNCHECKED",
        ticket.id,
        f"{ticket.path} names the published ticket {entry} in `{key}`; not checked: a draft "
        "run reads no store, so nothing here says that it exists or is open",
        "run `check` on the store export once the drafts are published, where this relation "
        "resolves against the tickets the export holds",
    )


def _entries(ticket: Ticket) -> list[tuple[str, str]]:
    """One draft's relation entries, by key, in written order."""

    blocked, parent = _RELATION_KEYS
    written = [(blocked, entry) for entry in ticket.blocked_by]
    return written + ([(parent, ticket.parent)] if ticket.parent else [])


def draft_relations(tickets: Sequence[Ticket]) -> Mapping[str, tuple[Message, ...]]:
    """What the drafts given say about one another, by draft id.

    Two findings, in this order per id. An id two of the files claim is
    `ID_DUPLICATE` naming every one of them, because a draft's id is its file
    name and a relation naming that id cannot say which file it means. Then each
    draft's `blocked-by` and `parent` entries: one naming a draft of this same
    run is a relation, and one that is a well-formed ticket id is accepted and
    takes no part in anything here, because no store is read on a draft run and
    there is nothing to check it against; `RELATION_UNCHECKED` says so, at INFO,
    so a wrong number is not passed in silence. Anything else is refused by name.

    Only the ids given are relations, so a caller that keeps one draft per id
    still reads one graph; what a relation then closes is `tickets_graph`'s.
    """

    given = {ticket.id for ticket in tickets}
    where: dict[str, list[str]] = {}
    for ticket in tickets:
        where.setdefault(ticket.id, []).append(ticket.path)
    found: dict[str, list[Message]] = {
        id: [_duplicate(id, sorted(paths))] for id, paths in where.items() if len(paths) > 1
    }
    for ticket in tickets:
        said = [
            _refused(ticket, key, entry)
            if _TICKET_ID.fullmatch(entry) is None
            else _unchecked(ticket, key, entry)
            for key, entry in _entries(ticket)
            if entry not in given
        ]
        if said:
            found.setdefault(ticket.id, []).extend(said)
    return MappingProxyType({id: tuple(messages) for id, messages in found.items()})


# --- what every draft repeats ------------------------------------------------------

# A Markdown heading line: it opens a section and is no paragraph.
_HEADING_LINE = re.compile(r"#{1,6}[ \t]+\S.*")
# The template a draft is written from; its own text is a placeholder, not guidance.
_TEMPLATE = ROOT / "templates/tickets/issue-template.md"
# How much of a repeated paragraph a message shows: enough to find it, not a measure.
_SHOWN_WORDS = 8


def _paragraphs(text: str) -> list[tuple[str, str]]:
    """Each paragraph of `text` with the heading it sits under, whitespace normalised.

    A paragraph is the lines between blank lines; a heading line ends one and is
    not part of any. A paragraph with no letter or digit, a rule or a lone fence,
    says nothing and is not returned.
    """

    found: list[tuple[str, str]] = []
    heading = ""
    lines: list[str] = []

    def close() -> None:
        joined = " ".join(" ".join(lines).split())
        if any(character.isalnum() for character in joined):
            found.append((heading, joined))
        lines.clear()

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            close()
        elif _HEADING_LINE.fullmatch(stripped):
            close()
            heading = stripped
        else:
            lines.append(stripped)
    close()
    return found


@functools.cache
def _placeholders() -> frozenset[str]:
    """The issue template's own paragraphs, split as a draft's are.

    A draft written from the template and left with its comment or a section's
    placeholder text repeats that text in every draft; that is the template's
    text, which no slicer chose to repeat. A template this engine cannot read
    leaves nothing to exclude.
    """

    try:
        text = _TEMPLATE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return frozenset()
    return frozenset(paragraph for _, paragraph in _paragraphs(text))


def _repeated(paragraph: str, headings: Sequence[str], drafts: int) -> Message:
    words = paragraph.split()
    shown = " ".join(words[:_SHOWN_WORDS]) + (" ..." if len(words) > _SHOWN_WORDS else "")
    where = " and ".join(f"`{heading}`" for heading in headings) or "no heading"
    return message(
        "REPEATED_GUIDANCE",
        "",
        f'the paragraph "{shown}" under {where} is in each of the {drafts} drafts given, '
        "word for word",
        "drop it from the drafts: guidance every ticket would repeat is said once, in the "
        "tickets fragment or the project's own instructions, and a paragraph that carries no "
        "decision is not written",
    )


def repeated_guidance(tickets: Sequence[Ticket]) -> tuple[Message, ...]:
    """One warning for each paragraph every draft's brief holds, about the run.

    Only a breakdown of two or more drafts is asked, and the condition is "in every
    draft": no count of drafts and no length of a paragraph enters it. The block
    is not part of a brief and a heading is no paragraph, so neither is compared.
    A paragraph of the issue template itself is its placeholder text and is passed
    over. Each paragraph is said once, in the order the first draft holds them,
    naming every heading it sits under across the drafts.
    """

    if len(tickets) < 2:
        return ()
    placeholders = _placeholders()
    read = [_paragraphs(ticket.brief) for ticket in tickets]
    held = [{paragraph for _, paragraph in found} for found in read]
    said: list[Message] = []
    for paragraph in dict.fromkeys(paragraph for _, paragraph in read[0]):
        if paragraph in placeholders or not all(paragraph in each for each in held):
            continue
        headings = dict.fromkeys(
            heading for found in read for heading, text in found if text == paragraph
        )
        said.append(_repeated(paragraph, [heading for heading in headings if heading], len(read)))
    return tuple(said)
