"""The store declaration: its schema and the typed value it is read into.

Driven through the module's public seam over declarations built in
`tmp_path`. This is the one part of the model that opens a file, so it is the
one test file that needs one; nothing here spawns a subprocess.
"""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

from outcomebound_tools.tickets_declaration import (
    DECLARATION_PATH,
    STORES,
    Grant,
    load_declaration,
)
from outcomebound_tools.tickets_report import Refusal

GITHUB_STORE = {
    "version": 1,
    "store": "github",
    "repo": "owner/project",
    "label": "ob-ticket",
    "human_label": "human-only",
    "request_label": "human-requested",
    "claims": ".outcomebound/ticket-claims.json",
}


def _declare(root: Path, document: object) -> Path:
    """Write one declaration under `root`, as a document or as raw text."""

    path = root / DECLARATION_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    text = document if isinstance(document, str) else json.dumps(document)
    path.write_text(text, encoding="utf-8")
    return path


def _refusal(root: Path) -> Refusal:
    with pytest.raises(Refusal) as raised:
        load_declaration(root)
    return raised.value


def test_the_declaration_path_is_the_one_the_guide_names() -> None:
    assert DECLARATION_PATH == ".outcomebound/tickets.json"
    assert STORES == ("github",)


def test_declaration_refuses_by_name(tmp_path: Path) -> None:
    """The two declaration refusals, and nothing else, whatever the file holds."""

    missing = _refusal(tmp_path)
    assert missing.code == "DECLARATION_MISSING"
    assert "tickets.json" in missing.text

    for malformed in ("{not json at all", "[1, 2, 3]"):
        _declare(tmp_path, malformed)
        assert _refusal(tmp_path).code == "DECLARATION_INVALID"

    _declare(tmp_path, {**GITHUB_STORE, "version": 2})
    wrong_version = _refusal(tmp_path)
    assert wrong_version.code == "DECLARATION_INVALID"
    assert "version" in wrong_version.text

    _declare(tmp_path, GITHUB_STORE)
    declaration = load_declaration(tmp_path)
    assert declaration.store == "github"
    assert declaration.repo == "owner/project"
    assert declaration.claims == ".outcomebound/ticket-claims.json"
    assert declaration.writes is None


def test_declaration_refuses_an_unknown_store_field_or_a_missing_one(tmp_path: Path) -> None:
    _declare(tmp_path, {**GITHUB_STORE, "store": "files"})
    refused = _refusal(tmp_path)
    assert refused.code == "DECLARATION_INVALID"
    assert "store" in refused.text and "github" in refused.text

    _declare(tmp_path, {**GITHUB_STORE, "root": "docs/tickets"})
    assert "root" in _refusal(tmp_path).text

    missing = {key: value for key, value in GITHUB_STORE.items() if key != "human_label"}
    _declare(tmp_path, missing)
    assert "human_label" in _refusal(tmp_path).text


def test_declaration_reads_and_refuses_a_grant(tmp_path: Path) -> None:
    """A `writes` grant is readable, and a malformed one is refused."""

    granted = {**GITHUB_STORE, "writes": {"granted_by": "the operator", "on": "2026-09-19"}}
    _declare(tmp_path, granted)
    assert load_declaration(tmp_path).writes == Grant(granted_by="the operator", on="2026-09-19")

    for malformed in ({"granted_by": ""}, {"granted_by": "the operator"}, "yes", {}):
        _declare(tmp_path, {**GITHUB_STORE, "writes": malformed})
        refused = _refusal(tmp_path)
        assert refused.code == "DECLARATION_INVALID"
        assert "writes" in refused.text


def test_declaration_paths_are_bounded(tmp_path: Path) -> None:
    for offending in ("/etc/passwd", "../elsewhere", "docs/../tickets"):
        _declare(tmp_path, {**GITHUB_STORE, "claims": offending})
        refused = _refusal(tmp_path)
        assert refused.code == "DECLARATION_INVALID"
        assert "claims" in refused.text


def test_a_repo_that_is_not_owner_project_is_refused(tmp_path: Path) -> None:
    """A name the tracker never spells would silently match no relation."""

    for offending in ("nonsense", "owner/", "/project", "owner project", "a/b/c"):
        _declare(tmp_path, {**GITHUB_STORE, "repo": offending})
        refused = _refusal(tmp_path)
        assert refused.code == "DECLARATION_INVALID", offending
        assert "repo" in refused.text, offending

    _declare(tmp_path, {**GITHUB_STORE, "repo": "an-owner/a.project"})
    assert load_declaration(tmp_path).repo == "an-owner/a.project"


def test_a_default_branch_is_accepted_and_read_as_nothing(tmp_path: Path) -> None:
    """No verb reads `default_branch`, so a declaration carrying it reads as the same
    declaration as one without it."""

    _declare(tmp_path, GITHUB_STORE)
    without = load_declaration(tmp_path)
    _declare(tmp_path, {**GITHUB_STORE, "default_branch": "origin/main"})
    assert load_declaration(tmp_path) == without


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("authors", ["an-account"]),
        ("humans", ["an-account"]),
        ("attestation", ["record"]),
        ("provisional_depth", 1),
        ("symbols", "ascii"),
    ],
)
def test_a_key_outside_the_schema_is_refused_by_name(
    tmp_path: Path, key: str, value: object
) -> None:
    """A key the schema does not define is refused, and named. Among them are keys
    that would list accounts: the label is the acceptance, and only accounts with
    triage access can label, so the declaration names none."""

    _declare(tmp_path, {**GITHUB_STORE, key: value})
    refused = _refusal(tmp_path)
    assert refused.code == "DECLARATION_INVALID"
    assert key in refused.text


def test_tests_import_only_public_names() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=__file__)
    reached = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        if not node.module.startswith("outcomebound_tools.tickets"):
            continue
        public = set(importlib.import_module(node.module).__all__)
        for alias in node.names:
            reached += 1
            assert alias.name in public, f"{node.module}.{alias.name} is not in __all__"
    assert reached >= 5, "the survey found fewer imported names than this file uses"
