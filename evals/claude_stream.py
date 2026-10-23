"""Decode a Claude Code call: its stream-JSON events and the native session it keeps.

`claude -p --output-format stream-json --verbose` prints one JSON event a line: a `system` event
of subtype `init` (the start event: the session id, working directory, model, tools, plugins,
skills, MCP servers and permission mode), `assistant` and `user` events that carry the messages
(a tool call is a `tool_use` part of an assistant message, its result a `tool_result` part of
the next user message, linked by id), `system` hook events where `--include-hook-events` is
given, and one `result` event at the end (the final answer, the session's usage and
`total_cost_usd`, the CLI's own list-price estimate). The field names are those of the
`SDKSystemMessage`, `SDKAssistantMessage`, `SDKUserMessage` and `SDKResultMessage` types the
Agent SDK documents, and of the start event the CLI builds (read in claude 2.1.308); which of
them a real call fills is UNVERIFIED until one runs, so a missing field is reported, never
filled in.

The transcript keeps the runner's `outcomebound-command-events-v1` form: `commands` holds the
Bash calls only, and `files` the Read, Edit and Write calls, each `[tool, path, status]`, so a
file the model read or changed with a tool leaves a record and a grader that counts commands
never counts one. A stream with any tool this module does not know (a subagent, a background
shell) has no `commands` and no `files`: what such a tool ran is not in the stream, so "no
command ran" cannot be shown. The one exception is a call the CLI refused because it has no such
tool (an error result whose `<tool_use_error>` says `No such tool available`, as read in claude
2.1.308): it ran nothing, so it is counted in `tools` but not as unknown.

The model and effort a call ran with are read from its native session, the
`<config>/projects/<folder>/<session id>.jsonl` file the CLI writes under `CLAUDE_CONFIG_DIR`:
each assistant record names its `message.model` and its `effort`.

Standard library only; nothing here starts a process.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any, NamedTuple

from evals.claude_events import _without_cd
from evals.codex_events import capped, parse_events
from evals.records import Command

FORMAT = "outcomebound-command-events-v1"
# The tools whose call is a shell command, a file event, or neither: none of the passive ones
# runs a command or names a file it changes. Every other tool (a subagent, a background shell,
# a monitor) is unknown, and its stream proves nothing about what ran.
COMMAND_TOOLS = frozenset({"Bash"})
FILE_TOOLS = frozenset({"Read", "Edit", "Write", "MultiEdit", "NotebookEdit"})
PASSIVE_TOOLS = frozenset(
    {
        "Glob",
        "Grep",
        "LS",
        "TodoWrite",
        "ToolSearch",
        "Skill",
        "WebFetch",
        "WebSearch",
        "AskUserQuestion",
        "ExitPlanMode",
        "EnterPlanMode",
        "TaskCreate",
        "TaskGet",
        "TaskList",
        "TaskUpdate",
    }
)
# What a file tool names as its file.
PATH_KEYS = ("file_path", "notebook_path", "path")
HOOK_EVENTS = ("hook_started", "hook_progress", "hook_response")
# The error the CLI returns for a call to a tool it does not have (read in claude 2.1.308).
NO_SUCH_TOOL = re.compile(r"<tool_use_error>[^<]*No such tool available")
# The message the CLI writes for an error it made itself, not the model.
SYNTHETIC = "<synthetic>"
# A built-in plugin's id ends with this; such a plugin ships with the CLI.
BUILTIN = "@builtin"


# --- the stream ------------------------------------------------------------------------------


def start_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The one `system` event of subtype `init`, or None where there is none or more than one."""

    found = [e for e in events if e.get("type") == "system" and e.get("subtype") == "init"]
    return found[0] if len(found) == 1 else None


def result_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The stream's one `result` event, where every event after it is a `system` event (a hook
    or other notice the CLI prints as it shuts down); else None."""

    found = [i for i, e in enumerate(events) if e.get("type") == "result"]
    if len(found) != 1:
        return None
    after = events[found[0] + 1 :]
    return events[found[0]] if all(e.get("type") == "system" for e in after) else None


def session_id(events: list[dict[str, Any]]) -> str:
    """The start event's session id, which every event that names one must share; ValueError
    where it is missing, not a canonical UUID, or contradicted."""

    start = start_event(events)
    key = start.get("session_id") if start else None
    if not isinstance(key, str) or str(uuid.UUID(key)) != key:
        raise ValueError("the stream has no single start event with a canonical session id")
    others = {e["session_id"] for e in events if isinstance(e.get("session_id"), str)}
    if others - {key}:
        raise ValueError(f"the stream names more than one session: {sorted(others)}")
    return key


def _parts(event: dict[str, Any]) -> list[dict[str, Any]] | None:
    """The content parts of an assistant or user event's message, or None where malformed."""

    message = event.get("message")
    if not isinstance(message, dict):
        return None
    parts = message.get("content")
    if isinstance(parts, str):
        return [{"type": "text", "text": parts}]
    if not isinstance(parts, list) or not all(isinstance(p, dict) for p in parts):
        return None
    return parts


def _text(content: Any) -> str | None:
    """A tool result's content as text: the string, or the text parts of a list joined."""

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [p.get("text") for p in content if isinstance(p, dict) and p.get("type") == "text"]
        return "\n".join(t for t in texts if isinstance(t, str))
    return None


