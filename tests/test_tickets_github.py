"""The GitHub export reader: the gate, relations and truncation.

Everything here is driven through the module's public seam —
`tickets_github.read_github_export` over `tests/fixtures/tickets/github-export.json`
(a synthetic export of a fictional project's tracker) and over variants written
under `tmp_path`. Nothing spawns a subprocess, opens a socket or reads a
credential, because the reader does none of those things: a caller runs the
pinned export and the engine reads the file it produced.

The fixture export holds parents with children and chains of blockers, every
ticket accepted and every relation local, and it reads clean. Each foreign
relation, dropped ticket, malformed value, refusal and truncation is built as a
`variant(...)` copy of it, so one case changes only what it names. Each node
also carries fields the pinned query does not ask for — its times, author,
`assignees`, `comments` and `timelineItems`, as a wider query answers — which
the reader passes over. `github-export-truncated.json` is a separate,
hand-built export for the page-truncation case.
"""

from __future__ import annotations

import ast
import importlib
import json
from collections.abc import Callable, Iterator, Mapping
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_github import read_github_export
from outcomebound_tools.tickets_model import ReadResult, Ticket
from outcomebound_tools.tickets_report import Message, Refusal

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "tickets"
EXPORT = FIXTURES / "github-export.json"
TRUNCATED = FIXTURES / "github-export-truncated.json"

# The declaration the fixture export reads against: its repository's name and
# the three labels its tracker carries.
DECLARED = Declaration(
    store="github",
    repo="example-org/example-project",
    label="ob-ticket",
    human_label="human-only",
    request_label="human-requested",
    claims=".outcomebound/ticket-claims.json",
)
# The one placeholder account every issue, comment and event in the fixture export carries.
PLACEHOLDER_LOGIN = "example-user"
# The same repository, spelled as a tracker also accepts it.
OTHER_CASE = replace(DECLARED, repo="Example-Org/Example-Project")
# `github-export-truncated.json` names its own placeholder repository; it reads
# against a declaration that matches it, not the fixture export's.
TRUNCATED_DECLARED = replace(DECLARED, repo="owner/project")

# Every ticket in the fixture export, in the order the reader returns them: the
# export answers no issue #30, as a real one does not where that number went to a
# pull request — the `issues` query does not answer pull requests, and a
# repository's issues and pull requests share one number sequence — and every
# other number from 1 to 39 is a ticket.
TICKET_IDS = [f"#{number}" for number in (*range(1, 30), *range(31, 40))]
# No issue in the fixture export fails the gate: every one of them carries `ob-ticket`.


# --- reading the fixtures -----------------------------------------------------------


def read(source: Path | str = EXPORT, declaration: Declaration = DECLARED) -> ReadResult:
    """The reader's result over an export, the fixture export by default."""

    return read_github_export(source, declaration)


def by_id(result: ReadResult) -> dict[str, Ticket]:
    return {ticket.id: ticket for ticket in result.tickets}


def ticket(result: ReadResult, id: str) -> Ticket:
    return by_id(result)[id]


def about(result: ReadResult, id: str) -> tuple[Message, ...]:
    """Every message the reader stamped with that ticket id, in the order given."""

    return tuple(item for item in result.messages if item.ticket == id)


def codes(result: ReadResult, id: str) -> list[str]:
    return [item.code for item in about(result, id)]


def pages() -> list[Any]:
    loaded: list[Any] = json.loads(EXPORT.read_text(encoding="utf-8"))
    return loaded


def nodes(loaded: list[Any]) -> Iterator[Any]:
    for page in loaded:
        yield from page["data"]["repository"]["issues"]["nodes"]


def node(loaded: list[Any], number: int) -> Any:
    for found in nodes(loaded):
        if found["number"] == number:
            return found
    raise AssertionError(f"the fixture holds no issue {number}")


def variant(tmp_path: Path, change: Callable[[list[Any]], None], name: str = "export.json") -> Path:
    """The fixture export with one deliberate change, written where a test can read it."""

    loaded = pages()
    change(loaded)
    path = tmp_path / name
    path.write_text(json.dumps(loaded, indent=2), encoding="utf-8")
    return path


