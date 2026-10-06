"""The ledger `outcomebound sources check` reads: the `## Sources` section of the file where the
requirements live, and the requirement ids that file defines in its `## Requirements` section
(`docs/specs/sources/design.md`).

What this module decides: the ledger's table (Source item, Disposition, Where, Basis), what a
row may say, and where a requirement id is defined (a line of `## Requirements` that starts with
`R<n>`, after an optional list marker or table bar or bold marks).

What it does not decide: whether a row is true. Standard library only.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

DISPOSITIONS = (
    "carried",
    "dropped (assumed)",
    "dropped (decided)",
    "not requirement-bearing",
    "deferred",
    "todo",
)
_HEADING_SOURCES = re.compile(r"##[ \t]+Sources[ \t]*")
_HEADING_REQUIREMENTS = re.compile(r"##[ \t]+Requirements[ \t]*")
_H2 = re.compile(r"##[ \t]+\S")
_FENCE = re.compile(r"[ ]{0,3}(`{3,}|~{3,})")
_REQUIREMENT = re.compile(r"[ \t]*(?:[-*+][ \t]+|\|[ \t]*)?(?:\*\*|__)?(R\d+)\b")
_REQUIREMENT_ID = re.compile(r"R\d+")
_ASSUMED = re.compile(r"\[assumed\]", re.IGNORECASE)
_SOURCE_CELL = re.compile(
    r"`?(?P<first>[a-z0-9][a-z0-9:-]*?)(?:\.\.(?P<last>[a-z0-9][a-z0-9:-]*))?`?"
    r"[ \t]+#(?P<revision>[0-9a-f]{8,64})"
)
_QUOTE = re.compile(r'"([^"]+)"|“([^”]+)”')


@dataclass
class Row:
    line: int
    cell: str
    first: str = ""
    last: str | None = None
    revision: str = ""
    disposition: str = ""
    where: list[str] = field(default_factory=list)
    where_text: str = ""
    basis: str = ""
    problem: str | None = None

    def quotes(self) -> list[str]:
        return [a or b for a, b in _QUOTE.findall(self.basis)]


@dataclass
class Ledger:
    present: bool
    rows: list[Row]
    requirements: dict[str, int]
    duplicate_requirements: list[tuple[str, int]]
    assumed: set[str]


def _cells(line: str) -> list[str]:
    """The cells of one table row, split at each `|` a backslash does not escape."""

    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
    cells = re.split(r"(?<!\\)\|", body)
    return [cell.replace("\\|", "|").strip() for cell in cells]


def _row(line_number: int, line: str) -> Row | None:
    cells = _cells(line)
    if all(set(cell) <= set("-: ") for cell in cells):
        return None
    if cells and cells[0].lower().startswith("source item"):
        return None
    row = Row(line_number, cells[0] if cells else "")
    if len(cells) != 4:
        row.problem = (
            f"has {len(cells)} cells, not the four of Source item, Disposition, Where, Basis"
        )
        return row
    source, disposition, where, basis = cells
    row.disposition, row.where_text, row.basis = disposition.lower(), where, basis
    row.where = _REQUIREMENT_ID.findall(where)
    matched = _SOURCE_CELL.fullmatch(source)
    if matched is None:
        row.problem = (
            "its Source item is not `<id>` or `<first id>..<last id>`, then ` #<revision>`"
        )
        return row
    row.first, row.last = matched["first"], matched["last"]
    row.revision = matched["revision"]
    if row.disposition not in DISPOSITIONS:
        row.problem = f"its Disposition is none of {', '.join(DISPOSITIONS[:-1])}"
    return row


def _unfenced(text: str) -> Iterator[tuple[int, str]]:
    """(line number, line) for each line of `text` outside a fenced block."""

    fence: str | None = None
    for number, line in enumerate(text.split("\n"), 1):
        opening = _FENCE.match(line)
        if fence is None:
            if opening:
                fence = opening.group(1)
            else:
                yield number, line
        elif opening and opening.group(1)[0] == fence[0] and len(opening.group(1)) >= len(fence):
            fence = None


def _section_of(line: str) -> str | None:
    """The section a level-two heading opens: `sources`, `requirements`, or None for another."""

    if _HEADING_SOURCES.fullmatch(line):
        return "sources"
    return "requirements" if _HEADING_REQUIREMENTS.fullmatch(line) else None


def parse(text: str) -> Ledger:
    """The ledger and the requirement ids `text` holds."""

    section: str | None = None
    ledger = Ledger(False, [], {}, [], set())
    for number, line in _unfenced(text):
        if _H2.match(line):
            section = _section_of(line)
            ledger.present = ledger.present or section == "sources"
        elif section == "sources" and line.lstrip().startswith("|"):
            row = _row(number, line)
            if row is not None:
                ledger.rows.append(row)
        elif section == "requirements":
            _requirement(ledger, number, line)
    return ledger


def _requirement(ledger: Ledger, number: int, line: str) -> None:
    found = _REQUIREMENT.match(line)
    if not found:
        return
    identifier = found.group(1)
    if identifier in ledger.requirements:
        ledger.duplicate_requirements.append((identifier, number))
    else:
        ledger.requirements[identifier] = number
    if _ASSUMED.search(line):
        ledger.assumed.add(identifier)


def skeleton(items: Sequence[tuple[str, str]]) -> str:
    """A ledger section with one `todo` row per (id, revision), for the agent to complete."""

    lines = [
        "## Sources",
        "",
        "| Source item | Disposition | Where | Basis |",
        "| --- | --- | --- | --- |",
    ]
    lines += [f"| {identifier} #{revision} | todo | | |" for identifier, revision in items]
    return "\n".join(lines) + "\n"
