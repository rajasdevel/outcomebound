"""The `check` verb: one ordered pass over what the readers and the links already say.

What this module decides: which tickets are judged — the open ones, and every
draft — the order in which one ticket is judged and where that pass stops, when
a body is too thin to be a brief, what a `reads` entry that will not resolve
reads, what a claim the plan does not define reads, what a claim that declares
it needs a path outside the ticket's `bounds` reads, and what is said about a
knot of the waiting graph, about a `discovered-from` the input does not hold,
and about a ticket whose work waits on a person's decision brief.
A closed or dropped ticket's links are history and are not resolved: it is read,
so that a relation naming it resolves, and it is not judged.

What it does not decide: anything a reader read. Every block message is carried
from the store reader unchanged and never re-derived, so one fact is reported
once. Nor what a draft is (`tickets_draft`), what a section is (`tickets_links`),
what a claim is (`tickets_claims`), what a knot is (`tickets_graph`), or what a
message does to a verdict (`tickets_report`). It prints nothing, exits nothing,
writes nothing and asks git nothing.

**The pass order is what makes the count honest.** One ticket is read in one
fixed order — the reader's own messages, the brief, the links, the claims, the
relations, the waits — and a block whose version this engine never shipped ends the pass
before any of the rest. **A draft goes down that same pass.** `--draft` reads
each local file through `tickets_draft` and judges the tickets it hands back
exactly as it judges a store's, and such a run reads no store at all.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from outcomebound_tools.tickets_bounds import covers
from outcomebound_tools.tickets_claims import ClaimsPlan, load_claims, placement
from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_draft import draft_relations, read_draft
from outcomebound_tools.tickets_graph import cycles
from outcomebound_tools.tickets_links import LinksError, section
from outcomebound_tools.tickets_model import (
    BLOCK_VERSIONS,
    HOLDS,
    STATES,
    InputInfo,
    ReadResult,
    Ticket,
)
from outcomebound_tools.tickets_report import (
    Counts,
    Message,
    Report,
    TicketResult,
    message,
)
from outcomebound_tools.tickets_store import read_store

__all__ = ["check", "check_loaded"]

_VERB = "check"

# The three states and the weakest hold, taken from the model so that this
# module never respells one.
_OPEN, _CLOSED, _DROPPED = STATES
_FREE = HOLDS[-1]

# The template's headings, in its order. A body carrying none of them says nothing
# a brief is meant to say, whatever its size — and no size is judged. `## Tests`, which
# the template does not carry, still counts, so a ticket written with it is not warned about.
_BRIEF_HEADINGS: tuple[str, ...] = ("## Outcome", "## Design", "## Tests", "## Limits")


# --- every section this run reads, read once ---------------------------------------


@dataclass(slots=True)
class _Sections:
    """The sections one run resolves, each read once however many tickets cite it.

    Mutable and private: it is one run's memory and lives for one call.
    """

    target: Path
    refused: dict[tuple[str, str], LinksError | None] = field(default_factory=dict)

    def refusal(self, path: str, anchor: str) -> LinksError | None:
        """Why `path#anchor` names no one section, or None where it names one."""

        key = (path, anchor)
        if key not in self.refused:
            try:
                section(self.target, path, anchor)
                self.refused[key] = None
            except LinksError as refused:
                self.refused[key] = refused
        return self.refused[key]


# --- what this run was given -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Input:
    """One run's subjects, whatever they were read from.

    `reported` is what a reader said about a ticket this run judges; `run_level`
    is what it said about anything else — a message stamped with an id no ticket
    carries has no row to sit on and is the run's. `known` is every id the
    input holds, tickets and issues alike, which `discovered-from` resolves
    against.
    """

    tickets: tuple[Ticket, ...] = ()
    known: frozenset[str] = frozenset()
    reported: Mapping[str, tuple[Message, ...]] = field(default_factory=dict)
    run_level: tuple[Message, ...] = ()
    relations: Mapping[str, tuple[Message, ...]] = field(default_factory=dict)
    source: InputInfo | None = None
    ignored: int = 0


def _stamped(
    messages: Sequence[Message], tickets: Sequence[Ticket]
) -> tuple[Mapping[str, tuple[Message, ...]], tuple[Message, ...]]:
    """A reader's messages by the ticket each was stamped with, and the rest.

    Indexed once, in the reader's own order, and a message stamped with an id no
    ticket carries stays visible as the run's rather than being dropped.
    """

    ids = {ticket.id for ticket in tickets}
    index: dict[str, list[Message]] = {}
    run: list[Message] = []
    for item in messages:
        if item.ticket in ids:
            index.setdefault(item.ticket, []).append(item)
        else:
            run.append(item)
    return MappingProxyType({key: tuple(value) for key, value in index.items()}), tuple(run)


def _from_read(read: ReadResult) -> _Input:
    """Every ticket a store reader handed back, indexed for this pass.

    It takes the reading rather than doing it, because a caller that has
    already read the store — `brief`, which needs the ticket it compiles —
    hands over what it read: an export on standard input is a stream, and the
    second reader of one finds it empty.
    """

    reported, run_level = _stamped(read.messages, read.tickets)
    return _Input(
        tickets=read.tickets,
        known=frozenset({ticket.id for ticket in read.tickets} | set(read.others)),
        reported=reported,
        run_level=run_level,
        source=read.input,
        ignored=read.ignored,
    )


def _from_drafts(paths: Sequence[str], declaration: Declaration) -> _Input:
    """The drafts this run was given, read through `tickets_draft` and linted together.

    Every file named is read, and `draft_relations` is asked about all of them,
    so an id two files claim is reported. Only the first draft of each id
    is then judged, which is the promise both store readers make: an index by id
    is total, and the knot detector reads one graph.
    """

    read = [read_draft(given, declaration) for given in paths]
    messages = [item for _, found in read for item in found]
    every = [ticket for ticket, _ in read if ticket is not None]
    relations = draft_relations(every)
    judged: list[Ticket] = []
    seen: set[str] = set()
    for ticket in every:
        if ticket.id not in seen:
            seen.add(ticket.id)
            judged.append(ticket)
    tickets = tuple(judged)
    reported, run_level = _stamped(messages, tickets)
    return _Input(
        tickets=tickets,
        known=frozenset(seen),
        reported=reported,
        run_level=run_level,
        relations=relations,
    )


# --- the brief ---------------------------------------------------------------------


def _brief_messages(ticket: Ticket) -> Iterator[Message]:
    """A ticket nobody holds says what the work is, under the brief's headings.

    The engine parses none of the brief and judges no size: what is warned about
    is a body that is empty, or carries none of the template's headings — a ticket
    whose decision was never written down. A ticket whose effective hold is not
    `no` is a person's to write and is not warned about.

    The scan is a plain line scan, not a fence-aware one, so a heading inside a
    code fence counts as a heading. The failure that leaves is a warning not
    raised about a body that does say what the work is, never one raised about a
    body that does not.
    """

    if ticket.hold != _FREE:
        return
    written = [line.rstrip() for line in ticket.brief.split("\n")]
    if ticket.brief.strip() and any(line in _BRIEF_HEADINGS for line in written):
        return
    yield message(
        "BRIEF_THIN",
        ticket.id,
        f"the body of {ticket.id} is empty or carries none of the headings "
        f"{', '.join(_BRIEF_HEADINGS)}, so nothing in it says what the work is",
        "write at least `## Outcome`, one sentence saying what becomes true",
    )


# --- links -------------------------------------------------------------------------


def _reads_messages(ticket: Ticket, sections: _Sections) -> Iterator[Message]:
    """Each `reads` entry resolved to one section."""

    for entry in ticket.reads:
        refused = sections.refusal(entry.path, entry.anchor)
        if refused is not None:
            yield message(
                refused.code,
                ticket.id,
                f"{ticket.id} reads {entry.cited()}, which resolves to no one section: {refused}",
            )


# --- claims ------------------------------------------------------------------------


def _claim_messages(ticket: Ticket, plan: ClaimsPlan) -> Iterator[Message]:
    """Each claim the plan does not define, in the ticket's declared order.

    A person's check is no claim of the plan and is passed over. No text from a
    ticket is executed here or anywhere.
    """

    for item in ticket.done_when:
        if item.human or item.claim in plan.claims:
            continue
        yield message(
            "CLAIM_PLANNED",
            ticket.id,
            f"{ticket.id} is open and its `done-when` names the claim `{item.claim}`, which "
            f"{plan.path} does not define; the ticket's own work may add it",
            f"define `{item.claim}` in the plan as part of this ticket's work",
        )


def _reach_messages(ticket: Ticket, plan: ClaimsPlan) -> Iterator[Message]:
    """Each defined claim that declares it needs a path the ticket's `bounds` do not cover.

    Decided only where the plan makes it decidable: from a claim's
    `required_paths`. A claim that declares none says nothing about what its
    command reads, and nothing is said about it. A path outside the checkout is
    covered by no entry.
    """

    for item in ticket.done_when:
        definition = None if item.human else plan.claims.get(item.claim)
        if definition is None:
            continue
        outside = list(
            dict.fromkeys(
                "a path outside the checkout" if path is None else path
                for path in definition.required_paths
                if path is None or not any(covers(entry, path) for entry in ticket.bounds)
            )
        )
        if not outside:
            continue
        yield message(
            "CLAIM_READS_OUTSIDE_BOUNDS",
            ticket.id,
            f"the claim `{item.claim}` of {ticket.id} declares in {plan.path} that it reads "
            f"{', '.join(outside)}, which the ticket's `bounds` do not cover, so a finding "
            "there is one this ticket's work may not repair",
            "widen `bounds` to cover what the claim reads, or put a ticket that repairs it "
            "first in `blocked-by`",
        )


def _cwd_messages(plan: ClaimsPlan, target: Path) -> tuple[Message, ...]:
    """A plan whose working directory resolves outside the checkout.

    It is a fact about the run and not about any ticket, so it is stamped with no
    id. `cwd_inside` is decided once, at load, and read here rather than
    re-derived.
    """

    if plan.cwd_inside:
        return ()
    return (
        message(
            "CLAIM_CWD_OUTSIDE",
            "",
            f"the claims plan {plan.path} names the working directory {plan.cwd_resolved}, "
            f"which resolves outside the checkout {target.resolve()}",
            "point the plan's cwd inside the checkout, because this engine runs a claim "
            "nowhere else; a relative cwd starts at the plan file's folder, as "
            "`outcomebound validation` reads it",
        ),
    )


def _placement_messages(plan: ClaimsPlan, target: Path) -> Iterator[Message]:
    """What shows that the plan's claims would run in a folder it was not written for.

    `CLAIM_PATH_ABSENT` for each claim that declares a required path the checkout
    does not hold from the plan's working directory but holds from the checkout root,
    since a run of that claim reads `UNVERIFIED` there; `CLAIM_CWD_PLAN_FOLDER`
    where the claims would run in the plan file's own folder below the checkout root,
    which a plan whose claims declare no paths shows in no other way. A path absent
    from both is planned, and nothing is said of it: the claim's own run reads
    `UNVERIFIED`, naming the path, until a ticket's work adds it. Both are facts
    about the plan and not about a ticket, so they are stamped with no id; both are
    warnings, because a plan may mean its own folder. `placement` decides both, the
    answer `adopt` reports too.
    """

    found = placement(plan, target)
    for name, moved in found.moved.items():
        yield message(
            "CLAIM_PATH_ABSENT",
            "",
            f"the claim `{name}` in {plan.path} declares {', '.join(moved)}, resolved from "
            f"its working directory {plan.cwd_resolved}, and the checkout holds none of "
            "them there, but holds each from the checkout root",
            f'write "cwd": "{found.to_root}" in the plan to run its claims at the checkout '
            "root (a relative cwd starts at the plan file's folder), or add the path where "
            "the claim runs",
        )
    if found.at_plan_folder:
        yield message(
            "CLAIM_CWD_PLAN_FOLDER",
            "",
            f"the claims plan {plan.path} runs its claims in {plan.cwd_resolved}, the plan "
            "file's own folder and not the checkout root; a plan with no cwd, or with "
            '"cwd": ".", runs them there, since a relative cwd starts at the plan file\'s folder',
            f'write "cwd": "{found.to_root}" in the plan to run its claims at the checkout root',
        )


# --- relations ---------------------------------------------------------------------


def _relation_messages(
    ticket: Ticket, given: _Input, knots: Mapping[str, tuple[str, ...]]
) -> Iterator[Message]:
    """What this ticket's relations resolve to, and whether they close a knot.

    A draft's refused entries come first, because an entry naming nothing is why
    the graph reads as it does. `discovered-from` is no edge of any graph and no
    verdict depends on it, so it is asked apart from the knot.
    """

    yield from given.relations.get(ticket.id, ())
    if ticket.discovered_from == ticket.id:
        yield message(
            "VALUE_INVALID",
            ticket.id,
            f"{ticket.id} names itself in `discovered-from`; a ticket is found during other "
            "work, never during its own",
            "name the ticket or issue during which this one was found, or drop the key",
        )
    elif ticket.discovered_from and ticket.discovered_from not in given.known:
        yield message(
            "DISCOVERED_FROM_ABSENT",
            ticket.id,
            f"{ticket.id} was discovered from {ticket.discovered_from}, which this input "
            "does not hold",
            "read the store again if it is an issue of this repository, and otherwise "
            "correct the key; no verdict depends on it",
        )
    knot = knots.get(ticket.id)
    if knot is not None:
        yield message(
            "DEPENDENCY_CYCLE",
            ticket.id,
            f"the waiting graph holds a cycle among {', '.join(knot)}, and {ticket.id} "
            "stands in it: a ticket waits on each blocker and a parent on each child",
            "break the cycle: drop one `blocked-by` entry, or re-parent one of them",
        )


def _knots(tickets: Sequence[Ticket]) -> Mapping[str, tuple[str, ...]]:
    """Each ticket that stands in a knot, against the knot it stands in."""

    return MappingProxyType({id: knot for knot in cycles(tickets) for id in knot})


# --- what the work waits on --------------------------------------------------------


def _wait_messages(ticket: Ticket) -> Iterator[Message]:
    """A ticket whose work waits on a person's decision brief reads as waiting.

    It is INFO, so the ticket still reads PASS and no other ticket moves: a
    brief nobody has answered yet holds the work it decides and nothing else. The
    message is what makes "can this start" computable from the report.
    """

    if not ticket.waits_on:
        return
    named = ", ".join(ticket.waits_on)
    yield message(
        "WAITS_ON_BRIEF",
        ticket.id,
        f"{ticket.id} waits on the decision brief(s) {named}: the work they decide starts "
        "once a person answers them",
        f"carry on with every ticket that does not wait on {named}; when the answer is "
        "recorded, drop its id from `waits-on`",
    )


# --- the pass ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Run:
    """Everything one pass reads that is the same for every ticket."""

    given: _Input
    sections: _Sections
    plan: ClaimsPlan
    knots: Mapping[str, tuple[str, ...]]


def _judge(ticket: Ticket, run: _Run) -> TicketResult:
    """One ticket, in the one order this verb reads it: the reader's own messages
    unchanged, then the brief, the links, the claims, the relations and the waits.

    A block whose version this engine never shipped ends the pass here, before
    anything else is asked. A block that could not be read at all is
    not that case — it has no version, the reader has already said what is wrong
    with it, and what it carries is empty rather than unknown.
    """

    reported = run.given.reported.get(ticket.id, ())
    if ticket.block_version and ticket.block_version not in BLOCK_VERSIONS:
        return TicketResult(ticket.id, ticket.title, ticket.state, reported)
    messages = (
        *reported,
        *_brief_messages(ticket),
        *_reads_messages(ticket, run.sections),
        *_claim_messages(ticket, run.plan),
        *_reach_messages(ticket, run.plan),
        *_relation_messages(ticket, run.given, run.knots),
        *_wait_messages(ticket),
    )
    return TicketResult(ticket.id, ticket.title, ticket.state, messages)


def _counts(given: _Input) -> Counts:
    """What this run read, and what the reader's gate left out."""

    states = Counter(ticket.state for ticket in given.tickets)
    return Counts(
        tickets=len(given.tickets),
        ignored=given.ignored,
        open=states[_OPEN],
        closed=states[_CLOSED],
        dropped=states[_DROPPED],
    )


