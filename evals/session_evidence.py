"""Keep child evidence, decode native tools and diagnose references to sealed inputs."""

from __future__ import annotations

import ast
import glob
import json
import re
import shlex
from pathlib import Path
from typing import Any

from evals.claude_stream import bash_outcome, directories, stream_transcript
from evals.codex_events import command_outcome
from evals.native_commands import directory_of, native_commands
from evals.native_receipts import copy_exact, parse_records
from evals.session_protocol import ORCHESTRATION_TOOLS
from evals.session_shell import (
    LiteralWord,
    braces,
    command_segments,
    path_expansions,
    recursive,
)
from evals.session_usage import CallUsage

_JS_TOKENS = re.compile(
    r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`'
    r"|//[^\n]*|/\*.*?\*/|[\w$]+|[^\s]",
    re.S,
)


def _js_string(token: str) -> str:
    if not token.startswith("`"):
        return str(ast.literal_eval(token))
    if "${" in token:
        raise ValueError("dynamic template")
    body = token[1:-1].replace('"', '\\"').replace("\n", "\\n").replace("\\`", "`")
    return str(json.loads('"' + body + '"'))


def _js_argument(tokens: list[str], start: int) -> Any:
    depth, literal = 0, []
    for j in range(start, len(tokens)):
        token = tokens[j]
        if depth == 0 and token in (",", ")"):
            break
        if token in ("{", "["):
            depth += 1
        elif token in ("}", "]"):
            depth -= 1
        if token.startswith(("'", '"', "`")):
            token = json.dumps(_js_string(token))
        elif re.fullmatch(r"[\w$]+", token) and tokens[j + 1 : j + 2] == [":"]:
            token = json.dumps(token)
        literal.append(token)
    return json.loads("".join(literal))


def _exec_requests(tool: dict[str, Any]) -> list[dict[str, Any]]:
    """Literal nested requests of a native exec wrapper; never execute its JavaScript."""
    tokens = [t for t in _JS_TOKENS.findall(str(tool["input"])) if not t.startswith(("//", "/*"))]
    found = []
    for i in range(len(tokens) - 4):
        if tokens[i : i + 2] != ["tools", "."] or tokens[i + 3] != "(":
            continue
        try:
            args = _js_argument(tokens, i + 4)
        except (ValueError, SyntaxError):
            continue
        found.append(
            {**tool, "id": f"{tool['id']}:{i}", "name": tokens[i + 2], "input": args, "result": {}}
        )
    return found


def _native_item(
    result: list[dict[str, Any]],
    starts: dict[Any, dict[str, Any]],
    item: dict[str, Any],
    position: int,
    timestamp: Any,
    cwd: str,
) -> None:
    prior = starts.get(item.get("id"))
    if prior is not None:
        prior.update(input=item, cwd=item.get("cwd", cwd))
    else:
        native = {
            "position": position,
            "started_at": timestamp,
            "id": item.get("id"),
            "name": item["type"],
            "input": item,
            "cwd": item.get("cwd", cwd),
        }
        result.append(native)
        starts[item.get("id")] = native


def retain_children(children: list[tuple[Path, str, str]], keep: Path) -> list[dict[str, Any]]:
    result = []
    for i, (source, key, parent) in enumerate(children, 1):
        destination = keep.with_name(f"{keep.stem}.child-{i}.jsonl")
        raw = source.read_bytes()
        digest = copy_exact(source, raw, destination)
        result.append(
            {
                "path": str(source),
                "copy": str(destination),
                "sha256": digest,
                "session_id": key,
                "parent_id": parent,
                "child": True,
            }
        )
    return result


def native_tools(records: list[dict[str, Any]], harness: str) -> list[dict[str, Any]]:
    result = []
    cwd = ""
    starts: dict[Any, dict[str, Any]] = {}
    for position, row in enumerate(records):
        payload = row.get("payload") or {}
        cwd = row.get("cwd") or payload.get("cwd") or cwd
        if harness == "codex":
            if row.get("type") == "response_item" and payload.get("type") in (
                "function_call",
                "custom_tool_call",
            ):
                result.append(
                    {
                        "position": position,
                        "started_at": row.get("timestamp"),
                        "id": payload.get("call_id") or payload.get("id"),
                        "name": payload.get("name", "unknown"),
                        "input": payload.get("arguments", payload.get("input", "")),
                        "cwd": cwd,
                    }
                )
            item = payload.get("item")
            if (
                row.get("type") == "event_msg"
                and payload.get("type") in ("item_started", "item_completed")
                and isinstance(item, dict)
                and item.get("type") in ("CommandExecution", "FileChange")
            ):
                _native_item(result, starts, item, position, row.get("timestamp"), cwd)
        elif row.get("type") == "assistant":
            result.extend(
                {
                    "position": position,
                    "started_at": row.get("timestamp"),
                    "id": part.get("id"),
                    "name": part.get("name", "unknown"),
                    "input": part.get("input", {}),
                    "cwd": cwd,
                }
                for part in (row.get("message") or {}).get("content", [])
                if isinstance(part, dict) and part.get("type") == "tool_use"
            )
    results, denied = _tool_results(records, harness)
    for tool in result:
        tool["result"] = results.get(tool.get("id"), {})
        tool["denied"] = tool.get("id") in denied
    expanded = []
    for tool in result:
        if harness == "codex" and tool["name"].rsplit(".", 1)[-1] == "exec":
            expanded.extend(_exec_requests(tool))
        expanded.append(tool)
    for position, tool in enumerate(expanded):
        tool["position"] = position
    return expanded


def _tool_results(records: list[dict[str, Any]], harness: str) -> tuple[dict[Any, Any], set[Any]]:
    results = {}
    denied: set[Any] = set()
    for row in records:
        denied.update(
            part.get("tool_use_id")
            for part in row.get("permission_denials", [])
            if isinstance(part, dict)
        )
        if harness == "codex":
            payload = row.get("payload") or {}
            if row.get("type") != "response_item" or payload.get("type") not in (
                "function_call_output",
                "custom_tool_call_output",
            ):
                continue
            output = payload.get("output")
            if isinstance(output, str):
                try:
                    output = json.loads(output)
                except ValueError:
                    output = {"content": output}
            results[payload.get("call_id")] = output if isinstance(output, dict) else {}
        elif row.get("type") == "user":
            for part in (row.get("message") or {}).get("content", []):
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    results[part.get("tool_use_id")] = {
                        **part,
                        "native_result": row.get("toolUseResult"),
                    }
    return results, denied


def decode_native(records: list[dict[str, Any]], harness: str) -> dict[str, Any]:
    if harness == "claude-code":
        # Native transcripts omit the print-mode start and final result, but keep tool ids,
        # assistant messages and tool results in the same form as the stream.
        orchestration_ids = {
            part.get("id")
            for row in records
            for part in (row.get("message") or {}).get("content", [])
            if isinstance(part, dict) and part.get("name") in ORCHESTRATION_TOOLS
        }
        filtered = []
        for row in records:
            message = row.get("message") or {}
            if not isinstance(message.get("content"), list):
                continue
            content = [
                part
                for part in message["content"]
                if not isinstance(part, dict)
                or (
                    part.get("id") not in orchestration_ids
                    and part.get("tool_use_id") not in orchestration_ids
                )
            ]
            filtered.append({**row, "message": {**message, "content": content}})
        events = [
            {"type": "system", "subtype": "init"},
            *filtered,
            {"type": "result", "subtype": "success", "result": ""},
        ]
        transcript, decoded = stream_transcript(
            "\n".join(json.dumps(r) for r in events), "", directories(records)
        )
        return {**json.loads(transcript), "unknown_tools": decoded.unknown}
    items = native_commands(records)
    commands = [
        [shlex.join(item.get("command", [])), command_outcome(item), directory_of(item.get("cwd"))]
        for item in items
    ]
    files = []
    unknown = set()
    known = {
        "exec_command",
        "write_stdin",
        "shell",
        "shell_command",
        "apply_patch",
        "CommandExecution",
        "FileChange",
        "exec",  # The code-mode wrapper; native events hold its executed commands.
        "wait",
        "list_agents",
        "interrupt_agent",
        *ORCHESTRATION_TOOLS,
    }
    for tool in native_tools(records, harness):
        name = tool["name"].rsplit(".", 1)[-1]
        if name not in known:
            unknown.add(tool["name"])
        if name == "apply_patch":
            for kind, path in re.findall(
                r"^\*\*\* (Add|Update|Delete) File: (.+)$", str(tool["input"]), re.M
            ):
                files.append([kind, path, "unverified"])
        if name == "FileChange":
            files.extend(
                [change.get("kind", "change"), change.get("path", ""), "unverified"]
                for change in tool["input"].get("changes", [])
                if isinstance(change, dict)
            )
    return {
        "commands": commands,
        "outputs": [i.get("aggregated_output") for i in items],
        "files": files,
        "events": [],
        "unknown_tools": sorted(unknown),
    }


def command_text(value: Any) -> str:
    """Native argv may contain a shell wrapper; keep the shell's actual command text."""
    if isinstance(value, list):
        if (
            len(value) >= 3
            and Path(value[0]).name in ("sh", "bash", "zsh")
            and value[1] in ("-c", "-lc", "-ic")
        ):
            return value[2]
        return shlex.join(value)
    return value if isinstance(value, str) else ""


def simple_argv(command: str) -> list[str] | None:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>")
        lexer.whitespace_split = True
        words = list(lexer)
    except ValueError:
        return None
    if any(re.fullmatch(r"[;&|()<>]+", word) for word in words) or "\n" in command:
        return None
    return words


def _arguments(tool: dict[str, Any]) -> dict[str, Any]:
    value = tool["input"]
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def _named_paths(args: dict[str, Any], name: str = "") -> list[str]:
    paths = [
        args[key]
        for key in ("file", "file_path", "notebook_path", "path", "directory")
        if isinstance(args.get(key), str)
    ]
    for key in ("paths", "files"):
        if isinstance(args.get(key), list):
            paths.extend(p for p in args[key] if isinstance(p, str))
    if name == "Glob" and isinstance(args.get("pattern"), str):
        paths.append(str(Path(args.get("path") or ".") / args["pattern"]))
    return list(dict.fromkeys(paths))


def _file_action(
    tool: dict[str, Any],
    args: dict[str, Any],
) -> dict[str, Any]:
    name = tool["name"].rsplit(".", 1)[-1]
    if name == "FileChange":
        entries = args.get("changes", [])
        paths = list(entries) if isinstance(entries, dict) else [c.get("path", "") for c in entries]
    elif name == "apply_patch":
        paths = re.findall(
            r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+)$",
            str(tool["input"]),
            re.M,
        )
    else:
        action = {"kind": "tool", "tool": tool["name"], "paths": _named_paths(args, name)}
        if "output_mode" in args:
            action["output_mode"] = args["output_mode"]
        return action
    return {"kind": "file_change", "paths": paths}


