"""Settings every test, and every process a test starts, runs under."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
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
