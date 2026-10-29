"""Read completed check receipts and local ref effects, independent of command spelling."""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import tarfile
from datetime import datetime
from functools import lru_cache
from pathlib import Path


def read(root=Path(".")):
    root = Path(root).resolve()
    done = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if done.returncode:
        return []
    folder = root / done.stdout.strip() / "ob-receipts"
    rows = [
        json.loads(line)
        for path in sorted(folder.glob("*.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    return sorted(rows, key=lambda row: row["ended_at"])


def before(rows, turn):
    end = turn.get("ended_at")
    if not end:
        raise ValueError("turn has no finish time for receipt evidence")
    return [
        row
        for row in rows
        if datetime.fromisoformat(row["ended_at"].replace("Z", "+00:00"))
        <= datetime.fromisoformat(end.replace("Z", "+00:00"))
    ]


def tree(root, revision):
    done = subprocess.run(
        ["git", "rev-parse", revision + "^{tree}"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return archived_tree(root, done.stdout.strip()) if done.returncode == 0 else {}


@lru_cache(maxsize=32)
def archived_tree(root, revision):
    done = subprocess.run(["git", "archive", revision], cwd=root, capture_output=True, check=False)
    if done.returncode:
        return {}
    with tarfile.open(fileobj=io.BytesIO(done.stdout)) as archive:
        return {
            member.name: hashlib.sha256(source.read()).hexdigest()
            for member in archive
            if member.isfile() and (source := archive.extractfile(member)) is not None
        }


def recorded(row):
    inputs = row.get("inputs")
    return bool(inputs) and (
        row.get("digest") == hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        and all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in inputs)
    )


def content(row, root=Path("."), revision=None):
    if not recorded(row):
        return False
    inputs = row["inputs"]
    expected = tree(root.resolve(), revision) if revision else {}
    if row.get("kind") == "process" and revision and set(inputs) != set(expected):
        return False
    for name, digest in inputs.items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            return False
        if revision:
            if expected.get(name) != digest:
                return False
            continue
        try:
            data = (root / path).read_bytes()
        except OSError:
            return False
        if hashlib.sha256(data).hexdigest() != digest:
            return False
    return True


def current(rows, root=Path("."), revision=None):
    return [row for row in rows if content(row, root, revision)]


def same_files(root, revision, prefixes):
    expected = {
        name: digest
        for name, digest in tree(root.resolve(), revision).items()
        if name.startswith(prefixes)
    }
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        text=True,
    ).split("\0")
    actual = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in names
        if name.startswith(prefixes) and (root / name).is_file()
    }
    return actual == expected


def slow(rows):
    return any(
        (
            row["kind"] == "check"
            and (
                row["name"].startswith("tests/integration/")
                or "integration" in Path(row["name"]).name
            )
        )
        or (
            row["kind"] == "process"
            and re.search(
                r"(?m)^integration: (?:all stages ok|\w+ ok \([\d.]+s\)|\d+ of \d+ passed)",
                str(row.get("output", "")),
            )
        )
        for row in rows
    )


def descendant_gaps(rows):
    """The frozen observer suppresses every child receipt, including ref hooks."""
    return [
        "unjudged: observed process suppresses descendant receipts: "
        + json.dumps(row.get("argv", []))
        for row in rows
        if row.get("kind") == "process"
    ]


def slow_problems(rows, label):
    return [label] if slow(rows) else descendant_gaps(rows)


def invocation(row):
    if row.get("kind") == "process":
        return row.get("argv", [])
    # Legacy unit rows omitted the interpreter and its options. They cannot prove
    # an exact process invocation, even where the runner selection is available.
    return []


def arguments(argv):
    return list(argv)


def runner(argv):
    if argv and Path(argv[0]).name.startswith(("python", "pypy")):
        args = iter(argv[1:])
        for arg in args:
            if arg == "-m":
                return next(args, "")
            if arg in {"-W", "-X"}:
                next(args, None)
            elif arg == "-c" or not arg.startswith("-") or arg == "-":
                return ""
        return ""
    return Path(argv[0]).name if argv else ""


def observed_failure(rows, argv, *, root=Path("."), revision=None):
    candidates = [
        row
        for row in current(rows, root, revision)
        if arguments(invocation(row)) == arguments(argv)
    ]
    if not candidates:
        raise ValueError("unjudged: no content-bound observation of the exact baseline invocation")
    if not isinstance(candidates[-1].get("exit_code"), int):
        raise ValueError("unjudged: baseline process exit was not observed")
    row = candidates[-1]
    if row["exit_code"] and not (row.get("failures", 0) or test_error(row)):
        raise ValueError("unjudged: baseline did not observe the named test failure")
    return row["exit_code"] != 0


def test_error(row):
    """An error raised inside a test, which fails it as an assertion does; never a loader or
    startup error, which ran no test."""

    output = str(row.get("output", ""))
    return (
        row.get("errors", 0) > 0
        and row.get("tests", 0) > 0
        and "unittest.loader._FailedTest" not in output
        and "Failed to import test module" not in output
    )


def checked_before(rows, root, revision):
    return any(
        credited(row)
        and content(row, root, revision)
        and (row.get("tests", 0) > 0 if row["kind"] == "process" else bool(row.get("modules")))
        and runner(invocation(row)) in {"unittest", "pytest"}
        for row in rows
    )


def credited(row):
    return row.get("exit_code") == 0 and (row.get("kind") != "make" or row.get("executed") is True)


def commits(root=Path(".")):
    done = subprocess.run(
        ["git", "log", "--format=%H %cI", "seed..HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return [line.split() for line in done.stdout.splitlines()] if not done.returncode else []


def at_turn(rows, turn, root=Path(".")):
    # Ref transactions retain subsecond execution times when Git's commit dates tie.
    prior = before(rows, turn)
    refs = [
        row
        for row in prior
        if row["kind"] == "ref" and not row.get("remote") and row["name"].startswith("refs/heads/")
    ]
    return refs[-1]["new"] if refs else "seed"


def interval(rows, start, end):
    def instant(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    return [
        row
        for row in rows
        if row["kind"] != "ref"
        and instant(row["started_at"]) >= instant(start)
        and (not end or instant(row["ended_at"]) <= instant(end))
    ]


def check(rows, argv, *, root=Path("."), revision=None):
    """Compatibility for shared brief callers: re-execute, never infer from receipts."""
    import importlib.util
    import shlex

    spec = importlib.util.spec_from_file_location(
        "delivered", Path(__file__).with_name("delivered.py")
    )
    if spec is None or spec.loader is None:
        raise ValueError("missing delivered-state checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.report(shlex.join(argv), root=root, revision=revision)
