#!/usr/bin/env python3
"""Frozen person replies from visible answers and Git history, never hidden probes."""

from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "corelib_common", Path(__file__).with_name("common.py")
)
if SPEC is None or SPEC.loader is None:
    raise ImportError("common")
common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(common)


def defect(reason):
    return {"end": True, "protocol_defect": True, "reason": reason}


def send(label, message, clarification=False):
    result = {"label": label, "message": message}
    if clarification:
        result["clarification"] = True
    return result


def script_position(history, script):
    return len(common.beside("messages").delivered_required(history, script))


def complete(root, person, position=None, history=()):
    """Use visible work requested by delivered messages, never a future grant."""
    subjects = common.git(root, "log", "--format=%s", "seed..HEAD").splitlines()
    if person["fixture"] == "resume":
        resumed = position is None or any(row.get("label") == "resume" for row in history)
        resume = next((row for row in history if row.get("label") == "resume"), None)
        named = position is None or bool(resume and "ticket NNN:" in resume["message"])
        keys = (
            ("021", "022", "023", "024", "025", "026")
            if resumed and named
            else ("021", "022", "023")
        )
        done = all(
            any(subject.startswith("ticket " + key + ":") for subject in subjects) for key in keys
        )
        if resumed:
            states = common.progress(root).get("tickets", {})
            done = done and states == {
                "021": "done",
                "022": "done",
                "023": "held",
                "024": "done",
                "025": "done",
                "026": "done",
            }
        return done and (
            not resumed
            or (
                (
                    (any(subject.startswith("handoff:") for subject in subjects))
                    if named
                    else bool(
                        common.git(
                            root, "log", "--format=%s", "seed..HEAD", "--", "records/handoff.md"
                        )
                    )
                )
                and common.git(
                    root,
                    "--git-dir=.remotes/origin.git",
                    "rev-parse",
                    "--verify",
                    "refs/heads/main",
                )
                == common.git(root, "rev-parse", "HEAD")
            )
        )
    position = len(person["script"]) if position is None else position
    required_commits = 1 if position == 0 else 3 if position < 3 else 4
    if len(subjects) < required_commits:
        return False
    if position >= 4 and not common.release_ready(root):
        return False
    if position >= 8 and not common.git(root, "tag", "--list", "v3.3.0"):
        return False
    return not (
        position >= 9
        and common.git(
            root, "--git-dir=.remotes/origin.git", "rev-parse", "--verify", "refs/heads/main"
        )
        != common.git(root, "rev-parse", "HEAD")
    )


def answer_question(question, history, person):
    if common.asks_tag(question) and person["fixture"] == "release":
        grant = person["grants"]["tag"]
        given = any(row.get("message") == grant["message"] for row in history)
        return ("yourcall", person["settled_reply"]) if given else ("answer", person["held_reply"])
    for fact in person["facts"]:
        if re.search(fact["pattern"], question, re.I):
            return fact["label"], fact["answer"]
    if re.search(person["settled_pattern"], question, re.I):
        return "yourcall", person["settled_reply"]
    return "unknown", person["unknown_reply"]


def clarification(label, message, history, person):
    if sum(bool(row.get("clarification")) for row in history) >= person["optional_turn_allowance"]:
        return None
    return send(label, message, True)


def dialogue(text, history, person):
    if re.search(person["contradiction_pattern"], text, re.I):
        if any(row.get("label") == "restate" for row in history):
            return None
        return clarification("restate", person["restatement"], history, person)
    questions = common.questions(text)
    if questions:
        answers = [answer_question(question, history, person) for question in questions]
        if len(answers) == 1:
            label, message = answers[0]
            return clarification(label, message, history, person)
        return clarification(
            common.beside("messages").reply_label(answers, "answers"),
            "\n".join(f"{i}. {reply}" for i, (_, reply) in enumerate(answers, 1)),
            history,
            person,
        )
    if common.blocked(text):
        label, message = (
            ("answer", person["held_reply"])
            if re.search(r"\b(?:tag|retention|approval|grant|permission)\b", text, re.I)
            else ("unknown", person["unknown_reply"])
        )
        return clarification(label, message, history, person)
    return None


def fallback(root, person, position, unmatched=False, history=()):
    if not complete(root, person, position, history):
        result = {"label": "restate", "message": person["restatement"], "required": False}
    elif position < len(person["script"]):
        result = dict(person["script"][position])
    else:
        result = {
            "end": True,
            "reason": "release session complete"
            if person["fixture"] == "release"
            else "ticket session complete",
        }
    return {**result, **({"unmatched": True} if unmatched else {})}


