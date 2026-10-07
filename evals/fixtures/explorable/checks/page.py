#!/usr/bin/env python3
"""Read the interactive pages a run built: exit 0 where the named reading holds, and 1 saying
why it does not. Lines starting `observed:` describe the rest and never change the exit status.

  check   there is a built page, and the engine's own check (without a browser) passes on each
  expect  each built page's content calls `explorable.expect` at least once
  own     no built page holds a starter's content unchanged
  one     there is exactly one built page
  named   the answer, the file OUTCOMEBOUND_EVAL_ANSWER names, holds each built page's file name

A built page is a `.html` file, anywhere in the workspace but `.git`, whose generator line names
the engine. The engine is imported from PYTHONPATH, as the runner sets it.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import sys
from pathlib import Path

GENERATOR = re.compile(r'<meta name="generator" content="outcomebound explorable [^"]*">')
EXPECT = re.compile(r"\bexplorable\s*\.\s*expect\s*\(")
NO_PAGE = "no page the engine built is in the workspace"


def pages(root: Path) -> list[Path]:
    """Each built page under `root`, in path order; links are not followed."""

    found: list[Path] = []
    for folder, folders, files in os.walk(root):
        folders[:] = sorted(name for name in folders if name != ".git")
        for name in sorted(files):
            path = Path(folder) / name
            if not name.endswith(".html") or path.is_symlink():
                continue
            try:
                head = path.read_text(encoding="utf-8", errors="replace")[:4096]
            except OSError:
                continue
            if GENERATOR.search(head):
                found.append(path)
    return found


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _content(path: Path) -> str | None:
    from outcomebound_tools import explorable_shell

    parts = explorable_shell.match(path.read_text(encoding="utf-8", errors="replace"))
    return None if parts is None else parts.content


def check(root: Path) -> list[str]:
    from outcomebound_tools import explorable

    found = pages(root)
    problems = [] if found else [NO_PAGE]
    for page in found:
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed):
            code = explorable.main(["check", _relative(page, root)])
        lines = printed.getvalue().splitlines()
        print(f"observed: {_relative(page, root)}: {lines[0] if lines else 'no output'}")
        if code != 0:
            problems.append(f"{_relative(page, root)}: the engine's check exits {code}")
            problems += [f"  {line}" for line in lines[1:] if "FAIL" in line]
    return problems


def expect(root: Path) -> list[str]:
    found = pages(root)
    problems = [] if found else [NO_PAGE]
    for page in found:
        content = _content(page)
        if content is None:
            problems.append(f"{_relative(page, root)}: not the engine's shell, so no content")
            continue
        count = len(EXPECT.findall(content))
        print(f"observed: {_relative(page, root)}: {count} expectation call(s)")
        if not count:
            problems.append(f"{_relative(page, root)}: its content calls explorable.expect nowhere")
    return problems


def _normal(text: str) -> str:
    return " ".join(text.split())


def own(root: Path) -> list[str]:
    from outcomebound_tools import explorable_shell, explorable_source

    found = pages(root)
    problems = [] if found else [NO_PAGE]
    starters = {
        kind: _normal(
            explorable_source.parse_source(
                explorable_shell.template(f"starters/{kind}.source.html")
            ).content
        )
        for kind in explorable_source.KINDS
    }
    for page in found:
        content = _content(page)
        if content is None:
            problems.append(f"{_relative(page, root)}: not the engine's shell, so no content")
            continue
        for kind, text in starters.items():
            if _normal(content) == text:
                problems.append(f"{_relative(page, root)}: the {kind} starter, unchanged")
    return problems


def one(root: Path) -> list[str]:
    found = pages(root)
    for page in found:
        print(f"observed: built page {_relative(page, root)}")
    return [] if len(found) == 1 else [f"{len(found)} built pages, not one"]


def named(root: Path) -> list[str]:
    found = pages(root)
    if not found:
        return [NO_PAGE]
    source = os.environ.get("OUTCOMEBOUND_EVAL_ANSWER", "")
    try:
        answer = Path(source).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ["no answer was supplied"]
    return [
        f"the answer does not name {_relative(page, root)}"
        for page in found
        if page.name not in answer
    ]


READINGS = {"check": check, "expect": expect, "own": own, "one": one, "named": named}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in READINGS:
        print(f"usage: page.py {{{','.join(READINGS)}}}")
        return 2
    problems = READINGS[argv[0]](Path.cwd())
    for line in problems:
        print(line)
    if not problems:
        print("holds")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