class Decoded(NamedTuple):
    """What the stream's tool calls show: the command records, their outputs and the file
    events (None for each where the stream cannot show them), each tool used with its count,
    the unknown tools, the skills invoked, and the final answer."""

    commands: list[Command] | None
    outputs: list[str | None] | None
    files: list[list[str]] | None
    tools: dict[str, int]
    unknown: list[str]
    skills: list[str]
    answer: str


class _Call(NamedTuple):
    name: str
    kind: str  # "command", "file", "passive" or "unknown"
    slot: int | None
    background: bool


def _status(result: dict[str, Any], key: str, denied: set[str]) -> str:
    """A finished call's status, from its own result, which the CLI links to it by id (so a
    call that ran beside another keeps its own): `declined` where the CLI denied it, `failed`
    for an error result, `succeeded` for a result with content, `unverified` where it gave no
    content."""

    if key in denied:
        return "declined"
    if result.get("is_error") is True:
        return "failed"
    if result.get("is_error", False) is False and _text(result.get("content")) is not None:
        return "succeeded"
    return "unverified"


def _refused(result: dict[str, Any]) -> bool:
    """Whether the CLI refused the call because it has no tool of that name: it ran nothing."""

    text = _text(result.get("content"))
    return result.get("is_error") is True and text is not None and bool(NO_SUCH_TOOL.search(text))


class _Decoder:
    """The state of one pass over the stream's tool calls and results (`decode`)."""

    def __init__(self, directories: dict[str, str], denied: set[str]) -> None:
        self.directories, self.denied = directories, denied
        self.commands: list[Command] = []
        self.outputs: list[str | None] = []
        self.files: list[list[str]] = []
        self.tools: dict[str, int] = {}
        self.unknown: set[str] = set()
        self.skills: list[str] = []
        self.pending: dict[str, _Call] = {}
        self.seen: set[str] = set()
        self.broken = False

    def call(self, part: dict[str, Any]) -> None:
        """One `tool_use` part: a command, a file event, or a passive or unknown tool."""

        name, key, args = part.get("name"), part.get("id"), part.get("input")
        if not isinstance(name, str) or not isinstance(args, dict):
            self.broken = True
            return
        if not isinstance(key, str) or not key or key in self.seen:
            self.broken = True
            return
        self.seen.add(key)
        self.tools[name] = self.tools.get(name, 0) + 1
        if name in COMMAND_TOOLS:
            self.command(key, name, args)
        elif name in FILE_TOOLS:
            path = next((args[k] for k in PATH_KEYS if isinstance(args.get(k), str)), None)
            if path is None:
                self.broken = True
                return
            self.files.append([name, path, ""])
            self.pending[key] = _Call(name, "file", len(self.files) - 1, False)
        else:
            if name == "Skill" and isinstance(args.get("skill"), str):
                self.skills.append(args["skill"])
            kind = "passive" if name in PASSIVE_TOOLS else "unknown"
            self.pending[key] = _Call(name, kind, None, False)

    def command(self, key: str, name: str, args: dict[str, Any]) -> None:
        command = args.get("command")
        if not isinstance(command, str):
            self.broken = True
            return
        index = len(self.commands)
        cwd = self.directories.get(key, "")
        self.commands.append(Command(_without_cd(command, cwd) if cwd else command, "", cwd))
        self.outputs.append(None)
        self.pending[key] = _Call(name, "command", index, args.get("run_in_background") is True)

    def result(self, part: dict[str, Any]) -> None:
        """One `tool_result` part, matched to its call by id."""

        key = part.get("tool_use_id")
        if not isinstance(key, str) or key not in self.pending:
            self.broken = True
            return
        call = self.pending.pop(key)
        if call.kind == "unknown" and not _refused(part):
            self.unknown.add(call.name)
        if call.slot is None:
            return
        if call.kind == "file":
            self.files[call.slot][2] = _status(part, key, self.denied)
            return
        status = _status(part, key, self.denied)
        if call.background and status == "succeeded":
            status = "unverified"  # started in the background, not seen to finish
        old = self.commands[call.slot]
        self.commands[call.slot] = Command(old.command, status, old.cwd)
        text = _text(part.get("content"))
        self.outputs[call.slot] = capped(text) if text is not None else None


def decode(events: list[dict[str, Any]], directories: dict[str, str] | None = None) -> Decoded:
    """The stream's tool calls, in the order they started. `directories` gives the working
    directory of a call by its tool-use id (from the native session); a call with none keeps an
    empty one. A call with no result, a result with no call, a reused id, a malformed part, an
    unknown tool (save one the CLI refused as no such tool), or a stream with no start or no
    final result event leaves no commands and no files."""

    result = result_event(events)
    denied = {
        str(item.get("tool_use_id"))
        for item in (result or {}).get("permission_denials") or []
        if isinstance(item, dict)
    }
    state = _Decoder(directories or {}, denied)
    for event in events:
        kind = event.get("type")
        if kind not in ("assistant", "user"):
            continue
        parts = _parts(event)
        if parts is None:
            state.broken = True
            continue
        for part in parts:
            if kind == "assistant" and part.get("type") == "tool_use":
                state.call(part)
            elif kind == "user" and part.get("type") == "tool_result":
                state.result(part)
    answer = result.get("result") if result else None
    answer = answer if isinstance(answer, str) else ""
    state.unknown.update(c.name for c in state.pending.values() if c.kind == "unknown")
    tools, unknown, skills = state.tools, sorted(state.unknown), state.skills
    whole = not (state.broken or state.pending or unknown or result is None)
    if not whole or start_event(events) is None:
        return Decoded(None, None, None, tools, unknown, skills, answer)
    return Decoded(state.commands, state.outputs, state.files, tools, unknown, skills, answer)


