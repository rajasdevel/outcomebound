"""What the layer says about itself, held to what the layer is.

The seam here is the shipped surface itself: `tickets.main`'s parser, and the
committed documents and templates. Nothing is imported privately and nothing is
rendered: a document is read as a reader reads it, and the parser is asked what
it offers.

The join this file makes is between prose and parser. `docs/tickets.md` names
the verbs; `tickets.VERBS` is what the command line actually has. Holding the
two equal as sets, in both directions, is what keeps a new verb from arriving
undocumented and a renamed verb from leaving a document behind.

The survey of what the engine may reach is not here. It is one survey, in
`tests/test_tickets_git.py`, beside the one seam the engine starts a process
through; two copies of one boundary would be two places to keep true.
"""

from __future__ import annotations

import re
from pathlib import Path

from outcomebound_tools.tickets import VERBS
from outcomebound_tools.tickets_model import DECISION_KEYS, parse_block

REPOSITORY = Path(__file__).resolve().parent.parent
GUIDE = REPOSITORY / "docs/tickets.md"
ISSUE_TEMPLATE = REPOSITORY / "templates/tickets/issue-template.md"

# The heading of `docs/tickets.md` under which one third-level heading names each
# verb.
VERB_SECTION = "## The verbs"

# `discovered-from` is optional; the other five decision keys are what a
# ticket block skeleton carries, so the template offers exactly those.
SKELETON_KEYS = tuple(key for key in DECISION_KEYS if key != "discovered-from")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """One document section: the heading's line, up to the next of its depth or above.

    Located by the heading's own prefix rather than by an exact line, so a
    section keeps its number or its trailing words without this file respelling
    them. A heading that matches no line, or more than one, is the caller's
    error: a test that silently searched an empty string would pass on a
    document that lost the section entirely.
    """

    depth = len(heading) - len(heading.lstrip("#"))
    lines = text.split("\n")
    starts = [index for index, line in enumerate(lines) if line.startswith(heading)]
    assert len(starts) == 1, f"{heading!r} heads {len(starts)} sections, not one"
    start = starts[0]
    for index in range(start + 1, len(lines)):
        found = lines[index]
        if found.startswith("#") and len(found) - len(found.lstrip("#")) <= depth:
            return "\n".join(lines[start:index])
    return "\n".join(lines[start:])


def _fenced(text: str, language: str) -> list[str]:
    fence = re.compile(rf"^```{language}[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
    return fence.findall(text)


# --- the verbs, in two places ------------------------------------------------------


def _guide_verbs() -> set[str]:
    """The verbs `docs/tickets.md` gives a section of its own."""

    section = _section(_read(GUIDE), VERB_SECTION)
    return set(re.findall(r"^### `([a-z]+)`", section, re.MULTILINE))


def test_documented_verbs_equal_the_parser_s() -> None:
    """The parser and the guide name one set of verbs."""

    parser = set(VERBS)
    assert parser, "the command line offers no verb at all"
    guide = _guide_verbs()
    assert guide == parser, (
        f"docs/tickets.md names {sorted(guide)} and the parser offers {sorted(parser)}; "
        f"undocumented: {sorted(parser - guide)}, documented but absent: {sorted(guide - parser)}"
    )


# --- the shipped templates ---------------------------------------------------------


def test_the_export_command_reads_the_query_from_the_engine_checkout() -> None:
    """The guide's export command reads the pinned query from the OutcomeBound
    checkout `outcomebound home` prints, so it runs from the project, where the ticket
    skills run it, and not from a path relative to wherever it runs."""

    section = _section(_read(GUIDE), "## Producing the export for the `github` store")
    blocks = _fenced(section, "sh")
    assert len(blocks) == 1, f"the export section holds {len(blocks)} sh blocks, not one"
    anchored = '"$(outcomebound home)/templates/tickets/github-export.graphql"'
    assert anchored in blocks[0]
    assert "cat templates/" not in blocks[0]
    shipped = anchored.strip('"').removeprefix("$(outcomebound home)/")
    assert (REPOSITORY / shipped).is_file(), f"{shipped} is not in this checkout"


# The template's headings, in its order: the one required and the two optional. `check`
# also accepts a `## Tests` section a ticket carries, but the template does not offer one:
# which tests to write is the implementer's.
TEMPLATE_HEADINGS = ("## Outcome", "## Design", "## Limits")


def test_the_issue_template_carries_the_brief_headings_and_a_ticket_block() -> None:
    """The three headings in order, no reference block, and one block skeleton."""

    text = _read(ISSUE_TEMPLATE)
    lines = [line.rstrip() for line in text.split("\n")]
    headings = [line for line in lines if line.startswith("## ")]
    assert headings == list(TEMPLATE_HEADINGS), headings
    assert "<details>" not in text, "a brief copies no shape from the tree"

    fields, messages = parse_block(text)
    structural = [item.code for item in messages if item.code.startswith("BLOCK_")]
    assert not structural, f"the template's ticket block does not parse: {structural}"
    assert fields.version == "1", f"the template's block is v{fields.version!r}, not v1"
    missing = [key for key in SKELETON_KEYS if key not in fields.present]
    assert not missing, f"the template's block skeleton lacks the decision keys {missing}"
    assert [item.code for item in messages if item.code == "KEY_UNKNOWN"] == []
