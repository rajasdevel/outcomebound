#!/usr/bin/env python3
"""Every file and line a text cites, as `path:line`, `path:line-line` or `path#Lline`,
exists in this tree: the file is here and holds that line.

The text is the file named on the command line, or the one OUTCOMEBOUND_EVAL_ANSWER
names. A path under an absolute workspace directory is read relative to this one. A
text citing nothing passes: there is no citation to be wrong.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

CITATION = re.compile(
    r"(?P<path>(?:[\w.@~+-]*/)*[\w.@~+-]*\w\.[A-Za-z0-9]+)"
    r"(?::(?P<line>\d+)(?:-(?P<end>\d+))?|#L(?P<lline>\d+)(?:-L?(?P<lend>\d+))?)"
)
WORKSPACE = re.compile(r"^.*/ob-fixture-[^/]+/")


def _relative(path: str, root: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate
    try:
        return candidate.relative_to(root)
    except ValueError:
        return Path(WORKSPACE.sub("", path))


def problems(text: str, root: Path) -> tuple[int, list[str]]:
    found = 0
    wrong = []
    for match in CITATION.finditer(text):
        if match.start() and text[match.start() - 1] == ":":
            continue
        found += 1
        first = int(match.group("line") or match.group("lline"))
        last = int(match.group("end") or match.group("lend") or first)
        relative = _relative(match.group("path"), root)
        target = root / relative
        if relative.is_absolute() or not target.is_file():
            wrong.append(f"{match.group(0)}: no such file here")
            continue
        count = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
        if not 1 <= first <= last <= count:
            wrong.append(f"{match.group(0)}: {relative} has {count} lines")
    return found, wrong


def _main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    source = arguments[0] if arguments else os.environ.get("OUTCOMEBOUND_EVAL_ANSWER", "")
    try:
        text = Path(source).read_text(encoding="utf-8", errors="replace")
    except OSError:
        print("no text was supplied to read citations from")
        return 1
    found, wrong = problems(text, Path.cwd().resolve())
    for line in wrong:
        print(line)
    if wrong:
        return 1
    print(f"{found} citation(s), each naming a file and line this tree holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
