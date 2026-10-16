"""`outcomebound <verb> ...`: the one table from each verb to the module that runs it.

The launcher runs this module isolated (`python -I -X utf8`): `scripts/outcomebound` in a
checkout, the package's console entry point (`launcher.py`) once installed. `home` prints where
the engine's own files are; every other verb runs its module as `__main__`, with the module's
name as `argv[0]`.

Every verb's text leaves as UTF-8 with LF line endings, whatever the platform's console code
page and newline are, so a script, a path or a JSON document the engine prints reads the same
through a pipe or a redirect everywhere. A word this table cannot run, or no word, exits 1,
never 2: a harness's stop hook reads exit 2 as holding the turn.
"""

from __future__ import annotations

import runpy
import sys

from outcomebound_tools import home

VERBS = {
    "adopt": "adopt",
    "tickets": "tickets",
    "brief": "decision_brief",
    "floor": "floor",
    "validation": "validation",
    "fragments": "fragments",
    "discovery": "discovery",
    "instructions": "instruction_audit",
    "finish-check": "finish_check",
    "research": "research",
    "sources": "sources",
    "review": "review_check",
    "explorable": "explorable",
    "scaffold": "scaffold",
}
USAGE = (
    "usage: outcomebound <verb> [argument ...]\nverbs: home version "
    + " ".join(VERBS)
    + "\nPrinted commands use POSIX shell syntax; on Windows they use PowerShell syntax."
)


# A word an agent tries that is no verb, and the verb that does what it meant.
HINTS = {
    "claims": "`outcomebound tickets check` reports a ticket's claims; "
    "`outcomebound floor check . --claim NAME` runs one floor claim",
    "check": "`outcomebound tickets check`, `floor check` and `instructions check` are the checks",
}


def version() -> str:
    """The engine's version, from the VERSION file beside the engine's own files."""

    try:
        return (home.ROOT / "VERSION").read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


def _utf8_lf_streams() -> None:
    """Make stdout and stderr UTF-8 with LF line ends. Each keeps its own error handler."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors=stream.errors, newline="\n")


def main(argv: list[str] | None = None) -> int:
    _utf8_lf_streams()
    arguments = sys.argv[1:] if argv is None else argv
    verb = arguments[0] if arguments else ""
    if verb == "home":
        if arguments[1:] in (["-h"], ["--help"]):
            print("usage: outcomebound home\nPrint the folder holding the engine's own files.")
        else:
            print(home.ROOT)
        return 0
    if verb in ("--version", "-V", "version"):
        print(f"outcomebound {version()}\nengine files: {home.ROOT}")
        return 0
    if verb in ("-h", "--help"):
        print(USAGE)
        return 0
    if verb not in VERBS:
        print(USAGE, file=sys.stderr)
        if verb in HINTS:
            print(f"no verb `{verb}`: {HINTS[verb]}", file=sys.stderr)
        return 1
    module = VERBS[verb]
    sys.argv = [module, *arguments[1:]]
    runpy.run_module(f"outcomebound_tools.{module}", run_name="__main__", alter_sys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
