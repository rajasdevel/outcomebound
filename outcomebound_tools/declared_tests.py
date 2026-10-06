"""Which test runner a component root declares.

What this module decides: the test options discovery offers for one component
root, from what the project itself declares there -- a pytest configuration,
`conftest.py` or a `pytest` requirement; a tox environment; a `tests/`
directory for the unittest fallback; the package scripts; `go.mod`; a Makefile
or justfile `test` target. It reads a few files at the root, each bounded, never
through a symlink, and parses no TOML: a table header and a quoted requirement
answer every question asked here.

What it does not decide: whether a candidate works, or which one a component
uses. Nothing here runs, and every option stays an unconfirmed candidate until a
person confirms it.
"""

from __future__ import annotations

import configparser
import os
import re
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from outcomebound_tools import paths, textio

__all__ = [
    "JUST_TEST",
    "MAKE_TEST",
    "PYTEST_KEY",
    "PYTEST_LINE",
    "PYTEST_REQUIREMENT",
    "PYTEST_TABLE",
    "TOX_TABLE",
    "runner_options",
]

PYTEST_TABLE = re.compile(r"^\s*\[\s*tool\.pytest\.ini_options\s*\]", re.MULTILINE)
TOX_TABLE = re.compile(r"^\s*\[\s*tool\.tox\s*\]", re.MULTILINE)
PYTEST_REQUIREMENT = re.compile(r"""["']\s*pytest\s*(?:\[[^\]]*\]\s*)?(?:[<>=!~;@][^"']*)?["']""")
PYTEST_KEY = re.compile(r"^\s*pytest\s*=", re.MULTILINE)
PYTEST_LINE = re.compile(r"^\s*pytest\s*(?:\[[^\]]*\]\s*)?(?:[<>=!~;@#]|$)", re.MULTILINE)
MAKE_TEST = re.compile(r"^(?:[^\s:#=]+[ \t]+)*test(?:[ \t]+[^\s:#=]+)*[ \t]*::?(?!=)", re.MULTILINE)
JUST_TEST = re.compile(r"^@?test(?:[ \t]+[^:\n=]*)?:(?!=)", re.MULTILINE)

# The Python a proposed command names: python.org and uv install `python` on Windows, and no
# `python3`, which there is at best a Store alias that does not run.
PYTHON = "python" if os.name == "nt" else "python3"
PYTEST = f"{PYTHON} -m pytest"
TOX = "tox"
UNITTEST = f"{PYTHON} -m unittest discover -s tests"
GO_TEST = "go test ./..."
MAKEFILES = ("GNUmakefile", "makefile", "Makefile")
JUSTFILES = ("justfile", "Justfile", ".justfile")
TOX_SECTIONS = ("tox", "testenv")
NODE_PRIORITY = {"test": 0, "check": 1, "typecheck": 2, "lint": 3, "build": 4}


class _Root:
    """A component root's files, read bounded and never through a symlink; unreadable is absent."""

    def __init__(self, target: Path | None, root: str, limit: int) -> None:
        self.target = target
        self.root = root
        self.limit = limit

    def _path(self, name: str) -> Path | None:
        if self.target is None:
            return None
        relative = name if self.root == "." else f"{self.root}/{name}"
        try:
            return paths.resolve_bounded(self.target, relative)
        except (paths.PathError, OSError):
            return None

    def _mode(self, name: str) -> int | None:
        path = self._path(name)
        if path is None:
            return None
        try:
            return path.lstat().st_mode
        except OSError:
            return None

    def present(self, name: str) -> bool:
        return self._mode(name) is not None

    def is_file(self, name: str) -> bool:
        mode = self._mode(name)
        return mode is not None and stat.S_ISREG(mode)

    def is_directory(self, name: str) -> bool:
        mode = self._mode(name)
        return mode is not None and stat.S_ISDIR(mode)

    def text(self, name: str) -> str | None:
        path = self._path(name)
        if path is None or not self.is_file(name):
            return None
        try:
            if path.lstat().st_size > self.limit:
                return None
            return textio.decode(path.read_bytes())
        except (OSError, UnicodeDecodeError):
            return None

    def sections(self, name: str) -> list[str]:
        text = self.text(name)
        if text is None:
            return []
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            parser.read_string(text)
        except configparser.Error:
            return []
        return parser.sections()

    def names(self, pattern: str) -> list[str]:
        """The regular files at the root whose name matches `pattern`, sorted."""

        if self.target is None:
            return []
        try:
            directory = paths.resolve_bounded(self.target, self.root, allow_root=True)
            return sorted(
                child.name for child in directory.glob(pattern) if self.is_file(child.name)
            )
        except (paths.PathError, OSError):
            return []


