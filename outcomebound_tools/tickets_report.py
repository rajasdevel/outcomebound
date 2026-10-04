"""What every ticket verb reports, and what its run exits with.

What this module decides: the one message table, what a
message's level makes its ticket read, what the worst ticket makes the run
read, which of 0, 1 and 2 the process exits with, and how a report is rendered
as text and as one JSON object under `schemas/tickets-report.schema.json`. It
is the bottom of the ticket engine: every other ticket module imports it and it
imports none of them.

What it does not decide: what a verb looks at, what a ticket is, when a refusal
is raised, or where anything is printed. A verb builds a `Report` or raises a
`Refusal`; `tickets.py` decides the stream and returns the exit code.

The verdict rule is two small tables rather than a ladder of conditions: a
level decides what a ticket reads, and results are ordered so that the worst of
a run's tickets is a `max`.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import IntEnum
from types import MappingProxyType
from typing import Protocol

__all__ = [
    "MESSAGES",
    "Counts",
    "EngineError",
    "InputSource",
    "Level",
    "Message",
    "PlanningError",
    "Refusal",
    "Report",
    "ReportError",
    "TicketResult",
    "exit_code",
    "message",
    "render_json",
    "render_text",
    "result",
    "ticket_result",
]


class EngineError(ValueError):
    """What every ticket module's own error derives from: the engine could not act.

    A file that stopped being a file between the reading and the writing, a
    directory the filesystem refused, a git that could not be asked. It is not
    a finding about a ticket and not one of the refusals, which name what a
    project got wrong; `tickets.py` prints it as one `ENGINE_ERROR` line and
    exits 1, so an operator reads the sentence the module wrote — whether
    anything was written, above all — and not a traceback. `ReportError` and
    the model's own error are not among them: a report or a value built wrong
    is this engine's defect, and a defect keeps its traceback.
    """


class ReportError(ValueError):
    """A report built wrong: a message code the contract forbids."""


class _Named(Exception):
    """One named line a verb stops on, printed instead of a report.

    The code and the text are carried separately because the line is composed
    once, by the command line, and never by the verb that raised it.
    """

    def __init__(self, code: str, text: str) -> None:
        super().__init__(f"{code}: {text}")
        self.code = code
        self.text = text


class Refusal(_Named):
    """A verb's refusal: one named line on standard error, exit 1, no report."""


class PlanningError(_Named):
    """A run that could not be planned: one named line, exit 2, no report.

    It is what a verb raises where what it needs to read was not given — a
    `github` store's export — which is missing evidence about the run rather
    than a finding about a ticket.
    """


class Level(IntEnum):
    """A message's level, ordered so that the worst of a ticket's messages is `max`."""

    INFO = 0
    WARNING = 1
    UNVERIFIED = 2
    ERROR = 3


# Every code a verb emits, grouped by level. A code
# no verb emits is not listed; `tests/test_tickets_report.py` holds each listed
# code to a module that spells it.
_CODES: Mapping[Level, tuple[str, ...]] = {
    Level.ERROR: (
        "TICKET_UNREADABLE",
        "BLOCK_MISSING",
        "BLOCK_MALFORMED",
        "BLOCK_DUPLICATE",
        "KEY_MISSING",
        "KEY_DUPLICATE",
        "KEY_UNKNOWN",
        "VALUE_INVALID",
        "ID_DUPLICATE",
        "READS_UNRESOLVED",
        "READS_AMBIGUOUS",
        "BOUNDS_INVALID",
        "DEPENDENCY_CYCLE",
        "CLAIM_CWD_OUTSIDE",
    ),
    Level.UNVERIFIED: (
        "EXPORT_TRUNCATED",
        "EXPORT_PARTIAL",
        "RELATION_EXTERNAL",
    ),
    Level.WARNING: (
        "BRIEF_THIN",
        "CLAIM_PLANNED",
        "CLAIM_READS_OUTSIDE_BOUNDS",
        "BOUNDS_WHOLE_REPOSITORY",
        "DISCOVERED_FROM_ABSENT",
    ),
    Level.INFO: ("HOLD_SURFACES_DIFFER", "WAITS_ON_BRIEF", "RELATION_UNCHECKED"),
}

MESSAGES: Mapping[str, Level] = MappingProxyType(
    {code: level for level, codes in _CODES.items() for code in codes}
)

