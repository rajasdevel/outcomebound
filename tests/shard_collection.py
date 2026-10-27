"""Report xdist's worker collections before it schedules any tests.

``--collect-only`` disables xdist in the controller, so the shard checker uses this plugin
with ``-n 2`` instead. The last worker's collection event stops the run before the scheduler
can send test indices. Collection errors still fail the check.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

COLLECTIONS: dict[str, list[str]] = {}
SESSION: pytest.Session | None = None


def pytest_sessionstart(session: pytest.Session) -> None:
    global SESSION
    SESSION = session
    COLLECTIONS.clear()


def pytest_xdist_node_collection_finished(node, ids: list[str]) -> None:
    COLLECTIONS[node.gateway.id] = list(ids)
    if len(COLLECTIONS) == 2:
        Path(os.environ["OUTCOMEBOUND_SHARD_REPORT"]).write_text(
            json.dumps(COLLECTIONS), encoding="utf-8"
        )
        assert SESSION is not None
        pytest.exit(
            "worker collections recorded; no tests run", returncode=int(SESSION.testsfailed > 0)
        )
