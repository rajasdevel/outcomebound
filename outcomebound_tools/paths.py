"""One path grammar for every writer and reader.

``admits`` and ``bounded_relative`` say whether a string is a path this engine may
write or read inside a target; ``resolve_bounded`` and ``read_bounded`` reach it
without crossing a symlink. They refuse with this module's own ``PathError``.

Standard library only, and no OutcomeBound import: every writer is downstream of
this module, so it can afford no dependency of its own.
"""

from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path, PurePosixPath

# The path grammar. A segment equal to any of these is refused wherever it
# appears, which is what forbids a leading, trailing or doubled separator.
FORBIDDEN_SEGMENTS = frozenset({"", ".", "..", ".git"})
FORBIDDEN_SUBSTRINGS = ("\\", ":")
FORBIDDEN_PREFIXES = ("/", "~")


class PathError(ValueError):
    """A path this engine will not accept. Callers may translate it."""


# What a Windows word may hold unquoted in a printed PowerShell command.
_PLAIN_WORD = re.compile(r"[\w@%+=:,./-]+")


def on_windows() -> bool:
    """Whether this process runs on Windows. One function reads the platform, so that a test can
    say Windows, and a type checker does not fold the other branch away."""

    return sys.platform == "win32"


def shell_word(word: str) -> str:
    """`word` quoted for the shell a person pastes an engine-printed command into.

    POSIX output uses `shlex.quote`. Windows output is for PowerShell: it doubles an
    apostrophe inside single quotes. It is not Git Bash or cmd syntax. This is printed
    command text, not a Done line, which the finish check runs under a POSIX shell.
    """

    if not on_windows():
        return shlex.quote(word)
    if _PLAIN_WORD.fullmatch(word):
        return word
    return "'" + word.replace("'", "''") + "'"


def shell_path(path: Path | str) -> str:
    """`path` as a printed command's word: forward slashes, which every Windows shell and
    program takes, then quoted."""

    return shell_word(Path(path).as_posix())


def is_control(character: str) -> bool:
    """The grammar's control-character rule, in one place.

    Deliberately exactly code point < 32 plus DEL, and no wider: the grammar is
    what every reader and every recorded manifest agrees on, so widening it here
    would silently refuse paths a recorded installation contains.
    """

    code = ord(character)
    return code < 32 or code == 127


def names_git(part: str) -> bool:
    """Whether a segment opens the repository's own `.git` on some filesystem.

    macOS and Windows fold case and Windows drops trailing dots and spaces, so
    `.GIT`, `.Git` and `.git.` all reach `.git` there.
    """

    return part.casefold().rstrip(". ") == ".git"


# What Windows will not make a file of, though the grammar above admits it: a character its file
# names cannot hold, a device name with any extension (`NUL`, `aux.txt`), and a name that ends in
# a dot or a space. The grammar stays narrow, as it is what every recorded manifest agrees on;
# `windows_refusal` is for the one place a name meets the Windows filesystem, the writer.
_WINDOWS_BAD_CHARACTERS = frozenset('<>"|?*')
_WINDOWS_DEVICES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{n}" for n in range(1, 10)),
        *(f"LPT{n}" for n in range(1, 10)),
    }
)


def windows_refusal(relative: str) -> str | None:
    """Why Windows cannot hold the bounded path ``relative`` as a file, or None.

    It says nothing on another platform, and nothing for a path it can hold.
    """

    if not on_windows():
        return None
    for part in relative.split("/"):
        if _WINDOWS_BAD_CHARACTERS & set(part):
            return f"{part!r} holds a character that a Windows file name cannot"
        if part.split(".", 1)[0].rstrip(" ").upper() in _WINDOWS_DEVICES:
            return f"{part!r} is a Windows device name"
        if part.endswith((".", " ")):
            return f"{part!r} ends in a dot or a space, which Windows drops"
    return None


# IO_REPARSE_TAG_MOUNT_POINT, the tag of a directory junction; the `stat` module names it only on
# Windows.
REPARSE_TAG_JUNCTION = 0xA0000003


def redirects(path: Path) -> bool:
    """Whether ``path`` is a symlink, or on Windows a directory junction: a way to reach files
    elsewhere that Git cannot commit and a normal account can make. Other reparse points, such as
    a cloud folder's placeholders, are ordinary files and directories."""

    if path.is_symlink():
        return True
    if not on_windows():
        return False
    try:
        return getattr(path.lstat(), "st_reparse_tag", 0) == REPARSE_TAG_JUNCTION
    except OSError:
        return False


def admits(value, *, allow_root=False) -> bool:
    """Whether ``value`` is a bounded repository-relative path. Never raises."""

    if not isinstance(value, str) or not value:
        return False
    if allow_root and value == ".":
        return True
    if value.startswith(FORBIDDEN_PREFIXES):
        return False
    if any(bad in value for bad in FORBIDDEN_SUBSTRINGS):
        return False
    if any(is_control(character) for character in value):
        return False
    return not any(part in FORBIDDEN_SEGMENTS or names_git(part) for part in value.split("/"))


def bounded_relative(value, *, allow_root=False) -> str:
    """``value`` if it is a bounded repository-relative path, else refuse.

    ``allow_root`` additionally admits exactly ``"."``, the whole-target
    selection the grammar gives the readers that accept it.
    """

    if not admits(value, allow_root=allow_root):
        raise PathError(f"not a bounded relative path: {value!r}")
    return value


def resolve_bounded(root, relative, *, allow_root=False) -> Path:
    """``root``/``relative`` with no symlink on the way and no escape.

    Every ancestor is checked rather than the final path alone: a symlinked
    directory relocates everything beneath it, and a check that resolved first
    and compared afterwards could not see the difference between a path inside
    the root and a path that merely spells one.
    """

    root = Path(root)
    bounded_relative(relative, allow_root=allow_root)
    if relative == ".":
        return root
    candidate = root
    for part in PurePosixPath(relative).parts:
        candidate = candidate / part
        if redirects(candidate):
            raise PathError(f"path contains a symlink: {relative}")
    if not candidate.absolute().is_relative_to(root.absolute()):
        raise PathError(f"path escapes its root: {relative}")
    return candidate


def read_bounded(root, relative) -> bytes:
    """The bytes of one bounded file inside ``root``.

    Reading is where a path stops being a string and starts being evidence, so
    the refusals are separated: a path this engine will not accept, a path that
    is not a regular file, and a file it cannot read are three different
    answers, and collapsing them would report a hostile path as an I/O problem.
    """

    path = resolve_bounded(root, relative)
    if redirects(path) or not path.is_file():
        raise PathError(f"not a readable file: {relative}")
    try:
        return path.read_bytes()
    except OSError as error:
        raise PathError(f"cannot read {relative}: {error}") from error
