"""The draft: a local file before it is a ticket, read through its own seam.

Everything here drives `tickets_draft.read_draft` and `tickets_draft.draft_relations`
over files written under `tmp_path`. No store is declared beyond the typed
`Declaration` the hold rule needs, no repository is built and no claims plan is
written, because the module under test reaches none of them —
`test_the_module_reads_no_store_no_git_and_no_plan` holds that true of its
imports.

What `check --draft` makes of a draft — the pass, the knots, the report — is
`tests/test_tickets_check.py`'s.
"""

from __future__ import annotations

import ast
import importlib
from collections.abc import Sequence
from pathlib import Path

import pytest

from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_draft import DraftError, draft_relations, read_draft
from outcomebound_tools.tickets_model import Ticket
from outcomebound_tools.tickets_report import Message

MODULE = Path(__file__).resolve().parent.parent / "outcomebound_tools/tickets_draft.py"

GITHUB = Declaration(
    store="github",
    repo="owner/project",
    label="ob-ticket",
    human_label="human-only",
    request_label="human-requested",
    claims=".outcomebound/claims.json",
)

BRIEF = ("## Outcome", "Something becomes observably true.", "")


# --- what the tests build ----------------------------------------------------------


def block(
    *,
    version: str = "1",
    bounds: Sequence[str] = ("outcomebound_tools/one.py",),
    human_only: str = "no",
    done_when: Sequence[str] = ("example-claim",),
    status: str = "",
    blocked_by: Sequence[str] | None = None,
    parent: str | None = None,
    keys: Sequence[str] = (),
) -> list[str]:
    """One `id=ticket` block, with only the keys a test spells out."""

    lines = [f"<!-- outcomebound:begin id=ticket v={version} -->"]
    if bounds is not None:
        lines.append(f"bounds: {', '.join(bounds)}")
    lines.append(f"human-only: {human_only}")
    lines.append("done-when:")
    lines.extend(f"- {item}" for item in done_when)
    if status:
        lines.append(f"status: {status}")
    if blocked_by is not None:
        lines.append(f"blocked-by: {', '.join(blocked_by)}")
    if parent is not None:
        lines.append(f"parent: {parent}")
    lines.extend(keys)
    lines.append("<!-- outcomebound:end id=ticket -->")
    return lines


def text_of(
    *,
    title: str = "A draft",
    heading: str = "",
    brief: Sequence[str] = BRIEF,
    tail: Sequence[str] = (),
    **keys: object,
) -> str:
    """One draft file: `# <title>` with no id, the brief, the block, nothing else."""

    lines = [heading or f"# {title}", "", *brief, *block(**keys), *tail]  # type: ignore[arg-type]
    return "\n".join(lines) + "\n"


def draft(tmp_path: Path, stem: str = "a-draft", **written: object) -> Path:
    path = tmp_path / f"{stem}.md"
    path.write_text(text_of(**written), encoding="utf-8")  # type: ignore[arg-type]
    return path


def read(path: Path, declaration: Declaration = GITHUB) -> tuple[Ticket, list[str]]:
    """One draft and the codes it was read with; the ticket must be there."""

    ticket, messages = read_draft(path, declaration)
    assert ticket is not None, [item.code for item in messages]
    return ticket, [item.code for item in messages]


def said(messages: Sequence[Message]) -> str:
    return " ".join(f"{item.text} {item.next}" for item in messages)


def named(tickets: Sequence[Ticket]) -> dict[str, list[str]]:
    """The relation findings by draft id, as codes."""

    return {id: [item.code for item in found] for id, found in draft_relations(tickets).items()}


def as_draft(
    id: str, *, blocked_by: Sequence[str] = (), parent: str = "", path: str = ""
) -> Ticket:
    return Ticket(
        id=id,
        title=id,
        path=path or f"drafts/{id}.md",
        blocked_by=tuple(blocked_by),
        parent=parent,
    )


# --- the normalised draft ----------------------------------------------------------