def _tool_outcome(tool: dict[str, Any], harness: str) -> tuple[int | None, str]:
    result = tool["result"]
    if harness == "claude-code":
        return bash_outcome(result, denied=tool["denied"])
    if tool["name"] == "FileChange":
        status = tool["input"].get("status")
        return {
            "completed": (0, "ok"),
            "failed": (None, "failed"),
            "declined": (None, "refused"),
        }.get(status, (None, "unknown"))
    metadata = result.get("metadata")
    if isinstance(metadata, dict):
        result = {**metadata, **result}
    if any(k in result for k in ("is_error", "exit_code", "exitCode", "status")):
        if result.get("status") in ("completed", "success", "ok") and not any(
            type(result.get(k)) is int for k in ("exit_code", "exitCode")
        ):
            result = {**result, "exit_code": 0}
        return bash_outcome(result)
    content = result.get("content", "")
    if isinstance(content, str):
        if content.startswith("Success."):
            return 0, "ok"
        if re.match(r"(?i)(?:error|failed)\b", content):
            return None, "failed"
    return None, "unknown"


def _invocation_cwd(tool: dict[str, Any], workspace: Path | None) -> str:
    args = _arguments(tool)
    known = directory_of(tool.get("cwd")) or workspace
    selected = args.get("workdir") or args.get("cwd") or "."
    if not known and not directory_of(selected):
        return ""
    return str((Path(known or ".") / (directory_of(selected) or selected)).resolve())


