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
from itertools import pairwise
from pathlib import Path

HERE = Path(__file__).resolve().parent
READ_ONLY_GIT = {"diff", "show", "status", "log", "rev-parse", "ls-files"}


def excluded(path):
    parts = path.parts
    return bool(
        set(parts)
        & {
            ".git",
            ".remotes",
            ".remote.git",
            ".worktrees",
            "__pycache__",
            ".pytest_cache",
            ".outcomebound-checks",
        }
        or any(
            (parent == ".agents" and child in {"work", "worktrees", "handoffs", "shared-memory"})
            or (parent == ".outcomebound" and child == "research-inbox")
            for parent, child in pairwise(parts)
        )
    )


def copy_tree(root, target, omit):
    """Apply the same exclusions to entry names and link destinations."""
    root = Path(root).resolve()

    def ignore(folder, names):
        skipped = []
        for name in names:
            path = Path(folder) / name
            if omit(path.relative_to(root)):
                skipped.append(name)
            elif path.is_symlink():
                resolved = path.resolve()
                if not resolved.is_relative_to(root):
                    raise ValueError("copy link escapes disposable copy")
                if omit(resolved.relative_to(root)):
                    skipped.append(name)
        return skipped

    shutil.copytree(root, target, dirs_exist_ok=True, symlinks=True, ignore=ignore)
    for path in target.rglob("*"):
        if path.is_symlink() and Path(os.readlink(path)).is_absolute():
            destination = (root / path.relative_to(target)).resolve().relative_to(root)
            path.unlink()
            path.symlink_to(os.path.relpath(target / destination, path.parent))


def overlay_machinery(target):
    sealed = HERE / "seed-checks"
    if sealed.is_dir():
        shutil.copytree(sealed, target, dirs_exist_ok=True)
    elif (HERE / "session.json").is_file():
        raise ValueError("unjudged: sealed seed machinery is unavailable")


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
            copy_tree(root, target, excluded)
        copy_repository(root, target, revision)
        if machinery:
            overlay_machinery(target)
        yield target


def archive_revision(root, target, revision):
    done = subprocess.run(["git", "archive", revision], cwd=root, capture_output=True, check=False)
    if done.returncode:
        raise ValueError("unjudged: described revision is unavailable: " + revision)
    with tarfile.open(fileobj=io.BytesIO(done.stdout)) as archive:
        links = []
        for member in archive:
            if excluded(Path(member.name)):
                continue
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
                path.parent.mkdir(parents=True, exist_ok=True)
                link = Path(member.linkname)
                if link.is_absolute() and link.is_relative_to(root):
                    link = Path(os.path.relpath(target / link.relative_to(root), path.parent))
                path.symlink_to(link)
                links.append(path)
        prune_links(target, links)


