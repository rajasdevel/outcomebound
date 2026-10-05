"""A run reads the export it is given, and none is a planning error.

Driven through `tickets_store.read_store`, the one place a verb reads its store.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from outcomebound_tools.tickets_declaration import DECLARATION_PATH, Declaration, load_declaration
from outcomebound_tools.tickets_report import PlanningError
from outcomebound_tools.tickets_store import read_store

ROOT = Path(__file__).resolve().parent.parent
EXPORT = ROOT / "tests" / "fixtures" / "tickets" / "github-export.json"
# The declaration names the repository the fixture export names, whichever it is,
# because an export of another repository is refused.
EXPORT_REPO = json.loads(EXPORT.read_text(encoding="utf-8"))[0]["data"]["repository"][
    "nameWithOwner"
]

GITHUB_STORE = {
    "version": 1,
    "store": "github",
    "repo": EXPORT_REPO,
    "label": "ob-ticket",
    "human_label": "human-only",
    "request_label": "human-requested",
    "claims": ".outcomebound/ticket-claims.json",
}


def _declared(root: Path, document: dict[str, object]) -> Declaration:
    path = root / DECLARATION_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return load_declaration(root)


def test_a_github_declaration_reads_the_export_it_is_given(tmp_path: Path) -> None:
    declaration = _declared(tmp_path, GITHUB_STORE)
    read = read_store(tmp_path, declaration, str(EXPORT))
    assert read.tickets, "the fixture export holds tickets"
    assert all(ticket.id.startswith("#") for ticket in read.tickets)
    assert read.input is not None and read.input.path == str(EXPORT)


def test_a_github_store_without_an_export_cannot_be_planned(tmp_path: Path) -> None:
    declaration = _declared(tmp_path, GITHUB_STORE)
    with pytest.raises(PlanningError) as raised:
        read_store(tmp_path, declaration, None)
    assert raised.value.code == "INPUT_REQUIRED"
    assert "--input" in raised.value.text
    assert EXPORT_REPO in raised.value.text
    owner, _, name = EXPORT_REPO.partition("/")
    assert f"gh api graphql --paginate --slurp -F owner={owner} -F name={name} " in (
        raised.value.text
    ), "the refusal carries the export command for the declared repository"
    assert "templates/tickets/github-export.graphql" in raised.value.text
    assert "outcomebound tickets export" in raised.value.text, "it names the verb that prints it"
