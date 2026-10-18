"""The `brief` verb: the one document an implementer is handed, and nothing else.

What this module decides: the brief's layout — which section follows
which, how a check line reads for each claim, what an empty brief, an
absent `reads` and an empty `bounds` say, where a project's workflow
document is named, how a ticket that waits on a decision brief says so, and
which refusals stop a compilation. The brief carries no size figure: no cutoff
applies to it, and a figure in a hand-off reads as one.

What it does not decide: anything it names. Which heading a `reads` entry names
is `tickets_links`'; a claim's command, working directory and timeout are
`tickets_claims`'; the ticket is the reader's that the declaration selects, or
`tickets_draft`'s. Whether the ticket is fit to compile is `tickets_check`'s
judgement, called here and never reimplemented: a brief that names a section that
does not resolve is worse than no brief, so any ERROR `check` reports for this
ticket is a refusal.

**It names and never quotes.** A cited section is named by its path, its
anchor and its heading, and the implementer reads it where it stands: a copy
outweighs the ticket it serves and goes stale.

**It writes nothing and reads no clock.** The header names the commit and whether
the tree was clean through `tickets_git`; everything else comes from the ticket,
the plan and the sections it cites. Two compilations of one ticket at one commit
are the same bytes, and the document is text rather than a `Report` because
`brief` prints no report and a document read by a person is not a structure
validated by a schema. The one line this module reshapes is the heading, whose
title is written as single spaces so that a title carrying a line end cannot
forge a header line of its own; `content` is unaffected, because the identity is
the model's over the title as written.
"""

from __future__ import annotations

import argparse
import os.path
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from outcomebound_tools import paths
from outcomebound_tools.tickets_claims import ClaimsPlan, load_claims
from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_git import GitError, head_commit, tree_clean
from outcomebound_tools.tickets_links import Section, section
from outcomebound_tools.tickets_model import DoneWhen, Ticket
from outcomebound_tools.tickets_report import Refusal
from outcomebound_tools.tickets_subject import (
    Subject,
    Use,
    read_subject,
    refuse_closed,
    refuse_findings,
)

__all__ = ["brief"]

# What `brief` says when it refuses a ticket.
_USE = Use(
    code="BRIEF_REFUSED",
    from_file="a brief is compiled from what the file says and nothing else",
    to_act="compile",
    from_ticket="a brief is compiled from the ticket it names and from no other",
    closed=(
        "a brief is the input to work that is still open; read the ticket itself for what was done"
    ),
    stopped="so no brief of it is compiled",
    again="compile it again",
)

# The project's workflow document, named and never quoted: the declaration
# has no field for it, so this is the one name the engine looks for.
_WORKFLOW = "CONTRIBUTING.md"

# The brief's sections, in order.
_TICKET = "## Ticket"
_READ = "## Read"
_CHECKS = "## Checks"
_BOUNDS = "## Bounds"
_WAITS = "## Waits on"
_STEPS = "## Steps"
_LANDS = "## How work lands"
_USING = "## Using this brief"

# The header's tree word.
_TREE: Mapping[bool, str] = {True: "clean", False: "dirty"}

# What each section says where the ticket gives it nothing. An empty section
# would read as a missing one, and silence about a decision is what a brief
# exists to prevent.
_NO_BRIEF = "This ticket's body is empty, so nothing here says what the work is."
_NO_READS = "This ticket cites no section to read."
_WHOLE_FILE = "the whole file"
_NO_BOUNDS = "This ticket grants no path, so nothing here says where the work may go."
_NO_WORKFLOW = (
    f"No {_WORKFLOW} is at the root of this checkout. Land as AGENTS.md or the goal envelope "
    "says; where neither says, commit on the current branch in the style the history shows, "
    "and say in the handover how it should land."
)

# What a ticket that waits on a person's decision brief says, beside the ids.
_WAITS_BODY = (
    "This ticket's work waits on the decision brief(s) {named}, which a person has yet to "
    "answer. Do every part the answer does not decide, then hand over naming what waits on it."
)

