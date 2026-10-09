"""Bounded subprocesses for evaluation setup, calls and checks. No model policy lives here."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


def stop_descendants(pid: int) -> None:
    """Stop the task's current POSIX descendants before their parent is reaped.

    A subprocess can start a separate session. The existing process-group stop
    cannot reach it. Use the host process table only on timeout, with a bounded
    read; Windows is already covered by the existing taskkill tree helper.
    """

    import contextlib
    import signal

    if os.name == "nt":
        return
    parents: dict[int, int] = {}
    if Path("/proc/self/stat").is_file():
        # Linux slim images need no external ps package for their process table.
        for entry in Path("/proc").iterdir():
            if entry.name.isdigit():
                try:
                    fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                    parents[int(entry.name)] = int(fields[1])
                except (OSError, ValueError, IndexError):
                    continue  # A process can exit while the table is read.
    else:
        try:
            listed = subprocess.run(
                ["ps", "-e", "-o", "pid=", "-o", "ppid="], capture_output=True, text=True, timeout=1
            )
            parents = {
                int(row.split()[0]): int(row.split()[1])
                for row in listed.stdout.splitlines()
                if len(row.split()) == 2
            }
        except (OSError, ValueError, subprocess.SubprocessError):
            return
    owned = {pid}
    for _ in range(len(parents)):
        found = {child for child, parent in parents.items() if parent in owned}
        if found <= owned:
            break
        owned |= found
    for child in owned - {pid}:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(child, signal.SIGKILL)


def bounded_command(
    command: list[str], *, timeout: float, input: str | None = None, **kwargs: Any
) -> subprocess.CompletedProcess[str]:
    """Keep partial output on timeout and stop the command's process group."""

    from outcomebound_tools.programs import new_group, stop_tree, track_tree

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **new_group(),
        **kwargs,
    )
    track_tree(process)
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
