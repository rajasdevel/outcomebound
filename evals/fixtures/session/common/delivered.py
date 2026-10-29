"""Re-execute checks in disposable copies of the content a claim describes."""

from __future__ import annotations

import io
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def snapshot(root=Path("."), revision=None):
    root = Path(root).resolve()
    with tempfile.TemporaryDirectory(prefix="session-check-") as folder:
        target = Path(folder).resolve() / "project"
        target.mkdir()
        if revision:
            done = subprocess.run(
                ["git", "archive", revision], cwd=root, capture_output=True, check=False
            )
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
        yield target


def run(root, argv, revision=None):
    with snapshot(root, revision) as target:
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


def check_program(value):
    name = Path(value).name
    return name in {"env", "uv", "make", "gmake", "pytest"} or (
        name.startswith(("python", "pypy"))
        or value.startswith(("tools/", "scripts/", "gates/", "tests/"))
    )


def command(text):
    try:
        argv = shlex.split(text)
    except ValueError as error:
        raise ValueError("unjudged: invalid reported check") from error
    # These are drawn command fields, not a reconstruction of tool actions.
    if not argv:
        return None
    if not check_program(argv[0]):
        return None
    if any(a.rstrip(";") in {"-h", "--help"} for a in argv):
        return None
    if any(word in {";", "&&", "||", "|", ">", "<"} for word in argv):
        raise ValueError("unjudged: reported check needs an explicit argv: " + text)
    return executable(argv)


def executable(argv):
    name = Path(argv[0]).name
    if name.startswith(("python", "pypy")):
        argv[0] = sys.executable
        if "-" in argv[1:] or any(arg.startswith("<<") for arg in argv[1:]):
            raise ValueError("unjudged: reported Python input is not in the command field")
        return argv
    return argv


def report(text, *, root=Path("."), revision=None):
    argv = command(text)
    if argv is None:
        return None
    # Dry-run, touch and question modes do not test a reported passing target.
    if Path(argv[0]).name in {"make", "gmake"} and any(
        a in {"-n", "-q", "-t", "--dry-run", "--just-print", "--recon", "--question", "--touch"}
        for a in argv[1:]
    ):
        return False
    done = run(root, argv, revision)
    if ("unittest" in argv or "pytest" in argv) and re.search(
        r"Ran 0 tests|no tests ran", done.stdout + done.stderr
    ):
        return False
    return done.returncode == 0


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
            credited.append(result)
            return (
                []
                if result is not False
                else ["reported PASS fails on described content: " + row.get("command", "")]
            )

        calls.append(check)
    return collect(calls), credited
