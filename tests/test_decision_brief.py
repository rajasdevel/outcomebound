"""The one place a decision brief is drawn.

The seams are `decision_brief.render`, `diagram` and `symbols_for`, asked over
values built here. A brief's own diagram is asked of `render`, where it is drawn.
"""

from __future__ import annotations

import ast
import io
import re
from collections import Counter
from itertools import pairwise
from pathlib import Path

import pytest

from outcomebound_tools.decision_brief import (
    MARKS,
    NOTHING_WAITS,
    SEPARATORS,
    Brief,
    Diagram,
    checked_mark,
    diagram,
    render,
    symbols_for,
)

REPOSITORY = Path(__file__).resolve().parent.parent

# An order: `A2` waits on `D1` and on `C3`.
ORDER = (("D1", "A2"), ("C3", "A2"))
# A chain: `H28` waits on `H9`, and `H1` on both.
CHAIN = (("H9", "H28"), ("H9", "H1"), ("H28", "H1"))

# The worked drawings: each order, and the lines its `text` fence holds.
W1_ONE_EDGE = (("D1", "A2"),)
W2_CHAIN = CHAIN
W3_FAN_OUT = (("D1", "A2"), ("D1", "C3"))
W4_FAN_IN = ORDER
W5_DIAMOND = (("D1", "A2"), ("D1", "A3"), ("A2", "H4"), ("A3", "H4"))
W6_TWO_CHAINS = (("D1", "A2"), ("C3", "H4"), ("A2", "H5"))
W7_BRANCH = (("D1", "A2"), ("A2", "C3"), ("A2", "H4"))
W8_HEAD_GIVEN_LAST = (("H2", "H3"), ("H2", "H4"), ("H1", "H2"))
W9_LONG_PATH = (("D1", "A2"), ("A2", "C3"), ("C3", "H4"), ("D1", "H4"))
W10_FIRST_EDGE_DROPPED = (("D1", "C3"), ("D1", "A2"), ("A2", "C3"))
W11_PAIR_TWICE = (("D1", "A2"), ("D1", "A2"))
K1_CIRCLE_BESIDE_ORDER = (("H3", "H5"), ("H5", "H3"), ("H7", "H9"), ("H9", "H8"), ("H7", "H8"))
K2_TWO_CIRCLES = (("H3", "H5"), ("H5", "H3"), ("H7", "H7"))

K1_DRAWN = """### Order — an arrow points at what waits on it
```text
H3 --> H5
H5 --> H3
H7 --> H9
H9 --> H8
H7 --> H8
```
- In a circle: H3, H5 — these wait on each other, so no order exists among them and every \
edge is drawn on its own line"""


AMEND = "amend CONTRIBUTING so a long-lived integration branch lands by one merge commit"


def _contributing(symbols: str) -> Brief:
    """A worked example, its heading composed with `symbols`' separator."""

    sep, _ = SEPARATORS[symbols]
    return Brief(
        heading=(
            f"D1{sep}CONTRIBUTING says no merge commits, and the last release landed as one: which"
            " gives way?"
        ),
        recommend=(
            "the rule then says what this project already does, and the next integration"
            " branch needs no exception"
        ),
        recommend_way=AMEND,
        confidence="80% (inferred)",
        options=(
            (
                AMEND,
                "the rule matches how the last release landed",
                "a reviewer does not flag a merge commit on main",
            ),
            (
                "keep the rule and record the last release as its one exception",
                "the rule stays strict",
                "every later integration branch asks again",
            ),
        ),
        checked=("checked", "`git log --merges main` shows the last release as a merge commit"),
        not_checked="whether another contributor relies on the rule as written",
    )


# The worked example as the renderer draws it under `emoji`, byte for byte.
CONTRIBUTING_DRAWN = (
    "### D1 · CONTRIBUTING says no merge commits, and the last release landed as one: which"
    " gives way?\n"
    "- 👉 Recommend: A — the rule then says what this project already does, and the next"
    " integration branch needs no exception · confidence 80% (inferred)\n"
    "- Options:\n"
    "  - A amend CONTRIBUTING so a long-lived integration branch lands by one merge commit"
    " — the rule matches how the last release landed\n"
    "    - 🔻 Downside: a reviewer does not flag a merge commit on main\n"
    "  - B keep the rule and record the last release as its one exception"
    " — the rule stays strict\n"
    "    - 🔻 Downside: every later integration branch asks again\n"
    "- ✅ Checked: `git log --merges main` shows the last release as a merge commit\n"
    "- ⚠️ Not checked: whether another contributor relies on the rule as written\n"
)


