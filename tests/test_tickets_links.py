"""`reads` sections: which one section an anchor names, and how far it runs.

Markdown written into `tmp_path` pins the grammar one decision at a time, and
this repository's own `docs/specs` pins that it reads the documents a ticket will
actually cite, rather than only the examples a test invented.

Every assertion is against the module's public seam; nothing private is
reached, and `test_tests_import_only_public_names` holds that true.
"""

from __future__ import annotations

import ast
import importlib
import re
from collections import Counter
from pathlib import Path

import pytest

from outcomebound_tools import identity
from outcomebound_tools.tickets_links import LinksError, Section, anchor_of, section

ROOT = Path(__file__).resolve().parent.parent
SPECS = "docs/specs"
# The heading grammar, spelled here so that a test can ask what the
# module should have seen without reaching into it.
HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t].*)?$")


# --- fixtures ---------------------------------------------------------------------


def _spec(root: Path, slug: str, **documents: str) -> Path:
    """Write one spec's files under the declared specs root, and return its directory."""

    directory = root / SPECS / slug
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in documents.items():
        (directory / f"{name}.md").write_text(text, encoding="utf-8", newline="")
    return directory


def _heading_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if HEADING.match(line)]


def _resolvable_heading_lines(target: Path, path: str, text: str) -> list[str]:
    """The heading lines `section` reaches, in document order, through the seam.

    A line counts as reached when the anchor `anchor_of` gives it resolves to a
    section that opens on that very line, which is the only way a caller can
    quote it.
    """

    reached: list[str] = []
    for line in _heading_lines(text.split("\n")):
        anchor = anchor_of(line)
        if not anchor:
            continue
        try:
            found = section(target, path, anchor)
        except LinksError:
            continue
        if found.text.split("\n")[0] == line:
            reached.append(line)
    return reached


# --- fences -----------------------------------------------------------------------


FENCED = """\
# A spec

## A section

```text
| id | statement |
| --- | --- |
| TKT-900 | a register inside a fence |
```

~~~
## A fenced heading
~~~

## A real heading

| id | statement | check |
| --- | --- | --- |
| TKT-001 | the only row | test |
"""


def test_fenced_tables_and_headings_are_not_read(tmp_path: Path) -> None:
    _spec(tmp_path, "a-spec", requirements=FENCED)
    path = f"{SPECS}/a-spec/requirements.md"

    with pytest.raises(LinksError) as raised:
        section(tmp_path, path, "a-fenced-heading")
    assert raised.value.code == "READS_UNRESOLVED"

    # A fenced heading ends no section either: `## A section` runs past both
    # fences, at the same level as the heading inside one, and stops only at the
    # real `## A real heading`.
    enclosing = section(tmp_path, path, "a-section")
    assert "## A fenced heading" in enclosing.text
    assert "| TKT-900 | a register inside a fence |" in enclosing.text
    assert "## A real heading" not in enclosing.text


MIXED_FENCES = """\
# Mixed fences

## Outside every fence

```text
## Inside a backtick fence
```

## Between the backtick fence and the tilde one

~~~text
## Inside a tilde fence
~~~

## After the tilde fence

~~~~
## Inside a fence whose closer is longer
~~~~~

## After the longer closer

```text
~~~
## Inside a backtick fence past a marker that does not close it
```

## After the marker that does not close it

~~~
## Inside a fence nothing closes
## Still inside the fence nothing closes
"""