def _matching_request(
    request: dict[str, Any], event: dict[str, Any], workspace: Path | None
) -> bool:
    if event["name"] == "CommandExecution":
        args = _arguments(request)
        return command_text(args.get("cmd", args.get("command"))) == command_text(
            event["input"].get("command")
        ) and _invocation_cwd(request, workspace) == _invocation_cwd(event, workspace)
    if request["name"].rsplit(".", 1)[-1] != "apply_patch":
        return False

    def paths(tool: dict[str, Any]) -> set[str]:
        cwd = Path(directory_of(tool.get("cwd")) or ".")
        return {str((cwd / p).resolve()) for p in _file_action(tool, _arguments(tool))["paths"]}

    return bool(paths(request)) and paths(request) == paths(event)


def _action_links(
    tools: list[dict[str, Any]], workspace: Path | None
) -> tuple[dict[int, dict[str, Any]], set[int]]:
    """A completion and its request name one act, including completion on a later turn."""
    pending: list[dict[str, Any]] = []
    links: dict[int, dict[str, Any]] = {}
    used: set[int] = set()
    for tool in tools:
        name = tool["name"].rsplit(".", 1)[-1]
        if name in ("exec_command", "shell", "shell_command", "apply_patch"):
            pending.append(tool)
        if name not in ("CommandExecution", "FileChange"):
            continue
        identity = tool["input"].get("call_id") or tool.get("id")
        matches = [t for t in pending if t.get("id") == identity] if identity else []
        # A native call id, when present, is authoritative. Event item ids need not be call ids.
        if not matches and not tool["input"].get("call_id"):
            matches = [t for t in pending if _matching_request(t, tool, workspace)]
        if len(matches) == 1:
            match = matches[0]
            pending.remove(match)
            used.add(match["position"])
            links[tool["position"]] = match
    return links, used