def split_pages(loaded: list[Any]) -> None:
    """Deal the fixture export's nodes across two pages, as `--paginate` would write them.

    The fixture export is one page, so a test that needs a page other than the
    last builds one from it rather than keeping a second export. The envelope is
    copied, the nodes are split between the two, the first page's own `pageInfo`
    reports a further page with a cursor, and the last page is otherwise the
    fixture's.
    """

    assert len(loaded) == 1, "split_pages assumes the fixture export is one page"
    last = loaded[0]
    all_nodes = last["data"]["repository"]["issues"]["nodes"]
    half = len(all_nodes) // 2
    first = json.loads(json.dumps(last))
    first["data"]["repository"]["issues"]["nodes"] = all_nodes[:half]
    first["data"]["repository"]["issues"]["pageInfo"] = {
        "hasNextPage": True,
        "endCursor": "cursor-page-one",
    }
    last["data"]["repository"]["issues"]["nodes"] = all_nodes[half:]
    loaded[:] = [first, last]


def refusal(source: Path | str, declaration: Declaration = DECLARED) -> Refusal:
    with pytest.raises(Refusal) as raised:
        read(source, declaration)
    return raised.value


def strip_label(number: int, label: str = DECLARED.label) -> Callable[[list[Any]], None]:
    """A change that drops the declared label, so this issue reads as an `other`."""

    def change(loaded: list[Any]) -> None:
        target = node(loaded, number)
        target["labels"]["nodes"] = [
            item for item in target["labels"]["nodes"] if item["name"] != label
        ]

    return change


# --- the pages ----------------------------------------------------------------------


def test_pages_are_joined_in_order(tmp_path: Path) -> None:
    # The whole export's order is test_the_fixture_export_reads_as_its_tickets'.

    # split across two pages, the first of them not the last: the pages join
    # in the same order, and whether more remain is read from the last page
    # only — the first page's own `hasNextPage: true` decides nothing
    split = read(variant(tmp_path, split_pages))
    assert [item.id for item in split.tickets] == TICKET_IDS
    assert split.messages == ()


def test_truncation_table(tmp_path: Path) -> None:
    # That the fixture export is whole, with no message, is
    # test_the_fixture_export_reads_as_its_tickets'.

    # the last page reports a further page: run-level (the constructed fixture)
    short = read(TRUNCATED, TRUNCATED_DECLARED)
    run = [item for item in short.messages if not item.ticket]
    assert [item.code for item in run] == ["EXPORT_TRUNCATED"]
    assert run[0].next

    # every connection of the query reports for itself, and names itself; the
    # fixture export is whole, so this is built. A connection the pinned query
    # does not ask for is read by nothing, so a further page of it says nothing.
    connections = {"#3": "labels", "#4": "blockedBy"}
    unread = {"#1": "assignees", "#5": "comments"}

    def flag_pages(loaded: list[Any]) -> None:
        for id, connection in {**connections, **unread}.items():
            node(loaded, int(id[1:]))[connection]["pageInfo"]["hasNextPage"] = True

    flagged = read(variant(tmp_path, flag_pages))
    for id, connection in connections.items():
        said = [item for item in about(flagged, id) if item.code == "EXPORT_TRUNCATED"]
        assert len(said) == 1, id
        assert f"`{connection}`" in said[0].text, id
        assert said[0].next, id
    assert all(codes(flagged, id) == [] for id in unread)


QUERY = ROOT / "templates" / "tickets" / "github-export.graphql"


def test_nested_connections_read_100_and_a_truncation_names_no_re_run(tmp_path: Path) -> None:
    """The pinned query asks 100 of each nested connection, GitHub's largest page, and a
    nested connection does not paginate: its truncation names the issue and the bound,
    and never sends a reader to run the export again, which would read the same 100."""

    query = QUERY.read_text(encoding="utf-8")
    assert "labels(first: 100)" in query and "blockedBy(first: 100)" in query

    def flag(loaded: list[Any]) -> None:
        node(loaded, 4)["blockedBy"]["pageInfo"]["hasNextPage"] = True
        strip_label(9)(loaded)
        node(loaded, 9)["labels"]["pageInfo"]["hasNextPage"] = True

    result = read(variant(tmp_path, flag))
    for id, connection in (("#4", "blockedBy"), ("#9", "labels")):
        [said] = [item for item in about(result, id) if item.code == "EXPORT_TRUNCATED"]
        assert "more than 100" in said.text, said
        assert id in said.next and f"`{connection}`" in said.next, said
        assert "cannot help" in said.next and "run the pinned export again" not in said.next


