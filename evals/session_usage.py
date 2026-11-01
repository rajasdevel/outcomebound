"""Per-call native accounting and run-owned session discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.claude_stream import StreamMeter
from evals.codex_events import COST_KEYS


class CallUsage:
    """A session and its native call positions, independent of retained file snapshots."""

    def __init__(self, harness: str) -> None:
        self.harness = harness
        self.calls: dict[tuple[str, str], dict[str, int]] = {}
        self.cumulative: dict[str, dict[str, int]] = {}

    def add(self, records: list[dict[str, Any]], fallback: str = "") -> None:
        session = fallback
        for position, row in enumerate(records):
            payload = row.get("payload") or {}
            if row.get("type") == "session_meta":
                session = payload.get("id") or session
            if self.harness == "claude-code":
                self._claude(row, fallback or session)
                continue
            if row.get("type") != "event_msg" or payload.get("type") != "token_count":
                continue
            info = payload.get("info")
            if not isinstance(info, dict):
                continue
            last = info.get("last_token_usage")
            if not isinstance(last, dict) or any(type(last.get(k)) is not int for k in COST_KEYS):
                raise ValueError("a native call has no last_token_usage")
            total = info.get("total_token_usage")
            # Repeated usage notifications keep the same native cursor. The cursor identifies
            # the call only: its spend always comes from last_token_usage.
            cursor = (
                json.dumps(total, sort_keys=True) if total else str(row.get("timestamp", position))
            )
            key = (session, cursor)
            counts = {k: last[k] for k in COST_KEYS}
            if key in self.calls and self.calls[key] != counts:
                raise ValueError("conflicting usage at one native call position")
            self.calls[key] = counts
            if isinstance(total, dict) and all(type(total.get(k)) is int for k in COST_KEYS):
                self.cumulative[session] = {k: total[k] for k in COST_KEYS}

    def _claude(self, row: dict[str, Any], session: str) -> None:
        message = row.get("message") if row.get("type") == "assistant" else None
        if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
            return
        meter = StreamMeter()
        meter.add(row)
        if not meter.messages:
            raise ValueError("an assistant usage has no call id or input counts")
        counts = {**meter.totals(), "reasoning_output_tokens": 0}
        key = (session or row.get("sessionId", ""), message["id"])
        old = self.calls.get(key, {})
        self.calls[key] = {k: max(v, old.get(k, 0)) for k, v in counts.items()}

    def total(self) -> dict[str, Any]:
        keys = (
            (*COST_KEYS, "cache_creation_input_tokens")
            if self.harness == "claude-code"
            else COST_KEYS
        )
        return {
            **{k: sum(c.get(k, 0) for c in self.calls.values()) for k in keys},
            "source": "native",
            **({"reasoning_in_output": True} if self.harness == "claude-code" else {}),
        }

    def reconciliation(self) -> list[dict[str, Any]]:
        result = []
        for session, total in self.cumulative.items():
            actual = {
                k: sum(c.get(k, 0) for (s, _), c in self.calls.items() if s == session)
                for k in COST_KEYS
            }
            if actual != total:
                result.append({"session": session, "per_call": actual, "cumulative": total})
        return result


def codex_children(sessions: Path, parents: set[str]) -> list[tuple[Path, str, str]]:
    """Follow session_meta parent links, never cwd or a filename shared with another run."""
    candidates = []
    for path in sessions.rglob("*.jsonl"):
        if path.is_symlink():
            continue
        try:
            with path.open(encoding="utf-8") as handle:
                row = json.loads(handle.readline())
        except (OSError, ValueError):
            continue
        payload = row.get("payload", {})
        source = payload.get("source")
        subagent = source.get("subagent", {}) if isinstance(source, dict) else {}
        spawned = subagent.get("thread_spawn", {}) if isinstance(subagent, dict) else {}
        parent = payload.get("parent_thread_id") or spawned.get("parent_thread_id")
        if row.get("type") == "session_meta" and parent and payload.get("id"):
            candidates.append((path, payload["id"], parent))
    owned = set(parents)
    while more := {key for _, key, parent in candidates if parent in owned} - owned:
        owned |= more
    return [
        (path, key, parent)
        for path, key, parent in candidates
        if parent in owned and key not in parents
    ]
