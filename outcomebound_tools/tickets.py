"""`outcomebound tickets <verb>`: the ticket engine's command line.

What this module decides: the two verbs, every option's name and default,
which stream a report and a refusal reach, and the exit code of the process. A
verb reads `options` and parses nothing.

It loads the project's declaration before any verb runs, so every verb
refuses an undeclared or misdeclared project alike and none loads it again.

What it does not decide: anything a verb does. It holds no ticket logic: a verb
returns a `Report`, this module renders it as text or as JSON and returns the
report's own exit code; `brief` alone returns its document's text. A verb that
stops instead raises, and the exception says which exit it carries: a `Refusal`
is one named line and exit 1, a `PlanningError` one named line and exit 2.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from outcomebound_tools.tickets_brief import brief
from outcomebound_tools.tickets_check import check
from outcomebound_tools.tickets_declaration import Declaration, load_declaration
from outcomebound_tools.tickets_report import (
    EngineError,
    PlanningError,
    Refusal,
    Report,
    exit_code,
    render_json,
    render_text,
)

__all__ = ["VERBS", "build_parser", "main"]

# The one signature every verb has. The declaration is loaded here, once,
# before any verb runs, so a project that declares no store is refused the
# same way by every verb.
VerbFunction = Callable[[Path, Declaration, argparse.Namespace], "Report | str"]


# One row per verb, in the order the command line lists them.
VERBS: Mapping[str, VerbFunction] = MappingProxyType(
    {
        "check": check,
        "brief": brief,
    }
)


def _check_options(command: argparse.ArgumentParser) -> None:
    """`check [--draft <file>…]`."""

    command.add_argument(
        "--draft",
        metavar="FILE",
        nargs="+",
        action="extend",
        help="lint these local files as drafts instead of reading the declared store",
    )


def _check_usage(options: argparse.Namespace) -> str:
    """A draft run reads no store, so an export is nothing it could read."""

    if options.draft and options.input is not None:
        return "--draft lints local files and reads no store, so it cannot be given with --input"
    return ""


def _brief_options(command: argparse.ArgumentParser) -> None:
    """`brief <ticket> [--draft <file>] [--detail plain|full]`.

    One file, where `check` takes many: a brief is one document about one
    ticket. The id is named beside it, because a draft's id is its file name
    without the extension and a brief headed with another id would be a
    document about the wrong work.
    """

    command.add_argument("ticket", help="the ticket whose brief to compile")
    command.add_argument(
        "--draft",
        metavar="FILE",
        nargs="+",
        action="extend",
        help="compile the draft among these local files whose name is the ticket named, "
        "instead of reading the declared store; the others are the breakdown it belongs to",
    )
    command.add_argument(
        "--detail",
        choices=("plain", "full"),
        default="plain",
        help="full adds `## Steps` after `## Bounds`: the same facts as numbered steps, "
        "each with its exact command",
    )


def _brief_usage(options: argparse.Namespace) -> str:
    """A draft run reads no store, so an export is nothing it could read."""

    if options.draft and options.input is not None:
        return (
            "--draft compiles a local file and reads no store, so it cannot be given with --input"
        )
    return ""


@dataclass(frozen=True, slots=True)
class _Surface:
    """What one verb's parser offers, in one row.

    `prints_report`: `check` prints a report, and `brief` prints a document.
    `own` adds the arguments one verb alone takes; it runs before the shared
    options are added, so one that names a shared option is argparse's own
    error when the parser is built, not a quiet shadow.

    `usage` is a combination of one verb's own options and a shared one that
    argparse cannot express as a group. It returns the sentence that verb's own
    parser prints, or the empty string, so a usage error stays the parser's and
    never becomes a refusal raised from inside a run.

    `epilog` is what the verb's `--help` says after its options: what it reads
    beyond the export, and its exits.
    """

    summary: str
    own: Callable[[argparse.ArgumentParser], None]
    usage: Callable[[argparse.Namespace], str]
    epilog: str
    prints_report: bool = True


# A report's exits; a usage error is argparse's 2.
_EXITS = "Exits: 0 PASS; 1 FAIL or a refusal; 2 UNVERIFIED, a planning error or a usage error."

_ROWS: Mapping[str, _Surface] = {
    "check": _Surface(
        "read the declared store's open tickets, or local drafts, and report what they say",
        own=_check_options,
        usage=_check_usage,
        epilog=_EXITS,
    ),
    "brief": _Surface(
        "print one ticket's brief as a document; write nothing",
        own=_brief_options,
        usage=_brief_usage,
        epilog="Exits: 0 the brief printed; 1 a refusal; 2 a planning error or a usage error.",
        prints_report=False,
    ),
}

# The rows, paired with the verbs at import: a verb with no row is an error
# when this module loads, never a verb whose parser quietly offers it nothing.
_SURFACE: Mapping[str, _Surface] = MappingProxyType({name: _ROWS[name] for name in VERBS})


# The generic options' defaults, given to every verb whether or not it offers
# the option.
_DEFAULTS: Mapping[str, object] = MappingProxyType({"input": None, "json": False})


class _CommandLine(argparse.ArgumentParser):
    """The module's parser, with each verb's own subparser kept beside it.

    A usage error one verb's row refuses is printed by that verb's subparser, so
    the usage line names the verb and what it takes rather than the module and
    its verbs. argparse offers no way back from a parsed namespace to the
    subparser that filled it, so the mapping is carried here.
    """

    verbs: Mapping[str, argparse.ArgumentParser] = MappingProxyType({})


def build_parser() -> _CommandLine:
    """The command line: the verbs, and every option's name and default."""

    parser = _CommandLine(
        prog="outcomebound tickets",
        description="Report what a project's tickets say, offline and without credentials",
    )
    commands = parser.add_subparsers(dest="verb", required=True)
    verbs: dict[str, argparse.ArgumentParser] = {}
    for name, surface in _SURFACE.items():
        command = commands.add_parser(name, help=surface.summary, epilog=surface.epilog)
        verbs[name] = command
        command.add_argument(
            "target",
            nargs="?",
            default=".",
            help="the checkout to read (default: the current directory)",
        )
        # The verb's own arguments come next, so its positionals follow the
        # target in the order a person types them.
        surface.own(command)
        command.add_argument(
            "--input",
            metavar="FILE",
            help="the tracker export to read; `-` is standard input",
        )
        if surface.prints_report:
            command.add_argument(
                "--json", action="store_true", help="print one JSON object instead of text"
            )
        # An option a verb does not offer is still refused on the command line,
        # and still has its default in the namespace: `options` is total, so a
        # verb that reads `options.input` never meets a missing attribute.
        command.set_defaults(**_DEFAULTS)
    parser.verbs = MappingProxyType(verbs)
    return parser


