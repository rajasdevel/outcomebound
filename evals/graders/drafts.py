#!/usr/bin/env python3
"""Find the ticket drafts written since the seed, and judge them with the engine.

    drafts.py lint              `tickets check --draft`, given every draft, reads PASS
    drafts.py count MIN MAX     there are at least MIN drafts and at most MAX
    drafts.py bounds            each draft names bounds, and each entry names a path the seed
                                commit holds

A draft is a file added or changed since the seed, outside `.git`, that carries a ticket
block. The engine is the OutcomeBound checkout on PYTHONPATH, never a program found on PATH.
The seed is the commit OUTCOMEBOUND_SEED_SHA names, else the `seed` tag. Each exits 0 where
it holds and 1 naming what does not; lines starting `observed:` never change the exit status.
"""

from __future__ import annotations

import contextlib
import fnmatch
import io
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

# The engine comes from PYTHONPATH; nothing beside this file may stand in for it.
_HERE = Path(__file__).resolve().parent
sys.path[:] = [entry for entry in sys.path if entry and Path(entry).resolve() != _HERE]

BLOCK = "<!-- outcomebound:begin id=ticket"


def _git(*arguments: str) -> bytes:
    done = subprocess.run(["git", *arguments], capture_output=True, timeout=60)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {done.stderr.decode(errors='replace')}")
    return done.stdout


def _seed() -> str:
    seed = os.environ.get("OUTCOMEBOUND_SEED_SHA", "")
    return seed or _git("rev-parse", "--verify", "refs/tags/seed^{commit}").decode().strip()


def drafts() -> list[Path]:
    """Every file added or changed since the seed that carries a ticket block, sorted."""

    listed = _git("ls-files", "--others", "-z") + _git("diff", "--name-only", "-z", _seed())
    found = set()
    for raw in listed.split(b"\0"):
        path = Path(os.fsdecode(raw)) if raw else None
        if path is None or path.is_symlink() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if BLOCK in text:
            found.add(path)
    return sorted(found)


def lint() -> list[str]:
    found = drafts()
    if not found:
        return ["no draft was written"]
    from outcomebound_tools import tickets

    printed = io.StringIO()
    with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed):
        code = tickets.main(
            [
                "check",
                str(Path.cwd()),
                "--draft",
                *(str(path.resolve()) for path in found),
                "--json",
            ]
        )
    try:
        report = json.loads(printed.getvalue())
    except ValueError:
        return [f"the lint refused the drafts: {printed.getvalue().strip()[:600]}"]
    for ticket in report.get("tickets", []):
        for item in ticket.get("messages", []):
            print(f"observed: {item['level']} {ticket['id']} {item['code']}")
    if code != 0 or report.get("result") != "PASS":
        failing = [
            f"{ticket['id']} {item['code']}"
            for ticket in report.get("tickets", [])
            for item in ticket.get("messages", [])
            if item["level"] == "ERROR"
        ]
        return [f"the lint reads {report.get('result')}: {', '.join(failing) or 'no ticket error'}"]
    return []


def count(least: int, most: int) -> list[str]:
    found = drafts()
    print(f"observed: {len(found)} draft(s): {', '.join(path.as_posix() for path in found)}")
    if not least <= len(found) <= most:
        return [f"{len(found)} draft(s), where {least} to {most} are allowed"]
    return []


def _seed_paths() -> set[str]:
    files = [raw for raw in _git("ls-tree", "-r", "--name-only", "-z", _seed()).split(b"\0") if raw]
    held = set()
    for raw in files:
        path = PurePosixPath(os.fsdecode(raw))
        held.add(path.as_posix())
        held.update(parent.as_posix() for parent in path.parents if parent.as_posix() != ".")
    return held


def _exists(entry: str, held: set[str]) -> bool:
    from outcomebound_tools.tickets_bounds import whole_repository

    name = entry.strip().rstrip("/").removeprefix("./")
    if whole_repository(name) or name in held:
        return True
    return any(mark in name for mark in "*?[") and any(
        fnmatch.fnmatchcase(path, name) for path in held
    )


def bounds() -> list[str]:
    found = drafts()
    if not found:
        return ["no draft was written"]
    from outcomebound_tools.tickets_model import parse_block

    held = _seed_paths()
    lacking = []
    for path in found:
        fields, _messages = parse_block(path.read_text(encoding="utf-8", errors="replace"))
        print(f"observed: {path.as_posix()} bounds {list(fields.bounds)}")
        if not fields.bounds:
            lacking.append(f"{path.as_posix()} names no bounds")
        lacking += [
            f"{path.as_posix()} names {entry!r}, which the seed does not hold"
            for entry in fields.bounds
            if not _exists(entry, held)
        ]
    return lacking


def _main(argv: list[str]) -> int:
    try:
        if argv == ["lint"]:
            lacking = lint()
        elif len(argv) == 3 and argv[0] == "count":
            lacking = count(int(argv[1]), int(argv[2]))
        elif argv == ["bounds"]:
            lacking = bounds()
        else:
            print("usage: drafts.py {lint | count MIN MAX | bounds}")
            return 2
    except ImportError as problem:
        lacking = [f"the engine is not importable from PYTHONPATH: {problem}"]
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as problem:
        lacking = [f"the check could not run: {problem}"]
    for reason in lacking:
        print(reason)
    return 1 if lacking else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
