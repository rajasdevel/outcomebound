"""The ticket a verb is about, and the gates a ticket must pass before a verb acts on it.

What this module decides: which ticket a ticket word names, in a declared store or in a
local draft; that only an open ticket is acted on; and that what `check` reports as an
ERROR on that ticket stops the verb. `brief` and `verify` both act on one named ticket, so
the reading and the three refusals are written once, and the ticket one verb is about is
the ticket the other is about.

What it does not decide: what a verb does with the ticket, or whether it is fit to act on
beyond what `check` says. Each verb gives its own `Use`, the code and the words of its
refusals, so a refusal names the verb that was refused.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from outcomebound_tools.tickets_check import check_loaded
from outcomebound_tools.tickets_claims import ClaimsPlan
from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_draft import read_draft
from outcomebound_tools.tickets_model import STATES, ReadResult, Ticket
from outcomebound_tools.tickets_report import Level, Refusal, held
from outcomebound_tools.tickets_store import read_store

__all__ = ["Subject", "Use", "read_subject", "refuse_closed", "refuse_findings"]

# The normalised ticket's first state: the only one a verb acts on, because a
# verb's input is work that is still to do.
_OPEN = STATES[0]


@dataclass(frozen=True, slots=True)
class Use:
    """What one verb says when it refuses a ticket, in its own words.

    `code` is the refusal's code. The other fields are the clauses of its sentences:
    `from_file` and `from_ticket` say what the verb acts on, `to_act` the verb of
    "no decision content to ...", `closed` why only an open ticket is acted on, and
    `stopped` and `again` the end of a refusal because of `check`.
    """

    code: str
    from_file: str
    to_act: str
    from_ticket: str
    closed: str
    stopped: str
    again: str


@dataclass(frozen=True, slots=True)
class Subject:
    """The ticket this run is about, and what was read to find it.

    `read` is the declared store as this verb read it, and None where
    `--draft` named a local file and no store was read at all. It is carried
    because `check` is asked about this same ticket and must be asked about
    this same reading: an export given as `--input -` is a stream, and a
    second reader of one finds it empty.
    """

    ticket: Ticket
    read: ReadResult | None


def _drafted(paths: tuple[str, ...], declaration: Declaration, wanted: str, use: Use) -> Ticket:
    """The draft named `wanted` among `paths`, read through the one draft reader.

    A draft's id is its file name without the extension, and the id a person
    named picks the file: the other files are the breakdown it belongs to, which
    `check` lints with it so that a `parent` or a `blocked-by` naming a sibling
    resolves. A verb acting on another ticket's id would be about the wrong
    work, so with no file of that name the first one's id is what the refusal
    names. The file that could not be read at all is the reader's own sentence.
    """

    path = next((path for path in paths if Path(path).stem == wanted), paths[0])
    ticket, messages = read_draft(path, declaration)
    if ticket is None:
        raise Refusal(
            use.code,
            f"no draft could be read at {path}: {messages[0].text}; name a draft file this "
            f"checkout holds, because {use.from_file}",
        )
    if ticket.id != wanted:
        raise Refusal(
            "TICKET_NOT_FOUND",
            f"the draft at {path} is the ticket {ticket.id}, not {wanted}; a draft's id is "
            "its file name without the extension, so name that id beside the file",
        )
    return ticket


# `<owner>/<name>#<n>`, the form the tracker itself writes a reference in.
_QUALIFIED = re.compile(r"(?P<repo>[^/\s#]+/[^/\s#]+)#(?P<number>[0-9]+)", re.ASCII)


def _store_id(wanted: str, declaration: Declaration) -> str:
    """The id a store ticket is named by: a bare issue number is `#<n>`.

    A shell reads `#20` as the start of a comment unless it is quoted, so a
    person types `20`; the tracker's own ids are all `#<n>`, and a bare number
    names nothing else. `<owner>/<name>#<n>` is how the tracker writes a
    reference, and it is `#<n>` where it names the declared repository, which
    the tracker compares without case. Another repository's issue is not in
    this store, so it is refused by name rather than reported as missing.
    """

    if wanted.isdecimal() and wanted.isascii():
        return f"#{wanted}"
    qualified = _QUALIFIED.fullmatch(wanted)
    if qualified is None:
        return wanted
    if qualified["repo"].casefold() != declaration.repo.casefold():
        raise Refusal(
            "TICKET_NOT_FOUND",
            f"{wanted} names the repository {qualified['repo']}; this project's declaration "
            f"names {declaration.repo}, and its store holds that repository's tickets only",
        )
    return f"#{qualified['number']}"


def _export_said(read: ReadResult) -> str:
    """The export a run read, as a refusal names it: path, time, age and id range."""

    source = read.input
    if source is None:
        return ""
    if source.modified is None or source.age_seconds is None:
        written = "written at a time standard input does not carry"
    else:
        written = f"written {source.modified} ({source.age_seconds}s ago)"
    return f"; the export {source.path}, {written}, {held(source)}"


def _from_store(read: ReadResult, given: str, declaration: Declaration, use: Use) -> Ticket:
    """The one ticket this run is about. A reader holds at most one per id."""

    wanted = _store_id(given, declaration)
    for ticket in read.tickets:
        if ticket.id == wanted:
            return ticket
    if wanted in read.others:
        raise Refusal(
            use.code,
            f"{wanted} is an issue this project's gate does not read as a ticket, so there "
            f"is no decision content to {use.to_act}; the declared label, the user's "
            "acceptance, makes it one",
        )
    raise Refusal(
        "TICKET_NOT_FOUND",
        f"the declared store holds no ticket {wanted}{_export_said(read)}; a ticket newer "
        "than the export needs a new export (`outcomebound tickets export` prints the "
        f"command); name a ticket the store carries, because {use.from_ticket}",
    )


def read_subject(
    root: Path, declaration: Declaration, options: argparse.Namespace, use: Use
) -> Subject:
    """The ticket the verb is about, and the reading it came from where it came from a store."""

    if options.draft:
        return Subject(_drafted(tuple(options.draft), declaration, options.ticket, use), None)
    read = read_store(root, declaration, options.input)
    return Subject(_from_store(read, options.ticket, declaration, use), read)


def refuse_closed(ticket: Ticket, use: Use) -> None:
    """Only an open ticket is acted on."""

    if ticket.state != _OPEN:
        raise Refusal(use.code, f"{ticket.id} is {ticket.state}, and {use.closed}")


def _judgement(options: argparse.Namespace) -> argparse.Namespace:
    """The options `check` reads, carried into it from this run.

    A verb that needs another verb's judgement calls that verb's function with a
    namespace carrying every option the callee reads, so `check` parses nothing
    and nothing of its own is reimplemented here. Its `--draft` files are the
    list `check` lints together.
    """

    return argparse.Namespace(
        input=options.input,
        draft=list(options.draft) if options.draft else None,
    )


def refuse_findings(
    root: Path,
    declaration: Declaration,
    options: argparse.Namespace,
    subject: Subject,
    plan: ClaimsPlan,
    use: Use,
) -> None:
    """What `check` says about this ticket stops the verb.

    It is asked through `check_loaded`, about the store this verb already read
    and the plan it already loaded, so one run reads each once.

    Scoped to the one ticket by the id every message is stamped with: what a
    reader found about another ticket is `check`'s to report and says nothing
    about this one. A message stamped with no id is the run's — a claims plan
    whose directory resolves outside the checkout is one — and a verb that
    does not run the plan's commands is not refused for it.

    A block this engine did not read is one of those ERRORs, so a verb never
    says such a ticket covers nothing and grants nothing.
    """

    ticket = subject.ticket
    report = check_loaded(root, declaration, _judgement(options), subject.read, plan)
    about = [
        item for result in report.tickets if result.id == ticket.id for item in result.messages
    ]
    found = [item for item in about if item.level is Level.ERROR]
    if not found:
        return
    said = "; ".join(f"{item.code}: {item.text}" for item in found)
    raise Refusal(
        use.code,
        f"`check` reports an error on {ticket.id}, {use.stopped} — {said}; "
        f"fix what `check` reports and {use.again}",
    )
