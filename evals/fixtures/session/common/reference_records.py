"""Protocol v1 writers for model-free reference sessions and their controls."""

from __future__ import annotations

import importlib
import json
import runpy
import sys
from datetime import datetime, timezone
from pathlib import Path

MESSAGES = runpy.run_path(str(Path(__file__).with_name("messages.py")))


def command(text, status, cwd, *, child=False):
    code = (
        0
        if status == "succeeded"
        else int(status.split()[-1])
        if status.startswith("exited ")
        else None
    )
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    shell = importlib.import_module("evals.session_shell")
    parts = shell.__dict__["command_segments"](
        text, Path(cwd), "ok" if code == 0 else "failed" if code is not None else "unknown"
    )
    return {
        "kind": "command",
        "session_id": "child" if child else "reference",
        "child": child,
        "parent_session_id": "reference" if child else None,
        "command": text,
        "segments": parts,
        "cwd": str(cwd),
        "exit_code": code,
        "status": "ok" if code == 0 else "failed" if code is not None else "unknown",
        "argv": parts[0]["argv"] if len(parts) == 1 else None,
        "started_at": None,
    }


def turn(label, message, answer, commands=(), *, number=1, output=Path("."), **metadata):
    path = output / f"answer-{number}.md"
    path.write_text(answer, encoding="utf-8")
    return {
        "turn": number,
        "label": label,
        "message": message,
        "required": label not in MESSAGES["OPTIONAL"],
        "clarification": False,
        "wait_seconds": 0,
        "answer_path": str(path.resolve()),
        "answer": answer,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "session_id": "reference",
        "calls": 0,
        "actions": [command(*row) for row in commands],
        **metadata,
    }


def save(output, turns):
    output.mkdir(parents=True, exist_ok=True)
    checker = Path(__file__).with_name("session_protocol.py")
    if not checker.is_file():
        checker = Path(__file__).resolve().parents[3] / "session_protocol.py"
    protocol = runpy.run_path(str(checker))
    protocol["turns"]({"version": 1, "turns": turns})
    (output / "turns.json").write_text(
        json.dumps({"version": 1, "turns": turns}, indent=2) + "\n", encoding="utf-8"
    )
    actions = [
        {**action, "turn": number}
        for number, row in enumerate(turns, 1)
        for action in row["actions"]
    ]
    protocol["actions"]({"version": 1, "actions": actions})
    (output / "actions.json").write_text(
        json.dumps({"version": 1, "actions": actions}, indent=2) + "\n", encoding="utf-8"
    )
    (output / "answer.md").write_text(turns[-1]["answer"] if turns else "", encoding="utf-8")


def brief(reference, output):
    reference, output = Path(reference), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = [
        (line, "succeeded", str(Path.cwd()))
        for line in (reference / "commands.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    answer = (reference / "answer.md").read_text(encoding="utf-8")
    save(
        output,
        [
            turn(
                "opener",
                (reference.parent.parent / "prompt.md").read_text(encoding="utf-8"),
                answer,
                rows,
                output=output,
            )
        ],
    )


if __name__ == "__main__":
    import sys

    brief(*sys.argv[1:])
