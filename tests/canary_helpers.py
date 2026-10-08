"""Synthetic projects and command helpers for canary tests."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "canary.py"
LAUNCHER = ROOT / "scripts" / "outcomebound"
IDENTITY = ("-c", "user.name=Canary", "-c", "user.email=canary@example.test")


def git(where: Path, *args: str) -> None:
    subprocess.run(["git", *IDENTITY, *args], cwd=where, check=True, capture_output=True)


def project(path: Path) -> Path:
    """A Git project with one commit, then OutcomeBound installed by this checkout and committed."""

    path.mkdir()
    git(path, "init", "-q")
    (path / "README.md").write_text("# a synthetic project\n", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "start")
    subprocess.run([str(LAUNCHER), "adopt", str(path)], check=True, capture_output=True)
    git(path, "add", "-A")
    git(path, "commit", "-qm", "adopt")
    return path


def stub(tmp_path: Path, body: str) -> Path:
    """An interpreter for the candidate that runs `body`; it is called as the canary calls a
    Python: `-I -c <code> <checkout> <verb> <project> ...`, so $5 is the verb, $6 the project."""

    path = tmp_path / "stub-python"
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def canary(tmp_path: Path, listed: list[Path], python: Path | str) -> subprocess.CompletedProcess:
    listing = tmp_path / "canary-projects.txt"
    listing.write_text("# private\n" + "".join(f"{p}\n" for p in listed), encoding="utf-8")
    env = {**os.environ, "OB_CANARY_LIST": str(listing)}
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--installed",
            str(LAUNCHER),
            "--python",
            str(python),
            "--records",
            str(tmp_path / "records"),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def assert_no_path(output: str, tmp_path: Path) -> None:
    assert str(tmp_path) not in output
    assert "private-alpha" not in output
    assert "private-beta" not in output


def load_canary():
    spec = importlib.util.spec_from_file_location("canary", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Its dataclasses read their annotations through the module's entry in sys.modules.
    sys.modules["canary"] = module
    spec.loader.exec_module(module)
    return module


def instructions(module):
    return next(c for c in module.COMMANDS if c.label == "instructions check")