def _result_output(result: dict[str, Any]) -> Any:
    for key in ("content", "aggregated_output", "output"):
        if result.get(key) is not None:
            return result[key]
    return [result[key] for key in ("stdout", "stderr") if result.get(key) is not None] or None


def _output_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return _output_text(value.get("text"))
    if isinstance(value, list):
        return "\n".join(_output_text(part) for part in value)
    return ""


def _native_actions(
    rows: list[dict[str, Any]],
    harness: str,
    session: str,
    child: bool,
    parent: str | None,
    workspace: Path | None,
) -> list[tuple[str, dict[str, Any]]]:
    tools = native_tools(rows, harness)
    links, used = _action_links(tools, workspace)
    actions = []
    # The native completed events are authoritative; function calls are their requests.
    for tool in tools:
        if tool["position"] in used:
            continue
        name = tool["name"].rsplit(".", 1)[-1]
        args = _arguments(tool)
        cwd = _invocation_cwd(tool, workspace)
        result = tool["result"]
        source = links.get(tool["position"], tool)
        record: dict[str, Any] = {
            "session_id": session,
            "child": child,
            "parent_session_id": parent,
            "started_at": source.get("started_at"),
            "cwd": cwd,
            "exit_code": None,
        }
        command = None
        if name == "CommandExecution":
            command = command_text(args.get("command"))
            record["exit_code"] = args.get("exit_code")
            record["status"] = _command_status(args)
            if record["status"] == "unknown":
                record["exit_code"], record["status"] = _tool_outcome(source, harness)
            record["output"] = args.get("aggregated_output") or _result_output(source["result"])
        elif name in ("Bash", "exec_command", "shell", "shell_command"):
            command = command_text(args.get("cmd", args.get("command")))
            record["exit_code"], record["status"] = (
                bash_outcome(
                    result,
                    denied=tool["denied"],
                    background=args.get("run_in_background") is True,
                )
                if name == "Bash"
                else _tool_outcome(tool, harness)
            )
            record["output"] = _result_output(result)
        if command is not None:
            record.update(kind="command", command=command, argv=simple_argv(command))
            record["segments"] = command_segments(
                command, Path(cwd) if cwd else None, record["status"], record.get("output")
            )
        else:
            file_action = _file_action(tool, args)
            record.update(file_action)
            record["exit_code"], record["status"] = _tool_outcome(tool, harness)
            record["paths"] = [
                str((Path(cwd) / p).resolve())
                for p in file_action["paths"]
                if cwd or Path(p).is_absolute()
            ]
        if record.get("output") is None:
            record.pop("output", None)
        key = str(
            source.get("id") or f"{source.get('started_at')}:{source['position']}:{source['name']}"
        )
        actions.append((source["position"], key, record))
    return [(key, record) for _, key, record in sorted(actions, key=lambda item: item[0])]


