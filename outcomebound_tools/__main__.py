"""`outcomebound <verb> ...`: the one table from each verb to the module that runs it.

The launcher, `scripts/outcomebound`, runs this module isolated (`python -I`), from a checkout
or from an installed package. `home` prints where the engine's own files are; every other verb
runs its module as `__main__`, with the module's name as `argv[0]`.
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
}
USAGE = "usage: outcomebound <verb> [argument ...]\nverbs: home " + " ".join(VERBS)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    verb = arguments[0] if arguments else ""
    if verb == "home":
        if arguments[1:] in (["-h"], ["--help"]):
            print("usage: outcomebound home\nPrint the folder holding the engine's own files.")
        else:
            print(home.ROOT)
        return 0
    if verb in ("-h", "--help"):
        print(USAGE)
        return 0
    if verb not in VERBS:
        print(USAGE, file=sys.stderr)
        return 2
    module = VERBS[verb]
    sys.argv = [module, *arguments[1:]]
    runpy.run_module(f"outcomebound_tools.{module}", run_name="__main__", alter_sys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