def _error_at(
    number: int, *rest: object, message: str = "Could not resolve"
) -> Callable[[list[Any]], None]:
    """A change adding a GraphQL error whose path runs into one issue's node."""

    def change(loaded: list[Any]) -> None:
        listed = loaded[0]["data"]["repository"]["issues"]["nodes"]
        at = next(index for index, found in enumerate(listed) if found["number"] == number)
        path = ["repository", "issues", "nodes", at, *rest]
        loaded[0].setdefault("errors", []).append({"message": message, "path": path})

    return change


def test_an_error_inside_one_issue_holds_that_issue_and_the_rest_are_read(
    tmp_path: Path,
) -> None:
    """An `errors` entry whose path lies inside one issue node makes that issue
    UNVERIFIED, read with what arrived of it, and every other ticket reads as before."""

    def change(loaded: list[Any]) -> None:
        _error_at(26, "blockedBy", "nodes", 1, message="Resource not accessible")(loaded)
        node(loaded, 26)["blockedBy"]["nodes"][1] = None

    result = read(variant(tmp_path, change))
    [said] = [item for item in about(result, "#26") if item.code == "EXPORT_PARTIAL"]
    assert said.level.name == "UNVERIFIED"
    assert "Resource not accessible" in said.text and "blockedBy.nodes.1" in said.text
    assert ticket(result, "#26").blocked_by == ("#24", "#3")
    assert [item.id for item in result.tickets] == TICKET_IDS
    clean = read()
    for id in TICKET_IDS:
        if id != "#26":
            assert about(result, id) == about(clean, id), id
            assert ticket(result, id) == ticket(clean, id), id


def test_an_error_inside_an_issue_outside_the_gate_is_reported_and_held(tmp_path: Path) -> None:
    """An errored issue the gate leaves out may carry the label on what the error cut,
    so it reads UNVERIFIED against its own id; the tickets are read as before."""

    def change(loaded: list[Any]) -> None:
        strip_label(9)(loaded)
        _error_at(9, "labels")(loaded)
        node(loaded, 9)["labels"] = None

    result = read(variant(tmp_path, change))
    assert "#9" in result.others
    assert codes(result, "#9") == ["EXPORT_PARTIAL"]
    assert len(result.tickets) == len(TICKET_IDS) - 1


def test_an_error_naming_no_issue_node_still_refuses(tmp_path: Path) -> None:
    """No path, a path to a whole node, or an index past the page names no one issue."""

    def at_whole_node(loaded: list[Any]) -> None:
        loaded[0]["errors"] = [{"message": "gone", "path": ["repository", "issues", "nodes", 0]}]

    def past_the_page(loaded: list[Any]) -> None:
        loaded[0]["errors"] = [
            {"message": "gone", "path": ["repository", "issues", "nodes", 999, "title"]}
        ]

    def at_the_repository(loaded: list[Any]) -> None:
        loaded[0]["errors"] = [{"message": "gone", "path": ["repository"]}]

    for change in (at_whole_node, past_the_page, at_the_repository):
        raised = refusal(variant(tmp_path, change, name=f"{change.__name__}.json"))
        assert raised.code == "EXPORT_UNREADABLE", change.__name__
        assert "names no issue node" in raised.text, change.__name__


def test_an_issue_outside_the_gate_with_unfinished_labels_reads_truncated(tmp_path: Path) -> None:
    """The gate was decided from a label set the export did not finish.

    Every issue in the fixture export carries `ob-ticket`, so both halves are
    built: two issues lose their ticket label, and one of them also reports a
    further `labels` page.
    """

    def change(loaded: list[Any]) -> None:
        strip_label(9)(loaded)
        node(loaded, 9)["labels"]["pageInfo"]["hasNextPage"] = True
        strip_label(6)(loaded)

    result = read(variant(tmp_path, change))
    assert "#9" in result.others
    said = [
        item for item in result.messages if item.code == "EXPORT_TRUNCATED" and item.ticket == "#9"
    ]
    assert len(said) == 1
    assert "#9" in said[0].text
    assert "labels" in said[0].text
    assert said[0].next

    # an issue outside the gate whose labels are complete says nothing
    assert "#6" in result.others
    assert not [item for item in result.messages if item.ticket == "#6"]


def test_an_empty_export_reads_no_ticket(tmp_path: Path) -> None:
    def empty(loaded: list[Any]) -> None:
        issues = loaded[0]["data"]["repository"]["issues"]
        issues["nodes"] = []
        issues["pageInfo"]["hasNextPage"] = False

    result = read(variant(tmp_path, empty))
    assert result.tickets == ()
    assert result.others == frozenset()
    assert result.ignored == 0
    assert result.messages == ()


