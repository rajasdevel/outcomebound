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


def _supported_items(events: list[dict]) -> bool:
    """Unknown tool items cannot establish that no command or environment act occurred."""

    passive = {"agent_message", "reasoning", "todo_list"}
    lifecycle = {"thread.started", "turn.started", "turn.completed", "error"}
    for event in events:
        if event.get("type") in lifecycle:
            continue
        if event.get("type") not in ("item.started", "item.updated", "item.completed"):
            return False
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") not in passive | {"command_execution"}:
            return False
    return True


def command_transcript(stdout: str | bytes, stderr: str | bytes) -> str:
    """Keep actual CLI events separate from output; incomplete/unknown evidence stays so."""

    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", "replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", "replace")
    try:
        events = [json.loads(line) for line in stdout.split("\n") if line.strip()]
    except ValueError:
        events = []
    valid = (
        bool(events)
        and all(isinstance(event, dict) for event in events)
        and events[0].get("type") == "thread.started"
        and sum(event.get("type") == "thread.started" for event in events) == 1
        and events[-1].get("type") == "turn.completed"
        and sum(event.get("type") == "turn.completed" for event in events) == 1
    )
    return json.dumps(
        {
            "format": "outcomebound-command-events-v1",
            "commands": _command_records(events) if valid and _supported_items(events) else None,
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
        models = {
            event["model"]
            for event in document.get("events", [])
            if event.get("type") in ("thread.started", "turn.started")
            and isinstance(event.get("model"), str)
            and event["model"]
        }
        return next(iter(models)) if len(models) == 1 else None
    _before, found, after = transcript.partition("\nworkdir: ")
    named = MODEL_LINE.search(after) if found else None
    return named.group(1) if named else None
