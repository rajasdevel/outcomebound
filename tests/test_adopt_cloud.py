"""The cloud note an install and a check print, and the data it is drawn from.

A cloud session starts from a fresh clone without the `outcomebound` command. The note names
the pinned install line and where each harness keeps its setup step; it writes nothing. The
note is output a person acts on, so these tests read the printed lines; the data file is held
to the shape the note reads, each entry carrying its source and read date.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from outcomebound_tools import adapters
from tests.adopt_helpers import ROOT, Capture, engine_copy, repo, run, snapshot

VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
CLOUD = json.loads((ROOT / "adapters/cloud.json").read_text(encoding="utf-8"))
UV = f"uv tool install outcomebound=={VERSION}"
SETUP_LINE = "add the install line to it with --setup, repeating each recorded command"
PIP = f"python3 -m pip install outcomebound=={VERSION}"


def cloud_lines(out: str) -> list[str]:
    """The report's note lines, the cloud note among them."""

    return [line for line in out.splitlines() if line.startswith("note ")]


def test_every_entry_names_its_setup_its_source_and_the_day_it_was_read() -> None:
    """Breaks if an entry loses its source or date, or names a harness the table lacks."""

    assert CLOUD, "the cloud table is empty"
    for name, entry in CLOUD.items():
        assert set(entry) == {"name", "harness", "setup", "read", "source", "says"}, name
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry["read"]), name
        assert entry["source"].startswith("https://"), name
        assert entry["name"] and entry["setup"] and entry["says"], name
        assert entry["harness"] is None or entry["harness"] in adapters.harness_names(), name


def test_an_install_names_the_pinned_line_and_each_selected_harnesss_setup(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if the line is not pinned to the engine's version, if a selected harness's
    setup location is missing, or if one the target does not use is named."""

    target = repo(tmp_path / "t")

    code, out, _ = run(capsys, str(target), "--harness", "claude-code")

    assert code == 0
    text = "\n".join(cloud_lines(out))
    assert UV in text and PIP in text
    assert "Claude Code on the web: the cloud environment's setup script" in text
    assert "GitHub Copilot: .github/workflows/copilot-setup-steps.yml" in text
    assert "Codex cloud" not in text and "Cursor" not in text
    assert SETUP_LINE not in text, "no Setup is recorded, so no line asks to add to it"


def test_the_note_prints_once_and_writes_no_file(tmp_path: Path, capsys: Capture) -> None:
    """Breaks if a harness's setup file or any other file is written for the note, or the
    install line is printed twice."""

    target = repo(tmp_path / "t")
    run(capsys, str(target), "--harness", "cursor")
    before = snapshot(target)

    code, out, _ = run(capsys, str(target), "--harness", "cursor")

    assert code == 0 and snapshot(target) == before
    assert not (target / ".cursor/environment.json").exists()
    assert not (target / ".github/workflows/copilot-setup-steps.yml").exists()
    assert sum(UV in line for line in cloud_lines(out)) == 1
    assert ".cursor/environment.json, the install key" in out


def test_a_dry_run_and_a_check_print_the_note_too(tmp_path: Path, capsys: Capture) -> None:
    target = repo(tmp_path / "t")
    _, dry, _ = run(capsys, str(target), "--harness", "codex", "--dry-run")
    assert UV in dry and "Codex cloud: the environment's setup script" in dry
    run(capsys, str(target), "--harness", "codex")

    code, out, _ = run(capsys, str(target), "--check")

    assert code == 0 and UV in out and "Codex cloud: the environment's setup script" in out
    assert sum(UV in line for line in cloud_lines(out)) == 1


def test_a_recorded_setup_is_asked_to_hold_the_install_line_too(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a project that records a Setup fact is not told to add the line there."""

    target = repo(tmp_path / "t")
    _, out, _ = run(capsys, str(target), "--harness", "claude-code", "--setup", "make setup")
    assert SETUP_LINE in "\n".join(cloud_lines(out))

    _, out, _ = run(capsys, str(target), "--check")
    assert SETUP_LINE in "\n".join(cloud_lines(out))


def test_a_target_with_no_harness_gets_every_entry(tmp_path: Path, capsys: Capture) -> None:
    """The generic route cannot say which harness is used, so each entry is named."""

    target = repo(tmp_path / "t")
    _, out, _ = run(capsys, str(target))
    text = "\n".join(cloud_lines(out))
    for entry in CLOUD.values():
        assert f"{entry['name']}: {entry['setup']}" in text


def test_the_line_follows_the_version_of_the_engine_installing(
    tmp_path: Path, capsys: Capture
) -> None:
    source = engine_copy(tmp_path)
    (source / "VERSION").write_text("9.8.7\n", encoding="utf-8")
    target = repo(tmp_path / "t")

    _, out, _ = run(capsys, str(target), "--harness", "claude-code", source=source)

    assert "uv tool install outcomebound==9.8.7" in out
    assert "python3 -m pip install outcomebound==9.8.7" in out


def test_an_entry_without_a_name_or_setup_is_left_out_and_a_broken_table_is_refused(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a half-written entry prints as `None: None`, or a table that is not JSON
    is read as empty."""

    source = engine_copy(tmp_path)
    table = source / "adapters/cloud.json"
    table.write_text(
        json.dumps({"x": {"harness": None}, "y": "text", "z": CLOUD["github-copilot"]}),
        encoding="utf-8",
    )
    target = repo(tmp_path / "t")

    _, out, _ = run(capsys, str(target), "--harness", "claude-code", source=source)

    assert "None" not in out and "GitHub Copilot: .github/workflows" in out
    table.write_text("{", encoding="utf-8")
    code, out, err = run(capsys, str(repo(tmp_path / "u")), source=source)
    assert code == 1 and "adapters/cloud.json" in err