def prune_links(target, links):
    # Resolve chains before removing any link, so an alias cannot restore evidence.
    removed = []
    for path in links:
        resolved = path.resolve()
        if not resolved.is_relative_to(target):
            raise ValueError("archive link escapes disposable copy")
        if excluded(resolved.relative_to(target)):
            removed.append(path)
    for path in removed:
        path.unlink()


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
        copy_tree(
            repository.stdout.strip(),
            target / ".git",
            lambda path: bool(set(path.parts) & {"hooks", "worktrees", "ob-receipts"}),
        )
        config = target / ".git/config"
        config.write_text(
            rewrite_path(config.read_text(encoding="utf-8"), root, target),
            encoding="utf-8",
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


def run(root, argv, revision=None, *, input=None, machinery=None):
    root = Path(root).resolve()
    with snapshot(root, revision, machinery=False) as target:
        argv = [rewrite_path(arg, root, target) for arg in argv]
        input = rewrite_path(input, root, target) if input is not None else None
        if machinery is None:
            machinery = any(
                protected_execution(target, call, input=input)
                for call in check_commands(shlex.join(argv))
            )
        if machinery:
            overlay_machinery(target)
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
                argv,
                cwd=target,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
                check=False,
                input=input,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError("unjudged: check could not finish: " + str(error)) from error


def rewrite_path(text, root, target):
    """Redirect native paths, including Python/JSON escaped Windows literals."""
    source = str(root)
    destination = str(target)
    text = text.replace(source.replace("\\", "\\\\"), destination.replace("\\", "\\\\"))
    text = text.replace(source, destination)
    return text.replace(root.as_posix(), target.as_posix())


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
        if len(argv) < 2 or argv[1] not in READ_ONLY_GIT:
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
    for argv in shell_groups(text):
        flags = list(makeflags)
        for word in argv:
            if word.startswith("MAKEFLAGS="):
                flags = word.partition("=")[2].split()
        argv = normalized(argv)
        if not argv:
            continue
        at = shell_body(argv)
        if at is not None:
            if at >= len(argv):
                raise ValueError("unjudged: shell check has no command body")
            result.extend(check_commands(argv[at], flags))
        elif argv[0] == "eval":
            result.extend(check_commands(" ".join(argv[1:]), flags))
        else:
            if Path(argv[0]).name in {"make", "gmake"} and make_modes(flags, environment=True):
                argv.insert(1, "-n")
            result.append(argv)
    return result


def python_entry(argv):
    """The first Python mode or script, after interpreter options."""
    if not argv or not Path(argv[0]).name.startswith(("python", "pypy")):
        return None
    index = 1
    while index < len(argv):
        arg = argv[index]
        if arg in {"-m", "-c", "-"} or not arg.startswith("-"):
            return index
        if arg == "--":
            return index + 1 if index + 1 < len(argv) else None
        index += 2 if arg in {"-W", "-X"} else 1
    return None


def normalized(argv):
    """Unwrap the known observer before runner, make-mode or view qualification."""
    launch = runpy.run_path(str(HERE / "commands.py"))["_program"]
    argv = list(launch(argv))
    while argv:
        at = python_entry(argv)
        if (
            at is None
            or Path(argv[at]).parts[-2:] != ("tools", "ob_receipts.py")
            or argv[at + 1 : at + 2] != ["observe"]
        ):
            break
        argv = list(launch(argv[at + 2 :]))
    return argv


def protected_path(root, path):
    path = (root / path).resolve()
    if not path.is_relative_to(root):
        return False
    path = path.relative_to(root)
    return bool(
        path.parts
        and (
            path.parts[0] == "tests"
            or path.as_posix() == "Makefile"
            or (HERE / "seed-checks" / path).is_file()
        )
    )


def protected_execution(root, argv, *, input=None, seen=()):
    """Choose a view before replay: protect executed machinery, not files read as data."""
    runner = check_runner(argv)
    if runner in {"unittest", "pytest", "make", "gmake"}:
        return True
    at = python_entry(argv)
    if at is not None:
        return python_execution(root, argv[at:], input, seen)
    entry = argv[0]
    shell = entry in {".", "source"} or Path(entry).name in {"sh", "bash", "zsh", "dash"}
    if shell:
        # Shell -c launchers are already expanded by check_commands; this is a script file.
        entry = next((arg for arg in argv[1:] if not arg.startswith("-")), "")
    path = root / entry
    if protected_path(root, path):
        return True
    if path.is_relative_to(root) and path.is_file():
        source = path.read_text(encoding="utf-8")
        if source.startswith("#!") and "python" in source.splitlines()[0]:
            return python_machinery(root, source, seen)
        if shell or (
            source.startswith("#!") and re.search(r"\b(?:sh|bash|zsh)\b", source.splitlines()[0])
        ):
            if path in seen:
                raise ValueError("unjudged: recursive reported script")
            return any(
                protected_execution(root, call, seen=(*seen, path))
                for call in check_commands(source)
            )
    return False


def python_execution(root, args, input, seen):
    entry = args[0]
    if entry == "-c":
        return python_machinery(root, args[1] if len(args) > 1 else "", seen)
    if entry == "-":
        return python_machinery(root, input or "", seen)
    if entry == "-m":
        module = (args[1] if len(args) > 1 else "").replace(".", "/")
        path = root / (module + ".py")
        if not path.is_file():
            path = root / module / "__main__.py"
        if not path.is_file():
            return False  # No local module to replace with sealed machinery.
    else:
        path = root / entry
    if protected_path(root, path):
        return True
    if not path.is_file():
        return False  # Replay retains the interpreter's missing-script failure.
    if path in seen:
        raise ValueError("unjudged: reported script execution cannot be resolved")
    return python_machinery(root, path.read_text(encoding="utf-8"), (*seen, path))


def python_imports(tree):
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name] = item.name
        elif isinstance(node, ast.ImportFrom):
            for item in node.names:
                aliases[item.asname or item.name] = (node.module or "") + "." + item.name
    return aliases