def stream_transcript(
    stdout: str | bytes, stderr: str | bytes, directories: dict[str, str] | None = None
) -> tuple[str, Decoded]:
    """The transcript document of a call and what it decoded. The events are kept where the
    stream is whole: one start event, and one `result` event, last."""

    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", "replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", "replace")
    events = parse_events(stdout) or []
    decoded = decode(events, directories)
    valid = start_event(events) is not None and result_event(events) is not None
    document = {
        "format": FORMAT,
        "commands": decoded.commands,
        "outputs": decoded.outputs,
        "files": decoded.files,
        "events": events if valid else [],
        "stdout": stdout,
        "stderr": stderr,
    }
    return json.dumps(document), decoded


def event_types(events: list[dict[str, Any]]) -> list[str]:
    """Each event type the stream carried, with its subtype where it has one."""

    return sorted(
        {
            f"{e.get('type')}.{e['subtype']}"
            if isinstance(e.get("subtype"), str)
            else str(e.get("type"))
            for e in events
        }
    )


def hook_events(events: list[dict[str, Any]]) -> list[str]:
    """Each hook the stream shows running, as `<event>:<name>`, once."""

    found: list[str] = []
    for event in events:
        if event.get("type") == "system" and event.get("subtype") in HOOK_EVENTS:
            label = f"{event.get('hook_event')}:{event.get('hook_name')}"
            if label not in found:
                found.append(label)
    return found


# --- usage and cost --------------------------------------------------------------------------

USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def _input(usage: Any) -> int | None:
    """The input of one usage record, cached input among it: new, cache-written and cache-read
    tokens; None where a count is missing."""

    if not isinstance(usage, dict) or not all(type(usage.get(k)) is int for k in USAGE_KEYS):
        return None
    return sum(usage[k] for k in USAGE_KEYS)


def session_tokens(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """What the call spent, in the runner's four counts, with its list-price cost.

    From the `result` event: its `modelUsage`, summed over every model the session called
    (each model's `inputTokens`, `cacheCreationInputTokens`, `cacheReadInputTokens`,
    `outputTokens` and `costUSD`), or its `usage` where it has no `modelUsage`; `cost_usd` is
    its `total_cost_usd`, the CLI's estimate at list prices. Where there is no result event (a
    stopped call), the assistant messages' usage, each message once, and no cost. The CLI
    counts thinking inside output and gives no count of its own: `reasoning_output_tokens` is 0
    and `reasoning_in_output` says so. None where nothing gives every count."""

    result = next((e for e in reversed(events) if e.get("type") == "result"), None)
    if result is not None:
        models = result.get("modelUsage")
        rows = list(models.values()) if isinstance(models, dict) and models else []
        keys = ("inputTokens", "cacheCreationInputTokens", "cacheReadInputTokens", "outputTokens")
        if rows and all(
            isinstance(r, dict) and all(type(r.get(k)) is int for k in keys) for r in rows
        ):
            fresh, written, read, out = (sum(r[k] for r in rows) for k in keys)
            source = "stream-result-model-usage"
        else:
            usage = result.get("usage")
            if not isinstance(usage, dict) or _input(usage) is None:
                return None
            if type(usage.get("output_tokens")) is not int:
                return None
            fresh, written, read = (usage[k] for k in USAGE_KEYS)
            out, source = usage["output_tokens"], "stream-result-usage"
        cost = result.get("total_cost_usd")
        return {
            "input_tokens": fresh + written + read,
            "cached_input_tokens": read,
            "output_tokens": out,
            "reasoning_output_tokens": 0,
            "cache_creation_input_tokens": written,
            "cost_usd": cost
            if isinstance(cost, (int, float)) and not isinstance(cost, bool)
            else None,
            "models": sorted(models) if isinstance(models, dict) else [],
            "reasoning_in_output": True,
            "source": source,
        }
    meter = StreamMeter()
    for event in events:
        meter.add(event)
    if not meter.messages:
        return None
    usage = meter.totals()
    return {
        **usage,
        "reasoning_output_tokens": 0,
        "cost_usd": None,
        "models": [],
        "reasoning_in_output": True,
        "source": "stream-assistant",
    }


class StreamMeter:
    """The input a running call has used, read from the stream as it is printed.

    Each assistant message is counted once, by its id (the stream repeats a message's usage on
    each of its parts), at the largest count seen for it; a subagent's messages count too. Only
    complete lines are read, and each read takes only what was printed since the last. None
    until a message with usage is read."""

    def __init__(self) -> None:
        self.messages: dict[str, dict[str, int]] = {}
        self._offset = 0
        self.last: int | None = None

    def add(self, event: dict[str, Any]) -> None:
        message = event.get("message") if event.get("type") == "assistant" else None
        if not isinstance(message, dict) or not isinstance(message.get("id"), str):
            return
        usage = message.get("usage")
        if not isinstance(usage, dict) or _input(usage) is None:
            return
        seen = self.messages.setdefault(message["id"], {})
        for key in (*USAGE_KEYS, "output_tokens"):
            value = usage.get(key)
            if type(value) is int:
                seen[key] = max(seen.get(key, 0), value)

    def totals(self) -> dict[str, int]:
        fresh, written, read, out = (
            sum(m.get(k, 0) for m in self.messages.values()) for k in (*USAGE_KEYS, "output_tokens")
        )
        return {
            "input_tokens": fresh + written + read,
            "cached_input_tokens": read,
            "cache_creation_input_tokens": written,
            "output_tokens": out,
        }

    def input(self, printed: str) -> int | None:
        complete = printed.rfind("\n") + 1
        for line in printed[self._offset : complete].splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict):
                self.add(event)
        self._offset = max(self._offset, complete)
        if self.messages:
            self.last = self.totals()["input_tokens"]
        return self.last


