"""The `outcomebound` command of an installed package: its console entry point.

pip and uv make `[console_scripts] outcomebound = _outcomebound_launch:main` a program that runs
the Python of the environment that holds the engine: a script in `bin/` on POSIX, an `.exe` in
`Scripts\\` on Windows. So the command finds its engine without a link or a neighbour to follow,
and it is the one `outcomebound` in that folder. `main` runs that Python again, isolated, as
`python -I -X utf8 -m outcomebound_tools <arguments>`: `-I` leaves the caller's folder and
PYTHONPATH off the engine's path, and `-X utf8` makes the engine's text UTF-8 whatever the console's
code page is. Nothing is exported, so a command the engine runs gets the caller's environment
unchanged.

The engine runs as a child process on every platform, and this process returns its exit code.
Windows has no call that replaces a process, and a harness that waits for a hook would see the
hook end at once if the parent did. POSIX could replace the process (`os.execv`), but the
quality floor's S606 rule flags that call and a change to the floor is a maintainer's act, so one
path serves both. While the child runs, Ctrl-C is left to the child, which the console sends it
as well, and SIGTERM is passed on to it; a child that a signal ended gives 128 plus the signal
number, as a shell reports it.

The wheel ships this file as the top-level module `_outcomebound_launch`, not inside
`outcomebound_tools`: a folder on PYTHONPATH that holds an `outcomebound_tools` of its own then
cannot take the first hop. What remains is a module of that exact name on PYTHONPATH, which only
the caller's own environment can place. The entry point's own folder is first on `sys.path`, not
the caller's.

Standard library only, and no OutcomeBound import: it runs before the engine's path is set.
An engine that cannot start exits 127, never 2, which a harness's stop hook reads as holding the
turn.
"""

from __future__ import annotations

import signal
import subprocess
import sys
from collections.abc import Sequence

NOT_STARTED = 127  # the exit code of a shell that finds no command to run
SIGNALLED = 128  # a shell's exit code for a child that a signal ended, plus the signal number


def command(arguments: Sequence[str]) -> list[str]:
    """The engine's command line: this environment's Python, isolated, UTF-8."""

    return [sys.executable, "-I", "-X", "utf8", "-m", "outcomebound_tools", *arguments]


def _run(argv: list[str]) -> int:
    """Run `argv` to its end and return its exit code."""

    process = subprocess.Popen(argv)
    handled = (signal.SIGINT, signal.SIGTERM)
    before = [
        signal.signal(signal.SIGINT, signal.SIG_IGN),
        signal.signal(signal.SIGTERM, lambda number, frame: process.send_signal(number)),
    ]
    try:
        code = process.wait()
    finally:
        for number, handler in zip(handled, before, strict=True):
            signal.signal(number, handler)
    return SIGNALLED - code if code < 0 else code


def main(arguments: Sequence[str] | None = None) -> int:
    given = sys.argv[1:] if arguments is None else arguments
    if not sys.executable:
        print("outcomebound: this Python does not name its own file", file=sys.stderr)
        return NOT_STARTED
    argv = command(given)
    try:
        return _run(argv)
    except OSError as error:
        print(f"outcomebound: cannot start the engine with {argv[0]}: {error}", file=sys.stderr)
        return NOT_STARTED