# The brief's own closing paragraph, wrapped as it is printed.
_USING_BODY = (
    "Read the sections named above, and source as needed in and around the bounds. Decide\n"
    "nothing the ticket or those sections already decide. When Limits holds a part for the\n"
    "person, finish every part it does not block, then hand over with that part as a decision\n"
    "brief naming what it waits on. Hand the work over saying what changed, each check's\n"
    "verdict, what you decided beyond the ticket, and the follow-ups you found."
)

# The two check lines, and a third: a claim the plan defines with nothing
# this engine could run.
_PLANNED = "planned: the plan does not define it yet; this ticket's work adds it"
_UNRUNNABLE = "the plan defines it with no command this engine could run"
# A person's check, on a ticket a person does: what the person observes.
_PERSON = "a person's check: {observation}"
_COMMAND_LINE = "`{command}` in `{cwd}`, {timeout}"
_TIMEOUT = "timeout {seconds}s"
_NO_TIMEOUT = "no timeout"

# `--detail full` adds `## Steps` after `## Bounds`;
# `plain`, the default, is the document without it, byte for byte.
_FULL = "full"


@dataclass(frozen=True, slots=True)
class _Compiled:
    """Everything the document is rendered from, read before a line is written.

    Gathering and rendering are kept apart so that the rendering is a pure
    function of this value, and two compilations at one commit are the same bytes.
    """

    ticket: Ticket
    commit: str
    clean: bool
    sections: tuple[Section, ...]
    plan: ClaimsPlan
    cwd: str
    workflow: bool


# --- what is read ------------------------------------------------------------------


def _checkout(root: Path) -> tuple[str, bool]:
    """The commit this brief is compiled at, and whether the tree was clean."""

    try:
        return head_commit(root), tree_clean(root)
    except GitError as error:
        raise Refusal(
            "NOT_A_REPOSITORY",
            f"{root} could not be read as a git repository with a commit: {error}; a brief "
            "names the commit it was compiled at, so it compiles only in a checkout with one",
        ) from error


def _sections(root: Path, ticket: Ticket) -> tuple[Section, ...]:
    """The section each `reads` entry names, in written order.

    Nothing is deduplicated: two entries naming one anchor name it twice,
    because the ticket wrote it twice and a brief is not a summary of itself.
    One reading serves both, since the answer is a pure function of the path and
    the anchor at this checkout.
    """

    read: dict[tuple[str, str], Section] = {}
    for entry in ticket.reads:
        key = (entry.path, entry.anchor)
        if key not in read:
            read[key] = section(root, entry.path, entry.anchor)
    return tuple(read[(entry.path, entry.anchor)] for entry in ticket.reads)


def _claims_cwd(plan: ClaimsPlan, root: Path) -> str:
    """Where a claim would run, as the brief names it: relative to the checkout,
    never absolute.

    A plan whose directory resolves outside the checkout is named with `../`
    segments, which is still a name relative to the checkout: `check` has already
    reported `CLAIM_CWD_OUTSIDE` as the run's own message and `brief` runs
    nothing, so the document says where the claim would run rather than refusing a
    ticket nothing is wrong with. An absolute path would put this machine's
    directory layout into a document written to be read and passed on.
    """

    return Path(os.path.relpath(plan.cwd_resolved, root.resolve())).as_posix()


def _compile(root: Path, declaration: Declaration, subject: Subject, plan: ClaimsPlan) -> _Compiled:
    """Everything the document names, read once at this checkout.

    The plan is the one this run already loaded, and not a second reading of
    it: `check` was asked about the claims of this same plan.
    """

    ticket = subject.ticket
    commit, clean = _checkout(root)
    return _Compiled(
        ticket=ticket,
        commit=commit,
        clean=clean,
        sections=_sections(root, ticket),
        plan=plan,
        cwd=_claims_cwd(plan, root),
        workflow=(root / _WORKFLOW).is_file(),
    )


# --- the layout --------------------------------------------------------------------


def _terminated(text: str) -> str:
    """One part of the document, ending in the line feed it may already carry."""

    return text if text.endswith("\n") else text + "\n"


