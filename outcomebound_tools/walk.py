"""One walk of a target's folders for the engine's readers.

What this module decides: how a reader goes through the folders under a target. It never
enters `.git`, a folder that holds its own `.git` (a nested repository, a worktree or a
submodule), a link, or a folder the caller names to skip, such as what Git ignores. It never
raises on an entry it cannot read: a folder it cannot list is not entered, and goes into the
caller's `unreadable` list where the caller gives one, so that the caller reports it or skips
it. The test for a nested repository is `os.path.lexists`, which reads a folder it cannot
enter as holding no `.git`; `Path.exists` raises there on Python 3.10 to 3.13.

What it does not decide: which files a reader opens, or what a reader says about a folder it
could not list. `tests/test_walk.py` holds each `os.walk` in the package to an allow-list, so
that a new walk is this one or a deliberate change to that list.
"""

from __future__ import annotations

import os
from collections.abc import Collection, Iterator
from pathlib import Path
from typing import NamedTuple

__all__ = ["Folder", "folders"]


class Folder(NamedTuple):
    """One folder the walk entered."""

    path: Path
    # The folder's path from the walk's root, `.` for the root itself.
    relative: str
    # The names, sorted, of what is not a folder: files, links to files, broken links.
    files: list[str]
    # The names, sorted, of the links to folders, which the walk does not enter.
    links: list[str]


def folders(
    root: Path, skip: Collection[str] = (), unreadable: list[Path] | None = None
) -> Iterator[Folder]:
    """Each folder under `root`, `root` first, top down and in name order. `skip` holds
    root-relative folder paths not to enter; each folder that cannot be listed is appended to
    `unreadable` where it is given."""

    def failed(error: OSError) -> None:
        if unreadable is not None and error.filename is not None:
            unreadable.append(Path(os.fsdecode(error.filename)))

    for directory, dirnames, filenames in os.walk(root, onerror=failed):
        here = Path(directory)
        relative = here.relative_to(root).as_posix()
        links = sorted(name for name in dirnames if os.path.islink(here / name))
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in links
            and name != ".git"
            and not os.path.lexists(here / name / ".git")
            and (name if relative == "." else f"{relative}/{name}") not in skip
        )
        yield Folder(here, relative, sorted(filenames), links)
