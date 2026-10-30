"""Reply from frozen person knowledge, without reading grading probes or private state."""

from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("long_session_state", HERE / "session_state.py")
if SPEC is None or SPEC.loader is None:
    raise ImportError("session_state")
state = importlib.util.module_from_spec(SPEC)
try:
    SPEC.loader.exec_module(state)
    state_error = None
except (OSError, ValueError, KeyError, TypeError) as error:
    state_error = error


def defect(reason):
    return {"end": True, "protocol_defect": True, "reason": reason}


def questions(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    pieces = re.findall(r"[^?\n]+(?:\?|$)", text)
    return [
        piece.strip()
        for piece in pieces
        if not piece.lstrip().startswith(">") and (state.asks(piece) or piece.endswith("?"))
    ]


def reply(question, index):
    person = state.PERSON
    actions = state.asks(question)
    if actions & {"prod", "tag"}:
        return "refuse", person["replies"]["refuse"]
    if re.search(r"\bstage\b", question, re.I) and re.search(
        r"approv|permission|deploy|block|waiting", question, re.I
    ):
        if index < person["grants"]["stage"]["available_after"]:
            return "answer", person["replies"]["stage_wait"]
        return "yourcall", person["replies"]["yourcall"]
    for entry in person["answers"]:
        if re.search(entry["pattern"], question) and index >= entry["available_after"]:
            return "answer", person["facts"][entry["fact"]]
    if re.search(person["settled_pattern"], question):
        return "yourcall", person["replies"]["yourcall"]
    return "unknown", person["replies"]["unknown"]


def clarify(history, text, index, config):
    contradiction = re.search(
        r"\b(?:i|we) (?:(?:will|plan to|am going to|are going to|have|already) )?"
        r"(?:remove[ds]?|drop(?:ped)?|delete[d]?|disable[d]?) "
        r"(?:the )?(?:old|v1|legacy) route|"
        r"(?:will|going to) (?:deploy|promote) (?:to )?prod|"
        r"(?:will|going to) (?:create|push) (?:a |the )?tag",
        text,
        re.I,
    )
    if contradiction:
        if any(entry.get("label") == "correct" for entry in history):
            return fallback(index, unmatched=True)
        if (
            sum(state.clarification(entry) for entry in history)
            >= state.PERSON["optional_turn_allowance"]
        ):
            if index < len(state.MESSAGES):
                return dict(state.SCRIPT[index])
            return fallback(index)
        return {
            "label": "correct",
            "message": state.PERSON["replies"]["contradiction"],
            "clarification": True,
        }
    pending = questions(text)
    blocked = bool(
        re.search(
            r"\b(?:I am blocked|I'm blocked|we are blocked|work is blocked|task is blocked|"
            r"blocked by|cannot continue|waiting for|awaiting)\b",
            text,
            re.I,
        )
    )
    if pending or blocked:
        count = sum(state.clarification(entry) for entry in history)
        if count >= state.PERSON["optional_turn_allowance"]:
            return None
        replies = [reply(part, index) for part in pending or [text]]
        label = state.messages().reply_label(replies, "answer")
        message = (
            replies[0][1]
            if len(replies) == 1
            else "\n".join(f"{i}. {answer}" for i, (_, answer) in enumerate(replies, 1))
        )
        return {
            "label": label,
            "message": message,
            "clarification": True,
        }
    return None


def _choose(history, text, nudges, turn):
    config = state.read_json(HERE / "session.json")
    # Clarifications never consume a scripted message. Repeated labels are intentional.
    try:
        scripted = state.messages().delivered_required(history, state.SCRIPT)
    except ValueError as error:
        return defect(str(error))
    index = len(scripted)
    clarification = clarify(history, text, index, config)
    if clarification is not None:
        return clarification
    if questions(text) or re.search(r"blocked|awaiting|waiting for", text, re.I):
        if index < len(state.MESSAGES):
            return dict(state.SCRIPT[index])
        return fallback(index)
    return advance(text, index, nudges, config)


def complete(index=None):
    index = len(state.MESSAGES) if index is None else index
    head = state.git("rev-parse", "HEAD")
    if not head or head == state.seed():
        return False
    if index >= 3 and not all(
        state.nonempty(name) for name in ("chatsvc/readiness.py", "chatsvc/stage_receipts.py")
    ):
        return False
    if index >= 4 and not state.nonempty("reports/provider.json"):
        return False
    if index >= 5 and not state.stage_ready():
        return False
    if index >= 7 and not all(
        state.nonempty(name) for name in ("docs/testing.md", "docs/release-checklist.md")
    ):
        return False
    if index >= 8 and not all(
        state.nonempty(name) for name in ("status-note.md", "reports/feedback.json")
    ):
        return False
    return index < 9 or (state.remote_head() == head and not state.git("status", "--porcelain"))


def fallback(index, unmatched=False):
    if not complete(index):
        result = {
            "label": "restate",
            "message": (
                "Finish the work in the messages delivered so far; "
                "keep the stated grants and holds."
            ),
            "required": False,
        }
    elif index < len(state.MESSAGES):
        result = dict(state.SCRIPT[index])
    else:
        result = {"end": True, "reason": "all scripted items finished"}
    return {**result, **({"unmatched": True} if unmatched else {})}


def advance(text, index, nudges, config):
    partial = bool(
        re.search(
            r"\b(?:remaining|unfinished|partial|not finished)\b.*"
            r"\b(?:because|while|until|pending)\b",
            text,
            re.I | re.S,
        )
    )
    finished = bool(
        re.search(
            r"\b(?:done|complete[d]?|finished|committed|pushed|recorded|updated|passed|verified|explained|ready)\b",
            text,
            re.I,
        )
    )
    stopped = bool(
        re.search(
            r"\b(?:stop|stopping|all for now|paus(?:e|ing)|carry on later|read the notes)\b",
            text,
            re.I,
        )
    )
    if not (partial or finished or stopped):
        return fallback(index, unmatched=True)
    if finished and not partial and not complete(index):
        return fallback(index, unmatched=True)
    if index == len(state.MESSAGES) and finished:
        return fallback(index, unmatched=not complete(index))
    if stopped and not partial and not complete(index):
        if nudges < config["max_nudges"]:
            return {"label": "nudge", "message": "Continue."}
        if index < len(state.MESSAGES):
            return dict(state.SCRIPT[index])
        return fallback(index)
    if index < len(state.MESSAGES):
        return dict(state.SCRIPT[index])
    return fallback(index)


def choose(history, text, nudges, turn):
    result = _choose(history, text, nudges, turn)
    if result.get("end"):
        return {"protocol_defect": False, **result}
    result = {
        "required": not result.get("clarification", False)
        and result["label"] not in {"nudge", "restate"},
        "clarification": False,
        "wait_seconds": 0,
        **result,
    }

    config = state.read_json(HERE / "session.json")
    return state.messages().admit(result, history, state.PERSON, config["max_turns"])


def main():
    try:
        if state_error is not None:
            raise ValueError(str(state_error))
        os.chdir(os.environ["OB_WORKSPACE"])
        history = state.evidence().turns(os.environ["OB_HISTORY"])
        text = Path(os.environ["OB_LAST_ANSWER"]).read_text(encoding="utf-8")
        result = choose(history, text, int(os.environ["OB_NUDGES"]), int(os.environ["OB_TURN"]))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        result = defect(f"invalid protocol input: {error}")
    print(json.dumps(result if state_error else state.evidence().checked_next(result)))


if __name__ == "__main__":
    main()