def _every_field(heading: str) -> Brief:
    return Brief(
        heading=heading,
        recommend="it is reverted in one step",
        recommend_way="take it",
        confidence="fact",
        options=(
            ("take it", "it lands today", "the release notes lag a day"),
            ("leave it", "it waits a week", "the fix waits with it"),
        ),
        why_now="unblocks #4",
        asked=("the reviewer signs off", "the owner signs off"),
        checked=("checked", "build PASS"),
        not_checked="the release notes",
        debt="one test marked slow",
        undo=("cannot_be_undone", "the tag is pushed"),
    )


def test_the_worked_example_is_what_the_renderer_prints() -> None:
    """The worked example is drawn exactly as the golden above holds it."""

    assert render([_contributing("emoji")], "emoji") == CONTRIBUTING_DRAWN


def test_every_mark_has_both_spellings_and_none_is_a_checkbox() -> None:
    """Each mark is spelled under both symbol sets, and no `ascii` mark is one a
    markdown view draws as a checkbox."""

    assert list(MARKS["emoji"]) == list(MARKS["ascii"])
    assert set(MARKS) == set(SEPARATORS) == {"emoji", "ascii"}
    assert MARKS["ascii"]["cannot_be_undone"] == "[!!]"
    assert not {"[ ]", "[x]", "[X]"} & set(MARKS["ascii"].values())


@pytest.mark.parametrize(
    ("verdicts", "mark"),
    [
        (("PASS",), "checked"),
        (("PASS", "PASS"), "checked"),
        ((), "unchecked"),
        (("PASS", "FAIL"), "unchecked"),
        (("UNVERIFIED",), "unchecked"),
        (("RUN_UNVERIFIED",), "unchecked"),
        (("pass",), "unchecked"),
    ],
)
def test_a_checked_line_passes_only_where_every_verdict_is_pass(
    verdicts: tuple[str, ...], mark: str
) -> None:
    """The passed mark only for verdicts that are not empty and are `PASS` alone,
    exactly: no verdict at all, any other word, and `pass` are not passed."""

    assert checked_mark(verdicts) == mark


def test_no_surface_chooses_the_passed_mark_itself() -> None:
    """No engine module but `decision_brief` names the `checked` mark key, so every
    surface reaches the passed mark through `checked_mark` alone."""

    engine = REPOSITORY / "outcomebound_tools"
    named = [
        f"{path.name}:{node.lineno}"
        for path in sorted(engine.rglob("*.py"))
        if path.name != "decision_brief.py"
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant) and node.value == "checked"
    ]
    assert named == []


def test_no_surface_letters_an_option_itself() -> None:
    """No engine module but `decision_brief` reads `ascii_uppercase` or spells the
    alphabet out, so an Option and a recommended way are lettered in one place."""

    engine = REPOSITORY / "outcomebound_tools"
    lettering = [
        f"{path.name}:{node.lineno}"
        for path in sorted(engine.rglob("*.py"))
        if path.name != "decision_brief.py"
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if (isinstance(node, ast.Attribute) and node.attr == "ascii_uppercase")
        or (isinstance(node, ast.Constant) and "ABCDEFGHIJKLMNOPQRSTUVWXYZ" in str(node.value))
    ]
    assert lettering == []


@pytest.mark.parametrize("symbols", ["emoji", "ascii"])
def test_briefs_are_headings_and_lists_separated_by_one_blank_line(symbols: str) -> None:
    """Every line a markdown view could join to the one above is a list item, and
    nothing is fenced; only a downside, a list item nested under its Option, is
    indented four spaces."""

    text = render([_every_field("X1"), Brief(heading="X2")], symbols)

    assert text.endswith("\n") and not text.endswith("\n\n")
    blocks = text[:-1].split("\n\n")
    assert len(blocks) == 2
    for block in blocks:
        first, *rest = block.split("\n")
        assert first.startswith("### ")
        for line in rest:
            assert line.startswith(("- ", "  - ", f"    - {MARKS[symbols]['downside']} ")), line
    assert len(blocks[0].split("\n")) == 14, "every field of the first brief is written"


