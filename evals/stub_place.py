"""Place the runner-owned stubs a fixture names where its call finds them first.

A stub is a small standard-library program the runner owns, kept under `evals/stubs/`: an
executable launcher `<name>` and, where it has one, the `<name>.py` it runs. A fixture names the
stubs its call needs in its `suite.json` (`"stubs": ["review"]`). Before the call the runner
copies each into a new folder of its own, outside the workspace, with the files and the folder
made read-only, and puts that folder first on the call's PATH. The checks find it through
`OB_EVAL_STUBS`.

Each stub's digest is taken before the call and after it, and the runner writes both to the
file `OB_EVAL_STUB_DIGESTS` names, `{"<stub>": {"before": hex, "after": hex}}`. A digest covers
the stub's own files and the names of every entry of the folder, so a file the call adds beside
a stub (a command that would shadow another) changes it as an edit of the stub does. A changed
digest is the checks' to score; it never voids a run.

Standard library only.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path

STUBS = Path(__file__).resolve().parent / "stubs"
STUBS_ENV = "OB_EVAL_STUBS"
DIGESTS_ENV = "OB_EVAL_STUB_DIGESTS"
NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
# The modes of a placed launcher, a placed `.py` and the placed folder while the call runs; the
# folder is made writable again after the call, so its kept copy can be removed.
LAUNCHER_MODE, SOURCE_MODE, FOLDER_MODE, RELEASED_MODE = 0o555, 0o444, 0o555, 0o700
MISSING = b"<missing>"


class StubError(ValueError):
    """A stub the runner cannot place; the message names which and why."""


def stub_files(name: str, source: Path = STUBS) -> tuple[Path, ...]:
    """The files of the stub `name` under `source`: its executable launcher, then its `.py`
    where it has one. StubError where the name is not a plain lowercase name, or where there is
    no executable launcher."""

    if not NAME.fullmatch(name):
        raise StubError(f"{name!r} is not a stub name (lowercase letters, digits and hyphens)")
    launcher = source / name
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise StubError(f"no executable stub {name} under {source}")
    script = source / f"{name}.py"
    return (launcher, script) if script.is_file() else (launcher,)


def check(names: tuple[str, ...], source: Path = STUBS) -> None:
    """StubError where a name is named twice or a stub cannot be placed."""

    if len(set(names)) != len(names):
        raise StubError("a stub is named twice")
    for name in names:
        stub_files(name, source)


def digest(folder: Path, name: str) -> str:
    """The SHA-256 of the placed stub `name`: the names of the folder's entries, then the bytes
    of its launcher and of its `.py`; an entry that cannot be read counts as missing."""

    hashed = hashlib.sha256()
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        entries = ["<unreadable>"]
    hashed.update("\0".join(entries).encode("utf-8") + b"\0\0")
    for file in (name, f"{name}.py"):
        try:
            data = (folder / file).read_bytes()
        except OSError:
            data = MISSING
        hashed.update(file.encode("utf-8") + b"\0" + str(len(data)).encode() + b"\0" + data)
    return hashed.hexdigest()


def digests(folder: Path, names: tuple[str, ...]) -> dict[str, str]:
    return {name: digest(folder, name) for name in names}


def place(names: tuple[str, ...], folder: Path, source: Path = STUBS) -> dict[str, str]:
    """Copy each named stub into the new `folder`, make the files and the folder read-only, and
    return each stub's digest. StubError or OSError where one cannot be placed; `folder` must
    not exist yet."""

    check(names, source)
    folder.mkdir(parents=True, exist_ok=False)
    for name in names:
        for path in stub_files(name, source):
            target = folder / path.name
            shutil.copyfile(path, target)
            target.chmod(LAUNCHER_MODE if path.name == name else SOURCE_MODE)
    folder.chmod(FOLDER_MODE)
    return digests(folder, names)


def release(folder: Path) -> None:
    """Make the placed folder writable again, after its digests were taken, so its kept copy can
    be removed; its files stay read-only."""

    if folder.is_dir():
        folder.chmod(RELEASED_MODE)


def record(before: dict[str, str], after: dict[str, str]) -> dict[str, dict[str, str]]:
    """The digests file's content: each stub's digest before and after the call."""

    return {name: {"before": before[name], "after": after.get(name, "")} for name in before}
