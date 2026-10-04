"""The waiting graph and its knots.

Everything here is driven over normalised tickets built in this file, because a
`Ticket` is what every reader hands a verb and no one store can
spell every relation this module reads. Nothing opens a store, a subprocess or a
network connection, because the module under test reads relations and nothing
else — which the import test at the foot of this file pins.
"""

from __future__ import annotations

import ast
import importlib
import sys
from collections.abc import Sequence
from pathlib import Path

from outcomebound_tools.tickets_graph import cycles
from outcomebound_tools.tickets_model import Ticket

# --- tickets built here -----------------------------------------------------------


def ticket(id: str, *, blocked_by: Sequence[str] = (), parent: str = "") -> Ticket:
    """One normalised ticket, with only the fields this module reads spelled out."""

    return Ticket(id=id, title=f"Ticket {id}", blocked_by=tuple(blocked_by), parent=parent)


def shuffle(tickets: Sequence[Ticket], *positions: int) -> list[Ticket]:
    """The tickets in a fixed order that is not their own: a shuffle a run can repeat."""

    assert sorted(positions) == list(range(len(tickets))), "a shuffle keeps every ticket"
    return [tickets[position] for position in positions]


# --- knots ------------------------------------------------------------------------


def test_cycles_are_components_reported_once() -> None:
    """A knot through both relations is one component, named once, with every member."""

    tickets = [
        ticket("T-1", blocked_by=["T-2"]),
        ticket("T-2"),
        ticket("T-3", parent="T-2", blocked_by=["T-1"]),
    ]
    assert cycles(tickets) == (("T-1", "T-2", "T-3"),)


def test_self_block_is_a_cycle() -> None:
    """A ticket that names itself among its blockers, or as its parent, is a knot of one."""

    assert cycles([ticket("T-1", blocked_by=["T-1"])]) == (("T-1",),)
    assert cycles([ticket("T-1", parent="T-1")]) == (("T-1",),)
    assert cycles([ticket("T-1")]) == ()


def test_a_child_blocked_by_its_parent_is_a_cycle() -> None:
    """The edge leaves the parent, so a child blocked by its own parent is a knot of two.

    The same fixture holds an ordinary parent and child, which is no knot at all.
    """

    tickets = [
        ticket("T-1"),
        ticket("T-2", parent="T-1", blocked_by=["T-1"]),
        ticket("T-3", parent="T-1"),
    ]
    assert cycles(tickets) == (("T-1", "T-2"),)


def test_each_the_others_parent_is_a_cycle() -> None:
    """Two tickets, two `parent` keys and no blocker at all: still a knot of two."""

    assert cycles([ticket("T-1", parent="T-2"), ticket("T-2", parent="T-1")]) == (("T-1", "T-2"),)


def test_cycle_order_is_the_input_order() -> None:
    """Members and knots come back by input position, and the knots themselves are
    whatever order the input arrived in."""

    knot = [
        ticket("T-3", blocked_by=["T-4"]),
        ticket("T-4", blocked_by=["T-3"]),
        ticket("T-1", blocked_by=["T-2"]),
        ticket("T-2", blocked_by=["T-1"]),
    ]
    assert cycles(knot) == (("T-3", "T-4"), ("T-1", "T-2")), "not by id, and not by traversal"
    assert cycles(list(reversed(knot))) == (("T-2", "T-1"), ("T-4", "T-3"))

    shuffled = shuffle(knot, 2, 0, 3, 1)
    assert {frozenset(found) for found in cycles(shuffled)} == {
        frozenset({"T-1", "T-2"}),
        frozenset({"T-3", "T-4"}),
    }


def test_a_long_chain_has_no_cycle_and_no_recursion_limit() -> None:
    """One parent chain longer than the interpreter's own recursion limit: no knot,
    and nothing that walks it one frame at a time could get this far."""

    depth = sys.getrecursionlimit() * 3
    chain = [ticket("T-1"), *(ticket(f"T-{n}", parent=f"T-{n - 1}") for n in range(2, depth + 1))]

    assert cycles(chain) == ()


# --- the seam this file is held to -------------------------------------------------


def test_the_graph_reaches_relations_only() -> None:
    """This module reads relations and nothing else — no record, no declaration,
    no store."""

    source = Path(importlib.import_module("outcomebound_tools.tickets_graph").__file__ or "")
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    reached: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            reached.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            reached.add(node.module)
            if node.module == "outcomebound_tools":
                reached.update(f"outcomebound_tools.{alias.name}" for alias in node.names)

    engine = {name for name in reached if name.startswith("outcomebound_tools.")}
    assert engine == {"outcomebound_tools.tickets_model"}, sorted(engine)


def test_tests_import_only_public_names() -> None:
    """Every name this file takes from the engine is one its module declares."""

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=__file__)
    reached = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        if not node.module.startswith("outcomebound_tools.tickets"):
            continue
        public = set(importlib.import_module(node.module).__all__)
        for alias in node.names:
            reached += 1
            assert alias.name in public, f"{node.module}.{alias.name} is not in __all__"
    assert reached == 2, "this file imports exactly the seam it tests"
