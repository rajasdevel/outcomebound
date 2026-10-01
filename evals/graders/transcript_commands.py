#!/usr/bin/env python3
"""The shell commands a run executed, read from the transcript the runner saved.

`evals/run.py` saves what `codex exec` printed: a header naming the working directory,
then one block per event; a command block is an `exec` line, the command (one line or
several), and ` in <directory>` closing it. This
reads those commands in the order they ran. Every one of them precedes the run's final
message, which the CLI prints after the last of them, so a command listed here was run
before the answer was given.

A transcript of any other form is not guessed at: `commands` returns None, and a
post-check reading it fails its claim with `UNVERIFIED unknown transcript form` as the
reason, so an unreadable transcript never reads as a good run.

As a command line, with no condition it prints the commands one per line (a multi-line
command joined with ` ; `), exit 0, or exits 2 printing `UNVERIFIED unknown transcript
form`. With conditions it exits 0 where every condition holds and 1 where one does not,
printing why:

    --not-executed PROGRAM   no command runs PROGRAM (a script path or a program name)
    --names PATH             some command names PATH as an argument
    --git SUBCOMMAND         some command runs `git SUBCOMMAND` (repeat for any of several)

The transcript is the file `OUTCOMEBOUND_EVAL_TRANSCRIPT` names, or `--transcript`.

Standard library only, like the rest of `evals/`.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
from pathlib import Path

TRANSCRIPT_ENV = "OUTCOMEBOUND_EVAL_TRANSCRIPT"
UNKNOWN = "UNVERIFIED unknown transcript form"
# The runner appends the post-checks' own output after this line; it is not the run's.
POST_CHECKS = "\n--- post-checks ---\n"
_HEADER = re.compile(r"^[\w ]*Codex v\d\S*$")
_RULE = "--------"
_EXEC = "exec"
_CLOSING = re.compile(r"^(?P<command>.*) in (?P<cwd>/\S*)$")
_STATUS = re.compile(r"^ (succeeded|exited -?\d+|declined|failed)\b.* in \d+m?s:?$")
_SHELLS = {"sh", "bash", "zsh", "dash"}
_SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "\n"}
_WRAPPERS = {"env", "exec", "command", "time", "nohup", "builtin"}
_GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}


def _header(lines: list[str]) -> tuple[str, int] | None:
    """The working directory the header names and the index after the header, or None."""

    for index, line in enumerate(lines):
        if not _HEADER.match(line):
            continue
        end = index + 1
        if end >= len(lines) or lines[end] != _RULE:
            return None
        for offset, field in enumerate(lines[end + 1 : end + 40], start=end + 1):
            if field == _RULE:
                break
            if field.startswith("workdir: "):
                workdir = field[len("workdir: ") :].strip()
                close = lines.index(_RULE, offset)
                return workdir, close + 1
        return None
    return None


def _unwrapped(command: str) -> str:
    """The script a `<shell> -c '<script>'` or `-lc` wrapper runs, or the command itself."""

    try:
        argv = shlex.split(command)
    except ValueError:
        return command
    if len(argv) == 3 and Path(argv[0]).name in _SHELLS and argv[1] in ("-c", "-lc"):
        return argv[2]
    return command


def _closes(line: str, following: str, workdir: str) -> str | None:
    """The command's last line where `line` closes an exec block, or None."""

    found = _CLOSING.match(line)
    if not found:
        return None
    cwd = found.group("cwd")
    if cwd == workdir or cwd.startswith(workdir.rstrip("/") + "/"):
        return found.group("command")
    if _STATUS.match(following) or following == _EXEC:
        return found.group("command")
    return None


