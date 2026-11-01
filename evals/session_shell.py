"""Static shell input handling for the session isolation scan; never execute input."""

from __future__ import annotations

import glob
import re
import shlex
from pathlib import Path
from typing import Any

from evals.session_scripts import script_effects

SHELL_PART = r"'[^']*'|\"(?:\\.|[^\"\\])*\"|\\.|[^'\"\\]+"
HERE = re.compile(
    r"'[^']*'|\"(?:\\.|[^\"\\])*\"|\\.|"
    r"(?P<here><<(?P<tabs>-)?[ \t]*(?P<end>'[^']*'|\"[^\"]*\"|[^\s;&|<>]+))"
)


class LiteralWord(str):
    """A quoted shell operand whose wildcard and brace characters are literal."""


def literal_words(command: str) -> set[str]:
    parts = re.findall(SHELL_PART, command)
    quoted = {
        shlex.split(part)[0] for part in parts if part.startswith(("'", '"')) and shlex.split(part)
    }
    unquoted = {
        word
        for part in parts
        if not part.startswith(("'", '"', "\\"))
        for word in re.split(r"[\s;&|()<>]+", part)
    }
    return quoted - unquoted


def _heredoc_line(
    line: str, command: str, count: int
) -> tuple[str, list[tuple[str, str, str | None, str]]]:
    pending: list[tuple[str, str, str | None, str]] = []

    def replace(match: re.Match[str]) -> str:
        if not match.group("here"):
            return match.group()
        delimiter = match.group("end")
        key = f"__session_stdin_{count + len(pending)}__"
        while key in command:
            key += "_"
        pending.append((key, shlex.split(delimiter)[0], match.group("tabs"), delimiter))
        return "<< " + key

    return HERE.sub(replace, line), pending


def heredocs(command: str) -> tuple[str, dict[str, tuple[str, bool]], bool]:
    """Keep bodies out of shell argv, retaining which ones permit shell expansion."""
    lines = iter(command.splitlines(keepends=True))
    shell = []
    bodies: dict[str, tuple[str, bool]] = {}
    for line in lines:
        header, pending = _heredoc_line(line, command, len(bodies))
        shell.append(header)
        for key, delimiter, tabs, quoted in pending:
            body = []
            for data in lines:
                data = data.lstrip("\t") if tabs else data
                if data.rstrip("\r\n") == delimiter:
                    break
                body.append(data)
            else:
                return "".join(shell), bodies, True
            bodies[key] = ("".join(body), not any(c in quoted for c in "'\"\\"))
    return "".join(shell), bodies, False


