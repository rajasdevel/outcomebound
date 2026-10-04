"""What a `bounds` entry grants.

Whether an entry grants the whole repository, and whether it covers one
repository-relative path, as pure functions of the text. It reads no block and
reports no message: `tickets_model` and `tickets_check` do both.

A folder may be written with a trailing `/`: `src/` grants what `src` grants.
"""

from __future__ import annotations

import re

__all__ = ["compiles", "covers", "folder", "whole_repository"]

# The glob characters a `bounds` entry may carry, and the one place they are named.
_GLOBS = "*?["


def folder(entry: str) -> str:
    """The entry with a folder's one trailing `/` dropped; `src/` is `src`.

    Only one is dropped, so `src//` keeps an empty segment and the path rules
    refuse it, as they refuse `a//b`.
    """

    return entry[:-1] if entry.endswith("/") else entry


def _literal_prefix(entry: str) -> str:
    """The part of an entry before its first glob character."""

    cuts = [entry.index(character) for character in _GLOBS if character in entry]
    return entry[: min(cuts)] if cuts else entry


def whole_repository(entry: str) -> bool:
    """Whether an entry grants the whole repository: its literal prefix is empty or `.`."""

    return _literal_prefix(folder(entry)) in ("", ".")


def _source(glob: str) -> str:
    """A glob as the source of a regular expression: `**` spans folders, `*` and `?`
    stay in one, and a `[...]` class is kept as written."""

    out, index = [], 0
    while index < len(glob):
        if glob.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
        elif glob.startswith("**", index):
            out.append(".*")
            index += 2
        elif glob[index] == "*":
            out.append("[^/]*")
            index += 1
        elif glob[index] == "?":
            out.append("[^/]")
            index += 1
        elif glob[index] == "[" and "]" in glob[index + 1 :]:
            close = glob.index("]", index + 1)
            out.append(glob[index : close + 1])
            index = close + 1
        else:
            out.append(re.escape(glob[index]))
            index += 1
    return "".join(out) + r"\Z"


def compiles(entry: str) -> bool:
    """Whether every `[...]` class in an entry is one a glob can hold; `src/[]` and
    `src/[^]` are not, and `tickets_model` refuses them as `BOUNDS_INVALID`."""

    try:
        re.compile(_source(folder(entry)))
    except re.error:
        return False
    return True


def _pattern(glob: str) -> re.Pattern[str]:
    """The glob as a regular expression. An entry `compiles` refuses is read as
    literal text here, so that no pass over a refused entry can end the run."""

    try:
        return re.compile(_source(glob))
    except re.error:
        return re.compile(re.escape(glob) + r"\Z")


def _ancestors(path: str) -> list[str]:
    """`path` and every folder above it, nearest last: `a/b/c` gives `a`, `a/b`, `a/b/c`."""

    parts = path.split("/")
    return ["/".join(parts[:count]) for count in range(1, len(parts) + 1)]


def covers(entry: str, path: str) -> bool:
    """Whether `entry` grants `path`, a repository-relative POSIX path or `.`.

    A literal entry grants itself and everything under it. A glob grants each
    path it matches and everything under one, and `<folder>/**` grants the
    folder itself too, so a check that reads all of `src` is inside `src/**`.
    An entry that grants the whole repository covers every path, `.` included.
    """

    if whole_repository(entry):
        return True
    written = folder(entry)
    if path == ".":
        return False
    if written.endswith("/**") and _literal_prefix(written[:-3]) == written[:-3]:
        written = written[:-3]
    if _literal_prefix(written) == written:
        return path == written or path.startswith(written + "/")
    pattern = _pattern(written)
    return any(pattern.match(candidate) for candidate in _ancestors(path))
