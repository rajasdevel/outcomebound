"""`outcomebound brief lookup`: the `Decided:` line's grammar, the brief search by id and words,
the roots, the JSON documents, the report's shape, and that nothing is written."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from outcomebound_tools import brief_lookup, decision_brief
from outcomebound_tools.schemacheck import validate

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schemas/brief-lookup.schema.json").read_text("utf-8"))
LINE = 'Decided: D7 · A · Pat · 2026-10-17 · "keep it"'


def put(folder: Path, name: str, text: str) -> Path:
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")
    return path


def lookup(*terms: str, roots: list[Path]) -> dict:
    return brief_lookup.search(terms, roots)


def doc(*pairs: tuple[str, str]) -> str:
    briefs = [
        {
            "id": i,
            "heading": h,
            "undo": {"can_be_undone": True, "text": "yes"},
            "checked": {"verdicts": ["PASS"], "text": "t"},
        }
        for i, h in pairs
    ]
    return json.dumps({"briefs": briefs})


def test_an_answered_and_an_unanswered_brief(tmp_path):
    put(tmp_path, "h.md", f"### D7 · Keep the old flag?\n\n{LINE}\n\n### D8 · Tag it?\n")
    found = lookup("flag", roots=[tmp_path])
    [match] = found["matches"]
    assert match["status"] == "ANSWERED" and match["answers"][0]["words"] == "keep it"
    assert match["answers"][0]["way"] == "A" and match["line"] == 1
    [other] = lookup("d8", roots=[tmp_path])["matches"]
    assert other["status"] == "UNANSWERED" and other["answers"] == []


@pytest.mark.parametrize(
    "line",
    [
        f"- {LINE}",
        f"> {LINE}",
        f"  1. {LINE}",
        'Decided: D7 | A | Pat | 2026-10-17 | "keep it"',
        "Decided: D7 · A · Pat · 2026-10-17 · “keep it”",
        '**Decided:** D7 · A · Pat · 2026-10-17 · "say "keep" or drop"',
        'Decided: D7 · A · Pat · 2026-10-17 · ""',
    ],
)
def test_forms_that_are_answers(tmp_path, line):
    put(tmp_path, "h.md", f"### D7 · Q?\n\n{line}\n")
    [match] = lookup("D7", roots=[tmp_path])["matches"]
    assert match["status"] == "ANSWERED"


@pytest.mark.parametrize(
    "line",
    [
        "Decided: D7 · A · Pat · 2026-10-17",
        'Decided: D7 · A · Pat · 2026-13-40 · "x"',
        'Decided: D7 · A · Pat · 17 Oct · "x"',
        "Decided: D7 · A · Pat · 2026-10-17 · keep it",
        'Decided: D7 · A · Pat · 2026-10-17 | "x"',
    ],
)
def test_forms_that_are_malformed_and_count_as_no_answer(tmp_path, line):
    put(tmp_path, "h.md", f"### D7 · Q?\n\n{line}\n")
    found = lookup("D7", roots=[tmp_path])
    assert found["matches"][0]["status"] == "UNANSWERED"
    assert [m["line"] for m in found["malformed"]] == [3]


def test_prose_and_fenced_lines_are_not_candidates(tmp_path):
    put(tmp_path, "h.md", f"### D7 · Q?\n\nWe Decided: soon.\n\n```\n{LINE}\n```\n")
    found = lookup("D7", roots=[tmp_path])
    assert found["matches"][0]["status"] == "UNANSWERED" and found["malformed"] == []


def test_two_answers_print_oldest_first_and_an_orphan_answer_is_reported(tmp_path):
    put(tmp_path, "a.md", '### D7 · Q?\n\nDecided: D7 · B · Pat · 2026-10-18 · "no"\n')
    put(tmp_path, "b.md", f'{LINE}\n\nDecided: D9 · A · Pat · 2026-10-01 · "y"\n')
    [match] = lookup("D7", roots=[tmp_path])["matches"]
    assert [a["way"] for a in match["answers"]] == ["A", "B"]
    [orphan] = lookup("d9", roots=[tmp_path])["matches"]
    assert orphan["status"] == "BRIEF_NOT_FOUND" and "heading" not in orphan
    assert orphan["source"].endswith("b.md") and orphan["line"] == 3


def test_the_id_is_matched_whole_and_a_prefixed_id_is_given_whole(tmp_path):
    put(tmp_path, "h.md", "### fix-login-D1 · Which store?\n\n### D12 · Other?\n")
    assert lookup("D1", roots=[tmp_path])["matches"] == []
    assert [m["id"] for m in lookup("fix-login-D1", roots=[tmp_path])["matches"]] == [
        "fix-login-D1"
    ]
    assert [m["id"] for m in lookup("which", "STORE", roots=[tmp_path])["matches"]] == [
        "fix-login-D1"
    ]
    assert lookup("which", "other", roots=[tmp_path])["matches"] == []


def test_review_findings_are_not_briefs(tmp_path):
    put(tmp_path, "r.md", "Reviewed: abc\n\n### F1 · Off by one\n\nDisposition: fixed — x\n")
    assert lookup("F1", roots=[tmp_path])["matches"] == []


def test_json_documents_only_when_they_are_briefs_documents(tmp_path):
    put(tmp_path, "b.json", doc(("D3", "Ship it?")))
    put(tmp_path, "bad.json", json.dumps({"briefs": [{"id": "D4"}]}))
    put(tmp_path, "other.json", json.dumps({"x": 1}))
    put(tmp_path, "broken.json", "{")
    found = lookup("ship", roots=[tmp_path])
    assert [m["id"] for m in found["matches"]] == ["D3"] and "line" not in found["matches"][0]
    assert len(found["not_read"]) == 1 and "bad.json" in found["not_read"][0]


def test_a_term_is_never_a_path_and_in_names_the_roots(tmp_path, monkeypatch, capsys):
    folder = tmp_path / "d7"
    put(folder, "h.md", "### D7 · Q?\n")
    monkeypatch.chdir(tmp_path)
    assert brief_lookup.main(["D7", "--in", str(folder)]) == 0
    assert capsys.readouterr().out.startswith("1 match(es); searched ")
    assert brief_lookup.main(["D7", "--in", str(tmp_path / "none")]) == 1
    assert capsys.readouterr().out.startswith("LOOKUP_UNREADABLE:")
    with pytest.raises(SystemExit) as stop:
        brief_lookup.main(["--in", str(folder)])
    assert stop.value.code == 2


def test_default_roots_include_the_main_checkout_of_a_worktree(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    main = tmp_path / "main"
    put(main, ".agents/work/x/h.md", "### D7 · Q?\n")
    put(main, "f.txt", "x")
    ident = ["-c", "user.name=T", "-c", "user.email=t@e.test", "-c", "commit.gpgsign=false"]
    for args in (["init", "-q", "-b", "main"], ["add", "f.txt"], [*ident, "commit", "-qm", "c"]):
        subprocess.run(["git", *args], cwd=main, check=True, capture_output=True)
    tree = tmp_path / "tree"
    subprocess.run(
        ["git", "worktree", "add", "-q", str(tree)], cwd=main, check=True, capture_output=True
    )
    roots = [r.resolve() for r in brief_lookup.default_roots(tree)]
    assert (main / ".agents/work").resolve() in roots
    assert lookup("D7", roots=roots)["matches"]


def test_json_report_matches_its_schema_and_nothing_is_written(tmp_path, capsys):
    put(tmp_path, "h.md", f"### D7 · Q?\n\n{LINE}\n\nDecided: D7 · broken\n")
    put(tmp_path, "b.json", doc(("D3", "Ship?")))
    before = sorted(p.name for p in tmp_path.iterdir())
    assert brief_lookup.main(["d7", "--in", str(tmp_path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert validate(out, SCHEMA) == [] and out["matches"][0]["answers"][0]["date"] == "2026-10-17"
    assert before == sorted(p.name for p in tmp_path.iterdir())


def test_brief_dispatches_lookup_and_still_draws_a_document(tmp_path, capsys):
    put(tmp_path, "h.md", "### D7 · Q?\n")
    assert decision_brief.main(["lookup", "D7", "--in", str(tmp_path)]) == 0
    assert "1 match(es)" in capsys.readouterr().out
    # A document named `lookup` is still read as a document, given as `./lookup`.
    assert decision_brief.main(["./lookup"]) == 2
    assert "cannot read ./lookup" in capsys.readouterr().err