def _part(heading: str, body: str) -> str:
    """A heading and what stands under it, with no blank line between them.

    Every section has a body: the sections a ticket may leave empty carry the
    sentence that says so, which is what keeps a heading from standing alone and
    reading as a section this engine failed to write.
    """

    return _terminated(heading) + _terminated(body)


def _title(ticket: Ticket) -> str:
    """The brief's heading: the ticket's id and its title, on one line.

    The title's white space, line ends included, is written as single spaces.
    That is the one reshaping this module does, and it is what keeps a title
    carrying a line end from forging a header line of its own — a tracker takes
    a title as the person typed it, and `compiled-at:` under a forged heading
    would read as this engine's own. The identity is not touched: `content` is
    the model's over the title as written, so the forged title still hashes to
    something no other title hashes to.
    """

    named = " ".join(part for part in (ticket.id, " ".join(ticket.title.split())) if part)
    return _terminated(f"# Brief — {named}")


def _header(compiled: _Compiled) -> str:
    """The header lines, in order."""

    lines = (
        f"compiled-at: {compiled.commit} ({_TREE[compiled.clean]})",
        f"content: {compiled.ticket.content}",
    )
    return "".join(_terminated(line) for line in lines)


def _cited(found: Section) -> str:
    """A section as its ticket cites it: `path#anchor`, or the path alone for a file."""

    return f"{found.path}#{found.anchor}" if found.anchor else found.path


def _heading(found: Section) -> str:
    """What a cited section is called: its heading, or what a whole-file citation names."""

    return found.heading if found.anchor else _WHOLE_FILE


def _read(compiled: _Compiled) -> str:
    """One line per `reads` entry, in written order: its path and anchor, then the
    heading it names, as the file writes it."""

    named = "\n".join(f"- {_cited(found)} — {_heading(found)}" for found in compiled.sections)
    return _part(_READ, named or _NO_READS)


def _timeout(value: float | None) -> str:
    """A timeout as the brief writes it: whole seconds carry no decimal point, and a
    claim the plan sets none for has none, which the line says."""

    if value is None:
        return _NO_TIMEOUT
    if not isfinite(value):
        return _TIMEOUT.format(seconds=value)
    whole = int(value)
    return _TIMEOUT.format(seconds=whole if value == whole else repr(value))


def _check_body(item: DoneWhen, compiled: _Compiled) -> str:
    """What one `done-when` claim says it takes to be done.

    The definition of a claim the plan defines, and the planned line for one it
    does not, which is the ticket's own work to add. A person's check, on a
    ticket a person does, says what the person observes. A claim the plan defines
    with no command this engine could run is the third case, which reads as what
    it is rather than as an empty command.
    """

    if item.human:
        return _PERSON.format(observation=item.human)
    definition = compiled.plan.claims.get(item.claim)
    if definition is None:
        return _PLANNED
    if not definition.command:
        return _UNRUNNABLE
    return _COMMAND_LINE.format(
        command=("& " if paths.on_windows() else "")
        + " ".join(map(paths.shell_word, definition.command)),
        cwd=compiled.cwd,
        timeout=_timeout(definition.timeout_seconds),
    )


def _checks(compiled: _Compiled) -> str:
    """One line per `done-when` item, in the ticket's declared order.

    This section needs no sentence for an empty one: the block requires the key, and
    a `done-when` that is absent is `KEY_MISSING` while one carrying no item is
    `VALUE_INVALID` — both ERRORs, both refused above, so a ticket that reaches
    here names at least one check.
    """

    lines = [
        f"- `{item.claim}` — {_check_body(item, compiled)}" for item in compiled.ticket.done_when
    ]
    return _part(_CHECKS, "\n".join(lines))


def _bounds(ticket: Ticket) -> str:
    """One line per `bounds` entry, in written order.

    An empty `bounds` is a valid ticket, so it gets a line of its own: a heading
    with nothing under it would read as a section this engine failed to write.
    """

    written = "\n".join(f"- {entry}" for entry in ticket.bounds)
    return _part(_BOUNDS, written if written else _NO_BOUNDS)


def _waits_named(ticket: Ticket) -> str:
    return ", ".join(ticket.waits_on)


