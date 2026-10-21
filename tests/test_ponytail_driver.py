"""The Ponytail driver: the patch applies to the pinned commit, a patch that does not apply stops
before anything runs, and the dry run's checks catch a leaked PONYTAIL_* variable and a missing
OutcomeBound install. Tests that need the pinned Ponytail clone skip when it is absent."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from evals.ponytail import checks, driver

CLONE = driver.default_clone()
HAVE_CLONE = (CLONE / ".git").exists() and driver._git(
    "cat-file", "-e", f"{driver.PINNED}^{{commit}}", cwd=CLONE if CLONE.is_dir() else None
).returncode == 0
needs_clone = pytest.mark.skipif(
    not HAVE_CLONE, reason=f"no Ponytail clone with commit {driver.PINNED} (set OB_PONYTAIL_CLONE)"
)


def _remove_worktree(path: Path) -> None:
    driver._git("worktree", "remove", "--force", str(path), cwd=CLONE)
    driver._git("worktree", "prune", cwd=CLONE)


@pytest.fixture(scope="module")
def worktree(tmp_path_factory):
    out = tmp_path_factory.mktemp("ponytail") / "wt"
    driver.prepare(CLONE, driver.PINNED, out)
    yield out
    _remove_worktree(out)


@pytest.fixture(scope="module")
def dry(worktree, tmp_path_factory):
    """One dry run of a surgical task in every arm, with a PONYTAIL_* variable planted in the
    environment the harness starts from."""
    out = tmp_path_factory.mktemp("dry")
    env = {**os.environ, "PONYTAIL_DEFAULT_MODE": "ultra", "PONYTAIL_PLUGIN_DIR": str(out)}
    done = subprocess.run(
        [
            sys.executable,
            str(driver.HERE / "driver.py"),
            "dry-run",
            "--worktree",
            str(worktree),
            "--clone",
            str(CLONE),
            "--commit",
            driver.PINNED,
            "--tasks",
            "safe-path",
            "--arms",
            "baseline,ponytail,ob",
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
        encoding="utf-8",
    )
    run_dir = max(p for p in out.iterdir() if p.is_dir())
    return done, run_dir


@needs_clone
def test_patch_applies_to_the_pinned_commit(worktree):
    run_py = (worktree / "benchmarks/agentic/run.py").read_text(encoding="utf-8")
    assert "def _build_cell(" in run_py and '"ob":' in run_py
    driver._prepared(worktree, driver.PINNED)


@needs_clone
def test_a_patch_that_does_not_apply_stops_before_anything_runs(tmp_path):
    broken = tmp_path / "broken.patch"
    broken.write_text(
        driver.PATCH.read_text(encoding="utf-8").replace(
            "import argparse, concurrent.futures, datetime, json",
            "import argparse, concurrent.futures, datetime, jsonx",
            1,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "wt"
    with pytest.raises(SystemExit, match="does not apply"):
        driver.prepare(CLONE, driver.PINNED, out, patch=broken)
    assert not out.exists()


@needs_clone
def test_dry_run_builds_isolated_cells_and_passes(dry):
    done, run_dir = dry
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    report = json.loads((run_dir / "ob-dry-run.json").read_text(encoding="utf-8"))
    assert report["failures"] == 0 and len(report["cells"]) == 3
    for cell in run_dir.iterdir():
        if cell.is_dir():
            rec = json.loads((cell / "evidence" / "dry_run.json").read_text(encoding="utf-8"))
            assert not [k for k in rec["env"] if k.startswith("PONYTAIL_")]
            assert not (cell / "evidence" / "_claude.jsonl").exists()  # nothing was started


def _cell_checks(run_dir: Path, arm: str) -> dict[str, bool]:
    cell = next(p for p in run_dir.iterdir() if p.is_dir() and p.name.split("__")[1] == arm)
    rec = json.loads((cell / "evidence" / "dry_run.json").read_text(encoding="utf-8"))
    no_run = rec["cmd"][rec["cmd"].index("--append-system-prompt") + 1]
    return {name: ok for name, ok, _ in driver.check_cell(cell, arm, {}, CLONE, no_run)}


@needs_clone
def test_dry_run_checks_catch_a_planted_ponytail_variable(dry, tmp_path):
    _done, run_dir = dry
    copy = tmp_path / run_dir.name
    shutil.copytree(run_dir, copy, symlinks=True)
    cell = next(p for p in copy.iterdir() if p.is_dir() and p.name.split("__")[1] == "baseline")
    record = cell / "evidence" / "dry_run.json"
    rec = json.loads(record.read_text(encoding="utf-8"))
    assert _cell_checks(copy, "baseline")["environment"]
    rec["env"]["PONYTAIL_DEFAULT_MODE"] = "ultra"
    record.write_text(json.dumps(rec), encoding="utf-8")
    assert not _cell_checks(copy, "baseline")["environment"]


@needs_clone
def test_dry_run_checks_catch_a_missing_ob_install(dry, tmp_path):
    _done, run_dir = dry
    copy = tmp_path / run_dir.name
    shutil.copytree(run_dir, copy, symlinks=True)
    assert _cell_checks(copy, "ob")["OB install (adopt --harness claude-code)"]
    cell = next(p for p in copy.iterdir() if p.is_dir() and p.name.split("__")[1] == "ob")
    (cell / "ws" / "AGENTS.md").unlink()
    found = _cell_checks(copy, "ob")
    assert not found["OB install (adopt --harness claude-code)"]
    assert not found["project instruction/settings files"]


def test_environment_check_names_each_leak(tmp_path):
    cell = tmp_path / "cell"
    clean = {k: str(cell / k.lower()) for k in driver.FRESH}
    clean["PATH"] = "/usr/bin"
    assert driver.check_env(clean, cell) == []
    leaked = {
        **clean,
        "PONYTAIL_DEFAULT_MODE": "ultra",
        "HOME": str(tmp_path / "elsewhere"),
        "EDITOR": "vi",
    }
    problems = driver.check_env(leaked, cell)
    assert "PONYTAIL_DEFAULT_MODE inherited" in problems
    assert "HOME outside the cell" in problems
    assert "EDITOR is not in the cell's allow list" in problems


def test_the_guard_refuses_to_start_claude(monkeypatch: pytest.MonkeyPatch):
    # The guard replaces subprocess.Popen for the process; monkeypatch puts the real one back.
    monkeypatch.setattr(subprocess, "Popen", subprocess.Popen)
    driver._guard_claude()
    with pytest.raises(driver.ClaudeRefused):
        subprocess.run(["claude", "--version"], capture_output=True)
    assert (
        subprocess.run(
            [sys.executable, "-c", "print(1)"], capture_output=True, text=True, encoding="utf-8"
        ).stdout.strip()
        == "1"
    )


def _init(**fields):
    return [{"type": "system", "subtype": "init", **fields}, {"type": "result", "result": "done"}]


def test_loading_check_reads_the_start_event():
    ponytail = _init(plugins=[{"name": "ponytail", "path": "/x"}], skills=[])
    ob = _init(plugins=[], skills=["using-outcomebound", "diagnose"])
    assert checks.loading_check("ponytail", ponytail)["status"] == "PASS"
    assert checks.loading_check("ob", ob)["status"] == "PASS"
    assert checks.loading_check("baseline", _init(plugins=[], skills=[]))["status"] == "PASS"
    assert checks.loading_check("baseline", ponytail)["status"] == "FAIL"
    assert checks.loading_check("ponytail", ob)["status"] == "FAIL"
    assert checks.loading_check("ob", [{"type": "result"}])["status"] == "UNVERIFIED"
    assert checks.loading_check("ob", _init(tools=[]))["status"] == "UNVERIFIED"