# What a verb that stopped exits with: a refusal is a failure, a run that
# could not be planned is missing evidence. One row per exception, and one
# handler below, so the line and the stream are written once.
_EXIT_BY_STOP: Mapping[type[Refusal | PlanningError], int] = MappingProxyType(
    {Refusal: 1, PlanningError: 2}
)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one verb and return the process's exit code (0, 1 or 2)."""

    parser = build_parser()
    options = parser.parse_args(argv)
    # A verb's own usage rule, from its row above, printed by that verb's own
    # parser: one line of argparse's own and exit 2, never a refusal raised from
    # inside a run.
    refused = _SURFACE[options.verb].usage(options)
    if refused:
        parser.verbs[options.verb].error(refused)
    try:
        target = Path(options.target)
        declaration = load_declaration(target)
        outcome = VERBS[options.verb](target, declaration, options)
    except (Refusal, PlanningError) as stopped:
        sys.stderr.write(f"{stopped.code}: {stopped.text}\n")
        return _EXIT_BY_STOP[type(stopped)]
    except EngineError as could_not:
        # The engine could not act. The module's own sentence is the line.
        sys.stderr.write(f"ENGINE_ERROR: {could_not}\n")
        return 1
    if isinstance(outcome, str):
        # `brief` prints its document and nothing else.
        sys.stdout.write(outcome)
        return 0
    sys.stdout.write(render_json(outcome) if options.json else render_text(outcome))
    return exit_code(outcome)


if __name__ == "__main__":
    raise SystemExit(main())