def python_machinery(root, source, seen):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False  # Replay reports the syntax failure on the described content.
    aliases = python_imports(tree)
    if any(
        module.split(".")[0] in {"unittest", "pytest"}
        or protected_path(root, module.replace(".", "/") + ".py")
        for module in aliases.values()
    ):
        return True

    def name(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return name(node.value) + "." + node.attr
        return ""

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = name(node.func)
        if python_call(root, called, node, seen):
            return True
    return False


def python_call(root, called, node, seen):
    # Dynamic loading executes code, unlike reading or hashing its bytes.
    if called.startswith(("unittest.", "pytest.")):
        return True
    if called.removeprefix("builtins.") in {"exec", "eval", "compile"}:
        return dynamic_python(root, node, seen)
    if called in {
        "__import__",
        "builtins.__import__",
        "importlib.import_module",
        "importlib.util.spec_from_file_location",
    } or called.endswith((".exec_module", ".load_module")):
        raise ValueError("unjudged: reported Python dynamic import cannot be resolved")
    return python_child(root, called, node, seen)


def dynamic_python(root, node, seen):
    """Resolve literal source and file-backed exec without replacing bytes read as data."""
    if not node.args:
        raise ValueError("unjudged: reported Python dynamic source is unavailable")
    source = node.args[0]
    try:
        literal = ast.literal_eval(source)
    except (ValueError, TypeError):
        literal = None
    if isinstance(literal, str):
        return python_machinery(root, literal, seen)
    # exec(Path('tools/check.py').read_text()) is execution of that protected file;
    # the same wrapper around a content inspector must retain the described files.
    if isinstance(source, ast.Call) and isinstance(source.func, ast.Attribute):
        reader = source.func
        if reader.attr in {"read_text", "read_bytes", "read"}:
            path_call = reader.value
            if isinstance(path_call, ast.Call) and path_call.args:
                try:
                    path = ast.literal_eval(path_call.args[0])
                except (ValueError, TypeError):
                    path = None
                if isinstance(path, str):
                    return python_execution(root, [path], None, seen)
    raise ValueError("unjudged: reported Python dynamic source cannot be resolved")


def python_child(root, called, node, seen):
    process = called.startswith(("subprocess.", "os.", "asyncio.")) and called.rsplit(".", 1)[
        -1
    ] in {
        "run",
        "call",
        "check_call",
        "check_output",
        "Popen",
        "system",
        "popen",
        "execv",
        "execve",
        "execl",
        "spawnv",
        "create_subprocess_exec",
        "create_subprocess_shell",
    }
    if not process and called not in {"runpy.run_path", "runpy.run_module"}:
        return False
    argument = (
        node.args[0]
        if node.args
        else next(
            (item.value for item in node.keywords if item.arg in {"args", "path_name", "mod_name"}),
            None,
        )
    )
    if argument is None:
        raise ValueError("unjudged: reported Python child command has no argument")
    if process and read_only_git_prefix(argument):
        return False
    try:
        child = ast.literal_eval(argument)
    except (ValueError, TypeError):
        if process:
            # Unresolved execution retains the sealed view. A known read-only Git
            # prefix above needs the delivery, even with computed revision/path operands.
            return True
        raise ValueError("unjudged: reported Python child command cannot be resolved") from None
    if called.startswith("runpy."):
        args = ["-m", child] if called == "runpy.run_module" else [child]
        return python_execution(root, args, None, seen)
    calls = check_commands(child if isinstance(child, str) else shlex.join(child))
    return any(protected_execution(root, call, seen=seen) for call in calls)


def read_only_git_prefix(argument):
    if not isinstance(argument, (ast.List, ast.Tuple)):
        return False
    prefix = []
    for item in argument.elts:
        try:
            word = ast.literal_eval(item)
        except (ValueError, TypeError):
            break
        if not isinstance(word, str):
            break
        prefix.append(word)
    prefix = normalized(prefix)
    return len(prefix) >= 2 and Path(prefix[0]).name == "git" and prefix[1] in READ_ONLY_GIT


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
    argv = normalized(argv)
    if not argv:
        return ""
    at = python_entry(argv)
    if at is not None:
        return argv[at + 1] if argv[at] == "-m" and at + 1 < len(argv) else ""
    if Path(argv[0]).name.startswith(("python", "pypy")):
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