# --- the export is this project's, and whole ----------------------------------------


def test_a_page_naming_another_repository_refuses(tmp_path: Path) -> None:
    """An export of another repository would otherwise be numbered as this one's.

    The repository is named on every page and not only on the first, so
    each case here is built on the second of two split pages.
    """

    def elsewhere(loaded: list[Any]) -> None:
        split_pages(loaded)
        loaded[1]["data"]["repository"]["nameWithOwner"] = "other/project"

    raised = refusal(variant(tmp_path, elsewhere))
    assert raised.code == "EXPORT_UNREADABLE"
    assert "other/project" in raised.text
    assert DECLARED.repo in raised.text

    def absent(loaded: list[Any]) -> None:
        split_pages(loaded)
        del loaded[1]["data"]["repository"]["nameWithOwner"]

    missing = refusal(variant(tmp_path, absent, name="absent.json"))
    assert missing.code == "EXPORT_UNREADABLE"
    assert "nameWithOwner" in missing.text

    # and the refusal comes before any id is assigned, whatever the page holds
    def numbered(loaded: list[Any]) -> None:
        split_pages(loaded)
        loaded[1]["data"]["repository"]["nameWithOwner"] = "other/project"
        loaded[1]["data"]["repository"]["issues"]["nodes"] = []

    assert refusal(variant(tmp_path, numbered, name="numbered.json")).code == "EXPORT_UNREADABLE"


# Every connection the query asks for, with the `pageInfo` flag that connection carries.
CONNECTION_FLAGS = {
    "labels": "hasNextPage",
    "blockedBy": "hasNextPage",
}


def test_a_connection_the_export_does_not_hold_refuses(tmp_path: Path) -> None:
    """A node's shape is validated whatever it is: the gate decides after."""

    for number in (1, 9):
        for index, (name, flag) in enumerate(CONNECTION_FLAGS.items()):

            def whole(loaded: list[Any], name: str = name, number: int = number) -> None:
                del node(loaded, number)[name]

            def listed(loaded: list[Any], name: str = name, number: int = number) -> None:
                del node(loaded, number)[name]["nodes"]

            def flagged(
                loaded: list[Any], name: str = name, flag: str = flag, number: int = number
            ) -> None:
                del node(loaded, number)[name]["pageInfo"][flag]

            def unanswered(
                loaded: list[Any], name: str = name, flag: str = flag, number: int = number
            ) -> None:
                node(loaded, number)[name]["pageInfo"][flag] = None

            changes = (("whole", whole), ("nodes", listed), ("flag", flagged), ("null", unanswered))
            for kind, change in changes:
                path = variant(tmp_path, change, name=f"{number}-{index}-{kind}.json")
                raised = refusal(path)
                assert raised.code == "EXPORT_UNREADABLE", (number, name, kind)
                assert f"`{name}`" in raised.text, (number, name, kind)
                assert f"#{number}" in raised.text, (number, name, kind)


def test_an_issue_without_the_parent_key_refuses(tmp_path: Path) -> None:
    """A null `parent` is a present value; an absent one is a key nobody answered."""

    def gone(loaded: list[Any]) -> None:
        del node(loaded, 1)["parent"]

    raised = refusal(variant(tmp_path, gone))
    assert raised.code == "EXPORT_UNREADABLE"
    assert "`parent`" in raised.text

    assert node(pages(), 1)["parent"] is None, "the fixture's issue #1 must carry a null parent"
    assert ticket(read(), "#1").parent == ""


# --- the gate -----------------------------------------------------------------------


def test_the_label_alone_makes_a_ticket(tmp_path: Path) -> None:
    """The declared label is the acceptance, and no edit lapses it. Who wrote the
    issue, who labelled it and an edit made after the label decide nothing; without
    the label an issue is another issue, whose id still resolves."""

    def edited_by_another(loaded: list[Any]) -> None:
        target = node(loaded, 4)
        target["author"] = {"login": "someone-else"}
        target["lastEditedAt"] = "2026-04-01T10:00:00Z"
        target["title"] = "A title changed after the label"
        for event in target["timelineItems"]["nodes"]:
            event["actor"] = {"login": "someone-else"}

    edited = read(variant(tmp_path, edited_by_another))
    assert [item.id for item in edited.tickets] == TICKET_IDS
    assert codes(edited, "#4") == []

    unlabelled = read(variant(tmp_path, strip_label(2), name="unlabelled.json"))
    assert unlabelled.others == frozenset({"#2"})
    assert unlabelled.ignored == 1


