"""Execution-aware shell commands shared by the session and brief graders."""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple, TypedDict


class Segment(NamedTuple):
    argv: tuple[str, ...] | None
    cwd: str
    status: str = "unknown"
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    runs: tuple[tuple[str, ...], ...] | None = ()
    command: str = ""


class GitOp(TypedDict):
    op: str
    repository: str
    remote: str | None
    refs: list[str]
    options: list[str]


def _options(argv, valued):
    while argv and (argv[0].startswith("-") or "=" in argv[0]):
        flag = argv.pop(0)
        if flag in valued and argv:
            argv.pop(0)
    return argv


def _program(words):
    argv = list(words)
    while argv:
        if re.match(r"[A-Za-z_][A-Za-z_0-9]*=", argv[0]):
            argv.pop(0)
            continue
        name = Path(argv[0]).name
        if name == "env":
            argv = _options(argv[1:], {"-u", "--unset", "-C", "--chdir"})
        elif name == "sudo":
            argv = _options(argv[1:], {"-u", "-g", "--user", "--group"})
        elif name == "uv" and "run" in argv:
            argv = _options(
                argv[argv.index("run") + 1 :],
                {"--with", "--with-requirements", "--python", "--project"},
            )
        elif name in {"time", "command", "exec", "nice"}:
            # A command lookup names no child invocation.
            if name == "command" and set(argv[1:]) & {"-v", "-V"}:
                return ()
            argv = _options(
                argv[1:],
                {"-a"}
                if name == "exec"
                else {"-n", "--adjustment"}
                if name == "nice"
                else {"-f", "--format", "-o", "--output"}
                if name == "time"
                else set(),
            )
        else:
            break
    return tuple(argv)


def segments(action) -> list[Segment]:
    """Read the driver's shell records. Missing records supply no execution evidence."""
    if action.get("kind") != "command":
        return []
    rows = action.get("segments")
    if rows is None:
        return [Segment(None, action["cwd"], runs=None, command=action["command"])]
    return [
        Segment(
            tuple(row["argv"]) if row["argv"] is not None else None,
            row["cwd"],
            row["status"],
            tuple(row["reads"]),
            tuple(row["writes"]),
            tuple(tuple(argv) for argv in row["runs"]) if row["runs"] is not None else None,
            action["command"],
        )
        for row in rows
    ]


def processes(part):
    """Include literal child processes that a script starts, without parsing its source."""
    children = [
        part._replace(argv=argv, reads=(), writes=(), runs=())
        for argv in (part.runs or ())
        if argv != part.argv
    ]
    return [part, *children]


def unresolved(part):
    return part.runs is None or (part.argv is None and part.runs != ())


def unjudged(part, reason):
    raise ValueError("unjudged: " + reason + "; command: " + part.command)


def settled(parts):
    for part in parts:
        if unresolved(part):
            unjudged(part, "process effects cannot be resolved")


def program(segment: Segment) -> tuple[str, ...]:
    """Resolve launchers and Python modules/scripts, preserving their arguments."""
    argv = _program(segment.argv or ())
    if not argv:
        return ()
    if Path(argv[0]).name.startswith(("python", "pypy")):
        for index, arg in enumerate(argv[1:], 1):
            if arg == "-m" and index + 1 < len(argv):
                return argv[index + 1 :]
            if arg == "-c":
                return argv
            if not arg.startswith("-"):
                return argv[index:]
    return argv


def executes(segment: Segment) -> str:
    argv = program(segment)
    return Path(argv[0]).name if argv else ""


_GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}


def git_op(segment: Segment) -> GitOp | None:
    argv = program(segment)
    if not argv or Path(argv[0]).name != "git":
        return None
    index, repository = 1, Path(segment.cwd)
    while index < len(argv) and argv[index].startswith("-"):
        flag = argv[index]
        value = argv[index + 1] if index + 1 < len(argv) else ""
        if flag == "-C" or flag == "--git-dir":
            repository = (repository / value).resolve()
        elif flag.startswith("--git-dir="):
            repository = (repository / flag.split("=", 1)[1]).resolve()
        index += 2 if flag in _GIT_OPTIONS_WITH_VALUE else 1
    if index >= len(argv):
        return None
    op, tail = argv[index], list(argv[index + 1 :])
    options: list[str] = []
    positional: list[str] = []
    for arg in tail:
        (options if arg.startswith("-") else positional).append(arg)
    result: GitOp = {
        "op": op,
        "repository": str(repository),
        "remote": positional[0] if op == "push" and positional else None,
        "refs": positional[1:] if op == "push" else positional,
        "options": options,
    }
    return result


def runs_git(part, operations):
    op = git_op(part)
    return bool(op and op["op"] in operations)


def tag_write(segment):
    op = git_op(segment)
    return bool(
        op
        and op["op"] == "tag"
        and op["refs"]
        and not set(op["options"])
        & {
            "--list",
            "-l",
            "--contains",
            "--points-at",
            "--verify",
            "-v",
        }
    )


def branch_push(segment, root):
    op = git_op(segment)
    return bool(
        op
        and op["op"] == "push"
        and op["repository"] == str(Path(root).resolve())
        and op["remote"] == "origin"
        and op["refs"]
        and all(
            ref in {"main", "HEAD", "refs/heads/main"}
            or (
                ":" in ref
                and bool(ref.split(":", 1)[0])
                and not ref.startswith("+")
                and ref.split(":", 1)[1] in {"main", "refs/heads/main"}
            )
            for ref in op["refs"]
        )
        and set(op["options"])
        <= {"-u", "--set-upstream", "--porcelain", "--quiet", "-q", "--no-follow-tags"}
    )


def unit_test(segment):
    argv = program(segment)
    return (
        executes(segment) in {"unittest", "pytest"}
        or (executes(segment) in {"make", "gmake"} and "test-unit" in argv[1:])
        or (bool(argv) and argv[0].startswith("tests/test_") and argv[0].endswith(".py"))
    )


def slow_test(segment):
    argv = program(segment)
    name = executes(segment)
    if name in {"make", "gmake"}:
        return bool(set(argv[1:]) & {"test", "test-integration"})
    if name == "run_integration.py":
        return True
    if name in {"unittest", "pytest"}:
        return any(
            "tests/integration" in arg or arg.startswith("tests.integration") for arg in argv[1:]
        )
    return bool(argv) and (
        "tests/integration/" in argv[0] or argv[0].startswith("tests.integration")
    )


def env_calls(part):
    argv = program(part)
    return [tuple(argv[1:3])] if executes(part) == "envctl" and len(argv) >= 3 else []
