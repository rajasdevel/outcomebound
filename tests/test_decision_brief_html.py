"""The HTML drawing of decision briefs: the example brief's marks, lines and order, its
escaping, and its diagram and order as `data-diagram` blocks. The refusals are those of
`decision_brief.read_document`, which `outcomebound brief` shares, and its tests hold them."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

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


FULL: dict[str, Any] = {
    "briefs": [
        {
            "id": "D1",
            "heading": "Keep the old flag?",
            "why_now": "the notes wait on it",
            "context": ["The flag <b>switches</b> the parser.", ["Two adopters set it."]],
            "terms": [["code path", "the branch the flag selects"]],
            "diagram": {"caption": "How an upgrade reads the flag", "edges": [["a", "b"]]},
            "picture": {"caption": "Before and after", "lines": ["old: a < b", "", "new: b"]},
            "explore": "try how many adopters break",
            "recommend": "two adopters set it",
            "recommend_way": "keep it",
            "confidence": "fact",
            "options": [
                {
                    "way": "keep it",
                    "leads_to": "a warning first",
                    "downside": "one more release",
                    "choose_if": "no adopter may break",
                },
                ["drop it", "the code path goes", "an adopter is refused"],
            ],
            "asked": ["the owner"],
            "checked": {"verdicts": ["PASS"], "text": "grep"},
            "not_checked": "the hosted run",
            "facts": [["Grant", "none"]],
            "debt": "one slow test",
            "undo": {"can_be_undone": True, "text": "revert"},
        }
    ]
}


def test_the_example_brief_is_drawn_with_the_marks_lines_and_order_of_the_markdown(tmp_path):
    page = drawn(tmp_path)

    assert page.startswith('<section class="xp-briefs" id="explorable-briefs"')
    assert '<article class="xp-brief" id="brief-D1" data-brief="D1">' in page
    assert '<span class="xp-brief-id">D1</span> · Keep the old flag' in page
    assert '<li class="xp-option" data-letter="B">' in page
    assert "🔻</span> Downside: an adopter is refused on upgrade" in page
    assert "⛔</span> Undo: a pushed tag cannot be taken back" in page
    assert '<span class="xp-label">If unanswered</span>: the flag stays' in page
    assert "<code>grep -r old_flag</code>" in page


def test_the_recommendation_is_inside_the_option_it_names_and_not_a_paragraph_of_its_own(tmp_path):
    page = drawn(tmp_path)

    first = page.index('data-letter="A"')
    second = page.index('data-letter="B"')
    text = "Recommended: two adopters still set it · 80% (inferred)</p>"
    assert first < page.index(text) < second
    assert page.count("Recommended:") == 1
    assert "xp-recommend" not in page, "a paragraph of its own only without a named way"


def test_the_blocks_are_in_the_order_a_person_decides(tmp_path):
    """Waiting, context, term, diagram, picture, explore, options (the recommendation, the
    condition and the downside in that order inside the option), then the evidence."""

    page = drawn(tmp_path, FULL)

    names = (
        'class="xp-line xp-why"',
        'class="xp-context"',
        'class="xp-context-list"',
        'class="xp-line xp-term"',
        'class="xp-figure"',
        'class="xp-figure xp-picture"',
        'class="xp-line xp-explore"',
        'class="xp-line xp-options"',
        'class="xp-rec-inline"',
        'class="xp-choose"',
        'class="xp-downside"',
        'class="xp-line xp-asked"',
        'class="xp-line xp-checked"',
        'class="xp-line xp-not-checked"',
        'class="xp-line xp-fact"',
        'class="xp-line xp-debt"',
        'class="xp-line xp-undo"',
    )
    positions = [page.index(name) for name in names]
    assert positions == sorted(positions)
    assert "a check shows this" in page


def test_a_picture_is_a_figure_with_a_caption_and_its_lines_escaped_in_a_pre(tmp_path):
    page = drawn(tmp_path, FULL)

    assert (
        '<figure class="xp-figure xp-picture"><figcaption><span class="xp-mark">🗺️</span> '
        "Before and after</figcaption>\n"
        '<pre class="xp-picture-lines">old: a &lt; b\n\nnew: b</pre></figure>'
    ) in page
    assert '<figcaption><span class="xp-mark">🗺️</span> How an upgrade reads the flag' in page
    assert "<b>switches</b>" not in page and "&lt;b&gt;switches&lt;/b&gt;" in page
    assert '<ul class="xp-context-list"><li>Two adopters set it.</li></ul>' in page
    assert "<em>code path</em>: the branch the flag selects" in page


def test_a_recommendation_with_no_named_way_is_a_paragraph_after_the_options():
    """The command's floor refuses such a brief; a surface that draws only what it knows may
    still hold one, and the page draws it as the markdown does."""

    brief = decision_brief.Brief(
        heading="D1 · Q?",
        recommend="do it",
        options=(("a", "b", "c"), ("d", "e", "f")),
        checked=("checked", "grep"),
    )

    page = decision_brief_html.render_html([("D1", brief)])

    assert page.index("</ol>") < page.index('class="xp-line xp-recommend"') < page.index("Checked:")
    assert page.count("Recommended:") == 1


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