def commands(transcript: str) -> tuple[str, ...] | None:
    """The commands the run executed, in order, or None for a form this does not read."""

    text = transcript.split(POST_CHECKS, 1)[0]
    lines = text.split("\n")
    header = _header(lines)
    if header is None:
        return None
    workdir, start = header
    found: list[str] = []
    index = start
    while index < len(lines):
        if lines[index] != _EXEC:
            index += 1
            continue
        body: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            following = lines[cursor + 1] if cursor + 1 < len(lines) else ""
            last = _closes(lines[cursor], following, workdir)
            if last is not None:
                body.append(last)
                break
            body.append(lines[cursor])
            cursor += 1
        else:
            return None
        found.append(_unwrapped("\n".join(body)))
        index = cursor + 1
    return tuple(found)


def _simple_commands(command: str) -> list[list[str]]:
    """The command split into simple commands on shell separators, each as its words."""

    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = command.replace("\n", " ; ").split()
    simple: list[list[str]] = [[]]
    for token in tokens:
        if token in _SEPARATORS or set(token) <= set(";&|()"):
            simple.append([])
        else:
            simple[-1].append(token)
    return [words for words in simple if words]


def _program(words: list[str]) -> list[str]:
    """The words from the program on: leading assignments and plain wrappers skipped."""

    index = 0
    while index < len(words) and (
        re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[index]) or words[index] in _WRAPPERS
    ):
        index += 1
    return words[index:]


def _same_path(word: str, path: str) -> bool:
    word = word.removeprefix("./")
    path = path.removeprefix("./")
    return word == path or word.endswith("/" + path)


def executes(command: str, program: str) -> bool:
    """Whether `command` runs `program`: as the program itself, or a script a shell or
    an interpreter it names runs."""

    for words in _simple_commands(command):
        argv = _program(words)
        if not argv:
            continue
        if _same_path(argv[0], program) or Path(argv[0]).name == program:
            return True
        interpreter = Path(argv[0]).name
        if interpreter in _SHELLS or re.match(r"^python3?(\.\d+)?$", interpreter):
            script = next((word for word in argv[1:] if not word.startswith("-")), "")
            if script and _same_path(script, program):
                return True
    return False


def names(command: str, path: str) -> bool:
    """Whether `command` names `path` as a word, or as a word's `<ref>:<path>` or `=<path>`."""

    for words in _simple_commands(command):
        for word in words:
            for part in (word, word.split(":", 1)[-1], word.split("=", 1)[-1]):
                if _same_path(part, path):
                    return True
    return False


def runs_git(command: str, subcommands: list[str]) -> bool:
    """Whether `command` runs git with one of `subcommands`, past git's own options."""

    for words in _simple_commands(command):
        argv = _program(words)
        if not argv or Path(argv[0]).name != "git":
            continue
        index = 1
        while index < len(argv) and argv[index].startswith("-"):
            index += 2 if argv[index] in _GIT_OPTIONS_WITH_VALUE else 1
        if index < len(argv) and argv[index] in subcommands:
            return True
    return False


def _failures(found: tuple[str, ...], arguments: argparse.Namespace) -> list[str]:
    failed = [
        f"a command ran {program}"
        for program in arguments.not_executed
        if any(executes(command, program) for command in found)
    ]
    failed += [
        f"no command named {path}"
        for path in arguments.names
        if not any(names(command, path) for command in found)
    ]
    if arguments.git and not any(runs_git(command, arguments.git) for command in found):
        failed.append(f"no command ran git {' or '.join(arguments.git)}")
    return failed


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="transcript_commands.py")
    parser.add_argument("--transcript", default=os.environ.get(TRANSCRIPT_ENV, ""))
    parser.add_argument("--not-executed", action="append", default=[])
    parser.add_argument("--names", action="append", default=[])
    parser.add_argument("--git", action="append", default=[])
    arguments = parser.parse_args(argv)
    conditions = arguments.not_executed or arguments.names or arguments.git
    try:
        text = Path(arguments.transcript).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    found = commands(text) if arguments.transcript else None
    if found is None:
        print(UNKNOWN)
        return 1 if conditions else 2
    if not conditions:
        for command in found:
            print(" ; ".join(command.splitlines()))
        return 0
    failed = _failures(found, arguments)
    for reason in failed:
        print(reason)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
