#!/usr/bin/env python3
"""The shell command attempts and outcomes in the transcript the runner saved.

`evals/run.py` saves what `codex exec` printed: a header naming the working directory,
then one block per event; a command block is an `exec` line, the command (one line or
several), and ` in <directory>` closing it. This
reads those attempts in order and preserves their reported outcomes. An attempt alone
is not proof of success or an effect. Authority checks keep denied attempts; checks
that need success must inspect the outcome.

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
_STATUS = re.compile(
    r"^ (?P<status>succeeded|exited -?\d+|declined|failed|unverified)\b.* in \d+m?s:?$"
)
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


def execution_records(transcript: str) -> tuple[tuple[str, str, str], ...] | None:
    """Command attempts and their adjacent result status, in call order.

    An absent or non-adjacent status is unverified; it is not assigned to another
    command. A denied or failed attempt is retained for authority checks.
    """

    text = transcript.split(POST_CHECKS, 1)[0]
    lines = text.split("\n")
    header = _header(lines)
    if header is None:
        return None
    workdir, start = header
    found: list[tuple[str, str, str]] = []
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
        status = _STATUS.match(following)
        outcome = status.group("status") if status else "unverified"
        closing = _CLOSING.match(lines[cursor])
        if closing is None:
            return None
        found.append((_unwrapped("\n".join(body)), outcome, closing.group("cwd")))
        index = cursor + 1
    return tuple(found)


def executions(transcript: str) -> tuple[tuple[str, str], ...] | None:
    """Command attempts with their result status, without working directories."""

    records = execution_records(transcript)
    return None if records is None else tuple((command, status) for command, status, _ in records)


def commands(transcript: str) -> tuple[str, ...] | None:
    """All command attempts, including denied ones, for scope and authority checks."""

    found = executions(transcript)
    return None if found is None else tuple(command for command, _ in found)


def successful_sequence(command: str) -> tuple[tuple[str, ...], ...] | None:
    """Arguments of a supported straight-line command or && chain.

    Quoted operators remain arguments. Branches, pipes, expansion, redirects and
    multiline scripts are not execution proof from one final success status.
    This is deliberately not a general shell interpreter.
    """

    if any(char in command for char in ("\n", "$", "`", "\\")):
        return None
    lexer = shlex.shlex(command, posix=False, punctuation_chars=";&|()<>")
    lexer.commenters = "#"
    lexer.whitespace_split = True
    sequence: list[tuple[str, ...]] = []
    words: list[str] = []
    try:
        for word in lexer:
            if word == "&&":
                if not words:
                    return None
                sequence.append(tuple(_program(words)))
                if "exec" in words[: len(words) - len(sequence[-1])]:
                    return tuple(sequence)
                words = []
            elif word and all(char in ";&|()<>" for char in word):
                return None
            else:
                parsed = shlex.split(word)
                if len(parsed) != 1:
                    return None
                words.append(parsed[0])
    except ValueError:
        return None
    if not words:
        return None
    sequence.append(tuple(_program(words)))
    return tuple(sequence) if all(sequence) else None


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
