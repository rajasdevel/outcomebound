"""The `export` verb: the pinned query's path and the command, and nothing run.

Driven through `tickets.main(argv)` with the streams captured, because what is
under test is what a person reads on the command line and the exit.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from outcomebound_tools import home
from outcomebound_tools.tickets import main

DECLARATION = {
    "version": 1,
    "store": "github",
    "repo": "owner/name",
    "label": "ob-ticket",
    "human_label": "human-only",
    "request_label": "human-requested",
    "claims": ".outcomebound/ticket-claims.json",
}


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }


def test_export_prints_the_pinned_query_path_and_the_command_and_runs_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    declared = tmp_path / ".outcomebound" / "tickets.json"
    declared.parent.mkdir()
    declared.write_text(json.dumps(DECLARATION), encoding="utf-8")
    before = _tree(tmp_path)

    def no_process(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"export started a process: {args!r}")

    monkeypatch.setattr(subprocess, "Popen", no_process)
    monkeypatch.setattr(subprocess, "run", no_process)

    code = main(["export", str(tmp_path)])
    captured = capsys.readouterr()

    assert code == 0, captured.err
    assert captured.err == ""
    query, command = captured.out.splitlines()
    pinned = (home.ROOT / "templates/tickets/github-export.graphql").resolve()
    assert query.startswith("# ") and query.endswith(str(pinned))
    assert pinned.is_file()
    assert command.startswith("gh api graphql --paginate --slurp -F owner=owner -F name=name ")
    assert "templates/tickets/github-export.graphql" in command
    assert command.endswith("> issues.json")
    assert _tree(tmp_path) == before, "export wrote nothing"


def test_export_refuses_without_a_declaration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["export", str(tmp_path)])
    captured = capsys.readouterr()

    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("DECLARATION_MISSING: ")
