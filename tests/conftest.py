"""Settings every test, and every process a test starts, runs under."""

from __future__ import annotations

import os

import pytest

# Git's automatic maintenance runs detached after a commit, so it can still be writing
# `.git/objects/maintenance.lock` into a fixture repository while a test snapshots or
# removes that repository. Git reads configuration from GIT_CONFIG_COUNT and its numbered
# pairs (Git 2.31 and later), so setting them here reaches every git a test starts,
# directly or through the engine, in every repository it creates.
GIT_CONFIG = (("maintenance.auto", "false"), ("gc.auto", "0"))


def pytest_configure(config: pytest.Config) -> None:
    """Append `GIT_CONFIG` to the environment's Git configuration, once per process."""

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
