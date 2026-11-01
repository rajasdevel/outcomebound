"""The long-session protocol between the driver and the fixtures: what `next_turn` prints, and the
turn and action records the driver writes for `next_turn` and the graders. One checker for both
sides, so the driver, the fixtures' scripts and their reference evidence agree on one format."""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

VERSION = 1
LABEL = re.compile(r"[a-z][a-z-]*\Z")
ACTION_KINDS = ("command", "file_change", "tool")
ACTION_STATUSES = ("ok", "failed", "refused", "unknown")
# The orchestration tools a run may call to delegate: known tools, recorded as `tool` actions.
ORCHESTRATION_TOOLS = (
    "spawn_agent",
    "send_message",
    "followup_task",
    "wait_agent",
    "sleep",
    "Task",
    "Agent",
)


class ProtocolError(ValueError):
    """A record that breaks the protocol."""


def _check(condition: bool, problem: str) -> None:
    if not condition:
        raise ProtocolError(problem)


def labels(value: Any) -> tuple[str, ...]:
    """The labels a fixture declares in session.json: a non-empty list of lowercase words."""

    _check(isinstance(value, list) and bool(value), "labels is a non-empty list")
    _check(all(isinstance(x, str) and LABEL.match(x) for x in value), "each label is a-z and -")
    _check(len(set(value)) == len(value), "labels are distinct")
    return tuple(value)


def next_turn(document: Any, declared: tuple[str, ...]) -> dict[str, Any]:
    """Check one `next_turn` output and return it with its defaults filled in."""

    _check(isinstance(document, dict), "next_turn prints one JSON object")
    if document.get("end") is True:
        _check(
            set(document) <= {"end", "reason", "protocol_defect", "unmatched"}, "unknown end fields"
        )
        _check(isinstance(document.get("reason"), str) and bool(document["reason"]), "reason")
        defect = document.get("protocol_defect", False)
        _check(isinstance(defect, bool), "protocol_defect is true or false")
        result = {"end": True, "reason": document["reason"], "protocol_defect": defect}
        if "unmatched" in document:
            _check(isinstance(document["unmatched"], bool), "unmatched is true or false")
            result["unmatched"] = document["unmatched"]
        return result
    known = {"label", "message", "required", "clarification", "wait_seconds", "unmatched"}
    _check(
        set(document) <= known, "unknown turn fields: " + ", ".join(sorted(set(document) - known))
    )
    label, message = document.get("label"), document.get("message")
    _check(isinstance(label, str) and label in declared, f"label {label!r} is not declared")
    _check(isinstance(message, str) and bool(message.strip()), "message is non-empty text")
    _check("\0" not in message, "message holds no NUL")
    turn = {
        "label": label,
        "message": message,
        "required": document.get("required", False),
        "clarification": document.get("clarification", False),
        "wait_seconds": document.get("wait_seconds", 0),
    }
    _check(isinstance(turn["required"], bool), "required is true or false")
    _check(isinstance(turn["clarification"], bool), "clarification is true or false")
    if "unmatched" in document:
        _check(isinstance(document["unmatched"], bool), "unmatched is true or false")
        turn["unmatched"] = document["unmatched"]
    wait = turn["wait_seconds"]
    _check(type(wait) in (int, float) and 0 <= wait <= 7200, "wait_seconds is 0 to 7200")
    return turn