# What a level makes a ticket read. It rises with the level, which is
# what lets the worst level decide a ticket.
_RESULT_BY_LEVEL: Mapping[Level, str] = MappingProxyType(
    {
        Level.INFO: "PASS",
        Level.WARNING: "PASS",
        Level.UNVERIFIED: "UNVERIFIED",
        Level.ERROR: "FAIL",
    }
)

# Results from best to worst, so the run's is the last of its tickets'.
_RESULT_ORDER: tuple[str, ...] = ("PASS", "UNVERIFIED", "FAIL")

# What a report exits with. It is the only place a
# report's exit code is decided; the exit of a refusal and of a planning error
# is `tickets.py`'s, beside the stream each is printed on. A verb never exits.
_EXIT_BY_RESULT: Mapping[str, int] = MappingProxyType({"PASS": 0, "FAIL": 1, "UNVERIFIED": 2})

# The keys, in the order a report prints them. Each tuple is the one list of
# its subject's keys: the document is built from it.
_REPORT_KEYS: tuple[str, ...] = (
    "result",
    "verb",
    "store",
    "input",
    "counts",
    "tickets",
    "messages",
)
_TICKET_KEYS: tuple[str, ...] = ("id", "title", "state", "result", "messages")


@dataclass(frozen=True, slots=True)
class Message:
    """One thing a verb has to say, always from the table above."""

    level: Level
    code: str
    ticket: str
    text: str
    next: str = ""


def message(code: str, ticket: str, text: str, next: str = "") -> Message:
    """The only way to build a `Message`; a code outside `MESSAGES` is a programming error."""

    level = MESSAGES.get(code)
    if level is None:
        raise ReportError(
            f"no message code {code!r} in MESSAGES; use a code it lists, or add the code "
            "there in the change that first emits it"
        )
    return Message(level=level, code=code, ticket=ticket, text=text, next=next)


@dataclass(frozen=True, slots=True)
class Counts:
    """The counts, in the order a report prints them."""

    tickets: int = 0
    ignored: int = 0
    open: int = 0
    closed: int = 0
    dropped: int = 0


class InputSource(Protocol):
    """What the report's `input` object offers: the export, when it was written, its age.

    The reader's value (`tickets_model.InputInfo`) satisfies this structurally.
    Naming the shape rather than importing the reader is what keeps this module
    at the bottom of the engine: the reader imports the report, never the other
    way round. `modified` and `age_seconds` are None for input read from
    standard input, whose age a report says is unknown.
    """

    @property
    def path(self) -> str: ...

    @property
    def modified(self) -> str | None: ...

    @property
    def age_seconds(self) -> int | None: ...


@dataclass(frozen=True, slots=True)
class TicketResult:
    """One ticket as a report carries it: what it is, and what was found about it."""

    id: str
    title: str
    state: str
    messages: tuple[Message, ...] = ()


@dataclass(frozen=True, slots=True)
class Report:
    """One run's report, key for key of `schemas/tickets-report.schema.json`."""

    verb: str
    store: str
    input: InputSource | None = None
    counts: Counts = Counts()
    tickets: tuple[TicketResult, ...] = ()
    messages: tuple[Message, ...] = ()


# --- verdicts and the exit rule ---------------------------------------------------


def _reads(messages: Sequence[Message]) -> str:
    """What one subject's messages make it read: the worst level decides."""

    if not messages:
        return "PASS"
    return _RESULT_BY_LEVEL[max(item.level for item in messages)]


def ticket_result(ticket: TicketResult) -> str:
    """What one ticket reads, as a report prints it: its worst level decides."""

    return _reads(ticket.messages)


def _worst(results: Iterable[str]) -> str:
    return max(results, key=_RESULT_ORDER.index)


def result(report: Report) -> str:
    """The run's result: the worst ticket's, run-level messages counting as one.

    A run with no tickets still has that last subject, so there is always one
    result to take the worst of.
    """

    per_ticket = [_reads(ticket.messages) for ticket in report.tickets]
    return _worst([*per_ticket, _reads(report.messages)])


def exit_code(report: Report) -> int:
    """0 for PASS, 1 for FAIL, 2 for UNVERIFIED."""

    return _EXIT_BY_RESULT[result(report)]


# --- rendering ---------------------------------------------------------------------


