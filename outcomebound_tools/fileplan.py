"""The one safe file writer every engine route writes a target through.

`write` holds three properties: no symlink anywhere on a destination's path (on Windows, no
junction either, and no name Windows cannot hold), every write staged with O_EXCL, fsynced and
renamed over its destination, and a refusal whenever a destination's bytes are not the bytes its
caller read. Every destination is checked before the first write, and again just before its own
rename. That is a recheck, not a compare-and-swap: an edit that lands in the instant between the
last check and the rename is still overwritten, and no lock closes that window. A destination the
caller read as absent is created exclusively instead (a hard link of the stage, or an open with
O_EXCL where the file system holds no link), so a file that appears in that instant is refused,
never overwritten. A staging file left
by an earlier run is refused before the first write and is never removed. Nothing here recovers an
interrupted run, and a failure after the first write does not roll the earlier writes back; the
target's Git history is the undo.
"""

from __future__ import annotations

import os
import stat
import time
from collections.abc import Callable, Mapping
from pathlib import Path

from outcomebound_tools import paths

STAGE_SUFFIX = ".outcomebound-stage"
NEW_FILE_MODE = 0o644
# On Windows a rename onto a file that another process has open fails until it lets go.
REPLACE_TRIES = 5
REPLACE_WAIT = 0.1


class WriteError(ValueError):
    """A destination `write` will not touch. Every destination is checked first."""


def destination(root: Path, relative: str) -> Path:
    """``root``/``relative``, refused when the path is unbounded or crosses a symlink."""

    try:
        resolved = paths.resolve_bounded(root, relative)
    except paths.PathError as error:
        raise WriteError(str(error)) from error
    unwritable = paths.windows_refusal(relative)
    if unwritable is not None:
        raise WriteError(f"{relative}: {unwritable}")
    return resolved


def current(root: Path, relative: str) -> bytes | None:
    """The bytes at ``relative`` under ``root``, or None when nothing is there."""

    path = destination(root, relative)
    if not path.exists():
        return None
    if not path.is_file():
        raise WriteError(f"not a regular file: {relative}")
    return path.read_bytes()


def write(
    root: Path, changes: Mapping[str, bytes | None], expected: Mapping[str, bytes | None]
) -> None:
    """Apply ``changes`` under ``root`` in their order: bytes are written, None deletes.

    ``expected`` holds each destination's bytes as the caller read them, None for
    absent. Every destination is checked before the first write and again just
    before its own. A deletion also removes the directories it leaves empty, up to
    ``root``; a write keeps an existing file's mode and gives a new one 0o644.
    """

    root = Path(root)
    for relative, content in changes.items():
        _unchanged(root, relative, expected)
        if content is not None:
            _no_stage_in_the_way(destination(root, relative))
    for relative, content in changes.items():
        _unchanged(root, relative, expected)
        path = destination(root, relative)
        if content is None:
            path.unlink(missing_ok=True)
            _prune(root, path.parent)
        else:

            def recheck(relative: str = relative) -> None:
                _unchanged(root, relative, expected)

            _replace(path, content, recheck, create=expected[relative] is None)


def _stage_of(path: Path) -> Path:
    return path.with_name(path.name + STAGE_SUFFIX)


def _no_stage_in_the_way(path: Path) -> None:
    """Refuse before the first write when a staging file, left by an earlier run, stands where
    a later destination's stage would go. It is never removed here: it is not this run's."""

    stage = _stage_of(path)
    if os.path.lexists(stage):
        raise WriteError(f"a staging file is in the way: {stage}; inspect it, then remove it")


def _unchanged(root: Path, relative: str, expected: Mapping[str, bytes | None]) -> None:
    if relative not in expected:
        raise WriteError(f"{relative} was not read before it was planned; plan it again")
    if current(root, relative) != expected[relative]:
        raise WriteError(f"{relative} changed after it was read; nothing more was written")


def _replace(
    path: Path, content: bytes, recheck: Callable[[], None], *, create: bool = False
) -> None:
    """Stage `content` beside `path`, recheck, then move it in: over the destination, or, with
    `create`, only where nothing is there."""

    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else NEW_FILE_MODE
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = _stage_of(path)
    try:
        descriptor = os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise WriteError(
            f"a staging file is in the way: {stage}; inspect it, then remove it"
        ) from error
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(stage, mode)
        recheck()
        if create:
            _create(stage, path, content)
        else:
            _move(stage, path)
    finally:
        stage.unlink(missing_ok=True)


def _create(stage: Path, path: Path, content: bytes) -> None:
    """Make `path` from the stage only where nothing is there: a hard link, which fails on an
    existing path, or, on a file system that holds no hard link, an exclusive open."""

    try:
        os.link(stage, path)
        return
    except FileExistsError as error:
        raise WriteError(
            f"{path.name} appeared after it was read; nothing more was written"
        ) from error
    except OSError:
        pass
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, NEW_FILE_MODE)
    except FileExistsError as error:
        raise WriteError(
            f"{path.name} appeared after it was read; nothing more was written"
        ) from error
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _move(stage: Path, path: Path) -> None:
    """Rename the staged file over its destination. On Windows a scanner or an editor that has the
    destination open, or just closed the stage, makes the rename fail for a moment, so it is tried
    a few times before the refusal; a read-only destination fails every time."""

    for _ in range(REPLACE_TRIES - 1 if paths.on_windows() else 0):
        if _replaced(stage, path):
            return
        time.sleep(REPLACE_WAIT)
    os.replace(stage, path)


def _replaced(stage: Path, path: Path) -> bool:
    try:
        os.replace(stage, path)
    except PermissionError:
        return False
    return True


def _prune(root: Path, directory: Path) -> None:
    while root in directory.parents:
        try:
            directory.rmdir()
        except OSError:
            return
        directory = directory.parent
