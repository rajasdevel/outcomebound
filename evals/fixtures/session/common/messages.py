"""Required follow-ups and the shared optional-reply budget for frozen scripts."""

from __future__ import annotations

OPENERS = {"opener", "resume"}
OPTIONAL = {"nudge", "restate", "answer", "answers", "clarify", "yourcall", "unknown", "refuse"}


def delivered_required(history, script=None):
    rows = [
        row
        for row in history
        if row.get("required") is True
        and not row.get("clarification")
        and row.get("label") not in OPENERS | {"nudge", "restate"}
    ]
    if script is not None and [(row.get("label"), row.get("message")) for row in rows] != [
        (row["label"], row["message"]) for row in script[: len(rows)]
    ]:
        raise ValueError("history does not follow the frozen script")
    return rows


def admit(result, history, person, max_turns, *, split=False):
    """Reserve the required messages before spending one optional turn."""
    if result.get("end") or result.get("required"):
        return result
    delivered = len(delivered_required(history, person["script"]))
    optional = sum(row.get("label") not in OPENERS for row in history) - delivered
    pending = len(person["script"]) - delivered
    resume = int(split and not any(row.get("label") == "resume" for row in history))
    if optional < person["optional_turn_allowance"] and max_turns - len(history) - resume > pending:
        return result
    flag = {"unmatched": True} if result.get("unmatched") else {}
    if pending:
        return {**person["script"][delivered], **flag}
    return {
        "end": True,
        "reason": "optional reply allowance exhausted",
        "protocol_defect": False,
        **flag,
    }


def reply_label(replies, default):
    labels = {label for label, _message in replies}
    for label in ("yourcall", "held", "refuse"):
        if label in labels:
            return label
    return (
        next(iter(labels))
        if len(labels) == 1
        else default
        if labels & {"answer", "answers", "clarify"}
        else "unknown"
    )