def test_the_ascii_spelling_differs_only_in_marks_and_separators() -> None:
    """The worked example under `ascii`, its marks and separators respelled, is the
    `emoji` rendering line for line, a nested option's dash included."""

    emoji = render([_contributing("emoji")], "emoji").splitlines()
    plain = render([_contributing("ascii")], "ascii").splitlines()
    twins = [(MARKS["ascii"][key], MARKS["emoji"][key]) for key in MARKS["ascii"]]
    twins += list(zip(SEPARATORS["ascii"], SEPARATORS["emoji"], strict=True))

    respelled = []
    for line in plain:
        lead = re.match(r"### |- |  - |    - ", line)
        assert lead is not None, line
        rest = line[lead.end() :]
        for spelled, symbol in twins:
            rest = rest.replace(spelled, symbol)
        respelled.append(lead.group() + rest)
    assert respelled == emoji
    assert "\n".join(plain).isascii()


def test_a_brief_writes_only_the_lines_it_is_given() -> None:
    """An empty field writes no line: no placeholder, and no ` · confidence` alone."""

    assert render([Brief(heading="X")], "ascii") == "### X\n"
    assert render([Brief(heading="X", recommend="do it", debt="d")], "ascii") == (
        "### X\n- [>] Recommend: do it\n- [debt] Debt: d\n"
    )


@pytest.mark.parametrize("symbols", ["emoji", "ascii"])
def test_each_downside_is_nested_under_its_option_behind_its_own_mark(symbols: str) -> None:
    """An Option given with its downside is followed by the downside, nested under it
    and behind the `downside` mark; one given without a downside, as a surface that
    knows none gives it, writes no downside line."""

    _, dash = SEPARATORS[symbols]
    mark = MARKS[symbols]["downside"]
    options = (("x", "one place", "it costs a day"), ("y", "another"))

    lines = render([Brief(heading="X", options=options)], symbols).splitlines()

    assert lines[1:] == [
        "- Options:",
        f"  - A x{dash}one place",
        f"    - {mark} Downside: it costs a day",
        f"  - B y{dash}another",
    ]


def test_one_option_is_refused() -> None:
    """A single way forward is not a choice, and is not laid out as a lettered list."""

    with pytest.raises(ValueError) as refused:
        render([Brief(heading="X", options=(("amend", "the rule matches"),))], "ascii")

    assert str(refused.value).endswith("this one lays out 1")


def test_more_options_than_letters_are_refused() -> None:
    """Options are lettered `A` to `Z`; a 27th has no letter, and is refused in words
    rather than failing on the lookup."""

    options = tuple((f"way {index}", "somewhere") for index in range(27))

    assert render([Brief(heading="X", options=options[:26])], "ascii").endswith(
        "  - Z way 25 - somewhere\n"
    )
    with pytest.raises(ValueError) as refused:
        render([Brief(heading="X", options=options)], "ascii")

    assert str(refused.value) == (
        "a brief letters its Options from A to Z, so it lays out at most 26; this one lays out 27"
    )


def test_a_confidence_without_a_recommendation_is_refused() -> None:
    """A confidence is never dropped without a word, nor printed on a line of its own."""

    with pytest.raises(ValueError) as refused:
        render([Brief(heading="X", confidence="fact")], "ascii")

    assert str(refused.value) == (
        "a brief's confidence belongs to its Recommend line, and this one has none"
    )


# Two ways forward, for the recommended-way tests.
TWO_WAYS = (("x", "one place"), ("y", "another"))


@pytest.mark.parametrize("symbols", ["emoji", "ascii"])
def test_a_recommended_way_is_lettered_by_the_renderer(symbols: str) -> None:
    """The renderer writes the letter of the Option whose way the surface names,
    and the surface's text after it, as given."""

    text = render(
        [Brief(heading="X", recommend="y, since R", options=TWO_WAYS, recommend_way="y")],
        symbols,
    )

    _, dash = SEPARATORS[symbols]
    recommend = f"- {MARKS[symbols]['recommend']} Recommend: B{dash}y, since R"
    assert text.splitlines()[1] == recommend