def _command_status(args: dict[str, Any]) -> str:
    code = args.get("exit_code")
    if type(code) is int:
        return "ok" if code == 0 else "failed"
    return {"failed": "failed", "declined": "refused"}.get(str(args.get("status")), "unknown")


class ActionLedger:
    """One native action per session and native id, across resumes and retained snapshots."""

    def __init__(self) -> None:
        self.seen: set[tuple[str, str]] = set()
        self.records: dict[tuple[str, str], dict[str, Any]] = {}

    def add(
        self,
        copies: list[dict[str, Any]],
        harness: str,
        workspace: Path | None = None,
        fallback: str = "",
    ) -> list[dict[str, Any]]:
        actions = []
        for item in copies:
            raw = Path(item["copy"]).read_bytes()
            rows = parse_records(raw[: raw.rfind(b"\n") + 1])
            session = next(
                (r["payload"]["id"] for r in rows if r.get("type") == "session_meta"),
                item.get("session_id") or fallback or item["path"],
            )
            for key, action in _native_actions(
                rows,
                harness,
                session,
                bool(item.get("child")),
                item.get("parent_session_id", item.get("parent_id")),
                workspace,
            ):
                identity = (session, key)
                if identity not in self.seen:
                    self.seen.add(identity)
                    actions.append(action)
                    self.records[identity] = action
                elif identity in self.records:
                    self.records[identity].update(
                        {key: value for key, value in action.items() if value is not None}
                    )
        # Native file order breaks ties and supplies order where timestamps are absent.
        return sorted(actions, key=lambda action: action.get("started_at") or "")