def test_a_relation_to_an_issue_outside_the_gate_still_resolves(tmp_path: Path) -> None:
    """A parent excluded by the gate is still a local id, not a foreign one."""

    def change(loaded: list[Any]) -> None:
        strip_label(2)(loaded)

    result = read(variant(tmp_path, change))
    assert "#2" in result.others
    outside = ticket(result, "#12")
    assert outside.parent == "#2"
    assert "RELATION_EXTERNAL" not in codes(result, "#12")


def test_state_mapping_table() -> None:
    result = read()
    states = {id: item.state for id, item in by_id(result).items()}
    assert states["#1"] == "open"
    assert states["#7"] == "closed"
    assert states["#27"] == "open"
    assert states["#28"] == "open"


def test_an_unknown_state_refuses(tmp_path: Path) -> None:
    def rewrite(loaded: list[Any]) -> None:
        node(loaded, 1)["state"] = "MERGED"

    raised = refusal(variant(tmp_path, rewrite))
    assert raised.code == "EXPORT_UNREADABLE"
    assert "MERGED" in raised.text


def test_a_closed_issue_with_a_dropped_reason_reads_dropped(tmp_path: Path) -> None:
    """`CLOSED` with `NOT_PLANNED` or `DUPLICATE` reads `dropped`.

    The fixture export holds no dropped ticket, so this is built: a `COMPLETED`
    close, rewritten with the reason the tracker writes for a dropped one.
    """

    def dropped(loaded: list[Any]) -> None:
        node(loaded, 10)["stateReason"] = "NOT_PLANNED"

    assert ticket(read(variant(tmp_path, dropped)), "#10").state == "dropped"


# --- relations ----------------------------------------------------------------------


def test_foreign_relations_and_unseen_children(tmp_path: Path) -> None:
    """Every relation in the fixture export is local; every case here is built."""

    def foreign_parent(loaded: list[Any]) -> None:
        node(loaded, 16)["parent"] = {"number": 7, "repository": {"nameWithOwner": "other/repo"}}

    result = read(variant(tmp_path, foreign_parent))
    found = ticket(result, "#16")
    assert found.parent == "other/repo#7"
    assert "RELATION_EXTERNAL" in codes(result, "#16")
    assert "other/repo#7" not in by_id(result)

    def mixed_blockers(loaded: list[Any]) -> None:
        node(loaded, 17)["blockedBy"]["nodes"] = [
            {"number": 2, "repository": {"nameWithOwner": "other/repo"}},
            {"number": 3, "repository": {"nameWithOwner": DECLARED.repo}},
        ]

    beside = read(variant(tmp_path, mixed_blockers, name="beside.json"))
    found_beside = ticket(beside, "#17")
    assert found_beside.blocked_by == ("other/repo#2", "#3")
    assert "RELATION_EXTERNAL" in codes(beside, "#17")
    assert ticket(beside, "#3").id == "#3", "the local ticket of that number is untouched"

    def unnamed_blocker(loaded: list[Any]) -> None:
        node(loaded, 18)["blockedBy"]["nodes"] = [{"number": 5}]

    unnamed_result = read(variant(tmp_path, unnamed_blocker, name="unnamed.json"))
    unnamed = ticket(unnamed_result, "#18")
    assert unnamed.blocked_by == ("?#5",)
    assert "RELATION_EXTERNAL" in codes(unnamed_result, "#18")
    assert "#5" in by_id(unnamed_result), "the local ticket of that number is a separate id"

    def unseen_children(loaded: list[Any]) -> None:
        node(loaded, 19)["subIssuesSummary"]["total"] = 2

    unseen_result = read(variant(tmp_path, unseen_children, name="unseen.json"))
    unseen = [item for item in about(unseen_result, "#19") if item.code == "RELATION_EXTERNAL"]
    assert len(unseen) == 1
    assert "2" in unseen[0].text

    # every child present, and a wholly local relation: nothing to report, as
    # the fixture export already reads
    whole = read()
    assert "RELATION_EXTERNAL" not in codes(whole, "#1"), "#1's 25 children are all in the export"
    assert ticket(whole, "#34").blocked_by == ("#33", "#32", "#31")
    assert "RELATION_EXTERNAL" not in codes(whole, "#34")


