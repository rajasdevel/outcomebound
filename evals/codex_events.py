"""Decode actual Codex CLI events. Printed output is data, never execution evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path

from evals.records import Command

MODEL_LINE = re.compile(r"^model: (\S+)$", re.MULTILINE)
TOKENS_LINE = re.compile(r"^tokens used\s*\n\s*([\d,]+)\s*$", re.MULTILINE)


def command_outcome(item: dict) -> str:
    """The status a completed command item records: `succeeded`, `exited N`, `failed`,
    `declined`, or `unverified` where it names no exit code or a status this does not know.
    The same rule reads a stream item and an item of the native session."""

    code, status = item.get("exit_code"), item.get("status")
    if status == "completed" and type(code) is int:
        return "succeeded" if code == 0 else f"exited {code}"
    return status if status in ("failed", "declined") else "unverified"


def _completed_command(item: dict, prior: Command) -> Command | None:
    command, directory = item.get("command"), item.get("cwd", "")
    if command != prior.command or not isinstance(directory, str):
        return None
    if directory and not Path(directory).is_absolute():
        directory = ""
        prior = Command(prior.command, prior.status, "")
    if directory and prior.cwd and directory != prior.cwd:
        return None
    return Command(command, command_outcome(item), directory or prior.cwd)


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


# The most of one command's recorded output a transcript keeps: its head and its tail, half each,
# around a marker that says how much was cut.
OUTPUT_CHARACTERS = 20_000
CUT = "\n[... {count} characters of this command's output cut ...]\n"


def capped(text: str, limit: int = OUTPUT_CHARACTERS) -> str:
    """`text`, or where it is longer than `limit`, its head and tail around a cut marker."""

    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + CUT.format(count=len(text) - 2 * half) + text[-half:]


def command_outputs(events: list[dict]) -> list[str | None]:
    """The output the harness recorded for each command, in the order of the command records
    (the order the commands started): the `aggregated_output` of its completed item, capped, or
    None where the item gives none. Output is data the command printed, never evidence that a
    command ran."""

    order: list[str] = []
    found: dict[str, str | None] = {}
    for event in events:
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "command_execution":
            continue
        key = item.get("id")
        if not isinstance(key, str):
            continue
        if event.get("type") == "item.started" and key not in found:
            order.append(key)
            found[key] = None
        elif event.get("type") == "item.completed" and key in found:
            output = item.get("aggregated_output")
            found[key] = capped(output) if isinstance(output, str) else None
    return [found[key] for key in order]


def with_outputs(transcript: str) -> str:
    """A transcript document from before `outputs` was kept, with them taken from its events;
    any other text as it came."""

    try:
        document = json.loads(transcript)
    except ValueError:
        return transcript
    if not isinstance(document, dict) or "outputs" in document:
        return transcript
    commands, events = document.get("commands"), document.get("events")
    if not isinstance(commands, list) or not isinstance(events, list):
        return transcript
    if not all(isinstance(event, dict) for event in events):
        return transcript
    outputs = command_outputs(events)
    if len(outputs) != len(commands):
        return transcript
    return json.dumps({**document, "outputs": outputs})


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
    """Keep actual CLI events separate from output; incomplete/unknown evidence stays so.

    `outputs` holds, for each command record, the output its completed item recorded (capped,
    `command_outputs`), or None; it is None where `commands` is."""

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
    commands = _command_records(events) if valid and not unknown_types(events) else None
    return json.dumps(
        {
            "format": "outcomebound-command-events-v1",
            "commands": commands,
            "outputs": command_outputs(events) if commands is not None else None,
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


# The four token counts a run's cost is read as, in the names codex gives them.
COST_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def _counts(usage: object) -> dict[str, int] | None:
    if not isinstance(usage, dict) or not all(type(usage.get(key)) is int for key in COST_KEYS):
        return None
    return {key: usage[key] for key in COST_KEYS}


def session_tokens(
    records: list[dict] | None, events: list[dict] | None = None
) -> dict[str, int | str] | None:
    """What a call spent, summed over its session: input (cached input among it), output and
    reasoning (among the output) tokens, and the record they were read from.

    The native session's `token_count` events carry the session's running total, so the last
    one with a total is the sum (`source` `native`). Where no session was read, the stream's
    `turn.completed` usage stands (`stream`); None where neither gives every count."""

    for record in reversed(records or []):
        if not isinstance(record, dict) or record.get("type") != "event_msg":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != "token_count" or not isinstance(payload.get("info"), dict):
            continue
        counts = _counts(payload["info"].get("total_token_usage"))
        if counts is not None:
            return {**counts, "source": "native"}
    totals = [_counts(e.get("usage")) for e in events or [] if e.get("type") == "turn.completed"]
    if totals and all(item is not None for item in totals):
        return {
            **{key: sum(item[key] for item in totals if item) for key in COST_KEYS},
            "source": "stream",
        }
    return None


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
