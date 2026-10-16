#!/usr/bin/env python3
"""The shell command attempts and outcomes in the transcript the runner saved.

`evals/run.py` and `claude_arm.py` save command records derived from structured
call/result events in a JSON document. Output and answers remain data, never events.
Plain printed transcripts cannot distinguish these sources and return None. A
post-check then reports UNVERIFIED rather than crediting or inventing an attempt.
Missing working directories stay empty; effect checks must not infer one.

`steps` reads a `;` and `&&` list and says, for each command in it, what the one final status
of the whole shows: that the command ran and succeeded, that it ran with its own status unknown,
or that it may not have run. `successful_sequence` is the stricter reader of a lone command or a
`&&` chain with no expansion at all.

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
import json
import os
import re
import shlex
from pathlib import Path

TRANSCRIPT_ENV = "OUTCOMEBOUND_EVAL_TRANSCRIPT"
UNKNOWN = "UNVERIFIED unknown transcript form"
# The runner appends the post-checks' own output after this line; it is not the run's.
POST_CHECKS = "\n--- post-checks ---\n"
_SHELLS = {"sh", "bash", "zsh", "dash"}
_SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "\n"}
_WRAPPERS = {"env", "exec", "command", "time", "nohup", "builtin"}
_GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}


def _unwrapped(command: str) -> str:
    """The script a `<shell> -c '<script>'` or `-lc` wrapper runs, or the command itself."""

    try:
        argv = shlex.split(command)
    except ValueError:
        return command
    if len(argv) == 3 and Path(argv[0]).name in _SHELLS and argv[1] in ("-c", "-lc"):
        return argv[2]
    return command


def execution_records(transcript: str) -> tuple[tuple[str, str, str], ...] | None:
    """Read only the runner's structured command records, never printed output."""

    try:
        document = json.loads(transcript.split(POST_CHECKS, 1)[0])
    except (ValueError, TypeError):
        return None
    if not isinstance(document, dict) or document.get("format") != "outcomebound-command-events-v1":
        return None
    records = document.get("commands")
    if not isinstance(records, list):
        return None
    found = []
    for record in records:
        if (
            not isinstance(record, list)
            or len(record) != 3
            or not all(isinstance(v, str) for v in record)
        ):
            return None
        command, status, directory = record
        if not re.fullmatch(r"succeeded|exited -?\d+|declined|failed|unverified", status):
            return None
        found.append((_unwrapped(command), status, directory))
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


_KEYWORDS = {
    "if", "then", "else", "elif", "fi", "while", "until", "do", "done", "for", "case", "esac",
    "select", "function", "{", "}", "!", "[[", "coproc",
}  # fmt: skip
_TERMINATING = {"exit"}


class _Scanner:
    """The words and the `;` and `&&` operators of one line, with quotes taken off the words."""

    def __init__(self, command: str) -> None:
        self.command = command
        self.tokens: list[tuple[str, str, bool, int]] = []  # (kind, text, expands, position)
        self.word: str | None = None
        self.expands = False
        self.quote = ""
        self.index = 0
        self.end = len(command)

    def _add(self, text: str, expands: bool = False) -> None:
        self.word = (self.word or "") + text
        self.expands = self.expands or expands

    def _flush(self) -> None:
        if self.word is not None:
            self.tokens.append(("word", self.word, self.expands, self.index))
        self.word, self.expands = None, False

    def _single(self, char: str) -> bool:
        if char == "'":
            self.quote = ""
        else:
            self._add(char)
        return True

    def _double(self, char: str) -> bool:
        if char == '"':
            self.quote = ""
        elif char == "$":
            return self._dollar()
        else:
            self._add(char)
        return True

    def _dollar(self) -> bool:
        after = self.command[self.index + 1 : self.index + 2]
        if after == "{":
            return False
        if after != "(":
            self._add("$", True)
            return True
        close = self.command.find(")", self.index)
        inner = self.command[self.index + 2 : close]
        if self.quote != '"' or close < 0 or any(mark in inner for mark in "\"'`($"):
            return False
        self._add(self.command[self.index : close + 1], True)
        self.index = close
        return True

    def _operator(self) -> bool:
        self._flush()
        operator = ";" if self.command[self.index] == ";" else "&&"
        self.tokens.append(("op", operator, False, self.index))
        self.index += len(operator) - 1
        return True

    def _bare(self, char: str) -> bool:
        if char in "'\"":
            self.quote = char
            self.word = self.word or ""
        elif char == "$":
            return self._dollar()
        elif char in " \t":
            self._flush()
        elif char == "#" and self.word is None:
            self.end, self.index = self.index, len(self.command)
        elif char == ";" or self.command.startswith("&&", self.index):
            return self._operator()
        elif char in "&|()<>":
            return False
        else:
            self._add(char)
        return True

    def run(self) -> list[tuple[str, str, bool, int]] | None:
        handlers = {"'": self._single, '"': self._double}
        while self.index < len(self.command):
            if not handlers.get(self.quote, self._bare)(self.command[self.index]):
                return None
            self.index += 1
        if self.quote:
            return None
        self._flush()
        return self.tokens