def test_a_recommended_way_not_among_the_options_is_refused() -> None:
    """A letter that names no Option is never drawn: the way is refused in words."""

    with pytest.raises(ValueError) as refused:
        render(
            [Brief(heading="X", recommend="z, since R", options=TWO_WAYS, recommend_way="z")],
            "ascii",
        )

    assert (
        str(refused.value)
        == "a brief letters only a way it lays out, and 'z' is not among its Options"
    )


def test_an_options_leads_to_text_is_not_a_way_it_lays_out() -> None:
    """Only an Option's way is matched: its leads-to text is refused in words, like
    any other way the brief does not lay out."""

    with pytest.raises(ValueError) as refused:
        render(
            [Brief(heading="X", recommend="R", options=TWO_WAYS, recommend_way="another")],
            "ascii",
        )

    assert str(refused.value) == (
        "a brief letters only a way it lays out, and 'another' is not among its Options"
    )


def test_a_recommended_way_without_a_recommendation_is_refused() -> None:
    """A recommended way belongs to a Recommend line, and is never drawn without one."""

    with pytest.raises(ValueError) as refused:
        render([Brief(heading="X", options=TWO_WAYS, recommend_way="y")], "ascii")

    assert str(refused.value) == (
        "a brief's recommended way belongs to its Recommend line, and this one has none"
    )


def test_a_missing_recommendation_is_refused_before_an_unknown_way() -> None:
    """A brief wrong on both counts is refused for the missing Recommend line first,
    in the order the refusals are listed."""

    with pytest.raises(ValueError) as refused:
        render([Brief(heading="X", options=TWO_WAYS, recommend_way="z")], "ascii")

    assert str(refused.value) == (
        "a brief's recommended way belongs to its Recommend line, and this one has none"
    )


def test_nothing_to_render_says_nothing_waits() -> None:
    """An empty rundown is one line a reader cannot mistake for a crash."""

    assert render([], "ascii") == NOTHING_WAITS == "nothing waits on a person\n"


@pytest.mark.parametrize(
    ("encoding", "symbols"),
    [("ascii", "ascii"), ("cp1252", "ascii"), ("latin-1", "ascii"), ("utf-8", "emoji")],
)
def test_symbols_follow_what_the_stream_can_encode(encoding: str, symbols: str) -> None:
    """`ascii` wherever the stream's own encoding cannot carry every emoji mark and
    separator, `cp1252`'s dash and middle dot notwithstanding."""

    assert symbols_for(io.TextIOWrapper(io.BytesIO(), encoding=encoding)) == symbols


def test_a_stream_that_names_no_encoding_is_read_as_utf8() -> None:
    assert symbols_for(io.StringIO()) == "emoji"


def test_the_order_follows_the_last_brief_and_only_where_there_is_one() -> None:
    """The diagram is one more block after the last brief, and absent without an order."""

    briefs = [Brief(heading="a"), Brief(heading="b", why_now="unblocks #2")]
    order = (("D1", "A2"),)

    drawn = render(briefs, "emoji", order, "mermaid")
    assert drawn == render(briefs, "emoji") + "\n" + diagram(order, "emoji", "mermaid") + "\n"

    plain = render(briefs, "emoji", (), "mermaid")
    assert not [line for line in plain.splitlines() if line.startswith("### Order")]


@pytest.mark.parametrize(
    ("order", "lines"),
    [
        (W1_ONE_EDGE, ["D1 --> A2"]),
        (W2_CHAIN, ["H9 --> H28 --> H1"]),
        (W3_FAN_OUT, ["D1 --> A2", "D1 --> C3"]),
        (W4_FAN_IN, ["D1 --> A2", "C3 --> A2"]),
        (W5_DIAMOND, ["D1 --> A2 --> H4", "D1 --> A3 --> H4"]),
        (W6_TWO_CHAINS, ["D1 --> A2 --> H5", "C3 --> H4"]),
        (W7_BRANCH, ["D1 --> A2 --> C3", "A2 --> H4"]),
        (W8_HEAD_GIVEN_LAST, ["H1 --> H2 --> H3", "H2 --> H4"]),
        (W9_LONG_PATH, ["D1 --> A2 --> C3 --> H4"]),
        (W10_FIRST_EDGE_DROPPED, ["D1 --> A2 --> C3"]),
        (W11_PAIR_TWICE, ["D1 --> A2"]),
    ],
    ids=[
        "one-edge",
        "chain",
        "fan-out",
        "fan-in",
        "diamond",
        "two-chains",
        "branch",
        "head-given-last",
        "long-path",
        "first-edge-dropped",
        "pair-twice",
    ],
)
def test_the_ascii_order_is_drawn_as_chains(
    order: tuple[tuple[str, str], ...], lines: list[str]
) -> None:
    """The order is its transitive reduction, one chain per line, each starting at an
    entry no undrawn edge points at; a pair given twice is drawn once."""

    assert diagram(order, "ascii") == (
        "### Order - an arrow points at what waits on it\n```text\n" + "\n".join(lines) + "\n```"
    )