def check(target: Path, declaration: Declaration, options: argparse.Namespace) -> Report:
    """Report what this project's open tickets, or the drafts given, say.

    The verb entry, which reads the store and the claims plan itself. It is
    `check_loaded` with nothing read yet, so there is one pass and not two.
    """

    return check_loaded(target, declaration, options)


def check_loaded(
    target: Path,
    declaration: Declaration,
    options: argparse.Namespace,
    read: ReadResult | None = None,
    plan: ClaimsPlan | None = None,
) -> Report:
    """The same pass over a store and a plan the caller may already hold.

    `read` is the declared store as some other verb read it and `plan` the
    claims plan as it loaded it; each is None where this run is to read it
    itself, which is what the verb entry passes. A caller hands over what it
    read because reading twice is two answers where there is one question —
    and where `--input -` names a stream, the second answer is that the export
    is empty. With `--draft` no store is read at all, by either caller, and
    `read` is then unused.

    The subjects come first: the declared store through the reader it selects,
    or the drafts alone. Then the claims plan, once — a plan this engine cannot
    read is a refusal, not a store of tickets proving nothing. Only
    then is anything judged, and only the open tickets: a knot is one among
    them. It reads `options.draft` and `options.input`, and parses neither.
    """

    root = Path(target)
    drafts = tuple(options.draft or ())
    given = (
        _from_drafts(drafts, declaration)
        if drafts
        else _from_read(read if read is not None else read_store(root, declaration, options.input))
    )
    claims = load_claims(root, declaration) if plan is None else plan
    judged = tuple(ticket for ticket in given.tickets if ticket.state == _OPEN)
    run = _Run(given=given, sections=_Sections(root), plan=claims, knots=_knots(judged))
    return Report(
        verb=_VERB,
        store=declaration.store,
        input=given.source,
        counts=_counts(given),
        tickets=tuple(_judge(ticket, run) for ticket in judged),
        messages=(
            *given.run_level,
            *_cwd_messages(claims, root),
            *_placement_messages(claims, root),
        ),
    )