def _message_document(item: Message) -> dict[str, object]:
    return {
        "level": item.level.name,
        "code": item.code,
        "ticket": item.ticket,
        "text": item.text,
        "next": item.next,
    }


def _input_document(source: InputSource | None) -> dict[str, object] | None:
    if source is None:
        return None
    return {
        "path": source.path,
        "modified": source.modified,
        "age_seconds": source.age_seconds,
    }


def _ticket_document(ticket: TicketResult) -> dict[str, object]:
    """One ticket: the fixed keys of `_TICKET_KEYS`, in that order."""

    fixed: tuple[object, ...] = (
        ticket.id,
        ticket.title,
        ticket.state,
        _reads(ticket.messages),
        [_message_document(item) for item in ticket.messages],
    )
    return dict(zip(_TICKET_KEYS, fixed, strict=True))


def _document(report: Report) -> dict[str, object]:
    """The report as one ordered mapping.

    The values are written in the order of `_REPORT_KEYS`, which is the one
    list of those keys; `strict=True` is what says the two have not drifted.
    """

    fixed: tuple[object, ...] = (
        result(report),
        report.verb,
        report.store,
        _input_document(report.input),
        dataclasses.asdict(report.counts),
        [_ticket_document(ticket) for ticket in report.tickets],
        [_message_document(item) for item in report.messages],
    )
    return dict(zip(_REPORT_KEYS, fixed, strict=True))


def render_json(report: Report) -> str:
    """The report as one JSON object, in the declared key order, with a final newline."""

    return json.dumps(_document(report), indent=2, sort_keys=False) + "\n"


def _input_line(source: InputSource | None) -> str:
    if source is None:
        return "input: none"
    modified = source.modified or "unknown"
    age = "unknown" if source.age_seconds is None else f"{source.age_seconds}s"
    return f"input: {source.path}; modified {modified}; age {age}"


def _counts_line(counts: Counts) -> str:
    named = "; ".join(f"{key} {value}" for key, value in dataclasses.asdict(counts).items())
    return f"counts: {named}"


def _message_row(item: Message, subject: str) -> str:
    """One message as a row: its level, its subject, then what it says."""

    reason = f"{item.code}: {item.text}"
    if item.next:
        reason = f"{reason}; next: {item.next}"
    return f"{item.level.name}\t{subject}\t{reason}"


# The codes text folds into one row per run: each is a WARNING a breakdown carries
# once per planned claim, which buries the findings that need action. `--json`
# keeps every one on its ticket.
_FOLDED: tuple[str, ...] = ("CLAIM_PLANNED",)


def _folded_rows(folded: Sequence[Message]) -> list[str]:
    """One row per folded code: how many messages, on which tickets."""

    rows: list[str] = []
    for code in _FOLDED:
        found = [item for item in folded if item.code == code]
        if not found:
            continue
        tickets = list(dict.fromkeys(item.ticket for item in found))
        summary = Message(
            level=found[0].level,
            code=code,
            ticket="",
            text=f"{len(found)} `done-when` claim(s) on {len(tickets)} ticket(s), "
            f"{', '.join(tickets)}, are not defined in the claims plan yet; each ticket's "
            "own work may add them",
            next="`--json` lists each claim on its ticket",
        )
        rows.append(_message_row(summary, "-"))
    return rows


def render_text(report: Report) -> str:
    """The report as text: the run's own lines, then one row per subject.

    A row is the verdict, the subject and the reason, tab-separated, which is
    what a person greps. The codes in `_FOLDED` are one summary row after the
    run's own messages instead of one row each; the verdicts do not change, since
    each is a WARNING.
    """

    header = [
        f"{report.verb}: {result(report)}",
        f"store: {report.store}",
        _input_line(report.input),
        _counts_line(report.counts),
    ]
    rows: list[str] = []
    folded: list[Message] = []
    for ticket in report.tickets:
        reads = _reads(ticket.messages)
        rows.append(f"{reads}\t{ticket.id}\t{ticket.title} ({ticket.state})")
        for item in ticket.messages:
            if item.code in _FOLDED:
                folded.append(item)
            else:
                rows.append(_message_row(item, ticket.id))
    rows.extend(_message_row(item, item.ticket or "-") for item in report.messages)
    rows.extend(_folded_rows(folded))
    blocks = [block for block in (header, rows) if block]
    return "\n\n".join("\n".join(block) for block in blocks) + "\n"