def _pytest_declared(files: _Root, names: set[str]) -> bool:
    if "pytest.ini" in names:
        return True
    if "pytest" in files.sections("tox.ini") or "tool:pytest" in files.sections("setup.cfg"):
        return True
    pyproject = files.text("pyproject.toml") or ""
    if (
        PYTEST_TABLE.search(pyproject)
        or PYTEST_REQUIREMENT.search(pyproject)
        or PYTEST_KEY.search(pyproject)
    ):
        return True
    if any(PYTEST_LINE.search(files.text(name) or "") for name in files.names("requirements*.txt")):
        return True
    return files.is_file("conftest.py") or files.is_file("tests/conftest.py")


def _tox_declared(files: _Root) -> bool:
    sections = files.sections("tox.ini")
    if any(section in TOX_SECTIONS or section.startswith("testenv:") for section in sections):
        return True
    return bool(TOX_TABLE.search(files.text("pyproject.toml") or ""))


def _node_scripts(root: str, packages: Sequence[Mapping[str, Any]]) -> list[str]:
    from outcomebound_tools.discovery import is_check_candidate

    scripts: list[Mapping[str, Any]] = []
    for package in packages:
        package_root = PurePosixPath(package["path"]).parent.as_posix()
        if package_root == root and package["status"] == "parsed":
            scripts.extend(row for row in package["scripts"] if is_check_candidate(row["name"]))
    scripts.sort(key=lambda row: (NODE_PRIORITY.get(row["name"], 100), row["name"]))
    return [row["invocation"] for row in scripts if row["invocation"]]


def _make_and_just(files: _Root) -> list[str]:
    options = []
    makefile = next((name for name in MAKEFILES if files.present(name)), None)
    if makefile is not None and MAKE_TEST.search(files.text(makefile) or ""):
        options.append("make test")
    if any(JUST_TEST.search(files.text(name) or "") for name in JUSTFILES):
        options.append("just test")
    return options


def runner_options(
    target: Path | None,
    root: str,
    markers: Sequence[Mapping[str, str]],
    packages: Sequence[Mapping[str, Any]],
) -> list[str]:
    """The test options one component root declares, in this order, duplicates dropped.

    python: `python3 -m pytest` (`python -m pytest` on Windows) for any pytest signal, `tox`
    for a declared tox environment, then the unittest fallback only where `tests/` is a
    directory and nothing declares pytest; node: the package scripts; go: `go test ./...`
    where `go.mod` is a marker; every kind: `make test` and `just test` for a
    declared `test` target. `target=None` reads no file.
    """

    from outcomebound_tools.discovery import MAX_PACKAGE_BYTES

    files = _Root(target, root, MAX_PACKAGE_BYTES)
    here = [row for row in markers if row["root"] == root]
    names = {PurePosixPath(row["path"]).name for row in here}
    kinds = {row["kind"] for row in here}
    options: list[str] = []
    if "python" in kinds:
        pytest = _pytest_declared(files, names)
        if pytest:
            options.append(PYTEST)
        if _tox_declared(files):
            options.append(TOX)
        if not pytest and files.is_directory("tests"):
            options.append(UNITTEST)
    if "node" in kinds:
        options.extend(_node_scripts(root, packages))
    if "go" in kinds and "go.mod" in names:
        options.append(GO_TEST)
    options.extend(_make_and_just(files))
    return list(dict.fromkeys(options))
