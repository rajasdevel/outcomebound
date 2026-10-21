"""What the ops fixtures' checks share: the seed, the answer, the runner's watch log, scratch copies
of the workspace, and the run's timeline of commands and file edits, read from the harness's own
records and never from printed text.

Each fixture's check script loads this file from beside itself (the grading stage, outside the
workspace) with `transcript_commands.py`. The seed is the commit OUTCOMEBOUND_SEED_SHA names,
else the `seed` tag; the answer is the file OUTCOMEBOUND_EVAL_ANSWER names; the transcript the
file OUTCOMEBOUND_EVAL_TRANSCRIPT names; the watch log the file OB_EVAL_WATCH_LOG names.

The timeline is the transcript's command records in order, with the edits of an apply-patch
tool placed among them where the transcript keeps the CLI's own events (a Codex run). A harness
whose file-edit tool leaves no event (Claude Code's Edit and Write) shows only the edits its
commands made, so "before the first edit" there reads the edits that are visible: each check
that relies on it says so.

Standard library only, like the rest of `evals/`.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
WATCH_ENV = "OB_EVAL_WATCH_LOG"
NOT_RECORDED = "not recorded"
# Never part of what a run is asked for: the working folder the runner makes, bytecode and the
# action log the stand-ins write.
COPY_SKIPS = (".git", ".agents", "__pycache__", ".actions")


def beside(name: str):
    """A module copied beside this file, loaded by path."""

    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    if spec is None or spec.loader is None:
        raise SystemExit(f"no {name}.py beside this file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


transcript_commands = beside("transcript_commands")


# --- the workspace, Git, the answer -------------------------------------------------------------


def git(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *arguments], capture_output=True, text=True, timeout=60, encoding="utf-8"
    )


def seed() -> str:
    found = os.environ.get("OUTCOMEBOUND_SEED_SHA", "")
    return found or git("rev-parse", "--verify", "refs/tags/seed^{commit}").stdout.strip()


def seed_blob(path: str) -> bytes | None:
    done = subprocess.run(
        ["git", "show", f"{seed()}:{path}"], capture_output=True, timeout=60, check=False
    )
    return done.stdout if done.returncode == 0 else None


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def answer() -> str | None:
    """The run's final answer, or None where none was supplied."""

    try:
        return Path(os.environ.get("OUTCOMEBOUND_EVAL_ANSWER", "")).read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return None


def workspace() -> Path:
    return Path.cwd().resolve()


def unchanged(paths: list[str]) -> list[str]:
    """Each of `paths` that differs from the seed, or is missing."""

    problems = []
    for path in paths:
        before = seed_blob(path)
        now = Path(path)
        if before is None:
            problems.append(f"{path} is not in the seed")
        elif not now.is_file():
            problems.append(f"{path} was removed")
        elif now.read_bytes() != before:
            problems.append(f"{path} was changed")
    return problems


def changed_paths(allowed: tuple[str, ...] = (".agents/",)) -> list[str]:
    """Paths the run added, changed or removed against the seed, in the tree or in a commit,
    less those under `allowed`; ignored files are not counted."""

    names = set(git("diff", "--name-only", seed(), "--").stdout.split())
    status = git("status", "--porcelain", "--untracked-files=all").stdout
    names |= {line[3:].strip().strip('"') for line in status.splitlines() if len(line) > 3}
    return sorted(name for name in names if name and not name.startswith(allowed))


def watched_changes(paths: list[str]) -> list[str]:
    """Each change of one of `paths` that the runner's watch log saw during the call, against
    the seed's bytes: a write later restored is still a change. Where no watch log was recorded
    the result says so, as one problem: a claim that needs the record fails without it."""

    name = os.environ.get(WATCH_ENV, "")
    if not name:
        return [f"the watch log was {NOT_RECORDED} ({WATCH_ENV} is not set)"]
    try:
        lines = Path(name).read_text(encoding="utf-8").splitlines()
    except OSError:
        return [f"the watch log was {NOT_RECORDED} ({name} cannot be read)"]
    seeded = {path: seed_blob(path) for path in paths}
    problems = []
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            return [f"the watch log is not JSON lines: {line[:80]}"]
        path = entry.get("path") if isinstance(entry, dict) else None
        if path not in seeded:
            continue
        before = seeded[path]
        if before is None or entry.get("sha256") != sha256(before):
            problems.append(f"{path} changed during the run, at {entry.get('t')} s")
    return problems


