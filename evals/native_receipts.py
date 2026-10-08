"""Retain the exact native session for one explicit evaluation, without grading its meaning.

A native receipt is separate from the CLI command transcript. Missing model or cwd evidence
in that transcript stays missing. This module never interprets arbitrary tool code.
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


def _thread_id(stdout: str) -> str:
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


def retain(transcript: str, capture: NativeCapture) -> dict[str, Any]:
    """Copy a unique matching native record, with its digest, outside the model workspace.

    The caller owns destination and must not grant it as a model writable root. Exact bytes
    and session identity are checked here; identity, tool links and behavior need review.
    """

    result: dict[str, Any] = {
        "exact_session_copy": "UNVERIFIED",
        "identity_qualification": "UNVERIFIED",
        "sequence_qualification": "UNVERIFIED",
        "behavioral_verdict": "UNVERIFIED",
    }
    sessions, destination = capture
    try:
        document = json.loads(transcript)
        if (
            not isinstance(document, dict)
            or document.get("format") != "outcomebound-command-events-v1"
            or not isinstance(document.get("stdout"), str)
        ):
            raise ValueError("CLI transcript has no original event stream")
        key = _thread_id(document["stdout"])
        result["thread_id"] = key
        matches = list(sessions.rglob(f"*-{key}.jsonl"))
        if len(matches) != 1:
            raise ValueError(f"matching native session count is {len(matches)}, expected 1")
        source = matches[0]
        if source.is_symlink() or not source.resolve().is_relative_to(sessions.resolve()):
            raise ValueError("native session is a symlink or outside the selected sessions folder")
        raw = source.read_bytes()
        lines = [line for line in raw.decode("utf-8").splitlines() if line.strip()]
        first = json.loads(lines[0])
        if not isinstance(first, dict) or first.get("type") != "session_meta":
            raise ValueError("native session has no initial session_meta")
        payload = first.get("payload")
        if not isinstance(payload, dict) or payload.get("id") != key:
            raise ValueError("native session identity differs from the actual CLI thread id")
        with destination.open("xb") as handle:
            handle.write(raw)
        if source.read_bytes() != raw or destination.read_bytes() != raw:
            raise ValueError("native session changed during retention")
        result.update(
            exact_session_copy="PASS",
            source=str(source),
            destination=str(destination),
            sha256=hashlib.sha256(raw).hexdigest(),
        )
    except (OSError, ValueError, IndexError) as error:
        result["error"] = f"{type(error).__name__}: {error}"
    return result
