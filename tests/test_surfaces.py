"""The form a diagram takes on the session's surface.

The shipped table is read as data and held to what the module reads of it and to
its provenance rule; the matching is asked of `session_surface` and `diagram_form`
over environments built here, and over built rows where the rule needs rows the
table does not have.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from outcomebound_tools import surfaces
from outcomebound_tools.surfaces import (
    UNKNOWN,
    SurfaceError,
    diagram_form,
    session_surface,
    table,
)

ROOT = Path(__file__).resolve().parent.parent
TABLE = json.loads((ROOT / "adapters/surfaces.json").read_text(encoding="utf-8"))

# The environment of a session of the harness's editor extension running inside the
# cursor editor, as the table's own source line records it.
EDITOR_SESSION = {
    "CLAUDECODE": "1",
    "CLAUDE_CODE_ENTRYPOINT": "claude-vscode",
    "AI_AGENT": "claude-code_2-1-280_agent",
    "CURSOR_LAYOUT": "unifiedAgent",
    "CURSOR_WORKSPACE_LABEL": "a-project",
    "VSCODE_PID": "10354",
}


def _row(
    environment: list[dict[str, str | None]] | None, mermaid: bool | None = None
) -> dict[str, object]:
    """A built row in the table's shape, selected by `environment`, whose rendering
    fact, where it records one, carries its provenance."""

    provenance = (
        None
        if mermaid is None
        else {"kind": "observed", "on": "2026-09-28", "by": "a person", "url": None, "says": "x"}
    )
    return {
        "harness": "a-harness",
        "signals": {"environment": environment, "store": None, "source": "a built row"},
        "mermaid": mermaid,
        "provenance": provenance,
    }


def _variable(name: str, value: str | None = "1") -> dict[str, str | None]:
    return {"name": name, "value": value}


def test_every_row_is_in_the_shape_the_module_reads() -> None:
    """Each row's selector is null or a non-empty list of named variables, each with a
    string or null value; a row selected by nothing is never chosen, so a selector
    malformed here would leave its surface unknown without a word."""

    assert TABLE, "the surface table is empty"
    assert table() == TABLE
    for name, row in TABLE.items():
        selector = row["signals"]["environment"]
        if selector is None:
            continue
        assert isinstance(selector, list) and selector, name
        for entry in selector:
            assert set(entry) == {"name", "value"}, name
            assert isinstance(entry["name"], str) and entry["name"], name
            assert entry["value"] is None or (isinstance(entry["value"], str) and entry["value"])


def test_every_rendering_fact_carries_its_provenance() -> None:
    """A rendering fact says who saw it or where it is written, and when; a row that
    records none says why."""

    for name, row in TABLE.items():
        provenance = row["provenance"]
        assert isinstance(row["mermaid"], (bool, type(None))), name
        assert (row["mermaid"] is None) == (provenance is None), name
        if provenance is not None:
            assert provenance["kind"] in ("observed", "reported"), name
            assert provenance["on"] and provenance["says"], name
        if provenance is not None and provenance["kind"] == "observed":
            assert provenance["by"] is not None and provenance["url"] is None, name
        if provenance is not None and provenance["kind"] == "reported":
            assert provenance["url"].startswith("https://") and provenance["by"] is None, name
        if row["mermaid"] is None:
            assert row.get("note"), f"{name} records no rendering and says nothing of why"


def test_the_editor_extension_session_is_identified_and_draws_ascii() -> None:
    """The surface observed showing a Mermaid block as its source text is identified
    from its environment, and draws ASCII, though the host editor's
    own variables name another row too."""

    assert session_surface(EDITOR_SESSION) == "claude-code-editor"
    assert diagram_form(EDITOR_SESSION) == "ascii"
    assert session_surface({**EDITOR_SESSION, "CURSOR_AGENT": "1"}) == "claude-code-editor"


def test_the_most_specific_row_wins_and_a_tie_is_unknown() -> None:
    rows = {
        "a": _row([_variable("X")], mermaid=False),
        "b": _row([_variable("Y")], mermaid=False),
        "c": _row([_variable("X"), _variable("Y")], mermaid=True),
    }
    both = {"X": "1", "Y": "1"}

    assert session_surface(both, rows) == "c"
    assert diagram_form(both, rows) == "mermaid"
    del rows["c"]
    assert session_surface(both, rows) == UNKNOWN


def test_a_string_value_matches_exactly_and_a_null_one_any_setting_but_empty() -> None:
    assert session_surface({"CURSOR_AGENT": "1"}) == "cursor-agent-chat"
    assert session_surface({"CURSOR_AGENT": "yes"}) == "cursor-agent-chat"
    assert session_surface({"CURSOR_AGENT": ""}) == UNKNOWN
    assert session_surface({"GEMINI_CLI": "1"}) == "gemini"
    assert session_surface({"GEMINI_CLI": "true"}) == UNKNOWN


@pytest.mark.parametrize(
    "environ",
    [{}, {"CLAUDECODE": "1"}, {"CODEX_SANDBOX": "seatbelt"}, {"CURSOR_AGENT": "1"}],
    ids=["nothing-set", "one-of-two-variables", "no-row-names-it", "no-rendering-recorded"],
)
def test_an_unknown_or_unrecorded_surface_draws_ascii(environ: dict[str, str]) -> None:
    """A session no row identifies, and one whose row records no rendering, draw ASCII."""

    assert diagram_form(environ) == "ascii"


def test_a_rendering_counts_only_from_a_row_that_is_selected_and_carries_provenance() -> None:
    """A row that names no variable is never chosen, even one recording Mermaid; and a
    `true` without its provenance is not taken as rendering it."""

    shipped = TABLE["cursor-cli"]
    assert shipped["mermaid"] is True and shipped["signals"]["environment"] is None
    for environ in ({}, {"Z": "1"}, EDITOR_SESSION):
        assert session_surface(environ, {"cursor-cli": shipped}) == UNKNOWN
        assert diagram_form(environ, {"cursor-cli": shipped}) == "ascii"

    selected = {"z": _row([_variable("Z")], mermaid=True)}
    assert diagram_form({"Z": "1"}, selected) == "mermaid"
    unsourced = {"z": {**selected["z"], "provenance": None}}
    assert diagram_form({"Z": "1"}, unsourced) == "ascii"


def test_the_persons_record_outranks_the_table() -> None:
    """`OUTCOMEBOUND_DIAGRAMS` names the form either way, over the row identified and
    over an unknown surface; a value that is neither form is ignored."""

    rows = {"z": _row([_variable("Z")], mermaid=True)}
    assert diagram_form({"Z": "1", "OUTCOMEBOUND_DIAGRAMS": "ascii"}, rows) == "ascii"
    assert diagram_form({**EDITOR_SESSION, "OUTCOMEBOUND_DIAGRAMS": "mermaid"}) == "mermaid"
    assert diagram_form({"OUTCOMEBOUND_DIAGRAMS": "mermaid"}) == "mermaid"
    assert diagram_form({**EDITOR_SESSION, "OUTCOMEBOUND_DIAGRAMS": " Mermaid "}) == "mermaid"
    assert diagram_form({"Z": "1", "OUTCOMEBOUND_DIAGRAMS": "yes"}, rows) == "mermaid"


def test_an_unreadable_table_is_refused_by_name_and_the_persons_record_still_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A table that cannot be read is refused without the checkout's path; the
    person's record is read first, so it holds where the table cannot be read."""

    prefix = "cannot read the surface table adapters/surfaces.json in the selected engine: "
    monkeypatch.setattr(surfaces, "_TABLE_PATH", tmp_path / "missing.json")
    with pytest.raises(SurfaceError) as missing:
        diagram_form({})
    assert str(missing.value).startswith(prefix)
    assert str(tmp_path) not in str(missing.value)
    assert diagram_form({"OUTCOMEBOUND_DIAGRAMS": "mermaid"}) == "mermaid"

    malformed = tmp_path / "surfaces.json"
    monkeypatch.setattr(surfaces, "_TABLE_PATH", malformed)
    for content in ("[]", '{"x": []}', "{"):
        malformed.write_text(content, encoding="utf-8")
        with pytest.raises(SurfaceError) as defective:
            session_surface({})
        assert str(defective.value).startswith(prefix), content
        assert str(tmp_path) not in str(defective.value), content
