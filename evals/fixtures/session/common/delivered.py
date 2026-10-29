"""Re-execute checks in disposable copies of the content a claim describes."""

from __future__ import annotations

import ast
import io
import json
import os
import re
import runpy
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent


def seal(root, folder, *, release=False):
    """Keep seed machinery outside the editable project before the first call."""
    folder = Path(folder)
    with snapshot(root, machinery=False) as source:
        if folder.exists():
            shutil.rmtree(folder)
        makefile = source / "Makefile"
        make = makefile.read_text(encoding="utf-8") if makefile.is_file() else ""
        checkers = set(re.findall(r"(?:tools|scripts)/[\w./-]+\.py", make))
        for path in source.rglob("*"):
            name = path.relative_to(source)
            if path.is_file() and (
                name.parts[0] == "tests"
                or (not release and name.as_posix() == "Makefile")
                or name.as_posix() in checkers
                or (name.parts[0] in {"tools", "scripts"} and "check" in path.stem)
            ):
                target = folder / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)


@contextmanager
def snapshot(root=Path("."), revision=None, *, machinery=True):
    root = Path(root).resolve()
    with tempfile.TemporaryDirectory(prefix="session-check-") as folder:
        target = Path(folder).resolve() / "project"
        target.mkdir()
        if revision:
            archive_revision(root, target, revision)
        else:
            shutil.copytree(
                root,
                target,
                dirs_exist_ok=True,
                symlinks=False,
                ignore=shutil.ignore_patterns(
                    ".git",
                    ".agents",
                    ".outcomebound",
                    ".remotes",
                    ".remote.git",
                    ".worktrees",
                    "__pycache__",
                    ".pytest_cache",
                ),
            )
        copy_repository(root, target, revision)
        if machinery:
            sealed = HERE / "seed-checks"
            if sealed.is_dir():
                shutil.copytree(sealed, target, dirs_exist_ok=True)
            elif (HERE / "session.json").is_file():
                raise ValueError("unjudged: sealed seed machinery is unavailable")
        yield target


def archive_revision(root, target, revision):
    done = subprocess.run(["git", "archive", revision], cwd=root, capture_output=True, check=False)
    if done.returncode:
        raise ValueError("unjudged: described revision is unavailable: " + revision)
    with tarfile.open(fileobj=io.BytesIO(done.stdout)) as archive:
        for member in archive:
            path = target / member.name
            if not path.resolve().is_relative_to(target):
                raise ValueError("archive path escapes disposable copy")
            if member.isfile():
                source = archive.extractfile(member)
                if source is not None:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(source.read())
                    path.chmod(member.mode)
            elif member.issym():
                link = path.parent / member.linkname
                if not link.resolve().is_relative_to(target):
                    raise ValueError("archive link escapes disposable copy")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(member.linkname)


def copy_repository(root, target, revision):
    # Read-only Git checks and Python checks which query Git need the described
    # revision and index too. All repository writes stay in the disposable copy.
    repository = subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if repository.returncode == 0:
        shutil.copytree(
            repository.stdout.strip(),
            target / ".git",
            ignore=shutil.ignore_patterns("hooks", "worktrees", "ob-receipts"),
        )
        config = target / ".git/config"
        config.write_text(
            config.read_text(encoding="utf-8").replace(str(root), str(target)), encoding="utf-8"
        )
        for key in ("core.worktree", "core.bare"):
            subprocess.run(["git", "config", "--unset", key], cwd=target, capture_output=True)
        if revision:
            subprocess.run(
                ["git", "read-tree", revision], cwd=target, check=True, capture_output=True
            )
            head = subprocess.check_output(
                ["git", "rev-parse", revision], cwd=root, text=True, encoding="utf-8"
            ).strip()
            (target / ".git/HEAD").write_text(head + "\n", encoding="utf-8")


