#!/usr/bin/env python3
"""Run OutcomeBound's eval fixtures with an in-session Claude subagent as the model.

evals/run.py builds each fixture, hands the prompt to `codex exec`, and grades what is left.
This reuses its build and grading unchanged and replaces only the model call: `prepare` builds
the fixture for an arm and writes the prompt a subagent receives; the subagent works in the
fixture; `grade` turns the subagent's tool calls into a transcript in the form the graders
read, then runs the protected-input check and the fixture's post-checks exactly as run.py does.

Limits (each is reported with the results):
- Claude Code would load the fixture's AGENTS.md and skill listing itself; here the prompt tells
  the subagent to read AGENTS.md and lists the installed skills with their descriptions.
- The transcript is synthesized from the subagent's Bash tool calls; file reads and edits made
  with Read/Edit/Write tools are not commands and do not appear in it.
- The subagent has a shell, so it can reach any path. That the fixture's files outside the
  protected set stay untampered, and that it works only in its fixture, rest on the subagent's
  own behaviour. What grades the run is sealed, though: `prepare` records in the state the SHA-256
  of each file (a symlink, by its target) under `evals/` and `outcomebound_tools/`, except under
  `__pycache__`, and this checkout's HEAD and porcelain
  status, and `grade` refuses where any differs, so an edit of a grader, a post plan or the engine
  between the two is refused. The state's SHA-256 is the seal: `prepare` prints it, and with
  `--seal-out PATH` writes it to a path outside the state folder; it writes it nowhere inside that
  folder, where the subagent works. The person running the evals keeps the seal and passes it to
  `grade` as `--seal`.
- The transcript is the subagent's own session file. JSON fields keep a command's text or the answer
  from forging a command; the file's integrity rests on the subagent, which could append or delete
  an event. A Bash call with no result of its own in a later user event is refused, which stops
  only a call appended without a result; one appended with a result passes.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "evals"))
sys.path.insert(0, str(REPO))
run = importlib.import_module("run")

# Prepared fixtures and results stay outside the tree: `--state DIR` moves them.
STATE = Path(tempfile.gettempdir()) / "outcomebound-claude-arm"


def _skills(workdir: Path) -> list[tuple[str, str]]:
    found = []
    for root in run.SKILL_ROOTS:
        for skill in sorted((workdir / root).glob("*/SKILL.md")):
            text = skill.read_text(encoding="utf-8")
            match = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
            found.append((str(skill.relative_to(workdir)), match.group(1) if match else ""))
    return found


def _fingerprint() -> dict:
    """What grades a run, as it stands now: the SHA-256 of each file under `evals/` and
    `outcomebound_tools/`, and this checkout's HEAD and porcelain status."""

    import subprocess

    files = {}
    for top in ("evals", "outcomebound_tools"):
        for path in sorted((REPO / top).rglob("*")):
            if "__pycache__" in path.parts:
                continue
            name = path.relative_to(REPO).as_posix()
            if path.is_symlink():  # by its target, so a dangling or retargeted link shows
                files[name] = "symlink:" + os.readlink(path)
            elif path.is_file():
                files[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def git(*arguments: str) -> str:
        done = subprocess.run(
            ["git", "-C", str(REPO), *arguments], capture_output=True, text=True, timeout=60
        )
        return done.stdout if done.returncode == 0 else "unavailable"

    return {
        "files": files,
        "head": git("rev-parse", "HEAD").strip(),
        "status": git("status", "--porcelain"),
    }


def _refuse_changed_engine(sealed: dict) -> None:
    """SystemExit, naming what differs, where the graders or the engine are not as `prepare`
    sealed them."""

    now = _fingerprint()
    if not isinstance(sealed, dict) or sealed.get("files") is None:
        raise SystemExit("refused: the state records no fingerprint of the graders and engine")
    before = sealed["files"]
    changed = sorted(
        name
        for name in before.keys() | now["files"].keys()
        if before.get(name) != now["files"].get(name)
    )
    if changed:
        raise SystemExit(f"refused: changed since prepare: {', '.join(changed[:5])}")
    for name in ("head", "status"):
        if sealed.get(name) != now[name]:
            raise SystemExit(f"refused: the checkout's {name} changed since prepare")


def prepare(fixture: str, arm_name: str, seal_out: Path | None = None) -> None:
    import os
    import subprocess
    import tempfile

    arm = run.load_arm(arm_name, run.selected_fragments(fixture))
    fixture_dir = run.FIXTURES / fixture
    work = STATE / "work"
    work.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix=f"{fixture}-{arm_name}-", dir=work))
    run.install(workdir, arm.files)
    built = subprocess.run(
        ["bash", str(fixture_dir / "setup.sh"), str(workdir)],
        capture_output=True,
        text=True,
        env={**run.child_env(), **run.HERMETIC_GIT, "OB_EVAL_ARM": arm.name},
        timeout=run.SETUP_TIMEOUT,
    )
    if built.returncode != 0:
        raise SystemExit(f"setup failed: {built.stderr[-800:]}")
    unfit = run.as_installed(workdir, arm) or run.installed(workdir, arm.files)
    if unfit:
        raise SystemExit(unfit)
    protected = run.protected_snapshot(
        fixture_dir, workdir, tuple(arm.files), without_skills=arm.name == run.NONE
    )
    seed = run.seed_commit(workdir)
    prompt = run.build_prompt(arm.kernel, run.task_text(fixture, workdir))
    launcher = run.call_path(arm, None).split(os.pathsep)[0] if arm.launcher else None
    skills = _skills(workdir)
    lines = [
        f"You are working in the repository at {workdir}. Run every shell command from there:",
        f"begin each Bash command with `cd {workdir} && `.",
        "If the repository has an AGENTS.md, read it first: it holds this project's instructions,",
        "as your harness would load them.",
    ]
    if skills:
        lines.append("Project skills (read a skill's SKILL.md when its description fits the task):")
        lines += [f"- {path}: {description}" for path, description in skills]
    if launcher:
        lines.append(
            f"The `outcomebound` command is at {launcher}/outcomebound; prefix PATH with "
            f"`{launcher}` to run it."
        )
    lines.append("When you are done, end with your final message to the person who gave the task.")
    full = "\n".join(lines) + "\n\n" + prompt
    STATE.mkdir(parents=True, exist_ok=True)
    key = f"{fixture}--{arm_name}"
    (STATE / f"{key}.prompt.md").write_text(full, encoding="utf-8")
    state_file = STATE / f"{key}.json"
    state_file.write_text(
        json.dumps(
            {
                "fixture": fixture,
                "arm": arm_name,
                "workdir": str(workdir),
                "seed": seed,
                "protected": protected,
                "kernel_sha256": run.sha256_text(arm.kernel),
                "engine": _fingerprint(),
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    seal = hashlib.sha256(state_file.read_bytes()).hexdigest()
    if seal_out is not None:
        seal_out.write_text(seal + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "key": key,
                "workdir": str(workdir),
                "prompt": str(STATE / f"{key}.prompt.md"),
                "seal": seal,
            }
        )
    )


_CD = re.compile(r"^cd[ \t]+(?P<dir>\"[^\"]*\"|'[^']*'|\S+)[ \t]*&&[ \t]*")


def _without_cd(command: str, workdir: str) -> str:
    """The command without a leading `cd <dir> && ` where <dir> is the workdir, compared as the
    OS resolves it (symlinks, a trailing slash, `.` and `..`), not as a string."""

    found = _CD.match(command)
    if found:
        try:
            named = shlex.split(found.group("dir"))
            if len(named) == 1 and os.path.realpath(named[0]) == os.path.realpath(workdir):
                return command[found.end() :]
        except ValueError:
            pass
    return command


def _inside(path: Path, folder: Path) -> bool:
    """Whether `path` is `folder` or below it, as the OS resolves both: through symlinks and
    `..`, and by file identity where the file system folds case."""

    folder = folder.resolve()
    for candidate in (path.resolve(), *path.resolve().parents):
        if candidate == folder:
            return True
        try:
            if candidate.exists() and folder.exists() and os.path.samefile(candidate, folder):
                return True
        except OSError:
            pass
    return False


def _block(command: str, workdir: str, status: str = "unverified") -> list[str]:
    """One actual Bash call and matched result, kept separate from printed text."""

    return [_without_cd(command, workdir) if workdir else command, status, workdir]


def _events(subagent_jsonl: Path) -> list[dict]:
    """Read JSONL strictly; a damaged line cannot prove the absence of an attempt."""

    found = []
    for line in subagent_jsonl.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError("a session event is not an object")
        found.append(event)
    return found


def _start_tool(part: dict, workdir: str, blocks: list[list[str]], state: dict) -> None:
    name, key, args = part.get("name"), part.get("id"), part.get("input")
    if not isinstance(name, str) or not isinstance(args, dict):
        raise ValueError("malformed tool call")
    if not isinstance(key, str) or not key or key in state["seen"]:
        raise ValueError("missing or reused tool call id")
    state["seen"].add(key)
    index, command = None, ""
    if name == "Bash":
        value = args.get("command")
        if not isinstance(value, str):
            raise ValueError("Bash command is not a string")
        command = value
        index = len(blocks)
        active = {i for i, _ in state["pending"].values() if i is not None}
        if active:
            state["overlap"].update(active | {index})
        blocks.append(_block(command, workdir))
    state["pending"][key] = (index, command)


def _assistant_parts(parts: list, workdir: str, blocks: list[list[str]], state: dict) -> list[str]:
    texts = []
    for part in parts:
        if part["type"] == "tool_use":
            _start_tool(part, workdir, blocks, state)
            if part.get("name") == "SubagentHandback":
                text = part["input"].get("message", "")
                if not isinstance(text, str):
                    raise ValueError("handback is not text")
                texts.append(text)
        elif part["type"] == "text":
            if not isinstance(part.get("text"), str):
                raise ValueError("assistant text is not a string")
            texts.append(part["text"])
    return texts


def _result_parts(parts: list, blocks: list[list[str]], state: dict) -> None:
    for part in parts:
        if part["type"] != "tool_result":
            continue
        key = part.get("tool_use_id")
        if not isinstance(key, str) or key in state["results"] or key not in state["pending"]:
            raise ValueError("unmatched or repeated tool result")
        state["results"].add(key)
        index, command = state["pending"].pop(key)
        if index is None:
            continue
        error = part.get("is_error", False)
        status = "unverified"
        if error is True:
            status = "failed"
        elif (
            error is False
            and isinstance(part.get("content"), (str, list))
            and index not in state["overlap"]
        ):
            status = "succeeded"
        blocks[index] = _block(command, blocks[index][2], status)


def _message_parts(event: dict) -> tuple[str, list] | None:
    message = event.get("message")
    if message is None:
        return None
    if not isinstance(message, dict) or not isinstance(message.get("role"), str):
        raise ValueError("malformed session message")
    parts = message.get("content")
    if isinstance(parts, str):
        parts = [{"type": "text", "text": parts}]
    if not isinstance(parts, list) or not all(
        isinstance(part, dict) and isinstance(part.get("type"), str) for part in parts
    ):
        raise ValueError("malformed message parts")
    return message["role"], parts


def _transcript(subagent_jsonl: Path, workdir: str) -> tuple[str, str]:
    """Pair actual tool identities; incomplete or ambiguous command evidence is refused."""

    blocks: list[list[str]] = []
    answer = ""
    events = _events(subagent_jsonl)
    state: dict = {"pending": {}, "seen": set(), "results": set(), "overlap": set()}
    for event in events:
        message = _message_parts(event)
        if message is None:
            continue
        role, parts = message
        if role == "user":
            _result_parts(parts, blocks, state)
        elif role == "assistant":
            cwd = event.get("cwd", "")
            cwd = cwd if isinstance(cwd, str) and Path(cwd).is_absolute() else ""
            texts = _assistant_parts(parts, cwd, blocks, state)
            answer = "\n".join(texts) if texts else answer
    if not events:
        raise ValueError("no readable event")
    if state["pending"]:
        raise ValueError("a tool call has no result in the transcript")
    return json.dumps(
        {"format": "outcomebound-command-events-v1", "commands": blocks, "answer": answer}
    ), answer


REQUIRED = ("fixture", "arm", "workdir", "seed", "protected", "kernel_sha256", "engine")


def _load_state(key: str, seal: str) -> dict:
    """The sealed state of a prepared run; SystemExit, with nothing written, where it is
    missing, unreadable, incomplete or not the one `prepare` sealed."""

    path = STATE / f"{key}.json"
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise SystemExit(f"refused: state unreadable: {error}") from error
    if hashlib.sha256(raw).hexdigest() != seal.strip().lower():
        raise SystemExit("refused: the state does not match --seal")
    try:
        state = json.loads(raw)
    except ValueError as error:
        raise SystemExit(f"refused: state is not JSON: {error}") from error
    if not isinstance(state, dict) or any(name not in state for name in REQUIRED):
        raise SystemExit("refused: state is incomplete")
    if not isinstance(state["protected"], dict) or not Path(str(state["workdir"])).is_dir():
        raise SystemExit("refused: state names no readable fixture")
    return state


def grade(key: str, subagent_jsonl: str, seal: str) -> None:
    state = _load_state(key, seal)
    _refuse_changed_engine(state["engine"])
    workdir = Path(state["workdir"])
    try:
        transcript, answer = _transcript(Path(subagent_jsonl), str(workdir))
    except (OSError, ValueError) as error:
        raise SystemExit(f"refused: subagent transcript unreadable: {error}") from error
    intact, protected_report = run.check_protected(workdir, state["protected"])
    verdict, output = "FAIL", "VERDICT: FAIL\n"
    if intact:
        verdict, output, _logs = run.post_check(
            run.FIXTURES / state["fixture"], workdir, state["seed"], transcript, answer
        )
    claims = {claim: result for result, claim in run.CLAIM_LINE.findall(output)}
    record = {
        **state,
        "verdict": verdict,
        "claims": claims,
        "protected_intact": intact,
        "commands": len(json.loads(transcript)["commands"]),
    }
    (STATE / f"{key}.result.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    (STATE / f"{key}.report.txt").write_text(
        f"{protected_report}\n{output}\n--- answer ---\n{answer}\n", encoding="utf-8"
    )
    print(json.dumps({"key": key, "verdict": verdict, "claims": claims}))


def main(argv: list[str]) -> None:
    global STATE
    args = list(argv)
    if "--state" in args:
        at = args.index("--state")
        if at + 1 >= len(args):
            raise SystemExit("--state needs a directory")
        STATE = Path(args[at + 1]).resolve()
        del args[at : at + 2]
    seal = ""
    if "--seal" in args:
        at = args.index("--seal")
        if at + 1 >= len(args):
            raise SystemExit("--seal needs the value that prepare printed")
        seal = args[at + 1]
        del args[at : at + 2]
    seal_out = None
    if "--seal-out" in args:
        at = args.index("--seal-out")
        if at + 1 >= len(args):
            raise SystemExit("--seal-out needs a file path")
        seal_out = Path(args[at + 1]).resolve()
        del args[at : at + 2]
        if _inside(seal_out, STATE):
            raise SystemExit(
                "refused: --seal-out is inside the state folder, where the subagent works"
            )
    usage = (
        "usage: claude_arm.py [--state DIR] [--seal-out FILE] prepare FIXTURE ARM"
        " | [--state DIR] --seal SHA256 grade KEY SUBAGENT_JSONL"
    )
    if len(args) == 3 and args[0] == "prepare":
        prepare(args[1], args[2], seal_out)
    elif len(args) == 3 and args[0] == "grade" and seal:
        grade(args[1], args[2], seal)
    else:
        raise SystemExit(usage)


if __name__ == "__main__":
    main(sys.argv[1:])
