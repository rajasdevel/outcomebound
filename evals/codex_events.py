"""Decode actual Codex CLI events. Printed output is data, never execution evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path

from evals.records import Command

MODEL_LINE = re.compile(r"^model: (\S+)$", re.MULTILINE)
TOKENS_LINE = re.compile(r"^tokens used\s*\n\s*([\d,]+)\s*$", re.MULTILINE)


def _completed_command(item: dict, prior: Command) -> Command | None:
    command, directory = item.get("command"), item.get("cwd", "")
    if command != prior.command or not isinstance(directory, str):
        return None
    if directory and not Path(directory).is_absolute():
        directory = ""
        prior = Command(prior.command, prior.status, "")
    if directory and prior.cwd and directory != prior.cwd:
        return None
    code, status = item.get("exit_code"), item.get("status")
    outcome = "unverified"
    if status == "completed" and type(code) is int:
        outcome = "succeeded" if code == 0 else f"exited {code}"
    elif status in ("failed", "declined"):
        outcome = status
    return Command(command, outcome, directory or prior.cwd)


def _command_records(events: list[dict]) -> list[Command] | None:
    records: list[Command] = []
    pending: dict[str, int] = {}
    seen: set[str] = set()
    overlapping: set[str] = set()
    for event in events:
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "command_execution":
            continue
        key, command, directory = item.get("id"), item.get("command"), item.get("cwd", "")
        if (
            not isinstance(key, str)
            or not isinstance(command, str)
            or not isinstance(directory, str)
        ):
            return None
        directory = directory if Path(directory).is_absolute() else ""
        kind = event.get("type")
        if kind == "item.started" and key not in seen:
            if pending:
                overlapping.update(pending)
                overlapping.add(key)
            pending[key] = len(records)
            seen.add(key)
            records.append(Command(command, "unverified", directory))
        elif kind == "item.completed" and key in pending:
            index = pending.pop(key)
            completed = _completed_command(item, records[index])
            if completed is None:
                return None
            if key in overlapping and completed.status == "succeeded":
                completed = Command(completed.command, "unverified", completed.cwd)
            records[index] = completed
        else:
            return None
    return records if not pending else None


# Item types that are not a command and cannot change what "no command ran" means: messages,
# reasoning, a to-do list, an apply-patch edit (`file_change`) and a CLI warning (`error`).
PASSIVE_ITEMS = frozenset({"agent_message", "reasoning", "todo_list", "file_change", "error"})
LIFECYCLE_EVENTS = frozenset({"thread.started", "turn.started", "turn.completed", "error"})
ITEM_EVENTS = ("item.started", "item.updated", "item.completed")


def parse_events(stdout: str) -> list[dict] | None:
    """The stream's events, or None where a line is not JSON or an event is not an object."""

    try:
        events = [json.loads(line) for line in stdout.split("\n") if line.strip()]
    except ValueError:
        return None
    return events if all(isinstance(event, dict) for event in events) else None


def unknown_types(events: list[dict]) -> list[str]:
    """Each event or item type that this decoder does not know, as `event.<type>` or
    `item.<type>`: an unknown tool form cannot establish that no command or environment act
    occurred."""

    found: set[str] = set()
    for event in events:
        kind = event.get("type")
        if kind in LIFECYCLE_EVENTS:
            continue
        if kind not in ITEM_EVENTS:
            found.add(f"event.{kind}")
            continue
        item = event.get("item")
        item_type = item.get("type") if isinstance(item, dict) else "<not-an-object>"
        if item_type not in PASSIVE_ITEMS | {"command_execution"}:
            found.add(f"item.{item_type}")
    return sorted(found)


def item_types(events: list[dict]) -> list[str]:
    """Each item type the stream carried, known or not."""

    return sorted(
        {str(event["item"].get("type")) for event in events if isinstance(event.get("item"), dict)}
    )


def warnings(events: list[dict]) -> list[str]:
    """The text of each `error` item: a warning the CLI printed, such as a role file it ignored."""

    return [
        str(event["item"].get("message", ""))
        for event in events
        if event.get("type") == "item.completed"
        and isinstance(event.get("item"), dict)
        and event["item"].get("type") == "error"
    ]


def stream_models(events: list[dict]) -> set[str]:
    """Each model an older CLI's `thread.started` or `turn.started` event names."""

    return {
        event["model"]
        for event in events
        if event.get("type") in ("thread.started", "turn.started")
        and isinstance(event.get("model"), str)
        and event["model"]
    }


def command_transcript(stdout: str | bytes, stderr: str | bytes) -> str:
    """Keep actual CLI events separate from output; incomplete/unknown evidence stays so."""

    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", "replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", "replace")
    events = parse_events(stdout) or []
    valid = (
        bool(events)
        and events[0].get("type") == "thread.started"
        and sum(event.get("type") == "thread.started" for event in events) == 1
        and events[-1].get("type") == "turn.completed"
        and sum(event.get("type") == "turn.completed" for event in events) == 1
    )
    return json.dumps(
        {
            "format": "outcomebound-command-events-v1",
            "commands": _command_records(events) if valid and not unknown_types(events) else None,
            "events": events if valid else [],
            "stdout": stdout,
            "stderr": stderr,
        }
    )


def tokens_used(transcript: str) -> int | None:
    """The token count codex printed last, or None where it printed none."""

    try:
        document = json.loads(transcript.split("\n--- post-checks ---\n", 1)[0])
    except ValueError:
        document = None
    if isinstance(document, dict):
        for event in reversed(document.get("events", [])):
            if event.get("type") == "turn.completed":
                usage = event.get("usage", {})
                counts = [usage.get("input_tokens"), usage.get("output_tokens")]
                return sum(counts) if all(type(n) is int for n in counts) else None
        return None
    found = TOKENS_LINE.findall(transcript)
    return int(found[-1].replace(",", "")) if found else None


def observed_model(transcript: str) -> str | None:
    """The model codex's own header names, after its `workdir:` line, or None."""

    try:
        document = json.loads(transcript.split("\n--- post-checks ---\n", 1)[0])
    except ValueError:
        document = None
    if isinstance(document, dict):
        if document.get("commands") is None:
            return None
        models = stream_models(document.get("events", []))
        return next(iter(models)) if len(models) == 1 else None
    _before, found, after = transcript.partition("\nworkdir: ")
    named = MODEL_LINE.search(after) if found else None
    return named.group(1) if named else None