def test_the_declared_repository_is_matched_with_case_folded(tmp_path: Path) -> None:
    """A tracker treats two spellings of one repository as one."""

    folded = read(declaration=OTHER_CASE)
    assert [item.id for item in folded.tickets] == TICKET_IDS

    def mixed_blockers(loaded: list[Any]) -> None:
        node(loaded, 17)["blockedBy"]["nodes"] = [
            {"number": 2, "repository": {"nameWithOwner": "other/repo"}},
            {"number": 3, "repository": {"nameWithOwner": "EXAMPLE-ORG/EXAMPLE-PROJECT"}},
        ]

    result = read(variant(tmp_path, mixed_blockers), declaration=OTHER_CASE)
    found = ticket(result, "#17")
    assert found.blocked_by == ("other/repo#2", "#3")
    assert "RELATION_EXTERNAL" not in [
        item.code for item in about(result, "#17") if "#3" in item.text
    ]


def test_a_relation_without_a_number_refuses_wherever_it_hangs(tmp_path: Path) -> None:
    """Blockers are validated for every issue, though only a ticket's are carried."""

    def missing_number(loaded: list[Any]) -> None:
        node(loaded, 22)["blockedBy"]["nodes"] = [{"repository": {"nameWithOwner": "other/repo"}}]

    assert refusal(variant(tmp_path, missing_number)).code == "EXPORT_UNREADABLE"

    def local_but_unnumbered(loaded: list[Any]) -> None:
        node(loaded, 23)["blockedBy"]["nodes"] = [{"repository": {"nameWithOwner": DECLARED.repo}}]

    raised = refusal(variant(tmp_path, local_but_unnumbered, name="other.json"))
    assert raised.code == "EXPORT_UNREADABLE"
    assert "number" in raised.text


# --- the block in a github body -----------------------------------------------------


def test_lifecycle_key_in_a_github_block_is_unknown(tmp_path: Path) -> None:
    lines = {
        "status": "status: open",
        "assignee": "assignee: author-one",
        "blocked-by": "blocked-by: #2",
        "parent": "parent: #2",
    }
    for index, (key, line) in enumerate(lines.items()):

        def rewrite(loaded: list[Any], line: str = line) -> None:
            first = node(loaded, 3)
            first["body"] = first["body"].replace("human-only: no", f"human-only: no\n{line}")

        result = read(variant(tmp_path, rewrite, name=f"key-{index}.json"))
        said = [item for item in about(result, "#3") if item.code == "KEY_UNKNOWN"]
        assert len(said) == 1, key
        assert key in said[0].text, key
        assert said[0].level.name == "ERROR", key


def test_waits_on_in_a_github_block_is_read_onto_the_ticket(tmp_path: Path) -> None:
    """No tracker relation holds a wait on a decision brief, so a `github` block carries
    it, and the reader puts it on the ticket without a message."""

    def change(loaded: list[Any]) -> None:
        target = node(loaded, 2)
        target["body"] = target["body"].replace(
            "<!-- outcomebound:end id=ticket -->",
            "waits-on: D1\n<!-- outcomebound:end id=ticket -->",
        )

    result = read(variant(tmp_path, change))
    assert ticket(result, "#2").waits_on == ("D1",)
    assert codes(result, "#2") == []


def test_hold_surfaces(tmp_path: Path) -> None:
    """The fixture export's two hold surfaces agree on every ticket; each disagreement
    is built here."""

    def change(loaded: list[Any]) -> None:
        block_no_label_yes = node(loaded, 16)
        block_no_label_yes["body"] = block_no_label_yes["body"].replace(
            "human-only: no", "human-only: no"
        )
        block_no_label_yes["labels"]["nodes"].append({"name": "human-only"})

        block_no_label_requested = node(loaded, 17)
        block_no_label_requested["labels"]["nodes"].append({"name": "human-requested"})

        block_yes_label_requested = node(loaded, 18)
        block_yes_label_requested["body"] = block_yes_label_requested["body"].replace(
            "human-only: no", "human-only: yes"
        )
        block_yes_label_requested["labels"]["nodes"].append({"name": "human-requested"})

        block_yes_label_yes = node(loaded, 19)
        block_yes_label_yes["body"] = block_yes_label_yes["body"].replace(
            "human-only: no", "human-only: yes"
        )
        block_yes_label_yes["labels"]["nodes"].append({"name": "human-only"})

    result = read(variant(tmp_path, change))
    holds = {id: (item.human_only, item.hold) for id, item in by_id(result).items()}
    assert holds["#16"] == ("no", "yes")
    assert holds["#17"] == ("no", "requested")
    assert holds["#18"] == ("yes", "yes")
    assert holds["#19"] == ("yes", "yes")
    assert holds["#20"] == ("no", "no"), "an untouched ticket is the consistent baseline"
    differ = {item.ticket for item in result.messages if item.code == "HOLD_SURFACES_DIFFER"}
    assert differ == {"#16", "#17", "#18"}