def _ascii_edges(drawn: str) -> list[tuple[str, str]]:
    """Each neighbouring pair of labels on the lines of an ASCII order's fence."""

    body = drawn.splitlines()[2:-1]
    edges: list[tuple[str, str]] = []
    for line in body:
        edges.extend(pairwise(line.split(" --> ")))
    return edges


def _mermaid_edges(drawn: str) -> list[tuple[str, str]]:
    """Each `(before, after)` a Mermaid order's fence draws."""

    return re.findall(r'^  n\d+\["([^"]+)"\] --> n\d+\["([^"]+)"\]$', drawn, flags=re.M)


@pytest.mark.parametrize(
    "order",
    [
        W1_ONE_EDGE,
        W2_CHAIN,
        W3_FAN_OUT,
        W4_FAN_IN,
        W5_DIAMOND,
        W6_TWO_CHAINS,
        W7_BRANCH,
        W8_HEAD_GIVEN_LAST,
        W9_LONG_PATH,
        W10_FIRST_EDGE_DROPPED,
        W11_PAIR_TWICE,
    ],
)
def test_the_ascii_and_mermaid_forms_draw_the_same_edges(
    order: tuple[tuple[str, str], ...],
) -> None:
    """Both forms draw the same edges of the reduction, each exactly once."""

    ascii_edges = Counter(_ascii_edges(diagram(order, "emoji", "ascii")))
    mermaid_edges = Counter(_mermaid_edges(diagram(order, "emoji", "mermaid")))

    assert ascii_edges == mermaid_edges
    assert set(ascii_edges.values()) == {1}


def test_mermaid_draws_the_reduction_with_the_ids_it_gave_before() -> None:
    """Mermaid ids are numbered over the order as given, so a label whose first
    edge the reduction drops keeps its id; a pair given twice is drawn once."""

    drawn = diagram(W10_FIRST_EDGE_DROPPED, "emoji", "mermaid")
    assert drawn.split("```mermaid\nflowchart LR\n", 1)[1] == (
        '  n1["D1"] --> n3["A2"]\n  n3["A2"] --> n2["C3"]\n```'
    )

    twice = diagram(W11_PAIR_TWICE, "emoji", "mermaid")
    assert twice.splitlines().count('  n1["D1"] --> n2["A2"]') == 1


def test_entries_waiting_on_each_other_are_drawn_edge_by_edge_and_named() -> None:
    """An order holding a circle is drawn edge by edge, nothing left out, and one
    list item after the fence names each circle, in either form."""

    assert diagram(K1_CIRCLE_BESIDE_ORDER, "emoji", "ascii") == K1_DRAWN
    item = K1_DRAWN.splitlines()[-1]
    assert diagram(K1_CIRCLE_BESIDE_ORDER, "emoji", "mermaid").endswith("\n```\n" + item)
    assert Counter(_mermaid_edges(diagram(K1_CIRCLE_BESIDE_ORDER, "emoji", "mermaid"))) == Counter(
        K1_CIRCLE_BESIDE_ORDER
    )

    assert (
        diagram(K2_TWO_CIRCLES, "emoji").splitlines()[-1].startswith("- In a circle: H3, H5; H7 — ")
    )
    # Two circles joined by one edge stay two circles (each member reaches the other),
    # and members and circles are named by rank, not by label.
    joined = (("H9", "H10"), ("H10", "H9"), ("H10", "H3"), ("H3", "H5"), ("H5", "H3"))
    assert diagram(joined, "ascii").splitlines()[-1].startswith("- In a circle: H9, H10; H3, H5 - ")