# --- the native session ------------------------------------------------------------------------


def parse_lines(raw: bytes) -> tuple[list[dict[str, Any]], int]:
    """The records of a session file's complete lines, and the bytes of an unfinished last line
    (0 where the file ends with a newline). ValueError where a complete line is not an object."""

    complete, _newline, tail = raw.rpartition(b"\n")
    records = [json.loads(line) for line in complete.decode("utf-8").splitlines() if line.strip()]
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("a native session line is not an object")
    if not complete and tail:
        # One line and no newline: it is whole only if it reads.
        try:
            only = json.loads(tail)
        except ValueError:
            return [], len(tail)
        return ([only] if isinstance(only, dict) else []), 0
    return records, len(tail)


def find_native(config: Path, key: str) -> tuple[Path, bytes, list[dict[str, Any]], int]:
    """The one native session file `<key>.jsonl` under `config/projects`, its exact bytes, its
    records and the bytes of an unfinished last line. ValueError where none or more than one
    matches, where it is a symlink or outside `config`, or where a record names another
    session."""

    projects = config / "projects"
    matches = list(projects.rglob(f"{key}.jsonl")) if projects.is_dir() else []
    if len(matches) != 1:
        raise ValueError(f"matching native session count is {len(matches)}, expected 1")
    source = matches[0]
    if source.is_symlink() or not source.resolve().is_relative_to(config.resolve()):
        raise ValueError("native session is a symlink or outside the call's config folder")
    raw = source.read_bytes()
    records, tail = parse_lines(raw)
    named = {r["sessionId"] for r in records if isinstance(r.get("sessionId"), str)}
    if named != {key}:
        raise ValueError(f"native session names sessions {sorted(named)}, not only {key}")
    return source, raw, records, tail