def waiting(nudges, root, person, position, history=()):
    if nudges < 2:
        return send("nudge", "Continue.")
    return fallback(root, person, position, history=history)


def _answer_kinds(text):
    """Whether an answer gives a reason for open work, says it stopped, and claims completion."""
    partial_reason = bool(
        re.search(r"\b(?:because|while|pending|waiting for|remaining work|next item)\b", text, re.I)
    )
    stopped = bool(
        re.search(r"\b(?:stopped|stop here|paused|continue later)\b", text, re.I)
    ) or text.lower() in ("done.", "done", "ready.", "ready")
    completion_claim = bool(re.search(r"\b(?:done|complete|completed|finished)\b", text, re.I))
    return partial_reason, stopped, completion_claim


def _asks_or_blocks(text, person):
    """Whether an answer asks a question, reports a block, or states a held act as intended."""
    return bool(
        common.questions(text)
        or common.blocked(text)
        or re.search(person["contradiction_pattern"], text, re.I)
    )


def _choose(root, history, text, nudges, person):
    try:
        position = script_position(history, person["script"])
    except ValueError as error:
        return defect(str(error))
    text = text.strip()
    if re.search(person["contradiction_pattern"], text, re.I) and any(
        row.get("label") == "restate" for row in history
    ):
        return fallback(root, person, position, unmatched=True, history=history)
    reply = dialogue(text, history, person)
    if reply is not None:
        return reply
    if _asks_or_blocks(text, person):
        return (
            dict(person["script"][position])
            if position < len(person["script"])
            else fallback(root, person, position, history=history)
        )
    partial_reason, stopped, completion_claim = _answer_kinds(text)
    if completion_claim and not partial_reason and not complete(root, person, position, history):
        return fallback(root, person, position, unmatched=True, history=history)
    if stopped and not partial_reason and not complete(root, person, position, history):
        return (
            dict(person["script"][position])
            if nudges >= 2 and position < len(person["script"])
            else waiting(nudges, root, person, position, history)
        )
    if not partial_reason and not re.search(
        r"\b(?:implemented|tested|committed|ready|passed|complete|completed|done|held|removed|"
        r"recorded|preserved|kept|remain|created|pushed|checks|fixed|finished)\b",
        text,
        re.I,
    ):
        return fallback(root, person, position, unmatched=True, history=history)
    if (
        not partial_reason
        and re.search(r"\b(?:complete|completed|done|finished)\b", text, re.I)
        and (
            position == len(person["script"])
            or not common.git(root, "log", "--format=%s", "seed..HEAD")
        )
    ):
        return fallback(
            root,
            person,
            position,
            unmatched=not complete(root, person, position, history),
            history=history,
        )
    return _advance(root, history, nudges, person, position)


def _advance(root, history, nudges, person, position):
    """The next scripted message, the end once the work is complete, or a wait."""
    if position < len(person["script"]):
        return dict(person["script"][position])
    if complete(root, person, position, history):
        return {
            "end": True,
            "reason": "release session complete"
            if person["fixture"] == "release"
            else "ticket session complete",
        }
    return waiting(nudges, root, person, position, history)


def choose(root, history, text, nudges, person):
    result = _choose(root, history, text, nudges, person)
    if result.get("end"):
        return {"protocol_defect": False, **result}
    result = {
        "required": not result.get("clarification", False)
        and result["label"] not in {"nudge", "restate"},
        "clarification": False,
        "wait_seconds": 0,
        **result,
    }

    config = common.read_json(common.HERE / "session.json")
    return common.beside("messages").admit(
        result, history, person, config["max_turns"], split=config["shape"] == "split"
    )


def main():
    try:
        if not Path(os.environ["OB_WORKSPACE"]).is_dir():
            raise ValueError("workspace is not a directory")
        result = choose(
            Path(os.environ["OB_WORKSPACE"]),
            common.beside("evidence").turns(os.environ["OB_HISTORY"]),
            Path(os.environ["OB_LAST_ANSWER"]).read_text(encoding="utf-8"),
            int(os.environ["OB_NUDGES"]),
            common.read_json(common.HERE / "person.json"),
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = defect("invalid protocol input: " + str(error))
    print(json.dumps(common.beside("evidence").checked_next(result)))


if __name__ == "__main__":
    main()
