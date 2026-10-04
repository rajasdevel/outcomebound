"""The block grammar, decision-content identity, holds, bounds and the ticket.

Everything here is driven through the module's public seam: the names
`tickets_model` exports, over documents built in the test. Nothing spawns a
subprocess and nothing touches the filesystem — a block is text a caller already
has, and the one part of the model that opens a file has its own test file.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_model import (
    BLOCK_VERSIONS,
    LIFECYCLE_KEYS,
    LIST_KEYS,
    WAIT_KEYS,
    BlockFields,
    DoneWhen,
    InputInfo,
    ReadResult,
    Reads,
    Ticket,
    content_identity,
    effective_hold,
    parse_block,
)

DIGEST = "b" * 64

TITLE = "Reports exit by the ratified convention"
BRIEF = "## Outcome\nA CI step can tell a failing ticket from a usage error.\n"

# The ticket block, key by key. A test names the one key it varies;
# `None` drops a key, a list writes it as `- ` items.
BLOCK: Mapping[str, object] = {
    "reads": "docs/specs/tickets/design.md#decisions",
    "bounds": "outcomebound_tools/tickets_model.py",
    "human-only": "no",
    "done-when": ["tickets-model"],
}


def _block(keys: Mapping[str, object] | None = None, version: str = "1") -> str:
    """One `id=ticket` block, with the named keys replaced or dropped."""

    lines: list[str] = []
    for name, value in {**BLOCK, **(keys or {})}.items():
        if value is None:
            continue
        if isinstance(value, list):
            lines.append(f"{name}:")
            lines.extend(f"- {item}" if item else "-" for item in value)
        else:
            lines.append(f"{name}: {value}")
    body = "\n".join(lines)
    return (
        f"<!-- outcomebound:begin id=ticket v={version} -->\n"
        f"{body}\n"
        "<!-- outcomebound:end id=ticket -->\n"
    )


def _fields(keys: Mapping[str, object] | None = None) -> BlockFields:
    """The block above, parsed, with nothing to report."""

    fields, messages = parse_block(_block(keys))
    assert messages == (), [item.code for item in messages]
    return fields


def _codes(text: str) -> list[str]:
    return [item.code for item in parse_block(text)[1]]


def _identity(
    title: str = TITLE, brief: str = BRIEF, keys: Mapping[str, object] | None = None
) -> str:
    return content_identity(title, brief, _fields(keys))


# --- the block's structure ---------------------------------------------------------


def test_fenced_block_is_not_a_block() -> None:
    """A block shown inside a code fence is documentation, not a block."""

    example = f"## Design\nA ticket carries a block:\n\n```markdown\n{_block()}```\n"
    fields, messages = parse_block(example)
    assert [item.code for item in messages] == ["BLOCK_MISSING"]
    assert fields == BlockFields()
    assert (fields.begin, fields.end) == (-1, -1)

    beside = example + "\n" + _block({"bounds": "outcomebound_tools/tickets_draft.py"})
    fields, messages = parse_block(beside)
    assert messages == ()
    assert fields.bounds == ("outcomebound_tools/tickets_draft.py",)


def test_block_offsets_locate_the_block_in_the_text_given() -> None:
    """`begin` and `end` are what a reader cuts the brief with."""

    head = f"{TITLE}\n\n{BRIEF}\n"
    example = f"```markdown\n{_block()}```\n"
    document = head + _block() + "\n" + example
    fields, messages = parse_block(document)
    assert messages == ()
    assert document[: fields.begin] == head, "everything before the block is the brief"
    assert document[fields.begin : fields.end] == _block().rstrip("\n")
    assert document[fields.end :].startswith("\n\n```markdown"), "the fenced example is untouched"

    swallowed, _ = parse_block("## Design\n\n```markdown\n" + _block())
    assert (swallowed.begin, swallowed.end) == (-1, -1)


def test_structural_failures_become_messages() -> None:
    inline = (
        "## Approach\n"
        "A sentinel outside a fence — <!-- outcomebound:begin id=ticket v=1 --> — is refused.\n"
        "\n" + _block()
    )
    assert _codes(inline) == ["BLOCK_MALFORMED"]

    foreign = (
        "## Example\n"
        "<!-- outcomebound:begin id=example v=1 -->\n"
        "ticket: #42\n"
        "<!-- outcomebound:end id=example -->\n"
        "\n" + _block()
    )
    fields, messages = parse_block(foreign)
    assert [item.code for item in messages] == ["BLOCK_MALFORMED"]
    assert "code fence" in messages[0].next, "any other block is shown inside a fence"
    assert fields == BlockFields()

    swallowed = "## Design\n\n```markdown\n" + _block()
    fields, messages = parse_block(swallowed)
    assert [item.code for item in messages] == ["BLOCK_MISSING"]
    assert "fence" in messages[0].text

    garbled = "<!-- outcomebound:begin id=ticket v -->\nreads:\n"
    assert _codes(garbled) == ["BLOCK_MALFORMED"]


def test_more_than_one_block_reads_duplicate() -> None:
    """The two hard rows of the duplicate/malformed discriminator, as built."""

    doubled = _block() + "\n" + _block({"bounds": "docs/tickets"})
    fields, messages = parse_block(doubled)
    assert [item.code for item in messages] == ["BLOCK_DUPLICATE"]
    assert fields == BlockFields(), "no key is read from a document carrying two blocks"

    # A balanced pair named in inline code counts as a second block: both
    # answers tell the writer the same thing, to show a sentinel in a fence.
    mentioned = (
        "## Approach\n"
        "The block runs `<!-- outcomebound:begin id=ticket v=1 -->` to "
        "`<!-- outcomebound:end id=ticket -->`.\n"
        "\n" + _block()
    )
    assert _codes(mentioned) == ["BLOCK_DUPLICATE"]

    nested = (
        "<!-- outcomebound:begin id=ticket v=1 -->\n"
        "<!-- outcomebound:begin id=ticket v=1 -->\n"
        "<!-- outcomebound:end id=ticket -->\n"
        "<!-- outcomebound:end id=ticket -->\n"
    )
    assert _codes(nested) == ["BLOCK_DUPLICATE"]


def test_a_body_line_that_is_not_a_key_fails_the_block_closed() -> None:
    """A body this parser cannot place is one message and no key read."""

    for offending in ("bounds", "  bounds: docs", "bōunds: docs", "= no"):
        text = _block().replace("human-only: no", offending)
        fields, messages = parse_block(text)
        assert [item.code for item in messages] == ["BLOCK_MALFORMED"], offending
        assert fields.present == frozenset(), offending
        assert fields.reads == () and fields.bounds == () and fields.done_when == ()
        assert dict(fields.written) == dict.fromkeys(LIST_KEYS, ())
        assert fields.version == "1" and fields.begin >= 0, "the block itself was found"


def test_unknown_version_stops_judgement() -> None:
    """A block version this engine does not ship is judged no further."""

    assert BLOCK_VERSIONS == ("1",)
    for version in ("2", "0.9"):
        fields, messages = parse_block(_block({"bounds": None}, version=version))
        assert [item.code for item in messages] == ["BLOCK_MALFORMED"]
        assert fields.version == version
        assert fields.present == frozenset()
        assert fields.bounds == () and fields.human_only == ""
        assert fields.begin >= 0 and fields.end > fields.begin


# --- the key table -----------------------------------------------------------------


def test_key_table_rules() -> None:
    doubled = _block().replace(
        "bounds: outcomebound_tools/tickets_model.py",
        "bounds: outcomebound_tools/tickets_model.py\nbounds: docs/tickets",
    )
    fields, messages = parse_block(doubled)
    assert [item.code for item in messages] == ["KEY_DUPLICATE"]
    assert "bounds" in messages[0].text
    assert fields.bounds == ("outcomebound_tools/tickets_model.py",)
    assert fields.written["bounds"] == ("outcomebound_tools/tickets_model.py",)

    unknown = parse_block(_block({"priority": "high"}))
    assert [item.code for item in unknown[1]] == ["KEY_UNKNOWN"]
    assert "priority" in unknown[1][0].text

    missing = parse_block(_block({"bounds": None}))
    assert [item.code for item in missing[1]] == ["KEY_MISSING"]
    assert "bounds" in missing[1][0].text

    for absent in ("human-only", "done-when"):
        assert _codes(_block({absent: None})) == ["KEY_MISSING"]
    assert _codes(_block({"reads": None})) == [], "reads may be absent"

    invalid = parse_block(_block({"human-only": "maybe"}))
    assert [item.code for item in invalid[1]] == ["VALUE_INVALID"]
    assert "human-only" in invalid[1][0].text and "maybe" in invalid[1][0].text
    assert invalid[0].human_only == ""
    assert "human-only" in invalid[0].present


def test_lifecycle_keys_are_read_whatever_the_store() -> None:
    """Which store forbids a lifecycle key is that reader's rule, not this one's."""

    lifecycle = _fields({"status": "open", "assignee": "a person", "parent": "T-0001"})
    assert lifecycle.status == "open"
    assert lifecycle.assignee == "a person"
    assert lifecycle.parent == "T-0001"
    assert set(LIFECYCLE_KEYS) == {"status", "assignee", "blocked-by", "parent"}
    assert _fields({"blocked-by": "T-0002, T-0003"}).blocked_by == ("T-0002", "T-0003")
    assert _fields({"blocked-by": ""}).blocked_by == ()
    assert "status" not in _fields().present
    assert _codes(_block({"status": "started"})) == ["VALUE_INVALID"]


def test_waits_on_names_decision_briefs_and_moves_no_identity() -> None:
    """`waits-on` reads one or more brief ids in written order, refuses anything that is
    not one, and is no part of the decision content: answering a brief and dropping its
    id leaves the identity where it was."""

    assert WAIT_KEYS == ("waits-on",)
    assert _fields({"waits-on": "D1"}).waits_on == ("D1",)
    assert _fields({"waits-on": "D1, brief-3"}).waits_on == ("D1", "brief-3")
    assert _fields().waits_on == ()
    for offending in ("", "#41", "D1 D2", "3D"):
        fields, messages = parse_block(_block({"waits-on": offending}))
        assert [item.code for item in messages] == ["VALUE_INVALID"], offending
        assert "waits-on" in messages[0].text and fields.waits_on == (), offending
    assert _codes(_block({"waits-on": ["D1"]})) == ["VALUE_INVALID"]
    assert _identity(keys={"waits-on": "D1"}) == _identity()


@pytest.mark.parametrize("key", ["discovered-from", "parent"])
@pytest.mark.parametrize("offending", ["#41, #42", "T-0001 T-0002", "a ticket"])
def test_a_key_that_names_one_ticket_refuses_a_list(key: str, offending: str) -> None:
    fields, messages = parse_block(_block({key: offending}))
    assert [item.code for item in messages] == ["VALUE_INVALID"]
    assert key in messages[0].text and "one ticket id" in messages[0].text
    assert fields.discovered_from == "" and fields.parent == ""


def test_reads_are_split() -> None:
    """Every reader hands over `{path, anchor}`; a path alone names the whole file."""

    fields = _fields({"reads": "docs/specs/tickets/design.md#outcome"})
    assert fields.reads == (Reads(path="docs/specs/tickets/design.md", anchor="outcome"),)
    whole = _fields({"reads": "schemas/ticket-store.schema.json"})
    assert whole.reads == (Reads(path="schemas/ticket-store.schema.json", anchor=""),)
    assert whole.reads[0].cited() == "schemas/ticket-store.schema.json"
    for offending in ("empty-anchor.md#", "#anchor-only", "../escapes.md#x", "../escapes.md"):
        assert _codes(_block({"reads": offending})) == ["VALUE_INVALID"], offending


def test_a_covers_key_is_unknown_and_its_message_names_reads() -> None:
    """`covers` is no key of the block: a block carrying it is refused, and the message
    says to cite the design section under `reads`."""

    _, messages = parse_block(_block({"covers": "tickets/TKT-001@1"}))
    assert [(item.code, item.level.name) for item in messages] == [("KEY_UNKNOWN", "ERROR")]
    assert "`reads`" in messages[0].next


# --- `done-when` -------------------------------------------------------------------


def test_done_when_forms() -> None:
    fields = _fields({"done-when": ["tickets-model", "gate-stdlib"]})
    assert fields.done_when == (DoneWhen(claim="tickets-model"), DoneWhen(claim="gate-stdlib"))

    for offending in ("Build_It", "1-first", "a: red-first: twice", "a-claim: seen"):
        assert _codes(_block({"done-when": [offending]})) == ["VALUE_INVALID"], offending

    repeated = parse_block(_block({"done-when": ["a-claim", "a-claim: red-first"]}))
    assert [item.code for item in repeated[1]] == ["VALUE_INVALID"]
    assert "a-claim" in repeated[1][0].text

    assert _codes(_block({"done-when": []})) == ["VALUE_INVALID"], "the block requires an item"
    assert _codes(_block({"done-when": None})) == ["KEY_MISSING"]


def test_a_red_first_marker_is_read_as_its_claim_alone() -> None:
    """A `done-when` item may carry the `red-first` marker after its claim: the item is
    no error and no warning, and reads as the claim it names."""

    fields, messages = parse_block(_block({"done-when": ["tickets-model: red-first", "gate"]}))

    assert messages == ()
    assert fields.done_when == (DoneWhen(claim="tickets-model"), DoneWhen(claim="gate"))


def test_a_human_item_is_named_and_the_claims_beside_it_still_read() -> None:
    """A `human:` item is a form this engine does not read. Each is refused where it
    stands, so the claims beside it are still read, and the identity still hashes it."""

    written = ["reads-well: human: legible at 80 columns", "tickets-model", "b: human:"]
    fields, messages = parse_block(_block({"done-when": written}))
    assert fields.done_when == (DoneWhen("tickets-model"),)
    assert [item.code for item in messages] == ["VALUE_INVALID", "VALUE_INVALID"]
    assert "reads-well: human: legible" in messages[0].text
    assert "command claim" in messages[0].next
    assert fields.written["done-when"] == tuple(written), "the identity still hashes it"

    alone, said = parse_block(_block({"done-when": ["reads-well: human: seen"]}))
    assert alone.done_when == ()
    assert [item.code for item in said] == ["VALUE_INVALID"]


def test_a_ticket_a_person_does_names_a_persons_check() -> None:
    """On `human-only: yes` a `human:` item is a person's check: read, with no
    message and no planned claim, beside the claims of the plan. One that names no
    observation is refused where it stands."""

    written = ["reads-well: human: legible at 80 columns", "tickets-model"]
    fields, messages = parse_block(_block({"human-only": "yes", "done-when": written}))

    assert messages == ()
    assert fields.done_when == (
        DoneWhen("reads-well", human="legible at 80 columns"),
        DoneWhen("tickets-model"),
    )

    empty, said = parse_block(_block({"human-only": "yes", "done-when": ["b: human:", "gate"]}))
    assert empty.done_when == (DoneWhen("gate"),)
    assert [item.code for item in said] == ["VALUE_INVALID"]
    assert "names no observation" in said[0].text

    asked, refused = parse_block(_block({"human-only": "requested", "done-when": written}))
    assert asked.done_when == (DoneWhen("tickets-model"),), "only a person's own ticket"
    assert [item.code for item in refused] == ["VALUE_INVALID"]


def test_an_item_with_nothing_after_the_dash_is_the_keys_to_refuse() -> None:
    """An empty item is a value its key refuses, never a line the parser cannot place."""

    empty_item = parse_block(_block({"done-when": [""]}))
    assert [item.code for item in empty_item[1]] == ["VALUE_INVALID"]
    assert "done-when" in empty_item[1][0].text

    listed = _block().replace(
        "bounds: outcomebound_tools/tickets_model.py", "bounds:\n- outcomebound_tools"
    )
    messages = parse_block(listed)[1]
    assert [item.code for item in messages] == ["VALUE_INVALID"]
    assert "bounds" in messages[0].text


# --- bounds ------------------------------------------------------------------------


def test_bounds_validity() -> None:
    assert _fields({"bounds": ""}).bounds == ()

    for offending in ("/etc/passwd", "../other", "a//b", "src//", "/", "a\\b", "c:/x"):
        fields, messages = parse_block(_block({"bounds": offending}))
        assert [item.code for item in messages] == ["BOUNDS_INVALID"], offending
        assert repr(offending) in messages[0].text
        assert fields.bounds == (offending,), "what is written is what is hashed"

    for whole in (".", "./", "**", "*.py"):
        assert _codes(_block({"bounds": whole})) == ["BOUNDS_WHOLE_REPOSITORY"], whole

    assert _codes(_block({"bounds": "docs/*, src/app"})) == []
    folders = _fields({"bounds": "docs/, src/app/"})
    assert _codes(_block({"bounds": "docs/, src/app/"})) == [], "a folder may end in `/`"
    assert folders.bounds == ("docs/", "src/app/"), "what is written is what is hashed"
    refused = parse_block(_block({"bounds": "a//b"}))[1][0]
    assert "a folder is written" in refused.next, "the remedy says how to write a folder"
    for unclosed in ("src/[]", "src/[^]"):
        said = parse_block(_block({"bounds": unclosed}))[1]
        assert [item.code for item in said] == ["BOUNDS_INVALID"], unclosed
        assert "class" in said[0].text


# --- decision-content identity -----------------------------------------------------


def test_content_identity_is_stable_under_line_endings_and_whitespace() -> None:
    digest = _identity()
    assert len(digest) == 64 and digest == digest.lower()
    assert _identity(brief=BRIEF.replace("\n", "\r\n")) == digest
    assert _identity(brief=BRIEF.replace("error.", "error.   ")) == digest
    assert _identity(brief="\n\n" + BRIEF + "\n  \n") == digest
    assert _identity(title="  " + TITLE + "  ") == digest
    trimmed = "docs/specs/tickets/design.md#decisions ,  "
    assert _identity(keys={"reads": trimmed}) == digest, "an entry is trimmed"
    assert _identity(brief="") != digest, "an empty brief still has an identity"
    assert len(_identity(brief="")) == 64
    assert _identity(title="Report exits — décidé") != digest


def test_content_identity_ignores_lifecycle_and_requested() -> None:
    digest = _identity()
    assert _identity(keys={"status": "closed"}) == digest
    assert _identity(keys={"assignee": "a person"}) == digest
    assert _identity(keys={"blocked-by": "T-0002"}) == digest
    assert _identity(keys={"parent": "T-0001"}) == digest
    assert _identity(keys={"human-only": "requested"}) == digest, "`requested` reads `no`"
    assert _identity(keys={"human-only": "yes"}) != digest


def test_content_identity_moves_with_every_decision_key() -> None:
    moved = {
        "title": _identity(title="Another outcome entirely"),
        "brief": _identity(brief=BRIEF + "\n## Non-goals\nNo colour.\n"),
        "reads": _identity(keys={"reads": "docs/specs/tickets/design.md#edges"}),
        "bounds": _identity(keys={"bounds": "docs/tickets"}),
        "human-only": _identity(keys={"human-only": "yes"}),
        "done-when": _identity(keys={"done-when": ["another-claim"]}),
        "discovered-from": _identity(keys={"discovered-from": "#41"}),
    }
    digests = {**moved, "base": _identity()}
    assert len(set(digests.values())) == len(digests), digests


def test_a_refused_entry_is_still_what_the_ticket_says() -> None:
    """The list keys are hashed as written, whether or not the engine read them."""

    one, messages = parse_block(_block({"reads": "rubbish-one#"}))
    assert [item.code for item in messages] == ["VALUE_INVALID"]
    assert one.reads == (), "nothing was parsed"
    assert one.written["reads"] == ("rubbish-one#",), "what was written is still there"
    two, _ = parse_block(_block({"reads": "rubbish-two#"}))
    absent, _ = parse_block(_block({"reads": None}))
    digests = [content_identity(TITLE, BRIEF, item) for item in (one, two, absent)]
    assert len(set(digests)) == 3, "two refused values are two contents, and neither is absent"


def test_two_spellings_of_one_item_are_two_contents() -> None:
    """`done-when` items are never re-rendered."""

    assert _identity(keys={"done-when": ["a-claim: red-first"]}) != _identity(
        keys={"done-when": ["a-claim:  red-first"]}
    )


def test_an_item_holding_the_separator_is_not_two_items() -> None:
    """A list stays a list, because every joined form collides."""

    one = content_identity(TITLE, BRIEF, parse_block(_block({"done-when": ["a | b"]}))[0])
    two = _identity(keys={"done-when": ["a", "b"]})
    assert one != two, "one item holding the separator is not two items"


def test_the_identity_is_the_digest_of_the_decision_document() -> None:
    """The preimage itself, built by hand: the title, the brief and the decision keys as
    one compact JSON object with sorted keys, its UTF-8 bytes hashed with SHA-256."""

    title = f"  {TITLE}  "
    brief = "## Outcome\r\nA CI step can tell.   \r\n\r\n"
    fields = _fields(
        {
            "reads": "docs/specs/tickets/design.md#edges",
            "bounds": "outcomebound_tools/tickets.py, docs/*",
            "human-only": "requested",
            "done-when": ["a-claim: red-first", "b-claim"],
            "discovered-from": "#41",
        }
    )
    document = {
        "title": TITLE,
        "brief": "## Outcome\nA CI step can tell.",
        "reads": ["docs/specs/tickets/design.md#edges"],
        "bounds": ["outcomebound_tools/tickets.py", "docs/*"],
        "human-only": "no",
        "done-when": ["a-claim: red-first", "b-claim"],
        "discovered-from": "#41",
    }
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert content_identity(title, brief, fields) == expected


# --- the effective hold ------------------------------------------------------------


def test_effective_hold_table() -> None:
    github = Declaration(
        store="github",
        repo="owner/project",
        label="ob-ticket",
        human_label="human-only",
        request_label="human-requested",
    )

    assert effective_hold("yes", (), github) == "yes"
    assert effective_hold("no", ("human-only",), github) == "yes"
    assert effective_hold("requested", ("human-only",), github) == "yes"
    assert effective_hold("requested", (), github) == "requested"
    assert effective_hold("no", ("human-requested",), github) == "requested"
    assert effective_hold("no", ("ob-ticket",), github) == "no"
    assert effective_hold("", (), github) == "no"


# --- the normalised ticket ---------------------------------------------------------


def _ticket() -> Ticket:
    return Ticket(
        id="#42",
        title=TITLE,
        url="https://tracker.invalid/owner/project/issues/42",
        state="closed",
        block_version="1",
        path="",
        brief=BRIEF,
        reads=(Reads("docs/specs/tickets/design.md", "edges"),),
        bounds=("outcomebound_tools/tickets.py",),
        human_only="no",
        hold="no",
        done_when=(DoneWhen("tickets-report-contract"),),
        blocked_by=("#41",),
        parent="#40",
        discovered_from="#39",
        content=DIGEST,
    )


def test_the_readers_result_carries_what_a_report_needs() -> None:
    """`InputInfo` satisfies `tickets_report.InputSource` without an import."""

    result = ReadResult(
        tickets=(_ticket(),),
        others=frozenset({"#7"}),
        ignored=1,
        messages=(),
        input=InputInfo(path="issues.json", modified="2026-09-20T09:00:00Z", age_seconds=120),
    )
    assert "#7" in result.others and result.tickets[0].id == "#42"
    assert ReadResult().input is None and ReadResult().others == frozenset()


# --- the seam ----------------------------------------------------------------------


def test_tickets_bounds_module_is_importable_directly() -> None:
    """What a `bounds` entry grants is its own module, which imports no engine module."""

    from outcomebound_tools.tickets_bounds import whole_repository

    assert whole_repository(".") and whole_repository("*.py")
    assert not whole_repository("docs/*")

    module = importlib.import_module("outcomebound_tools.tickets_bounds")
    source = Path(module.__file__ or "")
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    reached: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            reached.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            reached.add(node.module)
    engine = sorted(name for name in reached if name.split(".")[0] == "outcomebound_tools")
    assert engine == [], engine


def test_a_bounds_entry_covers_itself_and_what_is_under_it() -> None:
    """A literal entry, a folder written with `/` and a glob each grant what they
    name and everything under it; a path that reads more than the entry grants is
    outside it."""

    from outcomebound_tools.tickets_bounds import covers

    inside = [
        ("src/feature", "src/feature"),
        ("src/feature", "src/feature/a.py"),
        ("src/feature/", "src/feature/a.py"),
        ("src/feature/**", "src/feature"),
        ("src/feature/**", "src/feature/deep/a.py"),
        ("src/*.py", "src/a.py"),
        ("src/*/tests", "src/x/tests/test_a.py"),
        ("**", "."),
        (".", "anything/at/all"),
    ]
    outside = [
        ("src/feature", "src"),
        ("src/feature", "src/feature-two/a.py"),
        ("src/feature/**", "."),
        ("src/*.py", "src/sub/a.py"),
        ("src/feature", "tests/test_feature.py"),
    ]
    assert [pair for pair in inside if not covers(*pair)] == []
    assert [pair for pair in outside if covers(*pair)] == []
    assert not covers("src/[]", "src/a.py"), "a class that does not compile never raises"
    assert covers("src/[ab].py", "src/a.py")


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
    assert reached >= 14, "the survey found fewer imported names than this file uses"
