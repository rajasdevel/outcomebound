"""Settings every test, and every process a test starts, runs under."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from tests.portable import home_environment

# Git's automatic maintenance runs detached after a commit, so it can still be writing
# `.git/objects/maintenance.lock` into a fixture repository while a test snapshots or
# removes that repository. Git reads configuration from GIT_CONFIG_COUNT and its numbered
# pairs (Git 2.31 and later), so setting them here reaches every git a test starts,
# directly or through the engine, in every repository it creates.
GIT_CONFIG = (("maintenance.auto", "false"), ("gc.auto", "0"))


# Without --basetemp, every pytest run of this user shares one folder, pytest-of-<user> in the
# system's temporary folder, and each run that ends unlinks the dead `pytest-current` link there.
# Two runs that end together, such as suites in two worktrees, race on that unlink, and the loser
# ends in FileNotFoundError after every test passed. So a run that names no base folder gets one
# of its own, removed when the run passes and kept, as pytest keeps it, when a test fails.
OWN_BASE = pytest.StashKey[Path]()


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Give the run its own base folder before pytest reads the option, then append
    `GIT_CONFIG` to the environment's Git configuration, once per process."""

    if config.option.basetemp is None and not hasattr(config, "workerinput"):
        root = Path(tempfile.mkdtemp(prefix="outcomebound-pytest-"))
        config.option.basetemp = str(root / "base")
        config.stash[OWN_BASE] = root

    count = int(os.environ.get("GIT_CONFIG_COUNT") or 0)
    present = {
        (os.environ.get(f"GIT_CONFIG_KEY_{index}"), os.environ.get(f"GIT_CONFIG_VALUE_{index}"))
        for index in range(count)
    }
    for key, value in GIT_CONFIG:
        if (key, value) not in present:
            os.environ[f"GIT_CONFIG_KEY_{count}"] = key
            os.environ[f"GIT_CONFIG_VALUE_{count}"] = value
            count += 1
    os.environ["GIT_CONFIG_COUNT"] = str(count)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Remove the run's own base folder when every test passed."""

    root = session.config.stash.get(OWN_BASE, None)
    if root is not None and exitstatus == 0:
        shutil.rmtree(root, ignore_errors=True)


# A test that reads or writes a home must reach its own: the person's engine and codex folders
# in their home are theirs. `Path.home()` reads `HOME` on POSIX and `USERPROFILE` on Windows,
# and Git reads `HOME`, so every variable that names a home is set. The session's home covers
# fixtures wider than one test; each test then gets a fresh one.
FOREIGN_HOMES = ("CODEX_HOME", "CLAUDE_CONFIG_DIR")


def _isolate(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    for name, value in home_environment(home).items():
        monkeypatch.setenv(name, value)
    for name in FOREIGN_HOMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="session", autouse=True)
def session_home(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    home = tmp_path_factory.mktemp("session-home")
    with pytest.MonkeyPatch.context() as patch:
        _isolate(patch, home)
        yield home


@pytest.fixture(autouse=True)
def isolated_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch, session_home: Path
) -> Path:
    home = tmp_path_factory.mktemp("home")
    _isolate(monkeypatch, home)
    return home


# A Python child that a test starts writes its standard streams in UTF-8, as the engine does under
# the launcher's `-X utf8`, so a test that decodes a child's output as UTF-8 reads what a user's
# run prints on every platform; the Windows default would be the code page. Only the streams: a
# child's own files keep their default, so UTF-8 mode, which would silence the encoding guard in
# pytest's workers, stays off. An isolated child (`-I`), as the engine is started, ignores this and
# gets `-X utf8` from its own command line.
os.environ["PYTHONIOENCODING"] = "utf-8"


# The instruction audit reads a harness row as verified only until the row's `recheck_on` date,
# so a verdict that depends on the real day turns red on its own once that day passes. Every
# test runs on this day, inside the window of every row; a test of the overdue case sets its own.
AUDIT_DAY = date(2026, 10, 1)


@pytest.fixture(autouse=True)
def audit_day(monkeypatch: pytest.MonkeyPatch) -> date:
    monkeypatch.setattr("outcomebound_tools.instruction_audit._today", lambda: AUDIT_DAY)
    return AUDIT_DAY


def pytest_report_header() -> str | None:
    """Say when the encoding guard cannot fire: with no UTF-8 locale set, Python runs in UTF-8
    mode, where a call that names no encoding gets UTF-8 and no warning, so a run here passes
    what Windows fails."""

    if sys.flags.warn_default_encoding and sys.flags.utf8_mode:
        return (
            "UNVERIFIED encoding guard: Python runs in UTF-8 mode (no UTF-8 locale is set), which "
            "hides a call that names no encoding; set LANG to a UTF-8 locale, such as C.UTF-8"
        )
    if sys.flags.warn_default_encoding and sys.version_info < (3, 11):
        return (
            "encoding guard: Python 3.10 does not warn for a text-mode subprocess; "
            "`make test-containers` (3.13) and CI on 3.11 and later check it"
        )
    return None
