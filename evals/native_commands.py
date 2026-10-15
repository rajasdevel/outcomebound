"""Working directories of a Codex call's commands, read from its native session.

The `--json` stream of codex-cli 0.162.1 gives each `command_execution` item a command string and
no working directory, and a command may run in a directory other than the session's (the exec
`workdir`). The native session the CLI keeps does give one for each command, in an
`item_completed` event of type `CommandExecution`: `command` is the argv list, `cwd` a
`file://` URI. This module sets those directories into the stream's command records, only where
the two lists match exactly. A directory is never taken from the session's own working directory
or from the request.

The stream's command string is the argv, shell-quoted; reading it back with `shlex.split` gives
the argv exactly, on every command of 29 recorded runs. That is the whole correspondence rule.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, NamedTuple
from urllib.parse import unquote, urlparse

from evals.codex_events import command_outcome

SOURCE_KEY = "command_cwd_source"
DISAGREE_KEY = "command_native_disagreements"


def native_commands(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The `CommandExecution` items of the session's `item_completed` events, in file order."""

    found = []
    for record in records:
        payload = record.get("payload") if record.get("type") == "event_msg" else None
        item = payload.get("item") if isinstance(payload, dict) else None
        if (
            isinstance(payload, dict)
            and payload.get("type") == "item_completed"
            and isinstance(item, dict)
            and item.get("type") == "CommandExecution"
        ):
            found.append(item)
    return found


def directory_of(value: Any) -> str:
    """The absolute path a `file://` URI (or an absolute path) names, or an empty string."""

    if not isinstance(value, str) or not value:
        return ""
    if "://" in value:
        parsed = urlparse(value)
        if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
            return ""
        value = unquote(parsed.path)
        # A Windows URI path keeps a slash before its drive: `file:///C:/work` names `C:/work`.
        if re.match(r"^/[A-Za-z]:[/\\]", value):
            value = value[1:]
    # The CLI and the runner share one machine, so the path is in that machine's form; either
    # form's absolute path is accepted, and nothing relative is.
    absolute = PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()
    return value if absolute else ""


def _pairs(streams: list[list[str]], natives: list[list[str]], cwds: list[str]):
    """For each stream command, the index of its native command and whether the pair is
    unambiguous; or None where the two lists do not match."""

    if streams == natives:
        return [(index, True) for index in range(len(streams))]
    if sorted(streams) != sorted(natives):
        return None
    # The stream lists commands as they start, the session as they complete, so calls that
    # overlapped come in another order. Matching by text is exact where a repeated command
    # has one directory throughout.
    place: dict[tuple[str, ...], list[int]] = {}
    for index, argv in enumerate(natives):
        place.setdefault(tuple(argv), []).append(index)
    if any(len({cwds[i] for i in indexes}) > 1 for indexes in place.values()):
        return None
    taken: dict[tuple[str, ...], int] = {}
    pairs = []
    for argv in streams:
        key = tuple(argv)
        number = taken.get(key, 0)
        taken[key] = number + 1
        pairs.append((place[key][number], len(place[key]) == 1))
    return pairs


class Match(NamedTuple):
    """A stream's command records set against the native session's items."""

    document: dict[str, Any]
    items: list[dict[str, Any]]
    pairs: list[tuple[int, bool]]
    cwds: list[str]


def _match(transcript: str, session: list[dict[str, Any]] | None) -> Match | str:
    """The match of the transcript's command records with the native session, or why they do
    not match."""

    if session is None:
        return "no native session was read"
    try:
        document = json.loads(transcript)
    except ValueError:
        document = None
    records = document.get("commands") if isinstance(document, dict) else None
    if not isinstance(records, list) or not all(
        isinstance(row, list) and len(row) == 3 for row in records
    ):
        return "the stream gives no command records"
    items = native_commands(session)
    if len(items) != len(records):
        return f"the stream has {len(records)} commands, the native session {len(items)}"
    argvs: list[list[str]] = []
    for item in items:
        argv = item.get("command")
        if not (isinstance(argv, list) and argv and all(isinstance(word, str) for word in argv)):
            return "a native command has no argv list"
        argvs.append(argv)
    cwds = [directory_of(item.get("cwd")) for item in items]
    if not all(cwds):
        return "a native command has no absolute working directory"
    try:
        streams = [shlex.split(row[0]) for row in records]
    except (ValueError, TypeError):
        return "a stream command is not shell-quoted text"
    pairs = _pairs(streams, argvs, cwds)
    if pairs is None:
        return "the native commands do not match the stream's by text"
    return Match(document, items, pairs, cwds)


def fill_directories(
    transcript: str, session: list[dict[str, Any]] | None
) -> tuple[str, dict[str, Any]]:
    """The transcript document with each empty command directory set from the native session
    `session`, and what to record in the run's meta: `command_cwd_source` (`native`, or
    `none: <reason>`) and `command_native_disagreements`.

    The records are filled only where the session has as many commands as the stream, with the
    same argv at the same place, or in another order where every repeated command has one
    directory. Otherwise the transcript is returned as it came. A stream status that differs
    from the session's is kept and listed, never replaced.
    """

    meta: dict[str, Any] = {SOURCE_KEY: "", DISAGREE_KEY: []}
    found = _match(transcript, session)
    if isinstance(found, str):
        meta[SOURCE_KEY] = f"none: {found}"
        return transcript, meta
    document, items, pairs, cwds = found
    for position, row in enumerate(document["commands"]):
        index, unique = pairs[position]
        if not row[2]:
            row[2] = cwds[index]
        elif row[2] != cwds[index]:
            meta[DISAGREE_KEY].append(
                {"index": position, "field": "cwd", "stream": row[2], "native": cwds[index]}
            )
        native = command_outcome(items[index])
        if unique and row[1] != native:
            meta[DISAGREE_KEY].append(
                {"index": position, "field": "status", "stream": row[1], "native": native}
            )
    meta[SOURCE_KEY] = "native"
    return json.dumps(document), meta