# The design's worked diagram: how an upgrade reads the flag.
FLAG = Diagram(
    edges=(("config", "warning", "old_flag"), ("warning", "new flag", "")),
    caption="How an upgrade reads the flag",
)
FLAG_MERMAID = """How an upgrade reads the flag
```mermaid
flowchart LR
  n1["config"] -->|old_flag| n2["warning"]
  n2["warning"] --> n3["new flag"]
```"""
FLAG_ASCII = """How an upgrade reads the flag
```text
config --old_flag--> warning --> new flag
```"""


@pytest.mark.parametrize(("form", "drawn"), [("mermaid", FLAG_MERMAID), ("ascii", FLAG_ASCII)])
def test_a_briefs_diagram_is_its_own_block_after_its_list(form: str, drawn: str) -> None:
    """A brief's diagram follows its list as a block of its own, caption first, and
    comes before the next brief and before the order, all in the one form."""

    briefs = [Brief(heading="D1", diagram=FLAG), Brief(heading="D2")]
    order = (("D1", "D2"),)

    blocks = render(briefs, "emoji", order, form)[:-1].split("\n\n")

    assert blocks[:3] == ["### D1", drawn, "### D2"]
    assert blocks[3] == diagram(order, "emoji", form)


def test_a_diagram_without_a_caption_opens_with_its_fence() -> None:
    bare = Diagram(edges=(("a", "b", ""),))
    blocks = render([Brief(heading="X", diagram=bare)], "ascii")[:-1].split("\n\n")
    assert blocks[1] == "```text\na --> b\n```"


def _diagram_edges(drawn: str) -> Counter[tuple[str, str, str]]:
    """Each `(from, to, label)` a brief's drawn diagram shows, in either form."""

    if "```mermaid" in drawn:
        found = re.findall(
            r'^  n\d+\["([^"]+)"\] -->(?:\|([^|]+)\|)? n\d+\["([^"]+)"\]$', drawn, flags=re.M
        )
        return Counter((source, target, label) for source, label, target in found)
    edges: Counter[tuple[str, str, str]] = Counter()
    for line in drawn.split("```text\n", 1)[1].split("\n```", 1)[0].splitlines():
        labels = re.split(r" --(?:([^ ]+)--)?> ", line)
        nodes, arrows = labels[::2], labels[1::2]
        for (source, target), label in zip(pairwise(nodes), arrows, strict=True):
            edges[(source, target, label or "")] += 1
    return edges


# A diagram whose longer path already shows its last edge, a loop, and a pair drawn
# twice under two labels: each edge is drawn exactly as given.
UNREDUCED = (
    ("plan", "build", ""),
    ("build", "ship", ""),
    ("plan", "ship", "hotfix"),
    ("ship", "plan", "next"),
    ("build", "ship", "retry"),
)


@pytest.mark.parametrize("form", ["mermaid", "ascii"])
def test_a_briefs_diagram_draws_every_edge_as_given_and_none_reduced(form: str) -> None:
    """Unlike the order among briefs, a brief's own diagram is never reduced: an edge
    a longer path shows, one closing a loop, and two between the same nodes are
    each drawn exactly once."""

    text = render([Brief(heading="X", diagram=Diagram(edges=UNREDUCED))], "ascii", (), form)

    assert _diagram_edges(text) == Counter(UNREDUCED)


def test_mermaid_numbers_a_diagrams_nodes_by_first_appearance() -> None:
    """Mermaid ids are `n1`, `n2`, … in the order a label first appears, so a label
    such as `new flag` is never a node id and a node drawn twice keeps its id."""

    text = render([Brief(heading="X", diagram=Diagram(edges=UNREDUCED))], "ascii", (), "mermaid")

    ids = re.findall(r'^  (n\d+)\["[^"]+"\] -->(?:\|[^|]+\|)? (n\d+)\["', text, flags=re.M)
    assert ids == [
        ("n1", "n2"),
        ("n2", "n3"),
        ("n1", "n3"),
        ("n3", "n1"),
        ("n2", "n3"),
    ]