def run(root, argv, revision=None, *, input=None, machinery=True):
    with snapshot(root, revision, machinery=machinery and Path(argv[0]).name != "git") as target:
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("GIT_", "OB_RECEIPT", "MAKE"))
            and key not in {"PYTHONPATH", "PYTHONHOME"}
        }
        env.update(
            OB_RECEIPTS_DISABLED="1",
            PYTHONDONTWRITEBYTECODE="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_CONFIG_NOSYSTEM="1",
        )
        try:
            return subprocess.run(
                [arg.replace(str(Path(root).resolve()), str(target)) for arg in argv],
                cwd=target,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
                check=False,
                input=input.replace(str(Path(root).resolve()), str(target))
                if input is not None
                else None,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError("unjudged: check could not finish: " + str(error)) from error


def unit(root=Path("."), revision=None):
    done = run(root, [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"], revision)
    if re.search(r"Ran 0 tests", done.stdout + done.stderr):
        done.returncode = 1
        done.stderr += "\nNo delivered unit tests ran.\n"
    return done


def problems(done, label):
    return [] if done.returncode == 0 else [label + ": " + (done.stdout + done.stderr)[-1500:]]


def exit_code(problems):
    return 1 if any(not p.startswith("unjudged:") for p in problems) else 3 if problems else 0


def collect(checks):
    """Keep known failures even when another check cannot be judged."""
    failures: list[str] = []
    gaps: list[str] = []
    for check in checks:
        for problem in assessed(check):
            (gaps if problem.startswith("unjudged:") else failures).append(problem)
    return failures + gaps


def assessed(check):
    try:
        return check()
    except ValueError as error:
        if not str(error).startswith("unjudged:"):
            raise
        return [str(error)]


def without_assignments(argv):
    words = list(argv)
    while words and re.match(r"[A-Za-z_][A-Za-z_0-9]*=", words[0]):
        words.pop(0)
    if not words:
        raise ValueError("unjudged: reported check has assignments but no command")
    return words


def command(text):
    try:
        argv = shlex.split(joined_lines(text))
    except ValueError as error:
        raise ValueError("unjudged: invalid reported check") from error
    # These are drawn command fields, not a reconstruction of tool actions.
    if not argv:
        raise ValueError("unjudged: reported check has no command")
    words = without_assignments(argv)
    name = Path(words[0]).name
    if re.search(r"[^\s;&|][ \t]+\([^()\n]+\)[ \t]*$", text):
        raise ValueError("unjudged: reported check contains an unexpanded description")
    if shell_syntax(text):
        return ["sh", "-c", text]
    if argv[0] in BUILTINS:
        return ["sh", "-c", text]
    if name in {"sh", "bash", "zsh"} and "-c" in argv:
        return argv
    if name == "git":
        if len(argv) < 2 or argv[1] not in {
            "diff",
            "show",
            "status",
            "log",
            "rev-parse",
            "ls-files",
        }:
            raise ValueError("unjudged: reported Git operation is not a read-only check")
    elif not (
        name in {"env", "uv", "make", "gmake", "pytest"}
        or name.startswith(("python", "pypy"))
        or "/" in argv[0]
        or shutil.which(argv[0])
    ):
        raise ValueError("unjudged: unsupported reported check: " + text)
    return executable(argv)


def shell_syntax(text):
    """Keep expansion and operators in the shell, including inside double quotes."""
    quote = None
    escaped = False
    for char in text:
        if escaped:
            if char == "\n":
                return True
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif char == quote:
            quote = None
        elif char in "'\"" and quote is None:
            quote = char
        elif (quote != "'" and char in "$`") or (quote is None and char in ";&|<>()*?[]~{}#\n"):
            return True
    return bool(re.match(r"\s*[A-Za-z_][A-Za-z_0-9]*=", text))


def joined_lines(text):
    """Remove escaped newlines except inside literal single quotes."""
    result = []
    quote = None
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and quote != "'" and index + 1 < len(text):
            if text[index + 1] != "\n":
                result.extend(text[index : index + 2])
            index += 2
            continue
        if char == quote:
            quote = None
        elif char in "'\"" and quote is None:
            quote = char
        result.append(char)
        index += 1
    return "".join(result)


def prose_check(text, root=Path(".")):
    """A narrative assertion names no executable and supplies no check credit."""
    try:
        lexer = shlex.shlex(joined_lines(text), posix=True, punctuation_chars=";&|<>()")
        lexer.whitespace_split = True
        words = list(lexer)
    except ValueError:
        return False
    if not words:
        return True
    # Only a positive narrative form is prose. A missing program is not evidence
    # that a drawn command was a sentence on the machine which recorded it.
    first = words[0]
    if first not in {"compared", "surveyed", "reviewed", "inspected", "checked", "verified"}:
        return False
    if len(words) < 2 or shell_syntax(text) or any(word.startswith("-") for word in words[1:]):
        return False
    for word in words:
        path = (Path(root) / word).resolve()
        if shutil.which(word) or (path.is_file() and os.access(path, os.X_OK)):
            return False
    return all(re.fullmatch(r"[A-Za-z][A-Za-z./_-]*", word) for word in words)


BUILTINS = {
    ":",
    ".",
    "break",
    "cd",
    "command",
    "continue",
    "eval",
    "exec",
    "exit",
    "export",
    "getopts",
    "hash",
    "pwd",
    "read",
    "readonly",
    "return",
    "set",
    "shift",
    "test",
    "times",
    "trap",
    "type",
    "ulimit",
    "umask",
    "unset",
    "wait",
    "printf",
    "echo",
    "true",
    "false",
    "[",
}


def shell_groups(text):
    """Read simple invocations in a drawn report, leaving execution to the shell."""
    lexer = shlex.shlex(joined_lines(text), posix=True, punctuation_chars=";&|<>")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    groups = []
    argv: list[str] = []
    tokens = list(lexer)
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {";", "&&", "||", "|", "&"}:
            if argv:
                groups.append(argv)
            argv = []
        elif token and token[0] in "<>":
            if argv and argv[-1].isdigit():
                argv.pop()
            index += 1
        else:
            argv.append(token)
        index += 1
    if argv:
        groups.append(argv)
    return groups


def check_commands(text, makeflags=()):
    """Qualify drawn checks inside shell launchers and redirections, not tool actions."""
    result = []
    launch = runpy.run_path(str(HERE / "commands.py"))["_program"]
    for argv in shell_groups(text):
        flags = list(makeflags)
        for word in argv:
            if word.startswith("MAKEFLAGS="):
                flags = word.partition("=")[2].split()
        argv = list(launch(argv))
        if not argv:
            continue
        at = shell_body(argv)
        if at is not None:
            if at >= len(argv):
                raise ValueError("unjudged: shell check has no command body")
            result.extend(check_commands(argv[at], flags))
        else:
            if Path(argv[0]).name in {"make", "gmake"} and make_modes(flags, environment=True):
                argv.insert(1, "-n")
            result.append(argv)
    return result


def shell_body(argv):
    if not argv or Path(argv[0]).name not in {"sh", "bash", "zsh", "dash"}:
        return None
    index = 1
    while index < len(argv):
        arg = argv[index]
        if arg == "--" or not arg.startswith("-"):
            break
        if not arg.startswith("--") and "c" in arg[1:]:
            return index + 1
        index += 2 if arg in {"-o", "-O"} else 1
    return None


def make_modes(args, *, environment=False):
    valued = {"C", "f", "I", "o", "W"}
    long_valued = {
        "--directory",
        "--file",
        "--makefile",
        "--include-dir",
        "--old-file",
        "--assume-old",
        "--what-if",
        "--new-file",
        "--assume-new",
        "--eval",
    }
    words = iter(args)
    for index, arg in enumerate(words):
        if arg == "--":
            break
        name = arg.split("=", 1)[0]
        # make accepts an unambiguous abbreviation of a long option, so `--dry-ru` is a dry run.
        if len(name) > 2 and any(
            mode.startswith(name)
            for mode in ("--dry-run", "--just-print", "--recon", "--question", "--touch")
        ):
            return True
        if arg in long_valued:
            next(words, None)
        elif (arg.startswith("-") and not arg.startswith("--")) or (
            environment and index == 0 and not arg.startswith("-") and "=" not in arg
        ):
            letters = arg.lstrip("-")
            for at, letter in enumerate(letters):
                if letter in "nqt":
                    return True
                if letter in valued | {"j", "l", "O"}:
                    if letter in valued and at == len(letters) - 1:
                        next(words, None)
                    break
    return False


def check_runner(argv):
    if Path(argv[0]).name.startswith(("python", "pypy")):
        args = iter(argv[1:])
        for arg in args:
            if arg == "-m":
                return next(args, "")
            if arg in {"-W", "-X"}:
                next(args, None)
            elif arg == "-c" or arg == "-" or not arg.startswith("-"):
                return ""
        return ""
    return Path(argv[0]).name


def executable(argv, *, stdin=False):
    name = Path(argv[0]).name
    if name.startswith(("python", "pypy")):
        if shutil.which(argv[0]) is None:
            raise ValueError("unjudged: unavailable reported interpreter: " + argv[0])
        argv[0] = sys.executable
        if ("-" in argv[1:] and not stdin) or any(arg.startswith("<<") for arg in argv[1:]):
            raise ValueError("unjudged: reported Python input is not in the command field")
        return argv
    return argv


def report(text, *, root=Path("."), revision=None):
    if prose_check(text, root):
        print("diagnostic: prose-only reported check: " + text)
        return None
    body = None
    if re.match(r"\S*(?:python|pypy)\S*\s", text) and re.search(r"\s-\s*\(", text):
        body = recorded_body(text)
        argv = executable(shlex.split(text.split(" (", 1)[0]), stdin=True)
    else:
        argv = command(text)
    checks = check_commands(text) if body is None else [argv]
    if argv[0] in BUILTINS:
        argv = ["sh", "-c", text]
    # Qualification follows the inner command; a shell exit alone is not check credit.
    if any(Path(call[0]).name in {"make", "gmake"} and make_modes(call[1:]) for call in checks):
        return False
    done = run(root, argv, revision, input=body)
    if done.returncode == 127 or (
        done.returncode == 0
        and re.search(
            r"command not found|(?:^|\n)[^:\n]*:\s*(?:\d+:\s*)?[\w./-]+:\s*not found",
            done.stdout + done.stderr,
        )
    ):
        raise ValueError("unjudged: reported shell check uses an unavailable program")
    runners = {check_runner(call) for call in checks}
    if "unittest" in runners:
        return unit_report(root, argv, revision, done)
    if runners & {"unittest", "pytest"} and re.search(
        r"Ran 0 tests|no tests ran", done.stdout + done.stderr
    ):
        return False
    return done.returncode == 0


def unit_report(root, argv, revision, sealed):
    # Keep the seed's tests authoritative, and still catch a false PASS in tests
    # added to an existing file. Such additions cannot replace the original tests.
    if sealed.returncode and not loader_errors_only(sealed):
        return False
    actual = run(root, argv, revision, machinery=False)
    if actual.returncode or re.search(r"Ran 0 tests", actual.stdout + actual.stderr):
        return False
    if sealed.returncode == 0:
        return not re.search(r"Ran 0 tests", sealed.stdout + sealed.stderr)
    return added_reports(root, argv, revision)


def added_reports(root, argv, revision):
    selections = [arg for arg in argv if arg.startswith("tests.")]
    if not selections:
        raise ValueError("unjudged: sealed loader error has no separable added selection")
    prefix = [arg for arg in argv if arg not in selections]
    gaps = []
    for selection in selections:
        selected = [*prefix, selection]
        original = run(root, selected, revision)
        if original.returncode == 0:
            continue
        if not loader_errors_only(original):
            return False
        try:
            added_selection(root, selected, revision)
        except ValueError as error:
            if not str(error).startswith("unjudged:"):
                raise
            gaps.append(str(error))
    if gaps:
        raise ValueError("\n".join(gaps))
    return True


def loader_errors_only(done):
    failures = re.findall(r"^(?:FAIL|ERROR): (.+)$", done.stderr, re.M)
    return bool(failures) and all("unittest.loader._FailedTest" in row for row in failures)


def added_selection(root, argv, revision):
    seed = os.environ.get("OUTCOMEBOUND_SEED_SHA") or "seed"
    with (
        snapshot(root, revision, machinery=False) as delivery,
        snapshot(root, seed, machinery=False) as baseline,
    ):
        shutil.copytree(delivery / "tests", baseline / "tests", dirs_exist_ok=True)
        before = run(baseline, argv, machinery=False)
    if (
        before.returncode
        and re.search(r"^(?:FAIL|ERROR): test_", before.stderr, re.M)
        and not loader_errors_only(before)
    ):
        return
    raise ValueError("unjudged: added test selection has no failing seed control")


def recorded_body(text):
    """Recover an abbreviated stdin check, never the other commands in its tool call."""
    prefix = text.split(" (", 1)[0].strip()
    turns_path = os.environ.get("OB_TURNS")
    candidates = set()
    if turns_path:
        turns = json.loads(Path(turns_path).read_text(encoding="utf-8"))["turns"]
        for turn in turns:
            transcript = Path(turn.get("transcript", ""))
            native = transcript.with_name(
                transcript.name.replace(".transcript.txt", ".native.jsonl")
            )
            if not native.is_file():
                continue
            for line in native.read_text(encoding="utf-8").splitlines():
                item = json.loads(line).get("payload", {}).get("item", {})
                argv = item.get("command", [])
                if not isinstance(argv, list) or "-c" not in argv:
                    continue
                body = argv[argv.index("-c") + 1]
                pattern = (
                    r"(?m)^"
                    + re.escape(prefix)
                    + r"\s*<<\s*['\"]?(\w+)['\"]?\s*\n(.*?)\n\1(?:\n|$)"
                )
                for match in re.finditer(pattern, body, re.S):
                    candidates.add(match[2])
    if len(candidates) > 1:
        label = text.partition("(")[2].rstrip(")").lower()
        label = re.sub(r"\b(?:inline|assertions?|checks?)\b", "", label)
        label = " ".join(label.split())
        candidates = {body for body in candidates if label and body_named(body, label)}
    if len(candidates) != 1:
        raise ValueError("unjudged: abbreviated check has no unique native input body")
    return candidates.pop()


def body_named(body, label):
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
        and any(
            isinstance(arg, ast.Constant)
            and isinstance(arg.value, str)
            and label in " ".join(arg.value.lower().split())
            for arg in node.args
        )
        for node in ast.walk(ast.parse(body))
    )


def passed(result):
    return bool(re.search(r"\bpass(?:ed)?\b", result, re.I)) and not bool(
        re.search(r"\b(?:not|never)\s+pass(?:ed)?\b", result, re.I)
    )


def reports(checks, *, root=Path("."), revision=None):
    credited = []
    calls = []
    for row in checks:
        if not passed(row.get("result", "")):
            continue

        def check(row=row):
            result = report(
                row.get("command", ""), root=root, revision=row.get("revision", revision)
            )
            if result is not None:
                credited.append(result)
            return (
                []
                if result is not False
                else ["reported PASS fails on described content: " + row.get("command", "")]
            )

        calls.append(check)
    return collect(calls), credited


if __name__ == "__main__":
    seal(Path.cwd(), sys.argv[1], release="--release" in sys.argv[2:])
