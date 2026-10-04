"""The dependency gate is tested through the shipped script, never re-implemented.

A copy of the script's logic here would copy its defects too, and pass with them.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _gate():
    spec = importlib.util.spec_from_file_location(
        "check_no_deps", ROOT / "scripts" / "check-no-deps.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_python_imports_stdlib_only():
    assert _gate().violations(str(ROOT)) == []


def test_NEGATIVE_CONTROL_second_alias_in_a_multi_import_is_caught(tmp_path):
    package = tmp_path / "outcomebound_tools"
    package.mkdir()
    (package / "bad.py").write_text("import os, requests\n", encoding="utf-8")
    found = _gate().violations(str(tmp_path))
    assert [module for _, module in found] == ["requests"]


def test_NEGATIVE_CONTROL_scripts_directory_is_gated(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "helper.py").write_text("from yaml import safe_load\n", encoding="utf-8")
    found = _gate().violations(str(tmp_path))
    assert [module for _, module in found] == ["yaml"]


def test_check_no_deps_checks_the_root_it_is_given_and_the_current_directory_by_default(
    tmp_path: Path,
) -> None:
    """The positional is the root the script checks; `make gate`'s bare run checks `.`."""

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "helper.py").write_text("from yaml import safe_load\n", encoding="utf-8")
    gate = str(ROOT / "scripts" / "check-no-deps.py")

    given = subprocess.run(
        [sys.executable, gate, str(tmp_path)], capture_output=True, text=True, check=False
    )
    assert given.returncode == 1, given.stdout + given.stderr
    assert f"FAIL: {tmp_path / 'scripts' / 'helper.py'} imports non-stdlib 'yaml'" in given.stdout

    # A bare run over a clean tree passes; the repository's own scan is
    # test_repository_python_imports_stdlib_only's.
    clean = tmp_path / "clean"
    (clean / "scripts").mkdir(parents=True)
    (clean / "scripts" / "helper.py").write_text("import json\n", encoding="utf-8")
    by_default = subprocess.run(
        [sys.executable, gate], cwd=clean, capture_output=True, text=True, check=False
    )
    assert by_default.returncode == 0, by_default.stdout + by_default.stderr
    assert by_default.stdout.startswith("OK: "), by_default.stdout

    # The bare run reads the current directory itself, not a default that checks nothing.
    here = subprocess.run(
        [sys.executable, gate], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert here.returncode == 1, here.stdout + here.stderr
    assert "FAIL: ./scripts/helper.py imports non-stdlib 'yaml'" in here.stdout, here.stdout