def test_the_id_is_the_file_name_without_its_extension(tmp_path: Path) -> None:
    """The id is how other drafts name it, and the title is its heading."""

    ticket, codes = read(draft(tmp_path, "tk-08-check", title="One verb over every reader"))

    assert codes == []
    assert ticket.id == "tk-08-check"
    assert ticket.title == "One verb over every reader"
    assert ticket.path == (tmp_path / "tk-08-check.md").as_posix()


def test_a_draft_has_no_lifecycle_yet(tmp_path: Path) -> None:
    """Its state is open, and a `status` the file happens to write does not move it."""

    ticket, codes = read(draft(tmp_path, status="closed"))

    assert codes == [], "the block admits `status`; a draft simply has no lifecycle"
    assert ticket.state == "open"
    assert ticket.brief.startswith("## Outcome")


def test_the_hold_is_the_blocks_own_value(tmp_path: Path) -> None:
    """A draft has no label surface, so the block alone decides its hold."""

    path = draft(tmp_path, human_only="yes")

    assert read(path, GITHUB)[0].hold == "yes"
    assert read(draft(tmp_path, "free"), GITHUB)[0].hold == "no"


# --- a file that is no draft -------------------------------------------------------


def test_a_heading_that_is_only_an_id_refuses_the_file(tmp_path: Path) -> None:
    """`# #7` is an id and no title, and a draft's heading carries no id."""

    path = tmp_path / "bare-id.md"
    path.write_text(text_of(heading="# #7"), encoding="utf-8")

    _, messages = read_draft(path, GITHUB)

    assert [item.code for item in messages] == ["VALUE_INVALID"]
    assert "carries no id" in said(messages)


def test_a_file_with_no_heading_at_all_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "headless.md"
    path.write_text("Some prose.\n\n" + "\n".join(block()) + "\n", encoding="utf-8")

    ticket, messages = read_draft(path, GITHUB)

    assert ticket is not None and ticket.title == ""
    assert [item.code for item in messages] == ["VALUE_INVALID"]
    assert "# <title>" in said(messages)


# --- the block, read where it stands -----------------------------------------------