def _main_replies(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The native session's assistant records of the main thread, less the CLI's own synthetic
    ones."""

    return [
        r
        for r in records
        if r.get("type") == "assistant"
        and r.get("isSidechain") is not True
        and isinstance(r.get("message"), dict)
        and r["message"].get("model") != SYNTHETIC
    ]


def agreed(records: list[dict[str, Any]], field: str) -> tuple[str | None, str]:
    """The one value every main-thread assistant record gives for `field` (`model` is read from
    its message), and the problem otherwise."""

    replies = _main_replies(records)
    if not replies:
        return None, "the native session has no assistant record"
    values = [r["message"].get("model") if field == "model" else r.get(field) for r in replies]
    if any(not isinstance(value, str) or not value for value in values):
        return None, f"the native session gives no {field} on an assistant record"
    if len(set(values)) != 1:
        return (
            None,
            f"the native session gives conflicting {field} values: {sorted(map(str, set(values)))}",
        )
    return values[0], ""


def effort_of(records: list[dict[str, Any]]) -> tuple[str | None, str]:
    """The effort the native session's main-thread assistant records give, and why there is
    none. Records that name no effort (a model without effort support, an older CLI) do not
    count against it; values that differ do, and none recorded at all is `unrecorded`."""

    replies = _main_replies(records)
    if not replies:
        return None, "the native session has no assistant record"
    named = {r["effort"] for r in replies if isinstance(r.get("effort"), str) and r["effort"]}
    if not named:
        return None, "unrecorded"
    if len(named) != 1:
        return None, f"the native session gives conflicting effort values: {sorted(named)}"
    return named.pop(), ""


# A context-window suffix a model name may carry (`[1m]`), which names no other model.
CONTEXT_SUFFIX = re.compile(r"\[[^\]]*\]$")


def model_base(name: str | None) -> str | None:
    """`name` without a context-window suffix such as `[1m]`."""

    return CONTEXT_SUFFIX.sub("", name).strip() if isinstance(name, str) else None


def directories(records: list[dict[str, Any]]) -> dict[str, str]:
    """The working directory of each tool call, by its tool-use id, as the native session's
    assistant record that holds the call gives it (an absolute path), else nothing."""

    found: dict[str, str] = {}
    for record in records:
        if record.get("type") != "assistant" or not isinstance(record.get("cwd"), str):
            continue
        if not Path(record["cwd"]).is_absolute():
            continue
        message = record.get("message")
        parts = message.get("content") if isinstance(message, dict) else None
        for part in parts if isinstance(parts, list) else []:
            if (
                isinstance(part, dict)
                and part.get("type") == "tool_use"
                and isinstance(part.get("id"), str)
            ):
                found[part["id"]] = record["cwd"]
    return found


# --- isolation ---------------------------------------------------------------------------------

# Instruction files Claude Code reads from the working directory and each folder above it, and
# the rules folders it reads at each level.
ANCESTOR_FILES = (
    "CLAUDE.md",
    "CLAUDE.local.md",
    ".claude/CLAUDE.md",
    "AGENTS.md",
    ".claude/AGENTS.md",
)
ANCESTOR_RULES = ".claude/rules"
# Where an organisation's managed policy lives, by platform: its CLAUDE.md is read by every
# session, and its settings apply to every session.
MANAGED = {
    "darwin": Path("/Library/Application Support/ClaudeCode"),
    "linux": Path("/etc/claude-code"),
}
# Managed settings keys that load code, instructions or tools into every session.
LOADING_KEYS = ("hooks", "enabledPlugins", "statusLine", "apiKeyHelper", "mcpServers")


# The skills Claude Code itself ships, by name, as the 2.1.308 binary registers them: a bare
# skill name in a start event or a skill listing is the arm's only where its workspace holds it
# or it is one of these. A listed name outside both voids the cell; a built-in this list lacks
# shows as such in the first probe, and is added here.
BUILTIN_SKILLS = frozenset(
    {
        "artifact-capabilities",
        "artifact-components",
        "artifact-design",
        "artifact-diagramming",
        "artifact-pr-review",
        "batch",
        "claude-api",
        "claude-code-docs",
        "claude-in-chrome",
        "code-review",
        "commit",
        "commit-push-pr",
        "cowork-plugin",
        "dataviz",
        "debug",
        "deep-research",
        "design",
        "design-sync",
        "doctor",
        "explain-usage",
        "fewer-permission-prompts",
        "init",
        "keybindings-help",
        "loop",
        "memory-types",
        "plugin-authoring",
        "pr",
        "prototype",
        "review",
        "run",
        "run-skill-generator",
        "schedule",
        "security-review",
        "setup-claude",
        "simplify",
        "update-config",
        "verify",
        "workflow-authoring",
        "workshop",
    }
)
# Instruction files Claude Code loads from the working directory at start: these, and the
# AGENTS.md pair only where none of these exists.
WORKSPACE_INSTRUCTIONS = ("CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md")
WORKSPACE_AGENTS = ("AGENTS.md", ".claude/AGENTS.md")
# The native session's hook records, which name the command a hook ran.
HOOK_RECORDS = ("hook_success", "hook_non_blocking_error", "hook_blocking_error", "hook_cancelled")


class Expected(NamedTuple):
    """What a cell may load beyond Claude Code's own: the plugin folders its arm adds, the skills
    its workspace holds under `.claude/skills/`, the OutcomeBound skills it does not carry, which
    must not appear, its workspace, and the instruction files Claude Code should load from it
    (workspace-relative)."""

    plugin_dirs: tuple[Path, ...] = ()
    skills: tuple[str, ...] = ()
    foreign_skills: tuple[str, ...] = ()
    workdir: Path | None = None
    instructions: tuple[str, ...] = ()


def workspace_skills(workdir: Path) -> tuple[str, ...]:
    """The skills the workspace gives Claude Code: each folder of `.claude/skills/` with a
    `SKILL.md`."""

    return tuple(sorted(p.parent.name for p in (workdir / ".claude" / "skills").glob("*/SKILL.md")))


def workspace_instructions(workdir: Path) -> tuple[str, ...]:
    """The instruction files Claude Code should load from `workdir` at start: each
    `CLAUDE.md`, `CLAUDE.local.md` and `.claude/CLAUDE.md` there, or, where it has none of them,
    each `AGENTS.md` and `.claude/AGENTS.md`."""

    found = tuple(name for name in WORKSPACE_INSTRUCTIONS if (workdir / name).is_file())
    return found or tuple(name for name in WORKSPACE_AGENTS if (workdir / name).is_file())


def _row(item: str, verdict: str, detail: str) -> list[str]:
    return [item, verdict, detail]


def _inside(path: Any, folders: tuple[Path, ...]) -> bool:
    if not isinstance(path, str) or not path:
        return False
    resolved = Path(path).resolve()
    return any(resolved.is_relative_to(folder.resolve()) for folder in folders)


class Plugins(NamedTuple):
    """The start event's plugins, sorted: the arm's own and the built-in ones, by name and by
    folder."""

    own: tuple[str, ...] = ()
    builtin: tuple[str, ...] = ()
    builtin_paths: tuple[Path, ...] = ()


def _plugins_row(start: dict[str, Any], expected: Expected) -> tuple[list[str], Plugins]:
    """The plugins row, and the arm's own and the built-in plugins it names."""

    plugins = start.get("plugins")
    if not isinstance(plugins, list):
        return _row("plugins", "UNVERIFIED", "the start event names no plugins"), Plugins()
    own: list[str] = []
    builtin: list[str] = []
    paths: list[Path] = []
    foreign = []
    for plugin in plugins:
        entry = plugin if isinstance(plugin, dict) else {"name": str(plugin)}
        name, source = str(entry.get("name")), str(entry.get("source") or "")
        if _inside(entry.get("path"), expected.plugin_dirs):
            own.append(name)
        elif source.endswith(BUILTIN) or name.endswith(BUILTIN):
            builtin.append(name.removesuffix(BUILTIN))
            if isinstance(entry.get("path"), str) and entry["path"]:
                paths.append(Path(entry["path"]))
        else:
            foreign.append(f"{name} ({entry.get('path')})")
    missing = [
        str(folder)
        for folder in expected.plugin_dirs
        if not any(isinstance(p, dict) and _inside(p.get("path"), (folder,)) for p in plugins)
    ]
    problems = [f"not the arm's: {', '.join(foreign)}"] if foreign else []
    problems += [f"the arm's plugin did not load: {', '.join(missing)}"] if missing else []
    detail = "; ".join(problems) or f"the arm's {own or 'none'}; built in {builtin or 'none'}"
    found = Plugins(tuple(own), tuple(builtin), tuple(paths))
    return _row("plugins", "FAIL" if problems else "PASS", detail), found


def _stray(name: str, expected: Expected, namespaces: tuple[str, ...]) -> bool:
    """Whether one listed skill is not the arm's: an OutcomeBound skill it does not carry, a
    plugin skill of a plugin outside `namespaces`, or a bare name neither the workspace's nor
    built in."""

    space, _colon, bare = name.rpartition(":")
    if bare in expected.foreign_skills:
        return True
    if space:
        return space not in namespaces
    return bare not in expected.skills and bare not in BUILTIN_SKILLS


def _skill_problems(names: list[str], expected: Expected, plugins: Plugins) -> list[str]:
    """What is wrong with a list of skill names: a plugin skill of a plugin that is neither
    the arm's nor built in, an OutcomeBound skill the arm does not carry, a bare name that is
    neither the workspace's nor built in, and a workspace skill the list lacks."""

    namespaces = (*plugins.own, *plugins.builtin)
    stray = [name for name in names if _stray(name, expected, namespaces)]
    listed = {name.rpartition(":")[2] for name in names}
    missing = [name for name in expected.skills if name not in listed]
    problems = [f"not the arm's: {', '.join(stray)}"] if stray else []
    problems += [f"the workspace's skills did not load: {', '.join(missing)}"] if missing else []
    return problems


def _skills_row(start: dict[str, Any], expected: Expected, plugins: Plugins) -> list[str]:
    """The skills row, from the start event's skill names (`_skill_problems`)."""

    skills = start.get("skills")
    if not isinstance(skills, list):
        return _row("skills", "UNVERIFIED", "the start event names no skills")
    names = [str(s.get("name") if isinstance(s, dict) else s) for s in skills]
    problems = _skill_problems(names, expected, plugins)
    built = sorted({n for n in names if n in BUILTIN_SKILLS})
    detail = "; ".join(problems) or f"{len(names)} listed; built in accepted: {built or 'none'}"
    return _row("skills", "FAIL" if problems else "PASS", detail)


def attachments(records: list[dict[str, Any]] | None, kind: str) -> list[dict[str, Any]]:
    """The native session's attachments of type `kind`, in order."""

    found = []
    for record in records or []:
        attached = record.get("attachment") if record.get("type") == "attachment" else None
        if isinstance(attached, dict) and attached.get("type") == kind:
            found.append(attached)
    return found


def _listing_row(
    records: list[dict[str, Any]] | None, expected: Expected, plugins: Plugins
) -> list[str]:
    """The skill-listing row: the skills the native session shows the model was told of (its
    `skill_listing` attachments' names), checked as the start event's are; UNVERIFIED where the
    session holds no such record."""

    listings = attachments(records, "skill_listing")
    names = [str(n) for item in listings for n in item.get("names") or [] if isinstance(n, str)]
    if not listings:
        return _row("skill-listing", "UNVERIFIED", "the native session holds no skill listing")
    problems = _skill_problems(sorted(set(names)), expected, plugins)
    detail = "; ".join(problems) or f"{len(set(names))} skills listed to the model"
    return _row("skill-listing", "FAIL" if problems else "PASS", detail)


def _instructions_row(records: list[dict[str, Any]] | None, expected: Expected) -> list[str]:
    """The instruction-files row, from the native session's `instructions` attachments (each
    `files: [{path, type, content}]`): every file loaded lies in the workspace, and every file
    the workspace should give at start loaded. UNVERIFIED where the session holds no such
    record or the workspace is not known."""

    loaded = [
        item
        for attached in attachments(records, "instructions")
        for item in attached.get("files") or []
        if isinstance(item, dict)
    ]
    if expected.workdir is None or not attachments(records, "instructions"):
        detail = "the native session holds no instructions record"
        return _row("instruction-files", "UNVERIFIED", detail)
    workdir = expected.workdir.resolve()
    outside = [
        f"{item.get('path')} ({item.get('type')})"
        for item in loaded
        if not _inside(item.get("path"), (workdir,))
    ]
    seen = {
        Path(str(item["path"])).resolve().relative_to(workdir).as_posix()
        for item in loaded
        if _inside(item.get("path"), (workdir,))
    }
    missing = [name for name in expected.instructions if name not in seen]
    problems = [f"not the workspace's: {', '.join(outside)}"] if outside else []
    problems += [f"the workspace's did not load: {', '.join(missing)}"] if missing else []
    detail = "; ".join(problems) or f"loaded {sorted(seen) or 'none'}, all in the workspace"
    return _row("instruction-files", "FAIL" if problems else "PASS", detail)


def _hook_owners(
    records: list[dict[str, Any]] | None, expected: Expected, plugins: Plugins
) -> dict[str, set[str]]:
    """Whose each hook the native session shows running is, by hook name: `arm` where the
    command it ran lies in a plugin folder the arm adds, `builtin` where it lies in a built-in
    plugin's folder, `other` for any other command."""

    owners: dict[str, set[str]] = {}
    for kind in HOOK_RECORDS:
        for attached in attachments(records, kind):
            command = attached.get("command")
            if not isinstance(command, str) or not command:
                continue
            words = [w for w in command.replace("'", " ").replace('"', " ").split() if "/" in w]
            if any(_inside(w, expected.plugin_dirs) for w in words):
                owner = "arm"
            elif any(_inside(w, plugins.builtin_paths) for w in words):
                owner = "builtin"
            else:
                owner = "other"
            owners.setdefault(str(attached.get("hookName")), set()).add(owner)
    return owners


def _named_source(event: dict[str, Any], plugins: Plugins) -> str | None:
    """`builtin` or `managed` where a hook event names its source as a built-in plugin or the
    managed policy; None where it names none."""

    for key in ("source", "hook_source", "hookSource", "plugin"):
        value = event.get(key)
        if not isinstance(value, str):
            continue
        if value.endswith(BUILTIN) or value.removeprefix("plugin:") in plugins.builtin:
            return "builtin"
        if value in ("policySettings", "managed"):
            return "managed"
    return None


def _hook_kinds(
    events: list[dict[str, Any]], owners: dict[str, set[str]], plugins: Plugins
) -> dict[str, list[str]]:
    """Each hook the stream or the native session shows, by whose it is: the source its event
    names, else its native record's owner (`_hook_owners`), else `unattributed`."""

    kinds: dict[str, list[str]] = {}

    def add(kind: str, name: str) -> None:
        if name not in kinds.setdefault(kind, []):
            kinds[kind].append(name)

    for event in events:
        if event.get("type") == "system" and event.get("subtype") in HOOK_EVENTS:
            name = str(event.get("hook_name"))
            named = _named_source(event, plugins)
            for kind in {named} if named else owners.get(name, {"unattributed"}):
                add(kind, name)
    for name, found in owners.items():
        for kind in found:
            add(kind, name)
    return kinds


def _hooks_row(
    events: list[dict[str, Any]],
    expected: Expected,
    plugins: Plugins,
    records: list[dict[str, Any]] | None = None,
) -> list[str]:
    """The hooks row. A hook is attributed by the source its event names, or by the command its
    native record shows (`_hook_owners`): one of a built-in plugin or the managed policy is
    recorded and never voids the cell; one that ran a command outside the arm's and the
    built-in plugins' folders fails it; one with no attribution fails an arm that adds no
    plugin and stays UNVERIFIED in an arm that does. No hook event at all stays UNVERIFIED:
    the start event names no hooks."""

    sorted_hooks = _hook_kinds(events, _hook_owners(records, expected, plugins), plugins)
    if not sorted_hooks:
        detail = "no hook event in the stream or the session; the start event names no hooks"
        return _row("hooks", "UNVERIFIED", detail)
    detail = "; ".join(
        f"{kind}: {', '.join(names)}" for kind, names in sorted(sorted_hooks.items())
    )
    if "other" in sorted_hooks or ("unattributed" in sorted_hooks and not expected.plugin_dirs):
        return _row("hooks", "FAIL", f"a hook the arm does not add ran: {detail}")
    if "unattributed" in sorted_hooks:
        return _row("hooks", "UNVERIFIED", f"not all attributed to the arm's plugin: {detail}")
    return _row("hooks", "PASS", detail)


def loading_check(
    events: list[dict[str, Any]],
    expected: Expected,
    records: list[dict[str, Any]] | None = None,
) -> list[list[str]]:
    """What the call loaded, from its start event, its hook events and its native session's
    records (`records`), each item `PASS`, `FAIL` or `UNVERIFIED`. A field or record the call
    does not carry is UNVERIFIED, never a pass; a plugin, skill, MCP server, hook or
    instruction file the arm does not add is a FAIL."""

    start = start_event(events)
    if start is None:
        return [_row("start-event", "FAIL", "the stream has no single start event")]
    plugins_row, plugins = _plugins_row(start, expected)
    rows = [_row("start-event", "PASS", "one system init event"), plugins_row]
    rows.append(_skills_row(start, expected, plugins))
    rows.append(_listing_row(records, expected, plugins))
    servers = start.get("mcp_servers")
    if not isinstance(servers, list):
        rows.append(_row("mcp-servers", "UNVERIFIED", "the start event names no MCP servers"))
    else:
        named = [str(s.get("name") if isinstance(s, dict) else s) for s in servers]
        rows.append(_row("mcp-servers", "FAIL" if named else "PASS", ", ".join(named) or "none"))
    rows.append(_hooks_row(events, expected, plugins, records))
    rows.append(_instructions_row(records, expected))
    return rows


def isolation_verdict(rows: list[list[str]]) -> tuple[str, list[str]]:
    """The cell's isolation verdict over its rows: FAIL where any fails, else UNVERIFIED where
    any is unverified, else PASS; and the items behind it."""

    for verdict in ("FAIL", "UNVERIFIED"):
        items = [row[0] for row in rows if row[1] == verdict]
        if items:
            return verdict, items
    return "PASS", []


def _has_text(path: Path) -> bool:
    try:
        return path.is_file() and bool(path.read_bytes().strip())
    except OSError:
        return True  # unreadable reads as present, never as clean


def above(folder: Path) -> list[str]:
    """Each instruction file and rules file Claude Code would read from `folder` or a folder
    above it."""

    resolved = folder.resolve()
    found = []
    for place in (resolved, *resolved.parents):
        found += [str(place / name) for name in ANCESTOR_FILES if (place / name).is_file()]
        rules = place / ANCESTOR_RULES
        if rules.is_dir():
            found += [str(path) for path in sorted(rules.rglob("*.md"))]
    return found


def managed(platform: str | None = None) -> tuple[list[str], list[str]]:
    """What the managed policy of this machine gives every session: the problems (a managed
    CLAUDE.md with text, a managed settings file that loads code, instructions or tools, or one
    that cannot be read) and what else it sets, applied to every arm alike."""

    folder = MANAGED.get(platform or sys.platform)
    if folder is None or not folder.is_dir():
        return [], []
    problems, alike = [], []
    if _has_text(folder / "CLAUDE.md"):
        problems.append(f"{folder / 'CLAUDE.md'} instructs every session")
    settings = folder / "managed-settings.json"
    if settings.is_file():
        try:
            document = json.loads(settings.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            document = None
        if not isinstance(document, dict):
            problems.append(f"{settings} is not readable settings")
        else:
            loading = sorted(key for key in document if key in LOADING_KEYS)
            if loading:
                problems.append(f"{settings} sets {', '.join(loading)}")
            alike.append(f"{settings} sets {', '.join(sorted(document)) or 'nothing'}")
    return problems, alike


def reach_rows(workdir: Path, fresh: tuple[Path, ...] = ()) -> list[list[str]]:
    """What a call in `workdir` would read besides its workspace, checked before it runs:
    instruction or rules files in a folder above the workspace (which would also hide its
    AGENTS.md), the machine's managed policy, and each of the cell's fresh folders (`fresh`:
    its home, config and XDG folders), which must hold nothing."""

    over = above(workdir.parent)
    rows = [
        _row(
            "nothing-above-workspace",
            "FAIL" if over else "PASS",
            ", ".join(over) or "no instruction or rules file above the workspace",
        )
    ]
    problems, alike = managed()
    rows.append(
        _row(
            "managed-policy",
            "FAIL" if problems else "PASS",
            "; ".join(problems) or f"applies to every arm alike: {'; '.join(alike) or 'none'}",
        )
    )
    if fresh:
        held = [str(folder) for folder in fresh if not folder.is_dir() or any(folder.iterdir())]
        rows.append(
            _row(
                "fresh-home",
                "FAIL" if held else "PASS",
                f"not new and empty: {', '.join(held)}" if held else "home, config and XDG new",
            )
        )
    return rows


def failed(rows: list[list[str]]) -> list[str]:
    """Each row that failed, as `<item>: <detail>`."""

    return [f"{item}: {detail}" for item, verdict, detail in rows if verdict == "FAIL"]


def expected_start(workdir: Path, model: str, expected: Expected, session: str) -> dict[str, Any]:
    """A synthetic start event for a cell that loads exactly what it should: its plugins, its
    workspace's skills and nothing else. It stands in for the CLI's own in a dry run, which
    checks the setup and the check, never what a model loaded."""

    return {
        "type": "system",
        "subtype": "init",
        "cwd": str(workdir),
        "session_id": session,
        "tools": ["Bash", "Edit", "Read", "Write"],
        "mcp_servers": [],
        "model": model,
        "permissionMode": "acceptEdits",
        "apiKeySource": "none",
        "skills": [*expected.skills],
        "plugins": [
            {"name": folder.name, "path": str(folder), "source": f"{folder.name}@inline"}
            for folder in expected.plugin_dirs
        ],
    }


def expected_records(expected: Expected, session: str) -> list[dict[str, Any]]:
    """Synthetic native records for a cell that loads exactly what it should: the instruction
    files its workspace gives, and its skills listed to the model."""

    workdir = expected.workdir or Path("/workspace")
    files = [
        {"path": str(workdir / name), "type": "Project", "content": ""}
        for name in expected.instructions
    ]
    listing = {"type": "skill_listing", "names": [*expected.skills], "skillCount": 0}
    return [
        {"type": "attachment", "sessionId": session, "attachment": attached}
        for attached in ({"type": "instructions", "files": files}, listing)
    ]


def leaked_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The synthetic native records with a user-level rules file loaded, as a person's own
    setup would add: records the check must fail."""

    session = str(records[0].get("sessionId")) if records else ""
    stray = {"path": "/user/.claude/rules/stray.md", "type": "User", "content": ""}
    attached = {"type": "instructions", "files": [stray]}
    return [*records, {"type": "attachment", "sessionId": session, "attachment": attached}]


def leaked_start(start: dict[str, Any]) -> list[dict[str, Any]]:
    """The synthetic start event with a plugin, a skill and a hook the arm does not add, as a
    leak from a person's own setup would show: the events of a cell the check must fail."""

    plugin = {"name": "stray", "path": "/stray/plugin", "source": "stray@market"}
    hook = {
        "type": "system",
        "subtype": "hook_started",
        "hook_id": "h1",
        "hook_name": "SessionStart:startup",
        "hook_event": "SessionStart",
        "session_id": start["session_id"],
    }
    leaked = {**start, "plugins": [*start["plugins"], plugin]}
    leaked["skills"] = [*start["skills"], "stray-skill"]
    return [leaked, hook]


def model_names(events: list[dict[str, Any]]) -> set[str]:
    """Each model the stream's start event and main-thread assistant messages name."""

    found = set()
    start = start_event(events)
    if start and isinstance(start.get("model"), str):
        found.add(start["model"])
    for event in events:
        message = event.get("message") if event.get("type") == "assistant" else None
        if event.get("parent_tool_use_id") is None and isinstance(message, dict):
            model = message.get("model")
            if isinstance(model, str) and model and model != SYNTHETIC:
                found.add(model)
    return found


TOKEN = re.compile(r"(?i)(token|key|secret|password|auth|credential)")


def shown_env(env: dict[str, str]) -> dict[str, str]:
    """An environment as a dry run prints it: a credential's value is `<set>`."""

    return {key: "<set>" if TOKEN.search(key) else value for key, value in sorted(env.items())}
