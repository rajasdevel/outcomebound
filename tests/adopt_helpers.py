"""Repository construction and install observations shared by adopt tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import adopt
from tests.portable import write

ROOT = Path(__file__).resolve().parent.parent
GIT = shutil.which("git") or "git"
Capture = pytest.CaptureFixture[str]


def repo(path: Path, files: dict[str, str] | None = None) -> Path:
    """A fresh Git repository at `path` holding `files`, by relative path."""

    path.mkdir(parents=True)
    subprocess.run([GIT, "init", "-q", str(path)], check=True)
    for name, text in (files or {}).items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        write(path / name, text)
    return path


def run(capsys: Capture, *argv: str, source: Path = ROOT) -> tuple[int, str, str]:
    code = adopt.main(list(argv), source=source)
    out, err = capsys.readouterr()
    return code, out, err


def snapshot(root: Path) -> dict[str, bytes]:
    """Every file and symlink under `root` outside `.git`, by relative path."""

    found: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts[0] == ".git":
            continue
        if path.is_symlink():
            found[relative.as_posix()] = b"-> " + os.readlink(path).encode()
        elif path.is_file():
            found[relative.as_posix()] = path.read_bytes()
    return found


def manifest(target: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((target / adopt.MANIFEST).read_text(encoding="utf-8"))
    return document


def states(out: str) -> dict[str, str]:
    """`--check` output as {record label: state}, any detail after the label, the measurement
    note and the closing `next:` line left out."""

    lines = [line for line in out.splitlines() if not line.startswith(("next: ", "note "))]
    rows = [line.split(None, 1) for line in lines]
    return {name.split(": ", 1)[0]: found for found, name in rows}


def engine_copy(tmp_path: Path) -> Path:
    """The parts of this checkout adopt renders from, copied so a test can change them."""

    source = tmp_path / "engine"
    for directory in ("fragments", "adapters", "skills"):
        shutil.copytree(ROOT / directory, source / directory)
    for name in ("VERSION", adopt.KERNEL_TEMPLATE, "templates/fragment-local.md"):
        (source / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, source / name)
    return source


def change_kernel(source: Path, version: str) -> None:
    template = source / adopt.KERNEL_TEMPLATE
    text = template.read_text(encoding="utf-8")
    write(template, text.replace("not least work.", "not least work, now."))
    write(source / "VERSION", version + "\n")