def test_block_messages_are_stamped_with_the_drafts_id(tmp_path: Path) -> None:
    """A key the block is missing is the model's message, carried under this id."""

    path = tmp_path / "no-bounds.md"
    lines = ["# A draft", "", *BRIEF, "<!-- outcomebound:begin id=ticket v=1 -->"]
    lines += ["human-only: no", "done-when:", "- example-claim"]
    lines += ["<!-- outcomebound:end id=ticket -->"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _, messages = read_draft(path, GITHUB)

    assert [item.code for item in messages] == ["KEY_MISSING"]
    assert {item.ticket for item in messages} == {"no-bounds"}


def test_two_blocks_outside_a_fence_are_a_duplicate(tmp_path: Path) -> None:
    """A file saying two things about one ticket is `BLOCK_DUPLICATE`."""

    path = tmp_path / "twice.md"
    path.write_text(
        "\n".join(["# A draft", "", *BRIEF, *block(), "", *block()]) + "\n", encoding="utf-8"
    )

    _, messages = read_draft(path, GITHUB)

    assert [item.code for item in messages] == ["BLOCK_DUPLICATE"]


def test_a_newer_block_version_is_carried_through(tmp_path: Path) -> None:
    """The version is kept on the ticket, so `check` can end its pass at it."""

    ticket, codes = read(draft(tmp_path, version="2"))

    assert codes == ["BLOCK_MALFORMED"]
    assert ticket.block_version == "2"


# --- files this module cannot read -------------------------------------------------


def test_an_absent_file_and_an_unreadable_one_are_told_apart(tmp_path: Path) -> None:
    """Both are `TICKET_UNREADABLE` on that draft, and each names its own remedy."""

    absent = tmp_path / "not-here.md"
    broken = tmp_path / "broken.md"
    broken.write_bytes(b"# A draft\n\xff\xfe\n")

    missing_ticket, missing = read_draft(absent, GITHUB)
    unreadable_ticket, unreadable = read_draft(broken, GITHUB)

    assert (missing_ticket, unreadable_ticket) == (None, None)
    assert [item.code for item in missing] == ["TICKET_UNREADABLE"]
    assert [item.code for item in unreadable] == ["TICKET_UNREADABLE"]
    assert "no file" in said(missing)
    assert "UTF-8" in said(unreadable) and "no file" not in said(unreadable)
    assert said(missing) != said(unreadable)


def test_a_path_that_names_no_draft_is_the_engines_own_error() -> None:
    """A path with no file name has no id to report anything under, and a message
    this engine cannot stamp is a message nobody could act on."""

    with pytest.raises(DraftError) as refused:
        read_draft("", GITHUB)

    assert "file name" in str(refused.value)


# --- relations among the drafts given ----------------------------------------------


def test_relations_resolve_by_file_name_or_by_ticket_id() -> None:
    """A draft names another by file name, or an existing ticket by id; a
    cross-repository id is a ticket id too, and anything else is refused. A
    ticket id is accepted and said to be unchecked, since a draft run reads no
    store."""

    tickets = [
        as_draft("one", blocked_by=("two", "#42", "owner/project#7"), parent=""),
        as_draft("two", blocked_by=(), parent=""),
        as_draft("three", blocked_by=("tk-99-thing",), parent="also-missing"),
        as_draft("four", blocked_by=("?#7",)),
    ]

    found = draft_relations(tickets)

    assert named(tickets) == {
        "one": ["RELATION_UNCHECKED", "RELATION_UNCHECKED"],
        "three": ["VALUE_INVALID", "VALUE_INVALID"],
        "four": ["VALUE_INVALID"],
    }
    assert {item.level.name for item in found["one"]} == {"INFO"}, "no verdict moves"
    assert "#42" in said(found["one"]) and "not checked" in said(found["one"])
    assert "two" not in found, "a relation to a draft of this run and an empty one are accepted"
    assert "tk-99-thing" in said(found["three"])
    assert "also-missing" in said(found["three"])
    assert "drafts/three.md" in said(found["three"]), "the file is named beside the rule"


def test_two_drafts_of_one_name_are_one_id() -> None:
    """A draft's id is its file name, so two files of one name claim one id."""

    tickets = [
        as_draft("same", path="drafts/same.md"),
        as_draft("same", path="elsewhere/same.md"),
    ]

    found = draft_relations(tickets)

    assert [item.code for item in found["same"]] == ["ID_DUPLICATE"]
    assert "drafts/same.md" in said(found["same"])
    assert "elsewhere/same.md" in said(found["same"])


# --- what this module is allowed to reach ------------------------------------------


def test_the_module_reads_no_store_no_git_and_no_plan() -> None:
    """The model, the declaration's type and the report.

    A git call, a store read or a claims plan here would make a draft depend on a
    project it is written before, which is the whole point of linting one. The
    declaration is a value handed in, never loaded: the effective hold needs its type
    and nothing else. `home` locates the engine's own issue template, whose
    placeholder text a repeated paragraph is not warned about; it is the engine's
    file, not the project's. `textio` decodes the draft file the way every file the engine
    reads is decoded. The set is exact, so the next import has to be argued for.
    """

    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    reached: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            reached.add(node.module)
        elif isinstance(node, ast.Import):
            reached.update(alias.name for alias in node.names)
    engine = {name for name in reached if name.startswith("outcomebound_tools")}
    assert engine == {
        "outcomebound_tools.home",
        "outcomebound_tools.textio",
        "outcomebound_tools.tickets_declaration",
        "outcomebound_tools.tickets_model",
        "outcomebound_tools.tickets_report",
    }, sorted(engine)
    assert "subprocess" not in reached


def test_tests_import_only_public_names() -> None:
    """Every name this file takes from the engine is one its module declares."""

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
    assert reached == 6, "this file imports exactly the seam it tests"