def action(record: Any) -> None:
    """Check one action record: an executed command, a file change or a tool call, once."""

    _check(isinstance(record, dict), "an action is an object")
    _check(record.get("kind") in ACTION_KINDS, "kind is command, file_change or tool")
    _check(isinstance(record.get("session_id"), str), "session_id is text")
    _check(isinstance(record.get("child"), bool), "child is true or false")
    if "status" in record:
        _check(record["status"] in ACTION_STATUSES, "status is ok, failed, refused or unknown")
    if record["kind"] == "command":
        _check(isinstance(record.get("command"), str), "a command action holds its command text")
        _check(isinstance(record.get("cwd"), str), "a command action holds its cwd")
        code = record.get("exit_code")
        _check(code is None or type(code) is int, "exit_code is a whole number or null")
        if "status" in record:
            _check(
                (record["status"] == "ok" and code == 0)
                or (record["status"] == "failed" and code != 0)
                or (record["status"] in ("refused", "unknown") and code is None),
                "exit_code agrees with status",
            )
        argv = record.get("argv")
        _check(
            argv is None or (isinstance(argv, list) and all(isinstance(x, str) for x in argv)),
            "argv",
        )
        if "segments" in record:
            _check(isinstance(record["segments"], list), "segments is a list")
            for segment in record["segments"]:
                _segment(segment)
    if record["kind"] == "file_change" or (record["kind"] == "tool" and "paths" in record):
        paths = record.get("paths")
        _check(
            isinstance(paths, list)
            and all(
                isinstance(x, str)
                and "\0" not in x
                and (PurePosixPath(x).is_absolute() or PureWindowsPath(x).is_absolute())
                for x in paths
            ),
            "paths are absolute path strings",
        )
    if record["kind"] == "tool":
        _check(isinstance(record.get("tool"), str) and bool(record["tool"]), "tool names the tool")
        if "output_mode" in record:
            _check(
                record["output_mode"] in ("content", "files_with_matches", "count"),
                "output_mode is content, files_with_matches or count",
            )


def _segment(record: Any) -> None:
    _check(isinstance(record, dict), "a segment is an object")
    _check(
        set(record) == {"argv", "cwd", "status", "reads", "writes", "runs"},
        "segment fields are argv, cwd, status, reads, writes and runs",
    )
    argv = record["argv"]
    _check(
        argv is None
        or (isinstance(argv, list) and all(isinstance(x, str) and "\0" not in x for x in argv)),
        "segment argv is a list of strings or null",
    )
    _check(
        record["status"] in ("ok", "failed", "unknown"), "segment status is ok, failed or unknown"
    )
    for key in ("reads", "writes", "cwd"):
        paths = [record[key]] if key == "cwd" else record[key]
        _check(
            isinstance(paths, list)
            and all(
                isinstance(p, str)
                and "\0" not in p
                and (PurePosixPath(p).is_absolute() or PureWindowsPath(p).is_absolute())
                for p in paths
            ),
            f"segment {key} holds absolute path strings",
        )
    runs = record["runs"]
    _check(
        runs is None
        or (
            isinstance(runs, list)
            and all(
                isinstance(argv, list)
                and bool(argv)
                and all(isinstance(x, str) and "\0" not in x for x in argv)
                for argv in runs
            )
        ),
        "segment runs is a list of argv lists or null",
    )


def turns(document: Any) -> list[dict[str, Any]]:
    """Check an `OB_TURNS` or `OB_HISTORY` document and return its turns."""

    _check(isinstance(document, dict) and document.get("version") == VERSION, "version 1")
    rows = document.get("turns")
    _check(isinstance(rows, list), "turns is a list")
    for number, row in enumerate(rows, 1):
        _check(isinstance(row, dict) and row.get("turn") == number, f"turn {number} is numbered")
        for key in ("label", "message", "answer", "answer_path", "session_id"):
            _check(isinstance(row.get(key), str), f"turn {number}: {key} is text")
        for key in ("required", "clarification"):
            _check(isinstance(row.get(key), bool), f"turn {number}: {key} is true or false")
        if "unmatched" in row:
            _check(isinstance(row["unmatched"], bool), f"turn {number}: unmatched is true or false")
        _check(isinstance(row.get("actions"), list), f"turn {number}: actions is a list")
        for item in row["actions"]:
            action(item)
    return rows


def actions(document: Any) -> list[dict[str, Any]]:
    """Check an `OB_ACTIONS` document: every action of the run once, each with its turn."""

    _check(isinstance(document, dict) and document.get("version") == VERSION, "version 1")
    rows = document.get("actions")
    _check(isinstance(rows, list), "actions is a list")
    for item in rows:
        action(item)
        _check(type(item.get("turn")) is int and item["turn"] >= 1, "an action names its turn")
    return rows


def diagnostics(plan: Any) -> dict[str, str]:
    """The optional claim labels reported beside effect verdicts."""
    result = {}
    for claim in plan["claims"]:
        risk = claim.get("risk", "")
        for label in ("WORDING only", "COMMAND TEXT only"):
            if isinstance(risk, str) and risk.startswith(label):
                _check(claim.get("required", True) is False, label + " claims are not required")
                result[claim["name"]] = label
    return result
