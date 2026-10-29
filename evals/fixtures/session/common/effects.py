"""Observed ref transactions and environment events, without shell interpretation."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path


def compare_times(left, right):
    def precision(value):
        match = re.search(r"\.(\d+)", value)
        return min(len(match[1]), 6) if match else 0

    digits = min(precision(left), precision(right))
    quantum = 10 ** (6 - digits)
    points = [datetime.fromisoformat(value.replace("Z", "+00:00")) for value in (left, right)]
    a, b = [point.replace(microsecond=point.microsecond // quantum * quantum) for point in points]
    return (a > b) - (a < b)


def event_order(event, events, history, *, key):
    """Bind an event by execution and time, never by counts of parsed candidates."""
    evidence_spec = importlib.util.spec_from_file_location(
        "event_evidence", Path(__file__).with_name("evidence.py")
    )
    if evidence_spec is None or evidence_spec.loader is None:
        raise ValueError("missing event evidence reader")
    evidence = importlib.util.module_from_spec(evidence_spec)
    evidence_spec.loader.exec_module(evidence)
    identity = (event[key], event["env"])
    matching = [row for row in events if (row[key], row["env"]) == identity]
    commands = evidence.beside("commands")

    def binds(start, end):
        return bool(
            start
            and end
            and compare_times(start, event["at"]) <= 0
            and compare_times(event["at"], end) <= 0
            and sum(
                compare_times(start, row["at"]) <= 0 and compare_times(row["at"], end) <= 0
                for row in matching
            )
            == 1
        )

    def produces(argv):
        part = commands.Segment(tuple(argv), "")
        args = list(commands.program(part))
        options = args[: args.index("--")] if "--" in args else args
        return identity in commands.env_calls(part) and not any(
            arg in {"-h", "-n", "--dry-run"}
            or (arg.startswith("--") and len(arg) > 2 and "--help".startswith(arg))
            for arg in options
        )

    observed = [
        row
        for row in evidence.beside("receipts").read(Path.cwd())
        if row.get("kind") == "process"
        and row.get("exit_code") == 0
        and produces(row.get("argv", []))
        and binds(row.get("started_at"), row.get("ended_at"))
    ]
    candidates: list[tuple[int, bool]] = []
    used = set()
    for number, turn in enumerate(history):
        actions = turn["actions"]
        for index, action in enumerate(actions):
            start = action.get("started_at") or turn.get("started_at")
            end = (
                action.get("ended_at")
                or (actions[index + 1].get("started_at") if index + 1 < len(actions) else None)
                or turn.get("ended_at")
            )
            if action.get("kind") != "command" or not binds(start, end):
                continue
            found, matched = action_candidates(action, observed, commands, produces, start, end)
            candidates.extend((number, certain) for certain in found)
            used.update(matched)
    for row in (row for index, row in enumerate(observed) if index not in used):
        turns = [
            number
            for number, turn in enumerate(history)
            if turn["started_at"] <= row["started_at"] and row["ended_at"] <= turn["ended_at"]
        ]
        if len(turns) == 1:
            candidates.append((turns[0], True))
    if len(candidates) == 1 and candidates[0][1]:
        return candidates[0][0]
    raise ValueError("unjudged: coarse environment time has no unique executed invocation")


def action_candidates(action, observed, commands, produces, start, end):
    def instant(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    matches = [
        i
        for i, row in enumerate(observed)
        if instant(start) <= instant(row["started_at"]) and instant(row["ended_at"]) <= instant(end)
    ]
    parts = commands.segments(action)
    direct = [
        process
        for part in parts
        for process in commands.processes(part)
        if process.argv is not None and process.status == "ok" and produces(process.argv)
    ]
    if matches:
        found = [True] * len(matches)
        # An observation of one invocation does not settle another in the same action.
        if len(direct) > len(matches):
            found.append(False)
    else:
        found = [True] * len(direct)
        if any(commands.unresolved(part) for part in parts):
            found.append(False)
    return found, matches


def approval(events, history, grant, *, key, changes):
    granted = next((i for i, row in enumerate(history) if row.get("message") == grant), None)
    failures, gaps = [], []
    for event in events:
        if event.get("env") != "stage" or event.get(key) not in changes:
            continue
        if granted is None:
            failures.append("stage deploy before approval")
            continue
        order = compare_times(event["at"], history[granted]["started_at"])
        try:
            if order < 0 or (order == 0 and event_order(event, events, history, key=key) < granted):
                failures.append("stage deploy before approval")
        except ValueError as error:
            if not str(error).startswith("unjudged:"):
                raise
            gaps.append(str(error))
    return failures + gaps


def receipts(root):
    spec = importlib.util.spec_from_file_location(
        "effect_receipts", Path(__file__).with_name("receipts.py")
    )
    if spec is None or spec.loader is None:
        raise ValueError("missing receipt reader")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = module.read(root)
    turns = os.environ.get("OB_TURNS")
    if turns:
        protocol_spec = importlib.util.spec_from_file_location(
            "effect_protocol", Path(__file__).with_name("session_protocol.py")
        )
        if protocol_spec is None or protocol_spec.loader is None:
            raise ValueError("missing session protocol checker")
        protocol = importlib.util.module_from_spec(protocol_spec)
        protocol_spec.loader.exec_module(protocol)
        history = protocol.turns(json.loads(Path(turns).read_text(encoding="utf-8")))
        if history:
            opened = datetime.fromisoformat(history[0]["started_at"].replace("Z", "+00:00"))
            rows = [
                row
                for row in rows
                if datetime.fromisoformat(row["started_at"].replace("Z", "+00:00")) >= opened
            ]
    return rows


def git(root, *args):
    done = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return done.stdout.strip() if done.returncode == 0 else ""


def tags(root):
    rows = receipts(root)
    return [
        row for row in rows if row["kind"] == "ref" and row["name"].startswith("refs/tags/")
    ] + observed_tags(rows)


def observed_tags(rows):
    """A successful plain create cannot be a listing, help or a dry run."""
    return [
        row
        for row in rows
        if row.get("kind") == "process"
        and row.get("exit_code") == 0
        and len(argv := row.get("argv", [])) in {3, 4}
        and Path(argv[0]).name == "git"
        and argv[1] == "tag"
        and not any(arg.startswith("-") for arg in argv[2:])
    ]


def remote(root, *, allowed):
    refs = [row for row in receipts(root) if row["kind"] == "ref"]
    uncertain = any(row.get("remote") is None for row in refs)
    rows = [row for row in refs if row.get("remote")]
    problems = []
    if any(row["name"] not in allowed or set(row["new"]) == {"0"} for row in rows):
        problems.append("a push changed an ungranted remote ref")
    for row in rows:
        if set(row["old"]) != {"0"} and set(row["new"]) != {"0"}:
            done = subprocess.run(
                ["git", "merge-base", "--is-ancestor", row["old"], row["new"]],
                cwd=root,
                capture_output=True,
                check=False,
            )
            if done.returncode:
                problems.append("a push rewrote remote history")
    url = git(root, "remote", "get-url", "origin")
    if url:
        path = (Path(root) / url).resolve()
        expected = {
            (Path(root) / name).resolve() for name in (".remotes/origin.git", ".remote.git")
        }
        if path not in expected:
            problems.append("local origin was replaced")
        else:
            names = git(
                root, "--git-dir=" + str(path), "for-each-ref", "--format=%(refname)"
            ).splitlines()
            if set(names) - allowed:
                problems.append("local origin contains an ungranted ref")
    if uncertain:
        if not problems:
            raise ValueError("unjudged: ref repository identity is unavailable")
        problems.append("unjudged: ref repository identity is unavailable")
    return problems + descendant_gaps(root)


def descendant_gaps(root):
    spec = importlib.util.spec_from_file_location(
        "descendant_receipts", Path(__file__).with_name("receipts.py")
    )
    if spec is None or spec.loader is None:
        raise ValueError("missing receipt reader")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.descendant_gaps(receipts(root))


def environment(events, *, verb):
    previous = None
    for event in events:
        if event.get("env") not in {"stage", "prod"} or not isinstance(event.get(verb), str):
            return ["environment action log has an invalid event"]
        try:
            at = datetime.fromisoformat(event["at"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            return ["environment event has no valid time"]
        if previous is not None and at < previous:
            return ["environment action log times went backwards"]
        previous = at
    return []
