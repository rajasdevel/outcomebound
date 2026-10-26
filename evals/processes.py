"""Bounded subprocesses for evaluation setup, calls and checks. No model policy lives here."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


def _process_table() -> dict[int, tuple[int, str]] | None:
    """Every process of the host with its parent and the first letter of its state (`T` or `t`
    for stopped, `Z` for exited), or None where the table cannot be read."""

    table: dict[int, tuple[int, str]] = {}
    if Path("/proc/self/stat").is_file():
        # Linux slim images need no external ps package for their process table.
        for entry in Path("/proc").iterdir():
            if entry.name.isdigit():
                try:
                    fields = (entry / "stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()
                    table[int(entry.name)] = (int(fields[1]), fields[0][:1])
                except (OSError, ValueError, IndexError):
                    continue  # A process can exit while the table is read.
        return table
    try:
        listed = subprocess.run(
            ["ps", "-e", "-o", "pid=", "-o", "ppid=", "-o", "stat="],
            capture_output=True,
            text=True,
            timeout=1,
            encoding="utf-8",
        )
        return {
            int(row.split()[0]): (int(row.split()[1]), row.split()[2][:1])
            for row in listed.stdout.splitlines()
            if len(row.split()) == 3
        }
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def stop_descendants(pid: int) -> None:
    """Stop the task's current POSIX descendants before their parent is reaped.

    A subprocess can start a separate session. The existing process-group stop
    cannot reach it. Use the host process table only on timeout, with a bounded
    read; Windows is already covered by the existing taskkill tree helper.

    The command and each descendant are suspended (SIGSTOP) as the table shows them, and the
    table is read again until it shows none new and every suspended process stopped, and only
    then are the descendants killed. A process that is running forks while the table is read,
    or while the scan waits for the CPU on a loaded machine, and a child made after the read would
    outlive the kill. A suspended process makes none, but SIGSTOP takes hold only when the
    process next leaves the kernel: one inside `fork` finishes it first, so a read made before the
    stop shows can miss that child. The loop ends on two such reads in a row, as one read can skip
    an entry it could not read at that moment. The command itself is killed by the caller afterwards
    (SIGKILL ends a suspended process). Left open: a descendant that exits between two reads, with
    a child made in that time, leaves a child the table no longer ties to the command.
    """

    import contextlib
    import signal

    if os.name == "nt":
        return

    def suspend(target: int) -> None:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(target, signal.SIGSTOP)

    owned = {pid}
    try:
        suspend(pid)
        # Bounded: a descendant that cannot be suspended (another user's) may keep forking.
        quiet = 0
        for _read in range(256):
            table = _process_table()
            if table is None:
                break
            found = set(owned)
            while more := {c for c, (parent, _) in table.items() if parent in found} - found:
                found |= more
            # A process the table no longer holds, or holds as exited, makes no child.
            settled = all(table.get(each, (0, "Z"))[1] in "TtZ" for each in owned)
            # Two quiet reads in a row: an entry that one read could not read is in the next.
            quiet = quiet + 1 if found <= owned and settled else 0
            if quiet == 2:
                break
            for child in found - owned:
                suspend(child)
            owned |= found
    finally:
        for child in owned - {pid}:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(child, signal.SIGKILL)


def bounded_command(
    command: list[str], *, timeout: float, input: str | None = None, **kwargs: Any
) -> subprocess.CompletedProcess[str]:
    """Keep partial output on timeout and stop the command's process group."""

    from outcomebound_tools.programs import start_tree, stop_tree

    process = start_tree(
        command,
        stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )
    try:
        out, error = process.communicate(input.encode() if input is not None else None, timeout)
    except subprocess.TimeoutExpired as timed_out:
        stop_descendants(process.pid)
        stop_tree(process)
        try:
            out, error = process.communicate(timeout=1)
        except subprocess.TimeoutExpired as remaining:
            # A detached/reparented writer is outside the observed process tree.
            # Preserve its partial output without waiting forever on its pipe.
            out, error = remaining.output or timed_out.output or b"", remaining.stderr or b""
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

        raise subprocess.TimeoutExpired(
            command,
            timeout,
            output=out.decode("utf-8", "replace"),
            stderr=error.decode("utf-8", "replace"),
        ) from None
    except BaseException:
        stop_descendants(process.pid)
        stop_tree(process)
        process.wait(timeout=1)
        raise
    return subprocess.CompletedProcess(
        command,
        process.returncode,
        out.decode("utf-8", "replace"),
        error.decode("utf-8", "replace"),
    )


def partial_output(problem: BaseException) -> str:
    """Readable partial process evidence, when an exception carries it."""

    def text(value: str | bytes | None) -> str:
        return value.decode("utf-8", "replace") if isinstance(value, bytes) else value or ""

    return text(getattr(problem, "output", None)) + text(getattr(problem, "stderr", None))
