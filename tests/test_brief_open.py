"""`outcomebound brief open`: which briefs are open, their order, the collision, `why_now` from
both readers, the report's shape, and that nothing is written."""

from __future__ import annotations

import json
import os
from pathlib import Path

from outcomebound_tools import brief_open, decision_brief
from outcomebound_tools.schemacheck import validate

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schemas/brief-open.schema.json").read_text("utf-8"))


def put(folder: Path, name: str, text: str, when: int = 0) -> Path:
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")
    if when:
        os.utime(path, (when, when))
    return path


def ids(report: dict, key: str = "open") -> list[str]:
    return [e["id"] for e in report[key]]


def test_answered_ids_are_left_out_whatever_the_file_or_case(tmp_path):
    put(tmp_path, "a.md", "### D1 · One?\n\n### D2 · Two?\n\n### D3 · Three?\n")
    put(tmp_path, "b.md", 'Decided: d2 · A · Pat · 2026-10-17 · "y"\nDecided: D3 · broken\n')
    report = brief_open.find_open([tmp_path])
    assert ids(report) == ["D1", "D3"] and report["count"] == 2


def test_newest_source_first_and_why_now_from_markdown_and_json(tmp_path):
    put(
        tmp_path,
        "old.md",
        "### D1 · Old?\n\n⏳ Waiting on this: the release notes\n",
        1_700_050_000,
    )
    brief = {
        "id": "D2",
        "heading": "New?",
        "why_now": "the flag stays",
        "undo": {"can_be_undone": True, "text": "yes"},
        "facts": [["a", "b"]],
    }
    put(tmp_path, "new.json", json.dumps({"briefs": [brief]}), 1_800_000_000)
    report = brief_open.find_open([tmp_path])
    assert ids(report) == ["D2", "D1"]
    assert report["open"][0]["why_now"] == "the flag stays"
    assert report["open"][1]["why_now"] == "the release notes"
    assert report["open"][1]["date"] == "2023-11-15" and report["open"][1]["line"] == 1


def test_equal_dates_order_by_later_path_first_then_earlier_line_first(tmp_path):
    when = 1_750_000_000
    put(tmp_path, "a.md", "### D1 · One?\n\n### D2 · Two?\n", when)
    put(tmp_path, "b.md", "### D3 · Three?\n\n### D4 · Four?\n", when)
    report = brief_open.find_open([tmp_path])
    assert ids(report) == ["D3", "D4", "D1", "D2"]


def test_a_why_now_after_the_next_heading_belongs_to_that_brief(tmp_path):
    put(tmp_path, "a.md", "### D1 · One?\n\n### D2 · Two?\n\n[wait] Waiting on this: x\n")
    one, two = brief_open.find_open([tmp_path])["open"]
    assert "why_now" not in {e["id"]: e for e in (one, two)}["D1"]
    assert {e["id"]: e for e in (one, two)}["D2"]["why_now"] == "x"


def test_one_id_with_two_questions_is_a_collision_and_the_same_question_is_one_brief(tmp_path):
    put(tmp_path, "a.md", "### D1 · Keep the flag?\n\n### D2 · Tag it?\n")
    put(tmp_path, "b.md", "### D1 · Drop the cache?\n\n### D2 · tag  IT?\n")
    report = brief_open.find_open([tmp_path])
    assert ids(report) == ["D2"] and report["count"] == 1
    [collision] = report["collisions"]
    assert collision["id"] == "D1" and len(collision["briefs"]) == 2


def test_an_answered_collision_is_left_out(tmp_path):
    put(tmp_path, "a.md", '### D1 · A?\n\n### D1 · B?\n\nDecided: D1 · A · Pat · 2026-10-17 · ""\n')
    report = brief_open.find_open([tmp_path])
    assert report["open"] == [] and report["collisions"] == []


def test_review_findings_are_not_briefs(tmp_path):
    put(tmp_path, "r.md", "### F1 · Off by one\n\nDisposition: fixed — x\n")
    assert brief_open.find_open([tmp_path])["open"] == []


def test_main_text_json_exit_and_no_writes(tmp_path, capsys):
    put(tmp_path, "a.md", "### D1 · One?\n\n⏳ Waiting on this: w\n")
    before = sorted(p.name for p in tmp_path.iterdir())
    assert brief_open.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("1 open brief(s); 0 collision(s)") and "waits: w" in out
    assert brief_open.main([str(tmp_path), "--json"]) == 0
    assert validate(json.loads(capsys.readouterr().out), SCHEMA) == []
    assert brief_open.main([str(tmp_path / "none")]) == 1
    assert capsys.readouterr().out.startswith("OPEN_UNREADABLE:")
    assert before == sorted(p.name for p in tmp_path.iterdir())


def test_no_default_roots_is_zero_open_and_brief_dispatches_open(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert decision_brief.main(["open"]) == 0
    assert capsys.readouterr().out.startswith("0 open brief(s)")
    assert decision_brief.main(["./open"]) == 2
