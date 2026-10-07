"""`satisfies`: which requirements of a design a ticket answers to, and which an epic leaves.

What this module decides: which requirement ids a design file holds (the lines of its
`## Requirements` section that start `R<n>`, as `sources_ledger` reads them), which of
them the design marks `[excluded]` or `[deferred]`, when a ticket names an id the
design it reads does not hold (`REQUIREMENT_UNKNOWN`), and when an epic over a design
leaves an active requirement that no child satisfies (`REQUIREMENT_UNCOVERED`).

What it does not decide: whether a ticket's work meets a requirement it names. A ticket
that lists every id passes both checks, and this module cannot tell it from one that
meets them all. It reads the working tree, builds messages only, and writes nothing.
A run whose tickets carry no `satisfies` has no coverage check.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from outcomebound_tools import paths, textio
from outcomebound_tools.sources_ledger import parse
from outcomebound_tools.tickets_model import Ticket
from outcomebound_tools.tickets_report import Message, message

__all__ = ["Requirements"]

# A requirement line the design sets aside: no child is asked to satisfy it.
_SET_ASIDE = re.compile(r"\[(?:excluded|deferred)\]", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class _Design:
    """The requirement ids one design file defines, and the ones it sets aside."""

    ids: frozenset[str]
    active: tuple[str, ...]


class Requirements:
    """What the tickets of one run say about the requirements of the designs they read.

    Each design file is read once however many tickets cite it. Built once for a run.
    """

    def __init__(self, target: Path | str, tickets: Sequence[Ticket]) -> None:
        self._target = target
        self._tickets = tuple(tickets)
        self._designs: dict[str, _Design | None] = {}

    def _design(self, path: str) -> _Design | None:
        """The design `path` names, or None where it is no readable markdown file."""

        if path not in self._designs:
            self._designs[path] = self._read(path)
        return self._designs[path]

    def _read(self, path: str) -> _Design | None:
        if not path.endswith(".md"):
            return None
        try:
            text = textio.decode(paths.resolve_bounded(self._target, path).read_bytes())
        except (OSError, UnicodeDecodeError, paths.PathError):
            return None
        text = text.replace("\r\n", "\n")
        held = parse(text).requirements
        lines = text.split("\n")
        active = tuple(
            identifier
            for identifier, number in held.items()
            if _SET_ASIDE.search(lines[number - 1]) is None
        )
        return _Design(frozenset(held), active)

    @staticmethod
    def _reads(ticket: Ticket) -> tuple[str, ...]:
        return tuple(dict.fromkeys(entry.path for entry in ticket.reads))

    def unknown(self, ticket: Ticket) -> Iterator[Message]:
        """Each requirement id the ticket names that no design it reads holds."""

        if not ticket.satisfies:
            return
        reads = self._reads(ticket)
        held: set[str] = set()
        for path in reads:
            design = self._design(path)
            if design is not None:
                held |= design.ids
        absent = [identifier for identifier in ticket.satisfies if identifier not in held]
        if not absent:
            return
        named = ", ".join(absent)
        where = (
            f"the design(s) it reads ({', '.join(reads)}) hold none of them"
            if any(self._design(path) is not None for path in reads)
            else "it reads no design that holds a requirement"
        )
        yield message(
            "REQUIREMENT_UNKNOWN",
            ticket.id,
            f"{ticket.id} satisfies {named}, and {where}",
            "name an id from the `## Requirements` section of a design this ticket's `reads` "
            "names, or add that design to `reads`, or correct the id",
        )

    def uncovered(self, ticket: Ticket) -> Iterator[Message]:
        """The active requirements of each design an epic reads that no child satisfies.

        An epic is a ticket that has a child in the run, open or closed; a dropped
        child is no child, and covers nothing. An id the epic
        names itself counts as covered: it says an existing ticket already covers it.
        Nothing is asked of a run whose tickets carry no `satisfies`.
        """

        children = [
            other
            for other in self._tickets
            if other.parent == ticket.id and other.state != "dropped"
        ]
        if not children or not any(other.satisfies for other in self._tickets):
            return
        satisfied = self._covering(ticket, children)
        for path in self._reads(ticket):
            design = self._design(path)
            if design is None:
                continue
            missing = [i for i in design.active if (path, i) not in satisfied]
            if not missing:
                continue
            yield message(
                "REQUIREMENT_UNCOVERED",
                ticket.id,
                f"{ticket.id} is an epic over {path}, and no child satisfies its active "
                f"requirement(s) {', '.join(missing)}",
                "name each in a child's `satisfies`, or mark its line `[deferred]` or "
                "`[excluded]` in the design, or list it in this epic's own `satisfies` where "
                "an existing ticket already covers it",
            )

    def _covering(self, epic: Ticket, children: Sequence[Ticket]) -> set[tuple[str, str]]:
        found: set[tuple[str, str]] = set()
        for ticket in (epic, *children):
            for path in self._reads(ticket):
                design = self._design(path)
                if design is not None:
                    found.update((path, i) for i in ticket.satisfies if i in design.ids)
        return found
