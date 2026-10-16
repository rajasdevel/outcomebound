"""The Makefile's interpreter check: an old Python stops every target by name, before a script
fails on it with a raw error; an absent one is left to make's own line."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Only the tests that run `make` need it and a POSIX shell; those that read the Makefile's text
# run wherever the suite does.
needs_make = pytest.mark.skipif(
    os.name == "nt" or shutil.which("make") is None, reason="needs make and a POSIX shell"
)


def _stub(tmp_path: Path) -> tuple[Path, Path]:
    """A python3 that reports 3.9: it fails the version probe and logs every other call."""
    log = tmp_path / "calls.log"
    stub = tmp_path / "python3"
    stub.write_text(
        "#!/bin/sh\n"
        'case "$*" in *version_info*) exit 1 ;; -V) echo "Python 3.9.6"; exit 0 ;; esac\n'
        f'printf "%s\\n" "$*" >> "{log}"\n'
        "exit 0\n"
    )
    stub.chmod(0o755)
    return stub, log


def _make(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "--no-print-directory", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


@needs_make
def test_make_refuses_a_python_older_than_the_minimum_by_name(tmp_path: Path) -> None:
    stub, log = _stub(tmp_path)
    result = _make("gate", f"PYTHON={stub}")
    assert result.returncode != 0
    assert "outcomebound: no Python 3.10 or later" in result.stderr
    assert "Python 3.9.6" in result.stderr and str(stub) in result.stderr
    assert not log.exists(), "the gate script ran on the old interpreter"


@needs_make
def test_make_leaves_an_absent_python_to_makes_own_line(tmp_path: Path) -> None:
    result = _make("gate", f"PYTHON={tmp_path / 'absent' / 'python3'}")
    assert result.returncode != 0
    assert "no Python 3.10 or later" not in result.stderr
    assert "No such file or directory" in result.stderr


@needs_make
def test_make_runs_under_a_python_that_meets_the_minimum() -> None:
    result = _make("gate", f"PYTHON={sys.executable}")
    assert result.returncode == 0, result.stderr


def _targets() -> dict[str, tuple[str, str]]:
    """Each target: (its prerequisites, its recipe)."""
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    found: dict[str, list[str]] = {}
    prereqs: dict[str, str] = {}
    current = None
    for line in text.splitlines():
        rule = re.match(r"^([a-z][a-z \-]*):(?!=)(.*)$", line)
        if rule:
            current = None
            for name in rule.group(1).split():
                prereqs[name] = prereqs.get(name, "") + " " + rule.group(2)
                found.setdefault(name, [])
            names = rule.group(1).split()
            current = names[0] if len(names) == 1 else None
        elif line.startswith("\t") and current:
            found[current].append(line)
    return {name: (prereqs[name], "\n".join(found[name])) for name in found}


def test_every_make_target_that_runs_python_checks_the_interpreter_first() -> None:
    targets = _targets()
    runs_python = [
        n for n, (_, recipe) in targets.items() if "$(PYTHON)" in recipe and n != "python"
    ]
    assert runs_python, "the Makefile parse found no target"
    missing = [n for n in runs_python if "python" not in targets[n][0].split()]
    assert not missing, f"targets that run $(PYTHON) without the interpreter check: {missing}"


def test_the_python_minimum_agrees_in_the_makefile_the_launcher_and_the_package() -> None:
    backend = (ROOT / "scripts/build_backend.py").read_text(encoding="utf-8")
    assert 'REQUIRES_PYTHON = ">=3.10"' in backend
    for path in ("Makefile", "scripts/outcomebound"):
        assert "sys.version_info < (3, 10)" in (ROOT / path).read_text(encoding="utf-8"), path


def test_release_check_sweeps_the_main_checkouts_work_folder_and_ci_does_not() -> None:
    """A text check of the recipe, not a run of the sweep: it breaks if the release gate drops
    the sweep or the main-checkout lookup (`--git-common-dir`), so that it reads a worktree's own
    empty work folder, or if CI starts to run the sweep, which has no such folder."""

    recipe = _targets()["release-check"][1]
    assert "review sweep" in recipe and "--git-common-dir" in recipe
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "review sweep" not in workflow