def test_a_block_without_human_only_has_no_surface_to_differ(tmp_path: Path) -> None:
    """The missing required key is the finding; the labels do not add a second."""

    def drop(loaded: list[Any]) -> None:
        held = node(loaded, 16)
        held["body"] = held["body"].replace("human-only: no\n", "")
        held["labels"]["nodes"].append({"name": "human-only"})

    result = read(variant(tmp_path, drop))
    assert "KEY_MISSING" in codes(result, "#16")
    assert "HOLD_SURFACES_DIFFER" not in codes(result, "#16")
    assert ticket(result, "#16").hold == "yes", "the label still holds the ticket"
    assert ticket(result, "#16").human_only == ""


def test_a_record_in_a_body_makes_the_block_unreadable(tmp_path: Path) -> None:
    def unfenced(loaded: list[Any]) -> None:
        first = node(loaded, 1)
        first["body"] = (
            "<!-- outcomebound:begin id=evidence v=1 -->\nverdict: PASS\n"
            "<!-- outcomebound:end id=evidence -->\n\n" + first["body"]
        )

    result = read(variant(tmp_path, unfenced))
    assert "BLOCK_MALFORMED" in codes(result, "#1")


# --- the input a report prints ------------------------------------------------------


def test_input_age_from_a_file_and_from_standard_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "issues.json"
    path.write_text(EXPORT.read_text(encoding="utf-8"), encoding="utf-8")
    written = datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp()
    import os

    os.utime(path, (written, written))

    from_file = read(path)
    assert from_file.input is not None
    assert from_file.input.path == str(path)
    assert from_file.input.modified == "2026-09-01T00:00:00Z"
    assert from_file.input.age_seconds is not None
    assert from_file.input.age_seconds > 0

    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(path.read_text(encoding="utf-8")))
    piped = read("-")
    assert piped.input is not None
    assert piped.input.path == "-"
    assert piped.input.modified is None
    assert piped.input.age_seconds is None
    assert [item.id for item in piped.tickets] == [item.id for item in from_file.tickets]


# --- refusals -----------------------------------------------------------------------


def test_export_unreadable_refuses(tmp_path: Path) -> None:
    absent = tmp_path / "absent.json"
    assert refusal(absent).code == "EXPORT_UNREADABLE"

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert refusal(broken).code == "EXPORT_UNREADABLE"

    one = tmp_path / "one.json"
    one.write_text(json.dumps(pages()[0]), encoding="utf-8")
    assert "array" in refusal(one).text

    def failed(loaded: list[Any]) -> None:
        loaded[0]["errors"] = [{"message": "Something went wrong"}]

    assert refusal(variant(tmp_path, failed, name="errors.json")).code == "EXPORT_UNREADABLE"

    def repeated(loaded: list[Any]) -> None:
        split_pages(loaded)
        # #1 lives on the first page; appending it to the second is a
        # duplicate that spans a page boundary, not one page repeating itself
        issues = loaded[1]["data"]["repository"]["issues"]
        issues["nodes"].append(node(loaded, 1))

    assert "#1" in refusal(variant(tmp_path, repeated, name="twice.json")).text

    def shapeless(loaded: list[Any]) -> None:
        split_pages(loaded)
        loaded[1]["data"] = {"repository": None}

    assert refusal(variant(tmp_path, shapeless, name="shapeless.json")).code == "EXPORT_UNREADABLE"

    # a relation nobody can spell is never dropped in silence either: that is
    # test_a_relation_without_a_number_refuses_wherever_it_hangs


# --- the normalised ticket ----------------------------------------------------------


def test_two_reads_are_equal() -> None:
    first, second = read(), read()
    assert first.tickets == second.tickets
    assert first.others == second.others
    assert first.messages == second.messages
    assert first.ignored == second.ignored


# --- the fixture export itself ------------------------------------------------------