@contextlib.contextmanager
def scratch(restore: tuple[str, ...] = ()) -> Iterator[Path]:
    """A copy of the workspace's files, outside it, with each of `restore` put back as the seed
    holds it; removed when the block ends. Behaviour is graded here, never in the workspace."""

    folder = Path(tempfile.mkdtemp(prefix="ops-grade-"))
    try:
        copy = folder / "work"
        shutil.copytree(workspace(), copy, ignore=shutil.ignore_patterns(*COPY_SKIPS))
        for path in restore:
            blob = seed_blob(path)
            if blob is not None:
                (copy / path).parent.mkdir(parents=True, exist_ok=True)
                (copy / path).write_bytes(blob)
        yield copy
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def clean_env() -> dict[str, str]:
    """The checks' environment for a child: no Python or shipyard override from the caller."""

    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PYTHON", "SHIPYARD_"))
    }


def run_python(code: str, cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess:
    """`code` run in isolation with `cwd` as the folder it imports from."""

    prelude = f"import sys\nsys.path.insert(0, {str(cwd)!r})\n"
    return subprocess.run(
        [sys.executable, "-I", "-B", "-c", prelude + code],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        env=clean_env(),
    )


# --- the timeline of commands and edits ---------------------------------------------------------


class Step(NamedTuple):
    """One simple command of a recorded command, or one file edit of an edit tool.

    `kind` is `run` or `edit`. For a run: `argv` from the program on, `text` the whole recorded
    command, `status` its recorded status, `cwd` the folder the step ran in (after any `cd`
    before it in the same command). For an edit: `paths`, workspace-relative where inside it."""

    kind: str
    argv: tuple[str, ...] = ()
    text: str = ""
    status: str = ""
    cwd: str = ""
    paths: tuple[str, ...] = ()
    record: int = -1


FAILED = re.compile(r"exited -?[1-9]\d*|failed")
UNKNOWN_WRITE = "*"  # a step that writes files this reader cannot name
_PYTHON = re.compile(r"^python3?(\.\d+)?$")
_WRITERS = {"tee", "touch", "truncate", "rm", "ln", "dd"}
_TARGET_LAST = {"cp", "mv", "install"}
_GIT_WRITES = {"apply", "am", "merge", "cherry-pick", "revert", "pull", "rebase"}
_PY_WRITE = re.compile(
    r"write_text\(|write_bytes\(|\.write\(|shutil\.(?:copy|move)|os\.replace|\.rename\("
    r"|open\([^)]*['\"][wa]b?\+?['\"]"
)


def relative(word: str, cwd: str) -> str:
    """`word` as a path relative to the workspace, or as it is (absolute) where it lies outside."""

    base = Path(cwd) if cwd else workspace()
    path = Path(os.path.expanduser(word))
    full = Path(os.path.realpath(path if path.is_absolute() else base / path))
    try:
        return full.relative_to(Path(os.path.realpath(workspace()))).as_posix()
    except ValueError:
        return full.as_posix()


def _edit_positions(document: dict) -> list[tuple[int, tuple[str, ...]]]:
    """(how many commands had started, paths) for each completed apply-patch edit the CLI's
    own events record."""

    found = []
    started = 0
    for event in document.get("events") or []:
        item = event.get("item") if isinstance(event, dict) else None
        if not isinstance(item, dict):
            continue
        if event.get("type") == "item.started" and item.get("type") == "command_execution":
            started += 1
        elif (
            event.get("type") == "item.completed"
            and item.get("type") == "file_change"
            and item.get("status") != "failed"
        ):
            paths = tuple(
                str(change.get("path", ""))
                for change in item.get("changes", [])
                if isinstance(change, dict)
            )
            found.append((started, paths))
    return found


def timeline(transcript: str | None = None) -> list[Step] | None:
    """The run's steps in order, or None where the transcript is not the runner's structured
    record (an unknown form proves nothing, either way)."""

    if transcript is None:
        try:
            transcript = Path(os.environ.get("OUTCOMEBOUND_EVAL_TRANSCRIPT", "")).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            return None
    records = transcript_commands.execution_records(transcript)
    if records is None:
        return None
    try:
        document = json.loads(transcript.split(transcript_commands.POST_CHECKS, 1)[0])
    except ValueError:
        document = {}
    edits = _edit_positions(document if isinstance(document, dict) else {})
    steps: list[Step] = []
    for index, (command, status, directory) in enumerate(records):
        steps += [
            Step("edit", paths=tuple(relative(p, "") for p in paths if p))
            for started, paths in edits
            if started == index
        ]
        cwd = directory or str(workspace())
        for words in transcript_commands._simple_commands(command):
            argv = tuple(transcript_commands._program(list(words)))
            if argv and argv[0] == "cd":
                target = argv[1] if len(argv) > 1 else os.path.expanduser("~")
                cwd = os.path.realpath(target if os.path.isabs(target) else Path(cwd) / target)
                continue
            steps.append(Step("run", argv, command, status, cwd, record=index))
    steps += [
        Step("edit", paths=tuple(relative(p, "") for p in paths if p))
        for started, paths in edits
        if started >= len(records)
    ]
    return steps


def written(step: Step) -> tuple[str, ...]:
    """The workspace-relative paths a step writes, as far as its words show; `UNKNOWN_WRITE`
    where it writes files it does not name (a patch, `git apply`)."""

    if step.kind == "edit":
        return step.paths
    if not step.argv:
        return ()
    targets = _redirected(step.argv) + _program_targets(step)
    if UNKNOWN_WRITE in targets:
        return (UNKNOWN_WRITE,)
    return tuple(relative(target, step.cwd) for target in targets if target)


def _redirected(argv: tuple[str, ...]) -> list[str]:
    """The files a step's output redirections write."""

    targets = []
    for position, word in enumerate(argv):
        if word in (">", ">>", ">|") and position + 1 < len(argv):
            targets.append(argv[position + 1])
        elif word.startswith(">") and word.lstrip(">|"):
            targets.append(word.lstrip(">|"))
    return targets


def _in_place(name: str, argv: tuple[str, ...]) -> bool:
    if name in ("sed", "gsed"):
        return any(word.startswith("-i") or word == "--in-place" for word in argv)
    return name == "perl" and any(re.match(r"^-\w*i", word) for word in argv)


def _program_targets(step: Step) -> list[str]:
    """The files the step's program writes, by what the program is."""

    argv = step.argv
    name = Path(argv[0]).name
    plain = [word for word in argv[1:] if not word.startswith(("-", ">"))]
    if _in_place(name, argv) or name in _WRITERS:
        return plain
    if name in _TARGET_LAST:
        return plain[-1:] if len(plain) >= 2 else []
    if name == "patch":
        return [UNKNOWN_WRITE]
    if name == "git":
        sub = next((word for word in argv[1:] if not word.startswith("-")), "")
        if sub in _GIT_WRITES or (sub == "stash" and {"pop", "apply"} & set(argv)):
            return [UNKNOWN_WRITE]
        if sub in ("checkout", "restore") and "--" in argv:
            return list(argv[argv.index("--") + 1 :])
        return []
    if (_PYTHON.match(name) or name in ("sh", "bash", "zsh")) and _PY_WRITE.search(step.text):
        # A script that writes: each path the whole command names is taken as written.
        return re.findall(r"[\w./-]+\.\w+|Makefile", step.text)
    return []


def writes_under(step: Step, prefixes: tuple[str, ...]) -> bool:
    """Whether the step writes a path that starts with one of `prefixes`, or files unnamed."""

    return any(
        path == UNKNOWN_WRITE or path.startswith(prefixes) or path in prefixes
        for path in written(step)
    )


def failed(status: str) -> bool:
    return bool(FAILED.fullmatch(status))
