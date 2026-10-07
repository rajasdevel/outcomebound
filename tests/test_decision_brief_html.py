"""The HTML drawing of decision briefs: the example brief's marks, lines and order, its
escaping, its diagram and order as `data-diagram` blocks, and the same refusals as the markdown
drawing, which `decision_brief.read_document` shares with `outcomebound brief`."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import decision_brief, decision_brief_html

DOCUMENT: dict[str, Any] = {
    "briefs": [
        {
            "id": "D1",
            "heading": "Keep the old flag for one release?",
            "recommend": "two adopters still set it",
            "recommend_way": "keep it",
            "confidence": "80% (inferred)",
            "options": [
                ["keep it", "adopters get a warning first", "one more release carries old code"],
                ["drop it now", "the code path goes today", "an adopter is refused on upgrade"],
            ],
            "checked": {"verdicts": ["PASS"], "text": "`grep -r old_flag` finds two configs"},
            "facts": [["If unanswered", "the flag stays"]],
            "undo": {"can_be_undone": False, "text": "a pushed tag cannot be taken back"},
            "diagram": {
                "caption": "How an upgrade reads the flag",
                "edges": [["config", "warning", "old_flag"], ["warning", "new flag"]],
            },
        },
        {
            "id": "D2",
            "heading": "Tag the release once D1 is settled?",
            "not_checked": "the hosted run",
            "undo": {"can_be_undone": True, "text": "delete the tag"},
        },
    ],
    "order": [["D1", "D2"]],
}


def write(tmp_path: Path, document: object) -> Path:
    path = tmp_path / "briefs.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def drawn(tmp_path: Path, document: object = DOCUMENT) -> str:
    briefs, order = decision_brief.read_document(write(tmp_path, document))
    return decision_brief_html.render_html(briefs, order)


def test_the_example_brief_is_drawn_with_the_marks_lines_and_order_of_the_markdown(tmp_path):
    page = drawn(tmp_path)

    assert page.startswith('<section class="xp-briefs" id="explorable-briefs"')
    assert '<article class="xp-brief" id="brief-D1" data-brief="D1">' in page
    assert '<span class="xp-brief-id">D1</span> · Keep the old flag' in page
    assert "Recommend: A — two adopters still set it · confidence 80% (inferred)" in page
    assert '<li class="xp-option" data-letter="B">' in page
    assert "🔻</span> Downside: an adopter is refused on upgrade" in page
    assert "⛔</span> Undo: a pushed tag cannot be taken back" in page
    assert '<span class="xp-label">If unanswered</span>: the flag stays' in page
    assert "<code>grep -r old_flag</code>" in page
    lines = [
        page.index(f'class="xp-line {name}')
        for name in ("xp-recommend", "xp-options", "xp-checked", "xp-fact", "xp-undo")
    ]
    assert lines == sorted(lines)


def test_a_diagram_and_the_order_are_data_diagram_blocks_with_their_ascii_fallback(tmp_path):
    page = drawn(tmp_path)

    assert page.count("<pre data-diagram>flowchart LR") == 2
    assert page.count("<pre data-diagram-fallback>") == 2
    assert "config --old_flag--&gt; warning --&gt; new flag" in page
    assert '<figure class="xp-figure xp-order">' in page
    assert "D1 --&gt; D2" in page


def test_a_circle_in_the_order_is_named_beside_its_figure(tmp_path):
    document = copy.deepcopy(DOCUMENT)
    document["order"] = [["D1", "D2"], ["D2", "D1"]]

    assert "In a circle: D1, D2" in drawn(tmp_path, document)


def test_text_with_html_characters_is_escaped(tmp_path):
    document = copy.deepcopy(DOCUMENT)
    document["briefs"][0]["heading"] = 'Is <b>x</b> & "y" safe?'
    document["briefs"][0]["options"][0][0] = "keep <it>"
    document["briefs"][0]["recommend_way"] = "keep <it>"
    document["briefs"][0]["diagram"]["edges"][0][0] = "a<b"

    page = drawn(tmp_path, document)

    assert "<b>x</b>" not in page
    assert "Is &lt;b&gt;x&lt;/b&gt; &amp; &quot;y&quot; safe?" in page
    assert "keep &lt;it&gt;" in page
    assert "a&lt;b" in page


def test_no_brief_draws_nothing():
    assert decision_brief_html.render_html([]) == ""


def test_the_configuration_holds_each_brief_with_its_recommended_letter(tmp_path):
    briefs, _ = decision_brief.read_document(write(tmp_path, DOCUMENT))

    config = decision_brief_html.config_briefs(briefs)

    assert config[0] == {
        "id": "D1",
        "heading": "Keep the old flag for one release?",
        "recommend": "A",
        "options": [{"letter": "A", "way": "keep it"}, {"letter": "B", "way": "drop it now"}],
    }
    assert config[1]["recommend"] is None and config[1]["options"] == []


@pytest.mark.parametrize(
    "change, fragment",
    [
        (lambda d: d["briefs"][0]["options"].pop(), "lays out 1"),
        (lambda d: d["briefs"][0].pop("recommend"), "Recommend"),
        (lambda d: d["briefs"][1].pop("not_checked"), "line of evidence"),
        (lambda d: d["briefs"][0].update(heading="two\nlines"), "does not match pattern"),
    ],
)
def test_the_refusals_are_those_of_the_markdown_drawing(tmp_path, change, fragment):
    document = copy.deepcopy(DOCUMENT)
    change(document)

    with pytest.raises(ValueError, match=fragment):
        decision_brief.read_document(write(tmp_path, document))


def test_a_missing_document_is_refused(tmp_path):
    with pytest.raises(ValueError):
        decision_brief.read_document(tmp_path / "none.json")
