"""The `verify` verb: run the claims one ticket's `done-when` names, and say what each read.

What this module decides: which claims run (those the ticket names, found in the claims plan
the declaration names, and no other); that a name the plan does not define stops the verb
before any command runs; that the ticket requires every claim it names, whatever the plan's
`required` says; that a person's check is printed `UNVERIFIED` and run by nobody; and how the
run reads as one `VERDICT` line and an exit code.

What it does not decide: how a claim runs or is judged, and what is kept of an attempt. That is
`validation.run_plan` and `validation_record`, the runner of `outcomebound validation`; this
module has none of its own. Which ticket is meant, and whether it is open and well formed, is
`tickets_subject`'s, the reading `brief` shares.

**No ticket text is executed.** A ticket contributes names. The commands are the plan's, which
the repository committed, run as `outcomebound validation` runs them and under the same trust
rule: a plan is executable code.

It writes only what the runner writes: a record and an output for each attempt of each claim,
beside the plan's checks folder. It reads no clock and prints nothing until every claim has run.
"""

from __future__ import annotations

import argparse
import dataclasses
import os.path
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from outcomebound_tools import validation
from outcomebound_tools.tickets_claims import load_claims
from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_model import DoneWhen
from outcomebound_tools.tickets_report import PlanningError, Refusal
from outcomebound_tools.tickets_subject import (
    Use,
    read_subject,
    refuse_closed,
    refuse_findings,
)

__all__ = ["Verified", "verify"]

# What `verify` says when it refuses a ticket.
_USE = Use(
    code="VERIFY_REFUSED",
    from_file="a verify runs the checks that the file names and no other",
    to_act="verify",
    from_ticket="a verify runs the checks of the ticket it names and of no other",
    closed=(
        "only the checks of work that is still open are run; read the ticket itself for "
        "what was done"
    ),
    stopped="so none of its checks is run",
    again="verify it again",
)

# The results in the order a count line lists them.
_ORDER = (validation.PASSED, validation.FAIL, validation.UNVERIFIED)


@dataclass(frozen=True, slots=True)
class Verified:
    """What a run printed and what it exits with: the text, then the code of its verdict.

    A verb that runs commands has a verdict in the validation sense, which `Report` (a
    finding about tickets) does not carry, so the command line prints `text` and exits `code`.
    """

    text: str
    code: int


def _names(items: Iterable[DoneWhen]) -> tuple[str, ...]:
    """The claims a ticket names, in the order it writes them. `check` gives an ERROR for a name
    written twice, which stops the verb before this is read."""

    return tuple(item.claim for item in items if not item.human)


def _persons(items: Iterable[DoneWhen]) -> tuple[DoneWhen, ...]:
    """The checks a person makes, which no command settles."""

    return tuple(item for item in items if item.human)


def _inside(root: Path, declaration: Declaration) -> None:
    """The plan's commands run inside the checkout, since this verb runs them."""

    plan = load_claims(root, declaration)
    if not plan.cwd_inside:
        where = Path(os.path.relpath(plan.cwd_resolved, root.resolve())).as_posix()
        raise Refusal(
            _USE.code,
            f"the claims plan {declaration.claims} runs its claims in {where}, outside this "
            "checkout; verify runs the plan's commands, so it runs them only inside the "
            "checkout; set the plan's `cwd` to a folder of the checkout",
        )


def _plan(root: Path, declaration: Declaration) -> validation.Plan:
    """The plan as `outcomebound validation` loads it, or the planning error it reports."""

    try:
        return validation.load_plan(root / declaration.claims)
    except validation.PlanError as error:
        raise PlanningError(
            "PLAN_INVALID",
            f"the claims plan {declaration.claims} cannot be run: {error}; nothing was run, "
            "and `outcomebound validation` reports the same",
        ) from error


def _undefined(
    names: Iterable[str], plan: validation.Plan, declaration: Declaration, id: str
) -> None:
    """A name the plan does not define stops the run before any command starts."""

    defined = {claim.name for claim in plan.claims}
    missing = [name for name in names if name not in defined]
    if missing:
        raise PlanningError(
            "CLAIM_MISSING",
            f"{id} names {', '.join(missing)} in done-when, which the claims plan "
            f"{declaration.claims} does not define; nothing was run, because a part of the "
            "checks is no result for the ticket; add the claim to the plan, or correct the "
            "ticket's name for it",
        )


def _required(results: Iterable[validation.Result]) -> tuple[validation.Result, ...]:
    """Each result as the ticket reads it: the ticket requires every claim it names."""

    return tuple(
        dataclasses.replace(result, claim=dataclasses.replace(result.claim, required=True))
        for result in results
    )


def _person_line(item: DoneWhen) -> str:
    return (
        f"{validation.UNVERIFIED} {item.claim} [person's check] — {item.human}; "
        "no command settles it, so verify ran nothing for it\n"
    )


def _verdict(results: tuple[validation.Result, ...], persons: int) -> str:
    """`validation`'s verdict over the claims run; a person's check keeps it from `PASS`."""

    status = validation.verdict(results)
    return validation.UNVERIFIED if persons and status == validation.PASSED else status


def _counts(results: tuple[validation.Result, ...], persons: int) -> str:
    seen = [result.status for result in results] + [validation.UNVERIFIED] * persons
    return ", ".join(f"{seen.count(name)} {name}" for name in _ORDER if name in seen)


def verify(target: Path, declaration: Declaration, options: argparse.Namespace) -> Verified:
    """Run the claims the named ticket's `done-when` names, and return what they read.

    The order of the run keeps each refusal exact. The ticket is found and must be open
    and free of ERRORs from `check`, as for `brief`; the plan must run inside the checkout
    and load as `outcomebound validation` loads it; and every name must be defined, all
    before any command starts. Then the claims run in plan order through `run_plan`, which
    keeps a record of each attempt.
    """

    root = Path(target)
    subject = read_subject(root, declaration, options, _USE)
    ticket = subject.ticket
    refuse_closed(ticket, _USE)
    claims = load_claims(root, declaration)
    refuse_findings(root, declaration, options, subject, claims, _USE)
    _inside(root, declaration)
    plan = _plan(root, declaration)
    names = _names(ticket.done_when)
    _undefined(names, plan, declaration, ticket.id)
    persons = _persons(ticket.done_when)
    results = _required(validation.run_plan(plan, frozenset(names), keep=True)) if names else ()
    status = _verdict(results, len(persons))
    text = validation.render_results(results) + "".join(map(_person_line, persons))
    text += f"VERDICT: {status} (done-when of {ticket.id}: {_counts(results, len(persons))})\n"
    return Verified(text, validation.exit_code(status))
