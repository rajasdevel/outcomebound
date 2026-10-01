# tests/test_adapters.py
import pytest


def test_NEGATIVE_CONTROL_table_is_loaded_lazily_not_at_import(monkeypatch, tmp_path):
    """Importing the module must not depend on the checkout layout."""
    import importlib

    import outcomebound_tools.adapters as A

    try:
        importlib.reload(A)
        assert A._TABLE is None, "the harness table was read while the module was imported"
        monkeypatch.setattr(A, "_TABLE_PATH", tmp_path / "absent.json")
        with pytest.raises(A.AdapterError, match="harness table"):
            A.row("codex")
    finally:
        monkeypatch.undo()
        importlib.reload(A)


def test_adapter_error_reports_its_message_not_a_repr():
    """AdapterError subclasses KeyError, whose __str__ is repr(args[0]); an
    installer printing that would put a quoted, escaped string on stderr."""
    from outcomebound_tools.adapters import AdapterError, row

    with pytest.raises(AdapterError) as caught:
        row("some-future-agent")
    message = str(caught.value)
    assert message.startswith("unknown harness 'some-future-agent'")
    assert '"' not in message


def test_row_exposes_the_table_entry_and_fails_closed_on_an_unknown_name():
    """One reader for the row every placement decision is driven from."""

    from outcomebound_tools.adapters import AdapterError, row

    entry = row("claude-code")
    assert entry["skill_install_path"] == ".claude/skills/"
    assert entry["instruction_file"] == "CLAUDE.md"
    assert entry["verified"] is True
    with pytest.raises(AdapterError, match="unknown harness"):
        row("some-future-agent")


def test_harness_names_are_the_table_keys_sorted():
    from outcomebound_tools.adapters import harness_names

    names = harness_names()
    assert names == sorted(names)
    assert set(names) == {"claude-code", "codex", "amp", "gemini", "cursor", "pi"}


def test_native_skill_root_is_the_row_path_without_its_trailing_slash():
    """Codex and Amp share one directory because the table says so, not the code."""

    from outcomebound_tools.adapters import native_skill_root

    assert native_skill_root("claude-code") == ".claude/skills"
    assert native_skill_root("codex") == native_skill_root("amp") == ".agents/skills"
    assert native_skill_root("gemini") == ".gemini/skills"
    assert native_skill_root("cursor") == ".cursor/skills"
    # An unverified row still reports its candidate path; whether anything is
    # projected there is the profile's separate acceptance.
    assert native_skill_root("pi") == ".pi/skills"


def test_instruction_file_is_the_route_file_never_the_import_syntax():
    from outcomebound_tools.adapters import instruction_file, is_verified

    assert instruction_file("claude-code") == "CLAUDE.md"
    assert instruction_file("codex") == "AGENTS.md"
    assert instruction_file("pi") is None
    assert is_verified("codex") is True and is_verified("pi") is False


def test_row_refusal_names_only_remedies_that_work():
    """`generic` is adopt's route, not a table row: naming it here would send an
    operator to `row('generic')`, which raises the identical error."""

    from outcomebound_tools.adapters import AdapterError, harness_names, row

    with pytest.raises(AdapterError) as caught:
        row("some-future-agent")
    message = str(caught.value)
    assert "generic" not in message
    assert "explicit" in message
    for name in harness_names():
        assert name in message
    with pytest.raises(AdapterError, match="unknown harness 'generic'"):
        row("generic")


def test_table_read_failure_names_the_table_without_the_engine_path(monkeypatch, tmp_path):
    """A target-side refusal must not publish where this engine is checked out.

    A caller on a distribution without `adapters/` surfaces this message in its
    refusal, and `OSError.__str__` carries the absolute filename.
    """

    import importlib

    import outcomebound_tools.adapters as A

    monkeypatch.setattr(A, "_TABLE", None)
    monkeypatch.setattr(
        A, "_TABLE_PATH", tmp_path / "engine-source" / "adapters" / "harnesses.json"
    )
    with pytest.raises(A.AdapterError) as caught:
        A.row("codex")
    message = str(caught.value)
    assert "adapters/harnesses.json" in message and "No such file" in message
    assert str(tmp_path) not in message and "engine-source" not in message
    importlib.reload(A)


def test_row_hands_back_a_copy_so_one_caller_cannot_rewrite_the_table():
    from outcomebound_tools.adapters import row

    first = row("codex")
    first["doc_byte_cap"] = 1
    assert row("codex")["doc_byte_cap"] == 32768


def test_byte_cap_normalizes_once_for_every_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    """One reader turns a row's `doc_byte_cap` into a byte count.

    The rule lives beside the table it reads, so every caller gets the same
    answer. A boolean is not a 1-byte cap, a string is not a count, and an
    unknown harness is refused here rather than answered with a silent `None`.
    """

    import outcomebound_tools.adapters as A

    row = {
        "skill_install_path": ".x/skills/",
        "pointer_mechanism": "AGENTS.md",
        "command_format": "slash",
        "native_skills": True,
        "mcp": False,
        "verified": False,
    }
    monkeypatch.setitem(A._table(), "bool-cap", {**row, "doc_byte_cap": True})
    monkeypatch.setitem(A._table(), "text-cap", {**row, "doc_byte_cap": "32768"})
    assert A.byte_cap("bool-cap") is None
    assert A.byte_cap("text-cap") is None
    assert A.byte_cap("codex") == 32768
    assert A.byte_cap("") is None
    assert A.byte_cap(None) is None
    with pytest.raises(A.AdapterError, match="unknown harness 'some-future-agent'"):
        A.byte_cap("some-future-agent")
