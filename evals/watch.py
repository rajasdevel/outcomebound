"""What the runner watches while a call runs: the call's own process, and the paths it protects.

`watched_command` runs a command as `processes.bounded_command` does, and in the same loop asks a
caller's `poll` about once a second whether to stop it (the budget stop reads the tool's native
session there); a stop, or the time running out, ends the command's whole process tree.

`Watcher` hashes each watched path of a workspace about once a second while a call runs and
appends one JSON line to a run-owned log for each change it sees: a write the model makes and
undoes before the call ends is still seen, where it lasts longer than one sample. A change that
is undone within one second can be missed.

Standard library only; no model policy lives here.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

# How often a watched call's poll runs and a watched path is hashed, in seconds.
POLL_SECONDS = 1.0
# How long a stopped command's pipes are read after its tree is ended.
DRAIN_SECONDS = 2.0


class Watched(NamedTuple):
    """One watched command: its exit status (None where it was stopped or did not finish), what
    it printed, why it was stopped (`timeout`, a reason `poll` gave, or None) and its seconds."""

    returncode: int | None
    stdout: str
    stderr: str
    stopped: str | None
    seconds: float


def _end(process: subprocess.Popen[bytes]) -> None:
    """End the command and everything it started, and reap it."""

    from evals.processes import stop_descendants
    from outcomebound_tools.programs import stop_tree

    stop_descendants(process.pid)
    stop_tree(process)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=5)


def _drain(stream: Any, into: bytearray, lock: threading.Lock) -> None:
    """Read `stream` to its end into `into`."""

    while True:
        try:
            chunk = os.read(stream.fileno(), 65536)
        except (OSError, ValueError):
            return
        if not chunk:
            return
        with lock:
            into.extend(chunk)


def _feed(stream: Any, data: bytes) -> None:
    """Write `data` to the command's stdin and close it; a command that exits without reading
    it all is not an error."""

    with contextlib.suppress(OSError, ValueError):
        stream.write(data)
    with contextlib.suppress(OSError, ValueError):
        stream.close()


class _Pipes:
    """The threads that read a command's stdout and stderr to their end, and feed its stdin."""

    def __init__(self, process: subprocess.Popen[bytes], input: str | None) -> None:
        self.lock = threading.Lock()
        self.out, self.error = bytearray(), bytearray()
        self.readers = [
            threading.Thread(target=_drain, args=(stream, into, self.lock), daemon=True)
            for stream, into in ((process.stdout, self.out), (process.stderr, self.error))
        ]
        for reader in self.readers:
            reader.start()
        if input is not None:
            feeder = threading.Thread(target=_feed, args=(process.stdin, input.encode()))
            feeder.daemon = True
            feeder.start()

    def printed(self) -> str:
        with self.lock:
            return self.out.decode("utf-8", "replace")

    def join(self, seconds: float) -> bool:
        """Wait up to `seconds` for both pipes to end; whether they did."""

        deadline = time.monotonic() + seconds
        for reader in self.readers:
            reader.join(max(deadline - time.monotonic(), 0))
        return not any(reader.is_alive() for reader in self.readers)


def _watch(
    process: subprocess.Popen[bytes],
    pipes: _Pipes,
    deadline: float,
    poll: Callable[[Callable[[], str]], str | None] | None,
    interval: float,
) -> str | None:
    """Wait for the command to end, asking `poll` once an `interval`; the reason to stop it,
    or None where it ended by itself."""

    while process.poll() is None:
        left = deadline - time.monotonic()
        if left <= 0:
            return "timeout"
        reason = poll(pipes.printed) if poll is not None else None
        if reason:
            return reason
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=min(interval, max(left, 0.01)))
    # A process outside the reaped one may hold the pipes: it has until the deadline.
    return None if pipes.join(deadline - time.monotonic()) else "timeout"


def watched_command(
    command: list[str],
    *,
    timeout: float,
    input: str | None = None,
    poll: Callable[[Callable[[], str]], str | None] | None = None,
    interval: float = POLL_SECONDS,
    **kwargs: Any,
) -> Watched:
    """Run `command` for at most `timeout` seconds, asking `poll` about once an `interval`
    whether to stop it.

    `poll` gets a function that returns the stdout printed so far, and returns the reason to
    stop or None. A stop, or the time running out (`timeout`), ends the command's process tree
    and keeps what it printed. A command that ended by itself and left a process that holds its
    pipes open is waited for until the time runs out, then ended as a `timeout`, as
    `bounded_command` does. Raises what starting the command raises."""

    from outcomebound_tools.programs import start_tree

    started = time.monotonic()
    process = start_tree(
        command,
        stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )
    pipes = _Pipes(process, input)
    try:
        stopped = _watch(process, pipes, started + timeout, poll, interval)
    except BaseException:
        _end(process)
        raise
    if stopped:
        _end(process)
    pipes.join(DRAIN_SECONDS)
    for stream in (process.stdout, process.stderr):
        with contextlib.suppress(OSError):
            if stream is not None:
                stream.close()
    with pipes.lock:
        stdout = pipes.out.decode("utf-8", "replace")
        stderr = pipes.error.decode("utf-8", "replace")
    code = None if stopped else process.returncode
    return Watched(code, stdout, stderr, stopped, round(time.monotonic() - started, 1))


def path_digest(path: Path) -> str | None:
    """The SHA-256 of the file at `path`, or None where there is no file to read."""

    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


class Watcher:
    """A thread that hashes each of `paths` (relative to `root`) about once an `interval` while
    it is entered, and appends `{"t": seconds, "path": rel, "sha256": hex or null}` to the new
    file `log` for each change from the last digest seen; a missing file is null. The digests
    taken on entry are the baseline and are not logged; on exit it looks once more, so a change
    the call left at its end is logged. `changes` counts the lines written."""

    def __init__(
        self, root: Path, paths: tuple[str, ...], log: Path, interval: float = POLL_SECONDS
    ) -> None:
        self.root, self.paths, self.log, self.interval = root, paths, log, interval
        self.changes = 0
        self._last: dict[str, str | None] = {}
        self._started = 0.0
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> Watcher:
        with self.log.open("x", encoding="utf-8"):
            pass
        self._last = {path: path_digest(self.root / path) for path in self.paths}
        self._started = time.monotonic()
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._done.set()
        self._thread.join()
        self.sample()

    def _run(self) -> None:
        while not self._done.wait(self.interval):
            self.sample()

    def sample(self) -> None:
        """Hash each path once and log each that changed since the last look."""

        lines = []
        for path in self.paths:
            digest = path_digest(self.root / path)
            if digest != self._last[path]:
                self._last[path] = digest
                seconds = round(time.monotonic() - self._started, 2)
                lines.append(json.dumps({"t": seconds, "path": path, "sha256": digest}))
        if lines:
            with self.log.open("a", encoding="utf-8") as handle:
                handle.write("".join(f"{line}\n" for line in lines))
            self.changes += len(lines)
