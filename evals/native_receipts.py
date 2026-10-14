"""Find, read and copy the native session a Codex call wrote, outside the model's reach.

The CLI's own `--json` stream does not name the model, effort or working directory of a call
(codex-cli 0.162.1), so a run takes them from the session record the CLI keeps under its home.
The record is found by the stream's thread id, never by recency, and is checked before it is
trusted. Nothing here interprets a tool call: it reads identity only.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, NamedTuple


class NativeCapture(NamedTuple):
    """Two operator-owned paths; neither grants a model access to its retained evidence."""

    sessions: Path
    destination: Path

    def check_roots(self, roots: tuple[Path, ...]) -> None:
        roots = (*roots, *temporary_write_roots())
        if any(
            self.sessions.resolve().is_relative_to(root.resolve())
            or root.resolve().is_relative_to(self.sessions.resolve())
            for root in roots
        ):
            raise ValueError("native sessions directory overlaps a model writable root")
        if any(self.destination.resolve().is_relative_to(root.resolve()) for root in roots):
            raise ValueError("native receipt destination is inside a model writable root")


def temporary_write_roots() -> tuple[Path, ...]:
    """Default workspace-write includes system temporary folders outside explicit roots."""

    roots = {Path(tempfile.gettempdir()).resolve()}
    if os.name != "nt":
        roots.add((Path("/") / "tmp").resolve())
    names = ("TMP", "TEMP") if os.name == "nt" else ("TMPDIR",)
    for name in names:
        value = os.environ.get(name)
        if value:
            if not Path(value).is_absolute():
                raise ValueError(
                    f"implicit temporary write root {name} is relative; use an absolute path"
                )
            roots.add(Path(value).resolve())
    return tuple(roots)


def thread_id(stdout: str) -> str:
    """The id of the stream's one `thread.started`, which must be its first event."""

    events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    if not events or not all(isinstance(event, dict) for event in events):
        raise ValueError("CLI events are not readable objects")
    starts = [event for event in events if event.get("type") == "thread.started"]
    if events[0].get("type") != "thread.started" or len(starts) != 1:
        raise ValueError("CLI events have no unique first thread.started")
    key = starts[0].get("thread_id")
    if not isinstance(key, str) or str(uuid.UUID(key)) != key:
        raise ValueError("CLI thread id is not a canonical UUID")
    return key


def find_session(sessions: Path, key: str) -> tuple[Path, bytes, list[dict[str, Any]]]:
    """The one session file for thread `key` under `sessions`, its exact bytes and its records.

    Exactly one file must match; it must not be a symlink or lie outside `sessions`; its first
    record must be a `session_meta` whose id is `key`. Otherwise ValueError says which."""

    matches = list(sessions.rglob(f"*-{key}.jsonl"))
    if len(matches) != 1:
        raise ValueError(f"matching native session count is {len(matches)}, expected 1")
    source = matches[0]
    if source.is_symlink() or not source.resolve().is_relative_to(sessions.resolve()):
        raise ValueError("native session is a symlink or outside the selected sessions folder")
    raw = source.read_bytes()
    records = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    first = records[0] if records else None
    if not isinstance(first, dict) or first.get("type") != "session_meta":
        raise ValueError("native session has no initial session_meta")
    payload = first.get("payload")
    if not isinstance(payload, dict) or payload.get("id") != key:
        raise ValueError("native session identity differs from the actual CLI thread id")
    return source, raw, records


def copy_exact(source: Path, raw: bytes, destination: Path) -> str:
    """Write `raw` to a new `destination`, check both still hold the source's bytes, and give
    their SHA-256."""

    with destination.open("xb") as handle:
        handle.write(raw)
    if source.read_bytes() != raw or destination.read_bytes() != raw:
        raise ValueError("native session changed during retention")
    return hashlib.sha256(raw).hexdigest()