def test_fence_scan_agrees_with_identity(tmp_path: Path) -> None:
    """The module's fence scan and `identity.fence_free_lines` see one grammar.

    Asked through the seam: every anchor of an unfenced heading resolves, and an
    anchor only a fenced heading would give resolves for no one. Then, line for
    line over a document mixing both markers -- which `docs/specs` does not, so
    this repository alone would leave the tilde half of the grammar unchecked.
    """

    # A longer closer, a marker that closes nothing, a fence nothing closes, and
    # a heading inside and outside each: the heading lines this module lets
    # `section` reach are exactly the heading lines `identity` calls active.
    _spec(tmp_path, "a-spec", requirements=MIXED_FENCES)
    mixed = f"{SPECS}/a-spec/requirements.md"
    active = _heading_lines(identity.fence_free_lines(MIXED_FENCES))
    every = _heading_lines(MIXED_FENCES.split("\n"))
    assert len(active) < len(every), "the document must fence some of its headings"
    assert _resolvable_heading_lines(tmp_path, mixed, MIXED_FENCES) == active

    fenced_checked = 0
    unfenced_checked = 0
    for path in sorted((ROOT / SPECS).rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        active = _heading_lines(identity.fence_free_lines(text))
        every = _heading_lines(text.split("\n"))
        anchors = Counter(anchor for anchor in map(anchor_of, active) if anchor)
        for anchor, seen in anchors.items():
            if seen == 1:
                unfenced_checked += 1
                assert section(ROOT, relative, anchor).anchor == anchor
        for line in every:
            anchor = anchor_of(line)
            if anchor and anchor not in anchors:
                fenced_checked += 1
                with pytest.raises(LinksError) as raised:
                    section(ROOT, relative, anchor)
                assert raised.value.code == "READS_UNRESOLVED", line
    assert unfenced_checked, "no unfenced heading was found to check"
    assert fenced_checked, "no fenced heading was found to pin the scan against"


# --- the anchor rule ---------------------------------------------------------------


ANCHORS = [
    ("### 5.1 `bounds`", "51-bounds"),
    ("### 5.2 Decision content", "52-decision-content"),
    ("### 5.3 `reads`", "53-reads"),
    ("## 11. Reports", "11-reports"),
    ("## 17. Modules and seams", "17-modules-and-seams"),
    # A closing run of hashes is dropped before the anchor is taken, so neither
    # the space before it nor a space after it survives as a trailing hyphen.
    ("## Reports ##", "reports"),
    ("## Reports ## ", "reports"),
    ("## Reports##", "reports"),
    # A hash the text itself ends on is that run as far as the grammar can tell.
    ("## C# and F#", "c-and-f"),
    # Removal can leave neighbouring hyphens, and nothing collapses them.
    ("# Tickets — contracts", "tickets--contracts"),
    ("Tickets — contracts", "tickets--contracts"),
    # A heading of only removed characters defines no anchor.
    ("## —", ""),
    ("###", ""),
    # Hyphens and underscores survive; every space becomes a hyphen.
    ("## a_b-c 1", "a_b-c-1"),
    # "letter" and "digit" are read as Unicode, so another script keeps its letters.
    ("## Ünïcode Heiß", "ünïcode-heiß"),
    ("## Данные", "данные"),
]


@pytest.mark.parametrize(("heading", "expected"), ANCHORS)
def test_anchor_of_matches_the_rule(heading: str, expected: str) -> None:
    assert anchor_of(heading) == expected


# A line reaching for the `#` marker and missing it: no space after the run, a
# run of seven, and a marker indented past the three spaces the grammar allows.
MISSES_THE_MARKER = [
    "#no-space",
    "####### seven hashes",
    "    ## indented four spaces",
    "\t## indented by a tab",
    "#42",
]


@pytest.mark.parametrize("line", MISSES_THE_MARKER)
def test_a_line_that_misses_the_marker_has_no_anchor(tmp_path: Path, line: str) -> None:
    # `section` reads no heading there, so `anchor_of` grants none either: the
    # two public names never disagree about one string.
    assert anchor_of(line) == ""

    document = f"## A real heading\n\n{line}\n\nbody\n"
    _spec(tmp_path, "a-spec", requirements=document)
    path = f"{SPECS}/a-spec/requirements.md"

    # It neither ends the section it sits in nor opens one of its own, and the
    # anchor its text alone would give reaches nothing.
    found = section(tmp_path, path, "a-real-heading")
    assert line in found.text.split("\n")
    assert found.text.rstrip("\n").endswith("body")
    with pytest.raises(LinksError) as raised:
        section(tmp_path, path, anchor_of(line.lstrip("# \t")))
    assert raised.value.code == "READS_UNRESOLVED"


REPOSITORY_ANCHORS = [
    ("docs/specs/tickets/design.md", "decisions", 2),
    ("docs/specs/floor/design.md", "edges", 2),
    ("docs/specs/install/design.md", "validation", 2),
    # An em dash removed between two spaces leaves the doubled hyphen.
    ("docs/specs/tickets/design.md", "tickets--design", 1),
]


@pytest.mark.parametrize(("path", "anchor", "level"), REPOSITORY_ANCHORS)
def test_this_repositorys_own_headings_resolve(path: str, anchor: str, level: int) -> None:
    found = section(ROOT, path, anchor)

    assert isinstance(found, Section)
    assert (found.path, found.anchor, found.level) == (path, anchor, level)
    assert found.text.startswith("#" * level + " ")
    assert anchor_of(found.text.split("\n")[0]) == anchor


UNDERLINED = """\
---
name: a-spec
status: ratified
---

Title
=====

Subtitle
---

## A real heading

body
"""


def test_underlined_headings_are_not_headings(tmp_path: Path) -> None:
    _spec(tmp_path, "a-spec", requirements=UNDERLINED)
    path = f"{SPECS}/a-spec/requirements.md"

    for anchor in ("title", "subtitle", "name-a-spec", "status-ratified"):
        with pytest.raises(LinksError) as raised:
            section(tmp_path, path, anchor)
        assert raised.value.code == "READS_UNRESOLVED"

    # The only heading is the `#`-style one, and it runs to the end of the file.
    found = section(tmp_path, path, "a-real-heading")
    assert found.text.startswith("## A real heading\n")
    assert "body" in found.text


ONLY_REMOVED_CHARACTERS = """\
## —

the dash section

## ***

the star section

## A named heading

body
"""


def test_a_heading_of_only_removed_characters_is_citable_by_nobody(tmp_path: Path) -> None:
    _spec(tmp_path, "a-spec", requirements=ONLY_REMOVED_CHARACTERS)
    path = f"{SPECS}/a-spec/requirements.md"

    assert anchor_of("## —") == anchor_of("## ***") == ""
    # Two headings whose anchor is the empty string are not two headings sharing
    # an anchor: neither has one, so the empty citation resolves to nothing
    # rather than to whichever came first.
    with pytest.raises(LinksError) as raised:
        section(tmp_path, path, "")
    assert raised.value.code == "READS_UNRESOLVED"

    # They still end the section above them, because the extent rule counts
    # headings and the anchor rule only decides what can be cited.
    named = section(tmp_path, path, "a-named-heading")
    assert named.text.rstrip("\n").endswith("body")
    assert "the dash section" not in named.text


def test_this_repositorys_frontmatter_defines_no_anchor() -> None:
    # `docs/specs/tickets/design.md` opens with a `---` fence whose closing line
    # sits under `status: ratified`; a setext reader would call that a heading.
    with pytest.raises(LinksError) as raised:
        section(ROOT, "docs/specs/tickets/design.md", "status-ratified")
    assert raised.value.code == "READS_UNRESOLVED"


# --- the extent rule ---------------------------------------------------------------


EXTENT = """\
# Top

intro

## Alpha

alpha body

### Deep

deep body

#### Deeper

deeper body

### Beta

beta body

## Gamma

gamma body
"""


def test_section_extent_stops_at_the_same_or_higher_level(tmp_path: Path) -> None:
    _spec(tmp_path, "a-spec", requirements=EXTENT)
    path = f"{SPECS}/a-spec/requirements.md"

    deep = section(tmp_path, path, "deep")
    assert deep.level == 3
    assert deep.heading == "Deep"
    # A deeper heading does not end it; the next `###` does.
    assert "#### Deeper" in deep.text
    assert "deeper body" in deep.text
    assert "### Beta" not in deep.text

    # And a `##` ends a `###` section too.
    beta = section(tmp_path, path, "beta")
    assert "beta body" in beta.text
    assert "## Gamma" not in beta.text

    alpha = section(tmp_path, path, "alpha")
    assert "### Deep" in alpha.text and "### Beta" in alpha.text
    assert "## Gamma" not in alpha.text

    # The last heading in a file: the section runs to the end.
    gamma = section(tmp_path, path, "gamma")
    assert gamma.text.rstrip("\n").endswith("gamma body")

    # The first heading holds everything, since nothing is at its level or above.
    assert section(tmp_path, path, "top").text.rstrip("\n").endswith("gamma body")


VERBATIM = """\
## The example

Before.

```json
{"result": "UNVERIFIED",
 "verb": "check"}
```

~~~markdown
## A heading that is documentation
| id | statement |
| --- | --- |
| TKT-900 | not a row |
~~~

After.

## The next section

elsewhere
"""


def test_section_keeps_fenced_content_verbatim(tmp_path: Path) -> None:
    _spec(tmp_path, "a-spec", requirements=VERBATIM)

    found = section(tmp_path, f"{SPECS}/a-spec/requirements.md", "the-example")

    for line in VERBATIM.split("\n")[: VERBATIM.split("\n").index("## The next section")]:
        assert line in found.text.split("\n")
    assert '{"result": "UNVERIFIED",' in found.text
    assert "## A heading that is documentation" in found.text
    assert "## The next section" not in found.text


AMBIGUOUS = """\
## The brief

one

### the brief

two

## Only once

three
"""


def test_unresolved_and_ambiguous_anchors_raise(tmp_path: Path) -> None:
    _spec(tmp_path, "a-spec", requirements=AMBIGUOUS)
    path = f"{SPECS}/a-spec/requirements.md"

    with pytest.raises(LinksError) as unresolved:
        section(tmp_path, path, "nope")
    assert unresolved.value.code == "READS_UNRESOLVED"
    assert path in str(unresolved.value)

    with pytest.raises(LinksError) as ambiguous:
        section(tmp_path, path, "the-brief")
    assert ambiguous.value.code == "READS_AMBIGUOUS"
    # Both headings are named, so a person can tell which one to rename.
    assert "## The brief" in str(ambiguous.value)
    assert "### the brief" in str(ambiguous.value)

    # A missing file is unresolved too, not an absence to pass over.
    with pytest.raises(LinksError) as missing:
        section(tmp_path, f"{SPECS}/a-spec/nothing.md", "only-once")
    assert missing.value.code == "READS_UNRESOLVED"


@pytest.mark.parametrize("path", ["../x.md", "/etc/x.md", "a/../b.md", ".git/config", "~/x.md"])
def test_a_path_outside_the_repository_is_unresolved(tmp_path: Path, path: str) -> None:
    _spec(tmp_path, "a-spec", requirements=AMBIGUOUS)

    with pytest.raises(LinksError) as raised:
        section(tmp_path, path, "only-once")

    assert raised.value.code == "READS_UNRESOLVED"


# --- the seam ----------------------------------------------------------------------


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
    assert reached == 4, "this file imports exactly the seam it tests"