def braces(word: str) -> list[str]:
    """Expand comma and numeric or letter ranges, including nested braces."""
    match = re.search(r"\{([^{}]*)\}", word)
    if match is None:
        return [word]
    body = match[1]
    choices = body.split(",")
    if len(choices) == 1:
        span = re.fullmatch(r"(-?\d+|[a-zA-Z])\.\.(-?\d+|[a-zA-Z])(?:\.\.(-?\d+))?", body)
        if span is None:
            return [word]
        first, last, step = span.groups()
        numeric = first.lstrip("-").isdigit() and last.lstrip("-").isdigit()
        if not numeric and not (first.isalpha() and last.isalpha()):
            return [word]
        start, end = (int(first), int(last)) if numeric else (ord(first), ord(last))
        stride = (abs(int(step)) or 1) if step else 1
        stride *= 1 if end >= start else -1
        width = (
            max(len(first), len(last))
            if any(
                value.lstrip("-").startswith("0") and len(value.lstrip("-")) > 1
                for value in (first, last)
            )
            else 0
        )
        choices = [
            f"{n:0{width}d}" if numeric else chr(n)
            for n in range(start, end + stride // abs(stride), stride)
        ]
    return [
        expanded
        for choice in choices
        for expanded in braces(word[: match.start()] + choice + word[match.end() :])
    ]


def path_expansions(word: str, cwd: Path | None, *, unmatched: bool = True) -> list[Path]:
    if isinstance(word, LiteralWord):
        return [(cwd or Path("/")) / word]
    paths: list[Path] = []
    for value in braces(word):
        path = (cwd or Path("/")) / value
        matches = glob.glob(str(path)) if glob.has_magic(value) else []
        if matches:
            paths.extend(Path(p) for p in matches)
        elif unmatched or not glob.has_magic(value):
            paths.append(path)
    return paths


def expansion_words(command: str) -> list[str]:
    """Unquoted glob and brace operands, even where a text command discards them."""
    return [
        word
        for part in re.findall(SHELL_PART, command)
        if not part.startswith(("'", '"', "\\"))
        for word in part.split()
        if glob.has_magic(word) or re.search(r"\{[^{}]*(?:,|\.\.)[^{}]*\}", word)
    ]


def _segments(
    command: str,
    cwd: Path | None,
) -> tuple[list[tuple[list[str], Path | None, str]], bool]:
    """Split shell input; directory changes need execution evidence from the caller."""
    command = "".join(
        part if part.startswith(("'", '"', "\\")) else part.replace("\n", " \n ")
        for part in re.findall(SHELL_PART, command)
    )
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    lexer.whitespace = " \t\r"
    try:
        words = list(lexer)
        literals = literal_words(command)
        words = [LiteralWord(w) if w in literals else w for w in words]
    except ValueError:
        return [], True
    result = []
    segment: list[str] = []
    operator = ";"
    unresolved = False
    for word in [*words, ";"]:
        if word == "\n" and not segment:
            continue
        if word not in (";", "&&", "||", "|", "\n"):
            if word in ("(", ")", "&", "<<<"):
                unresolved = True
            segment.append(word)
            continue
        if segment:
            result.append((segment, cwd, operator))
            unresolved |= segment[0] in ("if", "for", "while", "until", "case", "function")
            segment = []
        operator = word
    return result, unresolved


def _find_roots(args: list[str]) -> list[str]:
    roots = []
    for arg in args:
        if arg.startswith("-") or arg in ("(", "!"):
            break
        roots.append(arg)
    return roots or ["."]


def _operands(name: str, args: list[str]) -> list[str]:
    if name == "find":
        return _find_roots(args)
    paths = []
    skip = False
    pattern_file = False
    pattern = name in ("grep", "rg", "sed", "awk") and "--files" not in args
    for arg in args:
        if skip:
            paths.extend([arg] if pattern_file else [])
            skip = False
            pattern_file = False
            continue
        if arg in ("-m", "--message", "--format", "--pretty") and name == "git":
            skip = True
            continue
        if name in ("rg", "grep", "sed", "awk") and arg in ("-e", "--regexp", "-f", "--file"):
            skip, pattern = True, False
            pattern_file = arg in ("-f", "--file")
            continue
        if name in ("rg", "grep") and arg.split("=", 1)[0] in (
            "-g",
            "--glob",
            "--iglob",
            "-t",
            "--type",
            "-T",
            "--type-not",
            "--include",
            "--exclude",
            "--exclude-dir",
        ):
            # These select names or patterns; they are not search roots.
            skip = "=" not in arg
            continue
        if arg.startswith("-"):
            if "=" in arg:
                paths.append(arg.split("=", 1)[1])
            continue
        if pattern:
            pattern = False
            continue
        paths.append(arg)
    return paths


def _git_paths(args: list[str]) -> list[str]:
    paths = []
    take_path = False
    skip = False
    for index, arg in enumerate(args):
        if take_path:
            paths.append(arg)
            take_path = False
        elif skip:
            skip = False
        elif arg in ("-C", "--git-dir", "--work-tree", "-F", "--file", "--output"):
            take_path = True
        elif arg in ("-c", "-m", "--message", "--format", "--pretty"):
            skip = True
        elif arg.startswith(("--git-dir=", "--work-tree=", "--file=", "--output=")):
            paths.append(arg.split("=", 1)[1])
        elif arg == "--":
            return paths + args[index + 1 :]
        elif arg.startswith(("/", "./", "../")):
            paths.append(arg)
    return paths


def _path_words(words: list[str]) -> tuple[list[str], bool]:
    """Drop literal text operands. Dynamic programs and paths cannot certify isolation."""
    while words and re.match(r"[A-Za-z_][A-Za-z_0-9]*=", words[0]):
        words = words[1:]
    if not words:
        return [], False
    executable, *args = words
    name = Path(executable).name
    if name in ("echo", "printf", "true", "false"):
        return [args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "<"], False
    if name in ("env", "sudo", "command", "exec"):
        while args and args[0] in ("--", "-n", "-i", "--ignore-environment"):
            args = args[1:]
        if args and args[0].startswith("-"):
            return [], True
        return _path_words(args)
    if name in ("sh", "bash", "zsh") and any("c" in a for a in args if a.startswith("-")):
        return [], True
    paths = ([executable] if "/" in executable else []) + (
        _git_paths(args) if name == "git" else _operands(name, args)
    )
    return paths, False


def _expands(command: str) -> bool:
    """Check before dropping text operands; quoted shell substitutions still execute."""
    for part in re.findall(r"'[^']*'|\"(?:\\.|[^\"\\])*\"|\\.|[^'\"\\]+", command):
        if part.startswith(("'", "\\")):
            continue
        pattern = r"(?<!\\)[$`]" if part.startswith('"') else r"[$`~]"
        if re.search(pattern, part):
            return True
    return False


def _recursive(words: list[str]) -> bool:
    while words and re.match(r"[A-Za-z_][A-Za-z_0-9]*=", words[0]):
        words = words[1:]
    if not words:
        return False
    name, args = Path(words[0]).name, words[1:]
    if name in ("env", "sudo", "command", "exec"):
        while args and (args[0].startswith("-") or "=" in args[0]):
            args = args[1:]
        return _recursive(args)
    if name in ("rg", "rgrep", "find", "fd", "tree", "du"):
        return True
    return name in ("grep", "ls") and any(
        arg in ("--recursive", "--dereference-recursive")
        or (
            arg.startswith("-")
            and not arg.startswith("--")
            and bool(set(arg) & set("rR" if name == "grep" else "R"))
        )
        for arg in args
    )


def output_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return output_text(value.get("text"))
    if isinstance(value, list):
        return "\n".join(output_text(part) for part in value)
    return ""


def _absolute(words: list[str], cwd: Path) -> list[str]:
    return list(
        dict.fromkeys(str(p.resolve()) for word in words for p in path_expansions(word, cwd))
    )


def recursive(argv: list[str] | None) -> bool:
    return _recursive(argv or [])


def _redirects(
    words: list[str], bodies: dict[str, tuple[str, bool]]
) -> tuple[list[str], list[str], list[str], list[tuple[str, bool]]]:
    argv: list[str] = []
    reads: list[str] = []
    writes: list[str] = []
    inputs: list[tuple[str, bool]] = []
    i = 0
    while i < len(words):
        word = words[i]
        if word in ("<", ">", ">>", "<<", "<<-", "<>", ">&", "<&"):
            if argv and argv[-1].isdigit():
                argv.pop()
            i += 1
            if i >= len(words):
                return argv, reads, writes, [("", True)]
            operand = words[i]
            if word.startswith("<<") and operand in bodies:
                inputs.append(bodies[operand])
            elif word not in (">&", "<&"):
                (reads if word == "<" else writes).append(operand)
                if word == "<>":
                    reads.append(operand)
        else:
            argv.append(word)
        i += 1
    return argv, reads, writes, inputs


def _program(argv: list[str]) -> list[str]:
    while argv and re.match(r"[A-Za-z_][A-Za-z_0-9]*=", argv[0]):
        argv = argv[1:]
    if argv and Path(argv[0]).name in ("env", "sudo", "command", "exec"):
        return (
            _program(argv[1:])
            if len(argv) > 1 and not argv[1].startswith("-")
            else _program(argv[2:])
            if argv[1:2] in (["-n"], ["--"], ["-i"])
            else argv
        )
    return argv


def interpreter(argv: list[str] | None) -> bool:
    program = _program(argv or [])
    name = Path(program[0]).name if program else ""
    return name.startswith(("python", "pypy")) or name in ("node", "nodejs", "sh", "bash", "zsh")


def _scripts(program: list[str], inputs: list[tuple[str, bool]]) -> tuple[list[str], bool]:
    return _interpreter_scripts(program, inputs) if interpreter(program) else ([], False)


def _stdin(inputs: list[tuple[str, bool]]) -> tuple[list[str], bool]:
    return [body for body, _ in inputs], not bool(inputs)


def _input_flag(arg: str, shell: bool) -> bool:
    letters = "abefhkmnptuvxBCEHPTailsr" if shell else "bBdEiqOuvsSIRxP"
    return arg.startswith("-") and bool(arg[1:]) and set(arg[1:]) <= set(letters)


def _inline_program(args: list[str], index: int, shell: bool, python: bool):
    arg = args[index]
    inline = ("-c",) if shell or python else ("-e", "--eval", "-p", "--print")
    if arg in inline or (shell and arg.startswith("-") and "c" in arg[1:]):
        return ([args[index + 1]], False) if index + 1 < len(args) else ([], True)
    if python and arg.startswith("-c"):
        return [arg[2:]], False
    if python and arg == "-m":
        return [], index + 1 >= len(args)
    if arg in ("--help", "--version", "-h", "-V"):
        return [], False
    return None


def _takes_value(shell: bool, python: bool) -> tuple[str, ...]:
    if python:
        return "-W", "-X"
    if shell:
        return "-o", "+o", "-O", "+O"
    return "-r", "--require", "--import", "--loader", "--input-type"


def _known_option(arg: str, shell: bool, python: bool) -> bool:
    return (shell or python) and (
        (python and arg.startswith(("-W", "-X"))) or _input_flag("-" + arg[1:], shell)
    )


def _interpreter_scripts(
    program: list[str], inputs: list[tuple[str, bool]]
) -> tuple[list[str], bool]:
    name, *args = program
    name = Path(name).name
    shell = name in ("sh", "bash", "zsh")
    python = name.startswith(("python", "pypy"))
    takes_value = _takes_value(shell, python)
    stdin = False
    index = 0
    while index < len(args):
        arg = args[index]
        if result := _inline_program(args, index, shell, python):
            return result
        if arg == "-":
            return _stdin(inputs)
        if shell and arg.startswith("-") and "s" in arg[1:]:
            stdin = True
        elif arg == "--":
            return (
                _stdin(inputs)
                if stdin or args[index + 1 : index + 2] in ([], ["-"])
                else ([], False)
            )
        elif arg in takes_value:
            index += 1
            if index >= len(args):
                return [], True
        elif not arg.startswith(("-", "+")):
            return _stdin(inputs) if stdin else ([], False)
        elif not _known_option(arg, shell, python):
            return [], True
        index += 1
    return _stdin(inputs)


def _file_effects(name: str, paths: list[str]) -> tuple[list[str], list[str]]:
    if name in ("rm", "mkdir", "rmdir", "touch", "chmod", "chown", "truncate", "tee"):
        return [], paths
    if name in ("cp", "mv", "install"):
        return paths[:-1], paths if name == "mv" else paths[-1:]
    return paths, []


def content_program(argv: list[str]) -> bool:
    """Whether the program can return content; execution is not established by its name."""
    program = _program(argv)
    if not program:
        return False
    name, *args = program
    name = Path(name).name
    if name in ("grep", "rg", "rgrep"):
        return not any(
            arg
            in ("--files", "--files-with-matches", "--files-without-match", "--count", "--quiet")
            or (
                arg.startswith("-")
                and not arg.startswith("--")
                and bool(set(arg[1:]) & set("lLqc"))
            )
            for arg in args
        )
    return name in (
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "sed",
        "awk",
        "jq",
        "cp",
        "install",
        "dd",
    )


def _dynamic_paths(paths: list[str], command: str, directory: Path, cwd: Path) -> bool:
    # Expansions in text arguments can still traverse a protected location.
    if not paths and any(
        not p.resolve().is_relative_to(cwd.resolve())
        for word in expansion_words(command)
        for p in path_expansions(word, directory)
    ):
        return True
    return any(
        glob.has_magic(p)
        and not glob.glob(str(directory / p))
        and not all(
            v.resolve().is_relative_to(cwd.resolve()) for v in path_expansions(p, directory)
        )
        for word in paths
        if not isinstance(word, LiteralWord)
        for p in braces(word)
    )


def _part(
    words: list[str],
    directory: Path,
    bodies: dict[str, tuple[str, bool]],
    command: str,
    cwd: Path,
    known_directory: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    argv, reads, writes, inputs = _redirects(words, bodies)
    program = _program(argv)
    name = Path(program[0]).name if program else ""
    paths, unknown = _path_words(argv)
    scripts, uncertain_input = _scripts(program, inputs)
    dynamic = (unknown and name not in ("bash", "sh", "zsh")) or uncertain_input
    dynamic |= any(expand and _expands(body) for body, expand in inputs)
    paths = (
        ([argv[0]] if argv and "/" in argv[0] else [])
        if scripts
        else [p for p in paths if p != "-"]
    )
    uncertain_input |= bool(inputs) and not interpreter(program) and name not in ("cat", "tee")
    dynamic |= uncertain_input
    runs: list[list[str]] | None = None if uncertain_input else []
    if name not in ("bash", "sh", "zsh"):
        for script in scripts:
            script_reads, script_writes, starts, unknown = script_effects(script, name)
            reads.extend(LiteralWord(path) for path in script_reads)
            writes.extend(LiteralWord(path) for path in script_writes)
            dynamic |= unknown
            if starts is None:
                runs = None
            elif runs is not None:
                runs.extend(starts)
        # A known inline process can also read a protected executable or file argument.
        for start in runs or []:
            if interpreter(start):
                runs, dynamic = None, True
            operands, unknown = _path_words(start)
            reads.extend(LiteralWord(path) for path in operands)
            dynamic |= unknown
    file_reads, file_writes = _file_effects(name, paths)
    reads.extend(file_reads)
    writes.extend(file_writes)
    if recursive(argv) and not reads:
        reads.append(".")
    dynamic |= _dynamic_paths([*reads, *writes], command, directory, cwd)
    if not known_directory:
        reads = [path for path in reads if Path(path).is_absolute()]
        writes = [path for path in writes if Path(path).is_absolute()]
    return {
        "argv": None if dynamic else list(argv),
        "cwd": str(directory.resolve()),
        "status": "unknown",
        "reads": _absolute(reads, directory),
        "writes": _absolute(writes, directory),
        "runs": runs,
    }, scripts if name in ("bash", "sh", "zsh") else []


def _statuses(operators: list[str], status: str) -> list[str]:
    result = ["unknown"] * len(operators)
    if len(operators) == 1:
        return ["failed" if status == "refused" else status]
    if status == "ok":
        for index in range(len(operators)):
            start = index
            while start > 0 and operators[start] not in (";", "\n"):
                start -= 1
            suffix = all(op == "&&" for op in operators[index + 1 :])
            conditional = any(op == "||" for op in operators[start + 1 : index + 1])
            if suffix and not conditional:
                result[index] = "ok"
    return result


def _parts(
    command: str, cwd: Path | None, status: str, output: Any, depth: int = 0
) -> list[dict[str, Any]]:
    shell, bodies, incomplete = heredocs(command)
    parsed, unsafe = _segments(shell, cwd)
    statuses = _statuses([op for _, _, op in parsed], status)
    directory = cwd
    result = []
    for (words, _, _), outcome in zip(parsed, statuses, strict=True):
        base = directory or cwd or Path("/")
        part, scripts = _part(words, base, bodies, shell, cwd or Path("/"), directory is not None)
        part["status"] = outcome
        if scripts:
            # The interpreter is the simple command. Body effects remain possible,
            # and its process operands share the same segment with both consumers.
            nested = (
                [
                    p
                    for script in scripts
                    for p in _parts(script, directory, "unknown", None, depth + 1)
                ]
                if depth < 8
                else []
            )
            part["reads"].extend(p for child in nested for p in child["reads"])
            part["writes"].extend(p for child in nested for p in child["writes"])
            if depth >= 8 or any(
                child["argv"] is None or child["runs"] is None or child["cwd"] != part["cwd"]
                for child in nested
            ):
                part["argv"], part["runs"] = None, None
            else:
                part["runs"] = [
                    argv for child in nested for argv in [child["argv"], *child["runs"]]
                ]
        if incomplete or unsafe or _expands(shell) or directory is None:
            part["argv"] = None
            part["runs"] = None
        if (
            len(parsed) > 1
            and not scripts
            and not interpreter(part["argv"])
            and _shown(part, output)
        ):
            part["status"] = "ok"
        result.append(part)
        program = _program(_redirects(words, bodies)[0])
        if program and program[0] == "cd":
            operands = [w for w in program[1:] if w != "--"]
            if (
                outcome == "ok"
                and len(operands) == 1
                and not _expands(operands[0])
                and directory is not None
            ):
                directory = (directory / operands[0]).resolve()
            else:
                directory = None
    if not parsed and command.strip():
        result.append(
            {
                "argv": None,
                "cwd": str((cwd or Path("/")).resolve()),
                "status": "unknown",
                "reads": [],
                "writes": [],
                "runs": None,
            }
        )
    return result


def command_segments(
    command: str, cwd: Path | None, status: str = "unknown", output: Any = None
) -> list[dict[str, Any]]:
    """The action and isolation view of a command, including literal inline effects."""
    return _parts(command, cwd, status, output)


def _shown(part: dict[str, Any], output: Any) -> bool:
    paths = []
    directory = Path(part["cwd"])
    for line in output_text(output).splitlines():
        path, colon, content = line.partition(":")
        if (
            colon
            and path
            and not re.search(
                r"(?i)permission denied|operation not permitted|access denied|sandbox.*refus",
                content,
            )
        ):
            paths.append((directory / path).resolve())
    return bool(part["reads"]) and all(
        any(
            path.is_relative_to(Path(operand))
            and not (
                directory != Path(operand)
                and directory.is_relative_to(Path(operand))
                and path.is_relative_to(directory)
            )
            for path in paths
        )
        for operand in part["reads"]
    )
