"""The one safe file writer every engine route writes a target through.

`write` holds three properties: no symlink anywhere on a destination's path, every
write staged with O_EXCL, fsynced and renamed over its destination, and a refusal
whenever a destination's bytes are not the bytes its caller read. Nothing here
recovers an interrupted run; the target's Git history is the undo.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from pathlib import Path

from outcomebound_tools import paths

STAGE_SUFFIX = ".outcomebound-stage"
NEW_FILE_MODE = 0o644


class WriteError(ValueError):
    """A destination `write` will not touch. Every destination is checked first."""


def destination(root: Path, relative: str) -> Path:
    """``root``/``relative``, refused when the path is unbounded or crosses a symlink."""

    try:
        return paths.resolve_bounded(root, relative)
    except paths.PathError as error:
        raise WriteError(str(error)) from error


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
    for relative in changes:
        _unchanged(root, relative, expected)
    for relative, content in changes.items():
        _unchanged(root, relative, expected)
        path = destination(root, relative)
        if content is None:
            path.unlink(missing_ok=True)
            _prune(root, path.parent)
        else:
            _replace(path, content)


def _unchanged(root: Path, relative: str, expected: Mapping[str, bytes | None]) -> None:
    if relative not in expected:
        raise WriteError(f"{relative} was not read before it was planned; plan it again")
    if current(root, relative) != expected[relative]:
        raise WriteError(f"{relative} changed after it was read; nothing more was written")


def _replace(path: Path, content: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else NEW_FILE_MODE
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = path.with_name(path.name + STAGE_SUFFIX)
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
        os.replace(stage, path)
    finally:
        stage.unlink(missing_ok=True)


def _prune(root: Path, directory: Path) -> None:
    while root in directory.parents:
        try:
            directory.rmdir()
        except OSError:
            return
        directory = directory.parent
