"""The harness table is data with one shipped shape.

Every row is validated against `schemas/harness-table.schema.json`, so a row
that loses a field, invents one, or promotes absent evidence to a verified
claim fails here rather than in whatever installer reads it next.
"""

import json
from pathlib import Path

from outcomebound_tools.schemacheck import validate

ROOT = Path(__file__).resolve().parent.parent
TABLE = json.loads((ROOT / "adapters/harnesses.json").read_text(encoding="utf-8"))
ROW_SCHEMA = json.loads((ROOT / "schemas/harness-table.schema.json").read_text(encoding="utf-8"))


def test_every_row_validates_against_the_table_schema():
    """Each row has the schema's shape: its `skill_install_path`, and evidence that may be null.

    `additionalProperties: false` keeps fields out too: a `command_format` or
    `mcp` key is an unknown field, not a tolerated extra.
    """

    assert TABLE, "the harness table is empty"
    for name, row in TABLE.items():
        assert validate(row, ROW_SCHEMA) == [], f"{name}: {validate(row, ROW_SCHEMA)}"
        assert "command_format" not in row and "mcp" not in row
        # A verified row carries no placeholder anywhere in it, and absent evidence is never
        # promoted: a row not verified has no date it was.
        if row["verified"]:
            assert "TODO" not in json.dumps(row), f"{name} is verified but carries a TODO"
        else:
            assert row["verified_on"] is None, name


def test_instruction_file_is_the_file_of_the_route_never_the_import_syntax():
    """`instruction_file` is FILE for FILE@REF, the file for a direct route, null otherwise.

    Import syntax lives only in `pointer_mechanism`, so a reader that wants the
    host to measure or route never has to parse an `@`.
    """

    assert TABLE["claude-code"]["instruction_file"] == "CLAUDE.md"
    assert TABLE["codex"]["instruction_file"] == "AGENTS.md"
    for name, row in TABLE.items():
        assert "@" not in (row["instruction_file"] or ""), name


def test_a_declared_cap_carries_its_provenance_note() -> None:
    for name, row in TABLE.items():
        if row["doc_byte_cap"] is not None:
            assert row.get("note"), f"{name} declares a byte cap with no source note"


def test_only_a_pointer_row_says_when_its_harness_reads_agents_md_itself() -> None:
    """`reads_agents_md` names the files that stop a harness reading AGENTS.md itself.

    Only a FILE@REF row can need a pointer at all, so only such a row may say
    when its harness does without one; every other row records null.
    """

    assert TABLE["claude-code"]["reads_agents_md"] == {
        "unless": ["CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md"],
        "since": "2.1.281",
    }
    for name, row in TABLE.items():
        assert "reads_agents_md" in row, name
        if name != "claude-code":
            assert row["reads_agents_md"] is None, name
        if row["reads_agents_md"] is not None:
            assert "@" in row["pointer_mechanism"], name


def test_every_row_names_its_files_config_and_recheck_date() -> None:
    """The harness table's loading fields.

    A row keeps one `verified_on` and gains one `recheck_on` after it; a key
    list no source settles is null, never an empty list standing in for one.
    """

    for name, row in TABLE.items():
        assert row["reads"] or row["overrides"], f"{name} names no instruction file"
        assert row["config"]["paths"], f"{name} names no project configuration file"
        assert set(row["config"]["keys"]) == {
            "hooks",
            "tool_servers",
            "enable_all",
            "endpoints",
            "bypass",
            "deny",
        }, name
        assert row["recheck_on"] > (row["verified_on"] or ""), name


def test_a_file_that_hides_agents_md_is_one_the_row_already_names() -> None:
    """`hides_agents_md` agrees with the row's `reads_agents_md.unless` list."""

    for name, row in TABLE.items():
        hiding = {read["path"] for read in row["reads"] if read["hides_agents_md"]}
        unless = set((row["reads_agents_md"] or {}).get("unless", []))
        assert hiding <= unless, name


def test_the_table_holds_no_finish_hook_and_the_audit_still_reads_each_hook_file() -> None:
    """The finish check is retired, so no row names a hook entry adopt writes, and the schema
    admits none; a committed hook is still read by `outcomebound instructions check` in the two
    settings documents that 1.6.0 wrote entries into.

    Breaks if a row or the schema gains a `finish_hook` again, or if either settings document
    drops out of `config.paths`, so a committed hook would run unread.
    """

    assert all("finish_hook" not in row for row in TABLE.values())
    assert "finish_hook" not in ROW_SCHEMA["properties"]
    assert "finish_hook" not in ROW_SCHEMA["required"]
    assert ".claude/settings.json" in TABLE["claude-code"]["config"]["paths"]
    assert ".codex/hooks.json" in TABLE["codex"]["config"]["paths"]
    for name in ("claude-code", "codex"):
        assert "hooks" in TABLE[name]["config"]["keys"]["hooks"], name