def test_the_fixture_export_reads_as_its_tickets() -> None:
    """`github-export.json` reads clean: every issue it holds is an accepted ticket,
    with the holds its labels and blocks show.
    """

    result = read()
    assert result.messages == ()
    assert [item.id for item in result.tickets] == TICKET_IDS
    assert result.others == frozenset()
    assert result.ignored == 0

    # a parent with children, and one of the children's own blockers
    assert ticket(result, "#1").parent == ""
    assert ticket(result, "#24").blocked_by == ("#39",)
    assert ticket(result, "#37").blocked_by == ("#10", "#36")

    # holds surface only where the tracker labelled them, and agree with the
    # block on every ticket
    held = {item.id for item in result.tickets if item.hold == "yes"}
    assert held == {"#1", "#2", "#4", "#5", "#8", "#9", "#11", "#25", "#28"}
    assert not [item for item in result.tickets if item.hold == "requested"]


def _issue_logins(issue: Mapping[str, Any]) -> Iterator[str]:
    """Every login one issue node spells: its author, assignees, comments and events,
    the fields a wider query than the pinned one answers."""

    if issue.get("author"):
        yield issue["author"]["login"]
    for assignee in issue["assignees"]["nodes"]:
        if isinstance(assignee, dict) and assignee.get("login"):
            yield assignee["login"]
    for comment in issue["comments"]["nodes"]:
        if comment.get("author"):
            yield comment["author"]["login"]
    for event in issue.get("timelineItems", {"nodes": []})["nodes"]:
        if event.get("actor"):
            yield event["actor"]["login"]


def test_the_fixture_export_is_the_pinned_querys_shape() -> None:
    """Every page carries the repository's name and every connection the query asks for."""

    loaded = pages()
    assert loaded, "the fixture export holds at least one page"
    logins: set[str] = set()
    for page in loaded:
        repository = page["data"]["repository"]
        assert repository["nameWithOwner"].casefold() == DECLARED.repo.casefold()
        issues = repository["issues"]
        assert isinstance(issues["pageInfo"]["hasNextPage"], bool)
        for issue in issues["nodes"]:
            assert "parent" in issue
            for name, flag in CONNECTION_FLAGS.items():
                connection = issue[name]
                assert isinstance(connection["nodes"], list), (issue["number"], name)
                assert isinstance(connection["pageInfo"][flag], bool), (issue["number"], name)
            logins.update(_issue_logins(issue))

    # the fixture names no real account: every login in it is the one placeholder
    assert logins == {PLACEHOLDER_LOGIN}


def test_an_export_without_times_author_or_timeline_reads_the_same(tmp_path: Path) -> None:
    """The gate reads the label alone, so the node's own times and author and its
    `timelineItems`, which the pinned query does not ask for, decide nothing: the
    fixture export, less them, reads the same tickets."""

    def trimmed(loaded: list[Any]) -> None:
        for found in nodes(loaded):
            for key in ("createdAt", "updatedAt", "lastEditedAt", "author", "timelineItems"):
                found.pop(key, None)

    assert read(variant(tmp_path, trimmed)).tickets == read().tickets


def test_an_export_without_closed_at_assignees_or_comments_reads_the_same(
    tmp_path: Path,
) -> None:
    """The engine does not judge how work landed, so `closedAt`, `assignees` and
    `comments`, which the pinned query does not ask for, decide nothing: the fixture
    export carries them and reads, and less them it reads the same."""

    def without(loaded: list[Any]) -> None:
        for found in nodes(loaded):
            for key in ("closedAt", "assignees", "comments"):
                del found[key]

    full, trimmed = read(), read(variant(tmp_path, without))
    assert (trimmed.tickets, trimmed.others, trimmed.messages) == (
        full.tickets,
        full.others,
        full.messages,
    )


# --- the seam -----------------------------------------------------------------------


def test_tests_import_only_public_names() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=__file__)
    reached = 0
    for found in ast.walk(tree):
        if not isinstance(found, ast.ImportFrom) or found.module is None:
            continue
        if not found.module.startswith("outcomebound_tools.tickets"):
            continue
        public = set(importlib.import_module(found.module).__all__)
        for alias in found.names:
            reached += 1
            assert alias.name in public, f"{found.module}.{alias.name} is not in __all__"
    assert reached >= 6, "the survey found fewer imported names than this file uses"


def test_the_public_seam_is_one_name() -> None:
    """This module has one seam, and a later package needs no other.

    How a relation is spelled reaches every later package through the ticket
    values themselves, so a store-agnostic module never imports this one to
    classify an id.
    """

    reader = importlib.import_module("outcomebound_tools.tickets_github")
    assert reader.__all__ == ["read_github_export"]