def family_evidence(
    transcript: str, extras: dict[str, Any], harness: str, before: dict[Path, bytes]
) -> str:
    document = json.loads(transcript)
    children = []
    unknown = {
        name
        for name in extras.get("unknown_item_types", [])
        if name.removeprefix("tool.").rsplit(".", 1)[-1] not in ORCHESTRATION_TOOLS
    }
    meter = CallUsage(harness)
    orchestration = False
    for item in extras.get("native_sessions", []):
        raw = Path(item["copy"]).read_bytes()
        rows = parse_records(raw[: raw.rfind(b"\n") + 1])
        meter.add(rows, item.get("session_id", item["path"]))
        prior = before.get(Path(item["path"]), b"")
        new = parse_records(raw[len(prior[: prior.rfind(b"\n") + 1]) : raw.rfind(b"\n") + 1])
        decoded = decode_native(new, harness)
        orchestration |= any(
            tool["name"].rsplit(".", 1)[-1]
            in (*ORCHESTRATION_TOOLS, "wait", "list_agents", "interrupt_agent")
            for tool in native_tools(rows, harness)
        )
        unknown.update(decoded["unknown_tools"])
        if not item.get("child"):
            for field in ("commands", "outputs", "files"):
                if document.get(field) is None or harness == "claude-code":
                    document[field] = decoded.get(field)
            continue
        child = {"session_id": item["session_id"], "parent_id": item["parent_id"], **decoded}
        children.append(child)
        document["stdout"] = (
            document.get("stdout", "")
            + f"\n--- child session {item['session_id']} ---\n"
            + json.dumps(decoded)
        )
    document["children"] = children
    if orchestration:
        unknown.discard("item.collab_agent_tool_call")
    ledger = ActionLedger()
    for source, raw in before.items():
        rows = parse_records(raw[: raw.rfind(b"\n") + 1])
        session = next(
            (r["payload"]["id"] for r in rows if r.get("type") == "session_meta"), source.stem
        )
        ledger.seen.update(
            (session, key) for key, _ in _native_actions(rows, harness, session, False, None, None)
        )
    document["actions"] = ledger.add(extras.get("native_sessions", []), harness)
    document["unknown_tools"] = sorted(unknown)
    # A partial decoder cannot prove absence or completeness. Graders that need commands or
    # files receive no authoritative list; the raw native copies and child lists remain.
    if unknown:
        document["decoded_commands"] = document.get("commands")
        document["decoded_files"] = document.get("files")
        document["commands"], document["files"] = None, None
    extras.update(
        unknown_tools=sorted(unknown),
        decoder_verdict="UNVERIFIED" if unknown else "PASS",
        session_tokens=meter.total(),
        usage_reconciliation=meter.reconciliation(),
    )
    return json.dumps(document)


def _strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except ValueError:
            return [value]
        return [value, *_strings(decoded)] if not isinstance(decoded, str) else [value, decoded]
    return []


def _matches(
    word: str, target: str, cwd: Path | None, recursive: bool = False, workspace: Path | None = None
) -> bool:
    if not Path(target).is_absolute():
        return Path(word).name == target and not (
            workspace is not None
            and cwd is not None
            and (cwd / word).resolve().is_relative_to(workspace.resolve())
        )
    if not Path(word).is_absolute() and cwd is None:
        return False
    paths = path_expansions(word, cwd)
    protected = Path(target).resolve()
    if workspace is not None:
        paths = [p for p in paths if not p.resolve().is_relative_to(workspace.resolve())]
    return any(
        p.resolve().is_relative_to(protected)
        or (recursive and protected.is_relative_to(p.resolve()))
        for p in paths
    )


def _unresolved_paths(
    paths: list[str], directory: Path | None, workspace: Path | None = None
) -> bool:
    return (directory is None and any(not Path(p).is_absolute() for p in paths)) or any(
        glob.has_magic(p)
        and not glob.glob(str((directory or Path("/")) / p))
        and not (
            workspace is not None
            and all(
                path.resolve().is_relative_to(workspace.resolve())
                for path in path_expansions(p, directory)
            )
        )
        for word in paths
        for p in ([word] if isinstance(word, LiteralWord) else braces(word))
    )


def _segment_matches(path: str, target: str, recursive: bool, workspace: Path | None) -> bool:
    resolved = Path(path).resolve()
    if workspace is not None and resolved.is_relative_to(workspace.resolve()):
        return False
    if not Path(target).is_absolute():
        return resolved.name == target
    protected = Path(target).resolve()
    return resolved.is_relative_to(protected) or (recursive and protected.is_relative_to(resolved))


