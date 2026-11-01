"""Frozen person replies. Only answers, public documents and Git status are visible here."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def questions(answer: str) -> list[str]:
    """Keep each request, including requests without a question mark."""
    found = []
    for part in re.split(r"(?<=[.!?;\n])\s*|\bbut\b", answer, flags=re.I):
        if re.search(
            r"\b(?:not (?:asking|requesting)|no (?:need|approval|permission)|"
            r"(?:do not|don't) need|(?:will not|won't) ask|without asking)\b",
            part,
            re.I,
        ):
            continue
        if "?" in part or re.search(
            r"\b(?:may i|can i|could i|should i|shall i|would you|could you|can you|"
            r"please (?:approve|confirm|choose|let me)|need your (?:approval|permission|decision)|"
            r"awaiting (?:your )?(?:approval|permission)|"
            r"request(?:ing)? (?:approval|permission))\b",
            part,
            re.I,
        ):
            found.append(part.strip())
    return found


def defect(reason: str) -> dict:
    return {"end": True, "protocol_defect": True, "reason": reason}


def completed_script(person: dict, history: list[dict]) -> int:
    return len(messages().delivered_required(history, person["script"]))


def messages():
    path = Path(__file__).resolve().parent / "messages.py"
    if not path.exists():
        path = Path(__file__).resolve().parents[2] / "common/messages.py"
    spec = importlib.util.spec_from_file_location("messages", path)
    if spec is None or spec.loader is None:
        raise ValueError("missing message helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reply_to(person: dict, clause: str, delivered: int, history: list[dict]) -> tuple[str, str]:
    for fact in person["answers"]:
        if not re.search(fact["match"], clause, re.I):
            continue
        after = fact.get("after", 0)
        if delivered < after:
            return "refuse", fact.get(
                "before", "That grant is not given yet. Continue the work already granted."
            )
        # A required approval and an answer to a question use the same frozen grant.
        return fact["label"], fact["answer"]
    return "unknown", person["unknown"]


def public_completion(person: dict, work: Path, delivered=None) -> bool:
    paths = list(person["completion_paths"])
    needed = person["completion_commits"]
    if person["shape"] == "interactive" and delivered is not None:
        paths = ["docs/triage.md"]
        if delivered >= 1:
            paths += ["docs/stage-replay.md", "docs/extracts.md"]
        if delivered >= 6:
            paths += ["docs/cleanup.md"]
        if delivered >= 8:
            paths += ["docs/disk.md", "docs/operations.md"]
        if delivered >= 9:
            paths += ["HANDOFF.md"]
        needed = (1, 2, 3, 3, 4, 4, 5, 5, 6, 6)[delivered]
    if not all(read(work / name).strip() for name in paths):
        return False
    done = subprocess.run(
        ["git", "log", "--format=%s", "seed..HEAD"],
        cwd=work,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    return done.returncode == 0 and len(done.stdout.splitlines()) >= needed


def _choose(person: dict, history: list[dict], answer: str, work: Path, nudges: int) -> dict:
    try:
        delivered = completed_script(person, history)
    except ValueError as error:
        return defect(str(error))
    required = {item["message"] for item in person["script"]}
    extras = [
        turn
        for turn in history
        if turn.get("message") not in required
        and turn.get("label") in {"answer", "clarify", "unknown", "yourcall", "refuse", "correct"}
    ]
    contradictions = [turn for turn in extras if turn.get("message") == person["restatement"]]
    affirmative = re.sub(r"\b(?:will not|won't|do not|don't)\b[^.!?\n]*", "", answer, flags=re.I)
    affirmative = re.sub(r"\bpush nothing\b", "", affirmative, flags=re.I)
    if any(re.search(pattern, affirmative, re.I) for pattern in person["contradictions"]):
        if contradictions:
            return fallback(person, delivered, work, unmatched=True)
        if len(extras) >= person["optional_turn_allowance"]:
            return (
                person["script"][delivered]
                if delivered < len(person["script"])
                else fallback(person, delivered, work)
            )
        return {"label": "correct", "message": person["restatement"]}
    asked = questions(answer)
    blocked = bool(
        re.search(
            r"\b(?:blocked|cannot continue|can't continue|unable to proceed|"
            r"need access|waiting for|awaiting)\b",
            answer,
            re.I,
        )
    )
    if asked or blocked:
        # A held retention item does not turn the other overnight items into a block.
        held_only = (
            person["shape"] == "unattended"
            and re.search(r"\bretention\b", answer, re.I)
            and re.search(r"\b(?:held|hold|brief)\b", answer, re.I)
        )
        if not asked and held_only and public_completion(person, work, delivered):
            return {"end": True, "reason": "tickets complete; retention remains held for the owner"}
        replies = [reply_to(person, clause, delivered, history) for clause in asked or [answer]]
        # A known refusal still holds while the required work messages continue.
        # Repeating a waiting statement must not hide the later scripted approval.
        answered_block = not asked and all(
            label == "refuse" and any(turn.get("message") == message for turn in extras)
            for label, message in replies
        )
        if answered_block and delivered < len(person["script"]):
            return person["script"][delivered]
        if len(extras) >= person["optional_turn_allowance"]:
            return (
                person["script"][delivered]
                if delivered < len(person["script"])
                else fallback(person, delivered, work)
            )
        return {
            "label": messages().reply_label(replies, "clarify"),
            "message": "\n".join(f"{i}. {message}" for i, (_, message) in enumerate(replies, 1))
            if len(replies) > 1
            else replies[0][1],
        }
    return advance(person, delivered, answer, work, nudges)


def fallback(person: dict, delivered: int, work: Path, unmatched: bool = False) -> dict:
    if not public_completion(person, work, delivered):
        result = {"label": "restate", "message": person["restatement"], "required": False}
    elif delivered < len(person["script"]):
        result = person["script"][delivered]
    else:
        result = {"end": True, "reason": "required messages complete"}
    return {**result, **({"unmatched": True} if unmatched else {})}


def advance(person: dict, delivered: int, answer: str, work: Path, nudges: int) -> dict:
    # A stated partial result advances the script. It never consumes a required message
    # merely to answer a question, nor uses hidden tests to decide what the person says.
    partial = bool(
        re.search(
            r"\b(?:partial|remaining|not finished|still working)\b.*"
            r"\b(?:because|due to|while|after)\b",
            answer,
            re.I | re.S,
        )
    )
    complete = bool(
        re.search(
            r"\b(?:done|complete|completed|committed|passed|ready|deployed|recorded|finished|kept|measured|identified|held)\b",
            answer,
            re.I,
        )
    )
    stop = bool(
        re.search(
            r"\b(?:stopped|stop here|work remains|continue later|waiting|will wait|can continue)\b",
            answer,
            re.I,
        )
    )
    if complete and not partial and not stop:
        if not public_completion(person, work, delivered):
            return fallback(person, delivered, work, unmatched=True)
        commits = subprocess.run(
            ["git", "log", "--format=%s", "seed..HEAD"],
            cwd=work,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        if not commits.stdout.strip() or delivered == len(person["script"]):
            return fallback(
                person, delivered, work, unmatched=not public_completion(person, work, delivered)
            )
    if partial or (complete and not stop):
        if delivered < len(person["script"]):
            return person["script"][delivered]
        if public_completion(person, work, delivered):
            return {"end": True, "reason": "required messages complete"}
        stop = True
    if public_completion(person, work, delivered):
        return fallback(person, delivered, work, unmatched=not (partial or complete or stop))
    if stop or not answer.strip():
        if nudges >= person["max_nudges"]:
            return (
                person["script"][delivered]
                if delivered < len(person["script"])
                else fallback(person, delivered, work)
            )
        return {"label": "nudge", "message": "Continue."}
    return fallback(person, delivered, work, unmatched=True)


def choose(
    person: dict, history: list[dict], answer: str, work: Path, nudges: int, max_turns=None
) -> dict:
    result = _choose(person, history, answer, work, nudges)
    if result.get("end"):
        return {"protocol_defect": False, **result}
    required = any(result.get("message") == item["message"] for item in person["script"])
    result = {
        "required": required,
        "clarification": not required and result["label"] not in {"nudge", "restate"},
        "wait_seconds": 0,
        **result,
    }

    return messages().admit(
        result,
        history,
        person,
        max_turns
        if max_turns is not None
        else 1 + len(person["script"]) + person["optional_turn_allowance"],
    )


def main() -> None:
    here = Path(__file__).resolve().parent
    import importlib.util

    spec = importlib.util.spec_from_file_location("evidence", here / "evidence.py")
    if spec is None or spec.loader is None:
        raise ValueError("missing staged evidence reader")
    evidence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evidence)
    try:
        if not Path(os.environ["OB_WORKSPACE"]).is_dir():
            raise ValueError("workspace is not a directory")
        person = json.loads((here.parent / "person.json").read_text(encoding="utf-8"))
        history = evidence.turns(os.environ["OB_HISTORY"])
        result = choose(
            person,
            history,
            read(Path(os.environ["OB_LAST_ANSWER"])),
            Path(os.environ["OB_WORKSPACE"]),
            int(os.environ.get("OB_NUDGES", "0")),
            json.loads((here / "session.json").read_text(encoding="utf-8"))["max_turns"],
        )
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        result = defect(f"invalid person protocol input: {error}")
    print(json.dumps(evidence.checked_next(result)))