def _scan(command: str):
    """The simple commands of a `;` and `&&` list as `(operator before, words, expands, text)`.

    Words are unquoted. `expands` is True where a word holds a variable or a `$( ... )`
    substitution outside single quotes. A pipe, `||`, `&`, a redirect, a subshell, a backtick,
    a backslash, a `${`, a newline, an unclosed quote or an empty command (`;;`, a trailing
    `;`) is not a list this reader supports, and the answer is None. A substitution is
    supported only inside double quotes, with no quote, backtick or further parenthesis inside
    it, so that its text cannot hide a separator this scan would read as one.
    """

    if "\n" in command or "\\" in command or "`" in command:
        return None
    scanner = _Scanner(command)
    tokens = scanner.run()
    if tokens is None:
        return None
    found: list[tuple[str, list[str], bool, str]] = []
    words: list[str] = []
    expands, operator, start = False, "", 0
    for kind, value, holds, position in [*tokens, ("op", "", False, scanner.end)]:
        if kind == "word":
            words.append(value)
            expands = expands or holds
            continue
        if not words:
            return None
        found.append((operator, words, expands, command[start:position].strip()))
        words, expands, operator, start = [], False, value, position + len(value)
    return found


def steps(command: str, succeeded: bool):
    """The simple commands of a `;` and `&&` list, each with what its run is known to be.

    Returns `(argv, expands, text, outcome)` per command, in order, or None for a command
    this reader does not support: an unknown shell form (see `_scan`), a branch, a loop, a
    negation or a group. `argv` starts at the program, past leading assignments and plain
    wrappers. `expands` is True where a word of the command holds a variable or a quoted
    `$( ... )`, so the program or an argument may not be what it reads as. `outcome` is what
    the shell's one final status, `succeeded`, and the list's shape show of that command:

        succeeded   it ran and exited 0: it is in the last `;` group, a chain of `&&`, and
                    the status of the whole is a success, which needs each link to succeed
        ran         it ran, and its own status is not shown: it is the first command of a
                    `;` group, which always runs, but only the last status is reported
        maybe       it may not have run: an earlier link of its `&&` chain may have failed

    A command after `exit`, or after one that `exec` replaces the shell with, never ran and
    is left out. Where that `exit` or `exec` follows `&&` and a later `;` group follows it,
    the `exit` may not have run and the later group may have ended the shell: the answer is
    None. This is not a general shell interpreter.
    """

    found = _scan(command)
    if found is None:
        return None
    parsed = []
    for position, (operator, words, expands, text) in enumerate(found):
        argv = tuple(_program(words))
        if argv and argv[0] in _KEYWORDS:
            return None
        parsed.append((operator, argv, expands, text))
        if "exec" in words[: len(words) - len(argv)] or (argv and argv[0] in _TERMINATING):
            # An `exit` or `exec` after `&&` runs only if the links before it succeeded. If a
            # later `;` group follows, that group may be what ended the shell.
            if operator == "&&" and any(later != "&&" for later, *_ in found[position + 1 :]):
                return None
            break
    # A `;` ends a group, so the operator before a command says where its group starts.
    starts = [index for index, (operator, *_) in enumerate(parsed) if operator != "&&"]
    last = starts[-1] if starts else 0
    result = []
    for index, (operator, argv, expands, text) in enumerate(parsed):
        if index >= last and succeeded:
            outcome = "succeeded"
        elif operator != "&&":
            outcome = "ran"
        else:
            outcome = "maybe"
        result.append((argv, expands, text, outcome))
    return tuple(result)


def _simple_commands(command: str) -> list[list[str]]:
    """The command split into simple commands on shell separators, each as its words."""

    # A newline ends a command. The `;` stands on a line of its own, so that a `#` comment, which
    # the lexer ends at the line's end, never takes the lines after it (a heredoc body with a
    # heading, a script with a comment).
    lexer = shlex.shlex(command.replace("\n", "\n;\n"), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        # An unclosed quote (an apostrophe in a heredoc's prose): split on blanks, with the
        # separators apart from the words they follow.
        spaced = re.sub(r"([;&|()])", r" \1 ", command.replace("\n", " ; "))
        tokens = spaced.split()
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
