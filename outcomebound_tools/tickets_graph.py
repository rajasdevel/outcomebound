"""The waiting graph and its knots.

What this module decides: which tickets stand in a knot of the waiting graph.

**It reads relations, and nothing else.** No declaration and no store:
it is given the tickets a reader read and answers from their ids and the two
relations alone. The import test beside it pins that.

What it does not decide: what a knot means — `check` reads one as an error, and
nothing here emits `DEPENDENCY_CYCLE` — or what a ticket is, which is the
readers'. It opens no file, runs no subprocess and writes nothing.

**Waiting runs from a ticket to each of its blockers and from a parent to each
of its children**, so a child blocked by its own parent is a knot of two, and so
is a pair of tickets each the other's parent; `discovered-from` is no edge.

**Data structures, and why these.** `_waiting_edges`, the successor lists of the
waiting graph, built in one pass and linear in tickets plus relations. Knots are
that graph's strongly connected components, found by Tarjan's algorithm driven
from an explicit stack, so a chain deeper than the interpreter's recursion limit
still walks and no pair of tickets is ever compared; members are then ordered by
input position and the knots by their first member's, so what is reported is
decided by the input and not by the order the traversal took. Enumerating simple
cycles was rejected: it reports one knot many times over and is exponential on a
graph nobody has bounded.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from outcomebound_tools.tickets_model import Ticket

__all__ = ["cycles"]


# --- knots in the waiting graph ---------------------------------------------------


def _waiting_edges(tickets: Sequence[Ticket]) -> dict[str, list[str]]:
    """The waiting graph over tickets alone: a ticket to each blocker, a parent to
    each child.

    An id no ticket carries is no edge, so an issue outside the gate closes no
    knot: nothing it relates to is a relation this graph can follow back.
    """

    edges: dict[str, list[str]] = {ticket.id: [] for ticket in tickets}
    for ticket in tickets:
        edges[ticket.id].extend(blocker for blocker in ticket.blocked_by if blocker in edges)
        if ticket.parent in edges:
            edges[ticket.parent].append(ticket.id)
    return edges


@dataclass(slots=True)
class _Tarjan:
    """The working memory of one strongly-connected-component walk.

    Mutable and private, because it is an algorithm's scratch state and lives
    for one call: `cycles` builds one, reads `components()` and drops it. The
    recursion is the explicit work list of `_walk`, so a hundred-deep chain
    costs a hundred tuples and no interpreter frames.
    """

    edges: Mapping[str, Sequence[str]]
    index: dict[str, int] = field(default_factory=dict)
    low: dict[str, int] = field(default_factory=dict)
    on_stack: set[str] = field(default_factory=set)
    stack: list[str] = field(default_factory=list)
    found: list[list[str]] = field(default_factory=list)

    def components(self) -> list[list[str]]:
        """Every component, each node visited once, in the order the walks closed them."""

        for start in self.edges:
            if start not in self.index:
                self._walk(start)
        return self.found

    def _walk(self, start: str) -> None:
        """One depth-first walk: each frame is a node and how far it has been read."""

        work: list[tuple[str, int]] = [(start, 0)]
        while work:
            node, position = work[-1]
            if position == 0:
                self._enter(node)
            position, descend = self._advance(node, position)
            work[-1] = (node, position)
            if descend:
                work.append((descend, 0))
                continue
            if self.low[node] == self.index[node]:
                self.found.append(self._pop(node))
            work.pop()
            if work:
                above = work[-1][0]
                self.low[above] = min(self.low[above], self.low[node])

    def _enter(self, node: str) -> None:
        self.index[node] = self.low[node] = len(self.index)
        self.stack.append(node)
        self.on_stack.add(node)

    def _advance(self, node: str, position: int) -> tuple[int, str]:
        """Read successors from `position` on: the next unvisited one, or none.

        A successor already on the stack lowers this node's link instead, which
        is what makes a component out of a path that returns to where it began.
        """

        successors = self.edges[node]
        while position < len(successors):
            successor = successors[position]
            position += 1
            if successor not in self.index:
                return position, successor
            if successor in self.on_stack:
                self.low[node] = min(self.low[node], self.index[successor])
        return position, ""

    def _pop(self, root: str) -> list[str]:
        """Everything above `root` on the stack, and `root`: one component."""

        component: list[str] = []
        while True:
            popped = self.stack.pop()
            self.on_stack.discard(popped)
            component.append(popped)
            if popped == root:
                return component


def cycles(tickets: Sequence[Ticket]) -> tuple[tuple[str, ...], ...]:
    """Every knot in the waiting graph, each reported once.

    A knot is a strongly connected component of two or more tickets, or one
    ticket with an edge to itself — a ticket that blocks itself, or is its own
    parent. Members come back in input order and the knots in the order of their
    first members, so one input renders one way however the traversal ran. What
    a knot means is `check`'s: every ticket in one reads ERROR
    `DEPENDENCY_CYCLE` there.
    """

    order = {ticket.id: position for position, ticket in enumerate(tickets)}
    edges = _waiting_edges(tickets)
    knots = [
        tuple(sorted(component, key=order.__getitem__))
        for component in _Tarjan(edges).components()
        if len(component) > 1 or component[0] in edges[component[0]]
    ]
    return tuple(sorted(knots, key=lambda knot: order[knot[0]]))
