"""Decode linked Claude tool calls and results without interpreting printed commands."""

from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from evals.records import Command


class PendingTool(NamedTuple):
    record_index: int | None
    command: str
    unknown: str | None = None  # the name of a tool that is none of the known forms


@dataclass
class ClaudeState:
    pending: dict[str, PendingTool] = field(default_factory=dict)
    seen: set[str] = field(default_factory=set)
    results: set[str] = field(default_factory=set)
    overlap: set[int] = field(default_factory=set)


_CD = re.compile(r"^cd[ \t]+(?P<dir>\"[^\"]*\"|'[^']*'|\S+)[ \t]*&&[ \t]*")


def _without_cd(command: str, workdir: str) -> str:
    """The command without a leading `cd <dir> && ` where <dir> is the workdir, compared as the
    OS resolves it (symlinks, a trailing slash, `.` and `..`), not as a string."""

    found = _CD.match(command)
    if found:
        try:
            named = shlex.split(found.group("dir"))
            if len(named) == 1 and os.path.realpath(named[0]) == os.path.realpath(workdir):
                return command[found.end() :]
        except ValueError:
            pass
    return command


def _block(command: str, workdir: str, status: str = "unverified") -> Command:
    """One actual Bash call and matched result, kept separate from printed text."""

    return Command(_without_cd(command, workdir) if workdir else command, status, workdir)


def _events(subagent_jsonl: Path) -> list[dict]:
    """Read JSONL strictly; a damaged line cannot prove the absence of an attempt."""

    found = []
    for line in subagent_jsonl.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError("a session event is not an object")
        found.append(event)
    return found


def _start_tool(part: dict, workdir: str, blocks: list[Command], state: ClaudeState) -> None:
    name, key, args = part.get("name"), part.get("id"), part.get("input")
    if not isinstance(name, str) or not isinstance(args, dict):
        raise ValueError("malformed tool call")
    known = name in {
        "Bash",
        "Read",
        "Edit",
        "Write",
        "Grep",
        "Glob",
        "LS",
        "TodoWrite",
        "SubagentHandback",
    }
    if not isinstance(key, str) or not key or key in state.seen:
        raise ValueError("missing or reused tool call id")
    state.seen.add(key)
    if not known:
        # Not a command, and not yet refused: only a result that says the tool does not exist
        # shows that nothing ran (`_result_parts` decides); any other form is unsupported.
        state.pending[key] = PendingTool(None, "", name)
        return
    index, command = None, ""
    if name == "Bash":
        value = args.get("command")
        if not isinstance(value, str):
            raise ValueError("Bash command is not a string")
        command = value
        index = len(blocks)
        active = {
            tool.record_index for tool in state.pending.values() if tool.record_index is not None
        }
        if active:
            state.overlap.update(active | {index})
        blocks.append(_block(command, workdir))
    state.pending[key] = PendingTool(index, command)


def _assistant_parts(
    parts: list, workdir: str, blocks: list[Command], state: ClaudeState
) -> list[str]:
    texts = []
    for part in parts:
        if part["type"] == "tool_use":
            _start_tool(part, workdir, blocks, state)
            if part.get("name") == "SubagentHandback":
                text = part["input"].get("message", "")
                if not isinstance(text, str):
                    raise ValueError("handback is not text")
                texts.append(text)
        elif part["type"] == "text":
            if not isinstance(part.get("text"), str):
                raise ValueError("assistant text is not a string")
            texts.append(part["text"])
    return texts


def _rejected_as_no_such_tool(result: dict, name: str) -> bool:
    """Whether the harness answered a call of the tool `name` with an error result that says
    this tool does not exist, which means that the call ran nothing."""

    content = result.get("content")
    if isinstance(content, list):
        texts = [part.get("text") for part in content if isinstance(part, dict)]
        content = texts[0] if len(texts) == 1 else None
    pattern = (
        rf"\s*<tool_use_error>\s*Error: No such tool available: {re.escape(name)}(?=\.?(?:\s|$))"
    )
    return (
        result.get("is_error") is True
        and isinstance(content, str)
        and re.match(pattern, content) is not None
    )


def _result_parts(parts: list, blocks: list[Command], state: ClaudeState) -> None:
    for part in parts:
        if part["type"] != "tool_result":
            continue
        key = part.get("tool_use_id")
        if not isinstance(key, str) or key in state.results or key not in state.pending:
            raise ValueError("unmatched or repeated tool result")
        state.results.add(key)
        tool = state.pending.pop(key)
        if tool.unknown is not None:
            if not _rejected_as_no_such_tool(part, tool.unknown):
                raise ValueError(f"unsupported tool form: {tool.unknown}")
            continue  # the harness ran nothing: no command, and no proof of one
        if tool.record_index is None:
            continue
        error = part.get("is_error", False)
        status = "unverified"
        if error is True:
            status = "failed"
        elif (
            error is False
            and isinstance(part.get("content"), (str, list))
            and tool.record_index not in state.overlap
        ):
            status = "succeeded"
        blocks[tool.record_index] = _block(tool.command, blocks[tool.record_index].cwd, status)


def _message_parts(event: dict) -> tuple[str, list] | None:
    message = event.get("message")
    if message is None:
        return None
    if not isinstance(message, dict) or not isinstance(message.get("role"), str):
        raise ValueError("malformed session message")
    parts = message.get("content")
    if isinstance(parts, str):
        parts = [{"type": "text", "text": parts}]
    if not isinstance(parts, list) or not all(
        isinstance(part, dict) and isinstance(part.get("type"), str) for part in parts
    ):
        raise ValueError("malformed message parts")
    return message["role"], parts


def _transcript(subagent_jsonl: Path, workdir: str) -> tuple[str, str]:
    """Pair actual tool identities; incomplete or ambiguous command evidence is refused."""

    blocks: list[Command] = []
    answer = ""
    events = _events(subagent_jsonl)
    state = ClaudeState()
    for event in events:
        message = _message_parts(event)
        if message is None:
            continue
        role, parts = message
        if role == "user":
            _result_parts(parts, blocks, state)
        elif role == "assistant":
            cwd = event.get("cwd", "")
            cwd = cwd if isinstance(cwd, str) and Path(cwd).is_absolute() else ""
            texts = _assistant_parts(parts, cwd, blocks, state)
            answer = "\n".join(texts) if texts else answer
    if not events:
        raise ValueError("no readable event")
    if state.pending:
        raise ValueError("a tool call has no result in the transcript")
    return json.dumps(
        {"format": "outcomebound-command-events-v1", "commands": blocks, "answer": answer}
    ), answer