def _command_hits(
    command: str,
    segments: list[dict[str, Any]],
    forbidden: list[str],
    workspace: Path | None = None,
) -> list[dict[str, Any]]:
    """Path references are attempts, never evidence that a program read content."""
    hits: list[dict[str, Any]] = []
    for part in segments:
        directory = Path(part["cwd"])
        paths = [*part["reads"], *part["writes"]]
        for target in forbidden:
            matched = [
                p
                for p in paths
                if _segment_matches(
                    p,
                    target,
                    recursive(part["argv"])
                    or any(recursive(start) for start in part["runs"] or []),
                    workspace,
                )
            ]
            if not matched and not any(
                _matches(word, target, directory, workspace=workspace)
                for word in part["argv"] or []
            ):
                continue
            hits.append({"target": target, "classification": "attempt"})
        if part["argv"] is None or part["runs"] is None:
            hits.append({"target": None, "classification": "unresolved"})
    named = {hit["target"] for hit in hits}
    text = command.replace(str(workspace.resolve()), "<workspace>") if workspace else command
    hits.extend(
        {"target": target, "classification": "attempt"}
        for target in forbidden
        if target not in named and target in text
    )
    return list({tuple(hit.items()): {**hit, "command": command} for hit in hits}.values())


def contamination(
    copies: list[dict[str, Any]], harness: str, forbidden: list[str], workspace: Path | None = None
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for item in copies:
        raw = Path(item["copy"]).read_bytes()
        rows = parse_records(raw[: raw.rfind(b"\n") + 1])
        tools = {
            str(
                tool.get("id") or f"{tool.get('started_at')}:{tool['position']}:{tool['name']}"
            ): tool
            for tool in native_tools(rows, harness)
        }
        for key, action in _native_actions(
            rows,
            harness,
            item.get("session_id", item["path"]),
            bool(item.get("child")),
            item.get("parent_id"),
            workspace,
        ):
            tool = tools[key]
            args = _arguments(tool)
            name = tool["name"].rsplit(".", 1)[-1]
            directory = Path(action["cwd"]) if action["cwd"] else workspace
            if action["kind"] == "command":
                found = _command_hits(
                    action["command"],
                    action["segments"],
                    forbidden,
                    workspace,
                )
            else:
                texts = _strings(tool["input"])
                paths = action.get("paths", []) or _named_paths(args, name)
                found = []
                command = f"{tool['name']} {json.dumps(tool['input'])}"
                for target in forbidden:
                    named = name not in ORCHESTRATION_TOOLS and any(
                        _matches(p, target, directory, name in ("Grep", "Glob", "LS"), workspace)
                        for p in paths
                    )
                    if named or any(target in text for text in texts):
                        found.append(
                            {
                                "target": target,
                                "classification": "attempt",
                                "command": command,
                            }
                        )
                if _unresolved_paths(paths, directory, workspace):
                    found.append(
                        {"target": None, "classification": "unresolved", "command": command}
                    )
            hits.extend(
                {
                    "session": item.get("session_id", item["path"]),
                    "child": bool(item.get("child")),
                    "copy": item["copy"],
                    **tool,
                    "call_id": key,
                    "status": action["status"],
                    **hit,
                }
                for hit in found
            )
    return hits


def isolation_residual(
    hits: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    workspace: Path,
) -> list[dict[str, Any]]:
    """Keep static uncertainty for inspection, without deciding isolation."""
    residual: list[dict[str, Any]] = [
        {
            key: hit[key]
            for key in ("session", "child", "call_id", "command", "target")
            if key in hit
        }
        for hit in hits
        if hit["classification"] == "unresolved"
    ]
    for action in actions:
        if action["kind"] == "command":
            paths = [
                path
                for part in action["segments"]
                if part["argv"] is None or part["runs"] is None or part["status"] == "unknown"
                for path in (*part["reads"], *part["writes"])
            ]
            command = action["command"]
        elif action["kind"] == "tool" and action.get("status") in ("unknown", "failed"):
            paths = action.get("paths", [])
            command = action["tool"]
        else:
            continue
        uncovered = sorted(
            {
                str(Path(path).resolve())
                for path in paths
                if not Path(path).resolve().is_relative_to(workspace.resolve())
            }
        )
        if uncovered:
            residual.append({"command": command, "paths": uncovered})
    return list({json.dumps(row, sort_keys=True): row for row in residual}.values())