def _waits(ticket: Ticket) -> tuple[str, ...]:
    """`## Waits on`, only for a ticket whose work waits on a person's decision brief.

    A ticket that waits on none has no such section: nothing is missing, and an
    empty one would read as a wait nobody named.
    """

    if not ticket.waits_on:
        return ()
    return (_part(_WAITS, _WAITS_BODY.format(named=_waits_named(ticket))),)


def _steps(compiled: _Compiled) -> str:
    """`## Steps`: the brief's own facts as numbered steps, in the order an implementer
    meets them.

    Read the cited sections, keep to the bounds, leave what waits on a decision
    brief, run each check as `## Checks` renders it, report. Every section, bound,
    check, brief and command named here is one the document already carries, and
    none it carries is left out, so the step form adds no fact and drops none. A
    ticket citing nothing still has the last three.
    """

    ticket = compiled.ticket
    steps = []
    if compiled.sections:
        read = ", ".join(f"`{_cited(found)}`" for found in compiled.sections)
        steps.append(f"Read the sections named above: {read}.")
    if ticket.bounds:
        paths = ", ".join(f"`{entry}`" for entry in ticket.bounds)
        steps.append(f"Keep every change inside the bounds: {paths}.")
    else:
        steps.append(f"Keep to the bounds: {_NO_BOUNDS}")
    if ticket.waits_on:
        steps.append(
            f"Do every part the decision brief(s) {_waits_named(ticket)} do not decide, and "
            "name what waits on them in the report."
        )
    checks = "".join(
        f"\n   - `{item.claim}` — {_check_body(item, compiled)}" for item in ticket.done_when
    )
    steps.append(f"Run each check:{checks}")
    steps.append(
        "Report what changed, each check's verdict, what you decided beyond the ticket, "
        "and the follow-ups you found."
    )
    return _part(_STEPS, "\n".join(f"{number}. {step}" for number, step in enumerate(steps, 1)))


def _document(compiled: _Compiled, detail: str = "plain") -> str:
    """The whole document: the brief's sections, one blank line between them.

    `## Waits on` follows `## Bounds` only where the ticket waits on a brief.
    `detail` full adds `## Steps` after those; plain leaves every other byte as it
    is. The engine applies no cutoff, here or anywhere.
    """

    steps = (_steps(compiled),) if detail == _FULL else ()
    sections = (
        _title(compiled.ticket),
        _header(compiled),
        _part(_TICKET, compiled.ticket.brief.strip() or _NO_BRIEF),
        _read(compiled),
        _checks(compiled),
        _bounds(compiled.ticket),
        *_waits(compiled.ticket),
        *steps,
        _part(_LANDS, _WORKFLOW if compiled.workflow else _NO_WORKFLOW),
        _part(_USING, _USING_BODY),
    )
    return "\n".join(sections)


# --- the seam ----------------------------------------------------------------------


def brief(target: Path, declaration: Declaration, options: argparse.Namespace) -> str:
    """The brief's document, returned for `tickets.py` to print.

    The order of the run is what makes the refusals exact. The subject is read
    first, from the declared store or from the one local file `--draft` names,
    because there is nothing to refuse about a ticket nobody found. Then the
    brief's gate — an open ticket — which is about this ticket alone and is
    answered before anything is judged. Then `check`, whose ERRORs on this ticket
    are a refusal, so nothing below names a citation that does not resolve. Only
    then is anything read to be named.

    What this run reads, it reads once. The store read for the subject and the
    claims plan loaded for the checks are handed to `check_loaded` rather than
    read again: two readings of one input are two answers to one question, and
    where `--input -` names a stream the second answer is that the export is
    empty.

    It returns the text where every other verb returns a `Report`, so that
    the bytes are testable without capturing a stream, and it writes nothing: no
    file, no cache, no record.
    """

    root = Path(target)
    subject = read_subject(root, declaration, options, _USE)
    refuse_closed(subject.ticket, _USE)
    plan = load_claims(root, declaration)
    refuse_findings(root, declaration, options, subject, plan, _USE)
    detail = getattr(options, "detail", None) or "plain"
    return _document(_compile(root, declaration, subject, plan), detail)
