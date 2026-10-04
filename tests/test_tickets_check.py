"""The `check` verb: one ordered pass over the open tickets, or over drafts.

Most tests here drive `tickets.main(argv)` with the streams captured, over a
`github` export or a set of draft files written under `tmp_path`; the verb's own
seam, `tickets_check.check`, is asked directly where a report is not what is
under test. No test needs a repository: `check` asks git nothing.

What a block says is `tests/test_tickets_model.py`'s; what a section is,
`tests/test_tickets_links.py`'s; what a knot is,
`tests/test_tickets_graph.py`'s; what a draft is,
`tests/test_tickets_draft.py`'s. This file pins what `check` makes of them.

A `bounds` entry is written without a trailing separator — `a`, never `a/`,
which the block refuses as `BOUNDS_INVALID` — so every entry here is one a
ticket could carry.
"""

from __future__ import annotations

import ast
import importlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from outcomebound_tools.schemacheck import validate
from outcomebound_tools.tickets import build_parser, main
from outcomebound_tools.tickets_check import check, check_loaded
from outcomebound_tools.tickets_claims import load_claims
from outcomebound_tools.tickets_declaration import load_declaration
from outcomebound_tools.tickets_model import ReadResult
from outcomebound_tools.tickets_store import read_store
from tests.tickets_export import LABEL, REPO, export, issue

REPOSITORY = Path(__file__).resolve().parent.parent
REPORT_SCHEMA = REPOSITORY / "schemas/tickets-report.schema.json"

SPECS = "docs/specs"
DECLARATION_PATH = ".outcomebound/tickets.json"
CLAIMS_PATH = ".outcomebound/ticket-claims.json"
CLAIM = "example-claim"
BOUNDS = ("outcomebound_tools/one.py",)

# --- what the tests build ----------------------------------------------------------


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def block(
    *,
    version: str = "1",
    reads: Sequence[str] = (),
    bounds: Sequence[str] = BOUNDS,
    human_only: str = "no",
    done_when: Sequence[str] = (CLAIM,),
    discovered_from: str = "",
    status: str = "",
    blocked_by: Sequence[str] | None = None,
    parent: str | None = None,
) -> list[str]:
    """One `id=ticket` block, with only the keys a test spells out.

    `blocked_by` and `parent` are None where the key is absent and a sequence —
    possibly empty — where it is written, because "absent" and "written and
    empty" are two different inputs to this verb.
    """

    lines = [f"<!-- outcomebound:begin id=ticket v={version} -->"]
    if reads:
        lines.append(f"reads: {', '.join(reads)}")
    lines.append(f"bounds: {', '.join(bounds)}")
    lines.append(f"human-only: {human_only}")
    lines.append("done-when:")
    lines.extend(f"- {item}" for item in done_when)
    if discovered_from:
        lines.append(f"discovered-from: {discovered_from}")
    if status:
        lines.append(f"status: {status}")
    if blocked_by is not None:
        lines.append(f"blocked-by: {', '.join(blocked_by)}")
    if parent is not None:
        lines.append(f"parent: {parent}")
    lines.append("<!-- outcomebound:end id=ticket -->")
    return lines


BRIEF = ["## Outcome", "Something becomes observably true.", ""]


_HOLD_LABELS = {"yes": "human-only", "requested": "human-requested"}


def number(id: str) -> int:
    return int(id.lstrip("#"))


def document(
    id: str,
    *,
    title: str = "A ticket",
    brief: Sequence[str] = tuple(BRIEF),
    status: str = "open",
    blocked_by: Sequence[str] = (),
    parent: str = "",
    **keys: object,
) -> dict[str, object]:
    """One accepted ticket as an export node: the brief and the block as its body, its
    hold on both surfaces, and its relations and state as the tracker's own."""

    hold = str(keys.get("human_only", "no"))
    return issue(
        number(id),
        text="\n".join([*brief, *block(**keys)]) + "\n",  # type: ignore[arg-type]
        labels=(LABEL, *([_HOLD_LABELS[hold]] if hold in _HOLD_LABELS else [])),
        state=status,
        parent=number(parent) if parent else None,
        blocked_by=[number(item) for item in blocked_by],
        title=title,
    )


def draft_text(
    *,
    title: str = "A draft",
    heading: str = "",
    brief: Sequence[str] = tuple(BRIEF),
    tail: Sequence[str] = (),
    **keys: object,
) -> str:
    """One draft file: `# <title>` with no id, the brief, the block, nothing else."""

    lines = [heading or f"# {title}", "", *brief, *block(**keys), *tail]  # type: ignore[arg-type]
    return "\n".join(lines) + "\n"


DECLARED = {
    "version": 1,
    "store": "github",
    "repo": REPO,
    "label": LABEL,
    "human_label": "human-only",
    "request_label": "human-requested",
    "claims": CLAIMS_PATH,
}


def checkout(
    tmp_path: Path,
    *documents: dict[str, object],
    claims: Sequence[str] = (CLAIM,),
    cwd: str | None = None,
) -> Path:
    """A checkout declaring the store and carrying one claims plan, its export beside it."""

    root = tmp_path / "repo"
    root.mkdir(parents=True, exist_ok=True)
    write(root, DECLARATION_PATH, json.dumps(DECLARED, indent=1))
    plan: dict[str, object] = {
        "version": 1,
        "claims": [{"name": item, "command": ["true"]} for item in claims],
    }
    if cwd is not None:
        plan["cwd"] = cwd
    write(root, CLAIMS_PATH, json.dumps(plan, indent=1))
    write(tmp_path, "export.json", json.dumps(export(*documents)))
    return root


def drafts(tmp_path: Path, **files: str) -> tuple[Path, list[str]]:
    """A checkout and the paths of the draft files written beside it."""

    root = checkout(tmp_path)
    written = [str(write(root, f"drafts/{stem}.md", text)) for stem, text in files.items()]
    return root, written


# --- running it --------------------------------------------------------------------


def run(root: Path, *arguments: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    """`check` over the checkout, reading the export beside it unless it lints drafts."""

    exported = root.parent / "export.json"
    reads = "--draft" not in arguments and "--input" not in arguments and exported.is_file()
    code = main(["check", str(root), *(("--input", str(exported)) if reads else ()), *arguments])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def report(
    root: Path, *arguments: str, capsys: pytest.CaptureFixture[str], expect: int
) -> dict[str, object]:
    code, out, err = run(root, "--json", *arguments, capsys=capsys)
    assert err == "", err
    assert code == expect, out
    found: dict[str, object] = json.loads(out)
    return found


def listed(holder: Mapping[str, object], key: str) -> list[dict[str, object]]:
    """One list of objects out of a report, typed for the checker."""

    value = holder[key]
    assert isinstance(value, list)
    return [dict(item) for item in value]


def rows(found: Mapping[str, object]) -> list[dict[str, object]]:
    return listed(found, "tickets")


def about(found: Mapping[str, object], id: str) -> dict[str, object]:
    matched = [row for row in rows(found) if row["id"] == id]
    assert len(matched) == 1, [row["id"] for row in rows(found)]
    return matched[0]


def messages_of(row: Mapping[str, object]) -> list[dict[str, object]]:
    return listed(row, "messages")


def codes_of(row: Mapping[str, object]) -> list[str]:
    return [str(item["code"]) for item in messages_of(row)]


def run_codes(found: Mapping[str, object]) -> list[str]:
    return codes_of(found)


def codes(found: Mapping[str, object], id: str) -> list[str]:
    return codes_of(about(found, id))


def every_message(found: Mapping[str, object]) -> list[dict[str, object]]:
    """Every message the report carries, per ticket and then about the run."""

    return [item for row in rows(found) for item in messages_of(row)] + messages_of(found)


def every_code(found: Mapping[str, object]) -> list[str]:
    return [str(item["code"]) for item in every_message(found)]


def said(found: Mapping[str, object], code: str) -> list[str]:
    """The text and next action of every message carrying one code."""

    return [
        f"{item['text']} {item['next']}" for item in every_message(found) if item["code"] == code
    ]


# --- the empty store and the early exit --------------------------------------------


def test_empty_store_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """No ticket at all: nothing is judged, nothing is said, and the run passes."""

    found = report(checkout(tmp_path), capsys=capsys, expect=0)

    assert found["result"] == "PASS"
    assert rows(found) == []
    assert run_codes(found) == []
    assert found["counts"] == {"tickets": 0, "ignored": 0, "open": 0, "closed": 0, "dropped": 0}


def test_a_newer_block_ends_the_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A block version this engine does not ship is judged no further.

    The ticket's body is the block alone, so a pass that carried on would warn
    `BRIEF_THIN` beside the `BLOCK_MALFORMED`; exactly one message is what says the
    pass stopped.
    """

    root = checkout(tmp_path, document("#1", brief=(), version="2"))

    found = report(root, capsys=capsys, expect=1)

    assert codes(found, "#1") == ["BLOCK_MALFORMED"]
    assert found["result"] == "FAIL"


# --- the brief ---------------------------------------------------------------------


def test_brief_thin_only_without_a_brief(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty body and a heading-less one warn; one sentence under a heading does not.

    No size is judged: the one-line brief under `## Outcome` is the shortest
    body a brief admits and reads clean.
    """

    root = checkout(
        tmp_path,
        document("#1", brief=()),
        document("#2", brief=("A paragraph with no heading at all.", "")),
        document("#3", brief=("## Outcome", "One sentence.", "")),
    )

    found = report(root, capsys=capsys, expect=0)

    assert codes(found, "#1") == ["BRIEF_THIN"]
    assert codes(found, "#2") == ["BRIEF_THIN"]
    assert codes(found, "#3") == []
    assert found["result"] == "PASS", "a warning alone passes"


def test_brief_thin_skips_a_held_ticket(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A ticket whose effective hold is not `no` needs no brief."""

    root = checkout(
        tmp_path,
        document("#1", brief=(), human_only="yes"),
        document("#2", brief=(), human_only="requested"),
        document("#3", brief=()),
    )

    found = report(root, capsys=capsys, expect=0)

    assert codes(found, "#1") == []
    assert codes(found, "#2") == []
    assert codes(found, "#3") == ["BRIEF_THIN"]


def test_a_malformed_block_is_the_parsers_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A brief quoting a sentinel outside a fence is `BLOCK_MALFORMED`."""

    root = checkout(
        tmp_path,
        document("#1", brief=("## Outcome", "`<!-- outcomebound:begin id=ticket v=1 -->`", "")),
    )

    found = report(root, capsys=capsys, expect=1)

    assert "BLOCK_MALFORMED" in codes(found, "#1")
    assert found["result"] == "FAIL"


# --- drafts ------------------------------------------------------------------------


def test_drafts_are_linted_together(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A knot among the drafts given is an error on each of them.

    Two drafts naming each other are one knot; a draft blocked by its own parent
    draft is another, because waiting runs from a parent to each of its children.
    """

    root, files = drafts(
        tmp_path,
        **{
            "one": draft_text(blocked_by=["two"]),
            "two": draft_text(blocked_by=["one"]),
            "parent-draft": draft_text(),
            "child-draft": draft_text(blocked_by=["parent-draft"], parent="parent-draft"),
        },
    )

    found = report(root, "--draft", *files, capsys=capsys, expect=1)

    for stem in ("one", "two", "parent-draft", "child-draft"):
        assert codes(found, stem) == ["DEPENDENCY_CYCLE"], stem
    assert found["result"] == "FAIL"
    assert found["counts"] == {"tickets": 4, "ignored": 0, "open": 4, "closed": 0, "dropped": 0}


def test_a_repeated_draft_flag_adds_to_the_drafts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--draft a --draft b` lints both: a second flag never drops the first's files."""

    root, files = drafts(tmp_path, one=draft_text(blocked_by=["two"]), two=draft_text())
    flagged = [argument for path in files for argument in ("--draft", path)]

    found = report(root, *flagged, capsys=capsys, expect=0)

    counts = found["counts"]
    assert isinstance(counts, dict) and counts["tickets"] == 2
    assert codes(found, "one") == []


def test_what_the_draft_reader_found_reaches_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A refused relation and a duplicated block both reach the report on their own
    draft and decide it.

    What each of them is, is `tests/test_tickets_draft.py`'s; that `check`
    carries them unchanged and never re-derives them is this one's.
    """

    twice = draft_text() + "\n" + "\n".join(block()) + "\n"
    root, files = drafts(
        tmp_path,
        good=draft_text(),
        unknown_relation=draft_text(blocked_by=["tk-99-thing"]),
        two_blocks=twice,
    )

    found = report(root, "--draft", *files, capsys=capsys, expect=1)

    assert codes(found, "good") == []
    assert codes(found, "unknown_relation") == ["VALUE_INVALID"]
    assert codes(found, "two_blocks") == ["BLOCK_DUPLICATE"]
    for stem in ("unknown_relation", "two_blocks"):
        assert about(found, stem)["result"] == "FAIL", stem
    assert any("tk-99-thing" in one for one in said(found, "VALUE_INVALID"))


def test_a_draft_run_reads_no_export(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A run given no `--input` is otherwise the planning error `INPUT_REQUIRED`; a
    draft run never asks for one, and its report names no input."""

    root, written = drafts(
        tmp_path, only=draft_text(blocked_by=["other"], parent=""), other=draft_text()
    )

    found = report(root, "--draft", *written, capsys=capsys, expect=0)

    assert found["store"] == "github" and found["input"] is None
    assert every_code(found) == []


def test_a_draft_that_cannot_be_read_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A draft file that is not UTF-8 text is `TICKET_UNREADABLE`, and the run goes on."""

    root = checkout(tmp_path)
    unreadable = root / "drafts/unreadable.md"
    unreadable.parent.mkdir(parents=True, exist_ok=True)
    unreadable.write_bytes(b"# A draft\n\xff\xfe\n")
    good = str(write(root, "drafts/good.md", draft_text()))

    found = report(root, "--draft", str(unreadable), good, capsys=capsys, expect=1)

    assert "TICKET_UNREADABLE" in every_code(found)
    assert [row["id"] for row in rows(found)] == ["good"], "the unreadable file is no ticket"


def test_draft_with_input_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--draft` reads no export, so naming one is a usage error and exit 2.

    The line is printed by `check`'s own parser, so the usage a person is shown
    is the one they were typing and not the module's, which lists every verb.
    """

    root = checkout(tmp_path)
    path = str(write(root, "drafts/a-draft.md", draft_text()))

    with pytest.raises(SystemExit) as stopped:
        main(["check", str(root), "--draft", path, "--input", "-"])

    assert stopped.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--draft" in captured.err and "--input" in captured.err
    assert "check" in captured.err.split("\n")[0], captured.err
    assert "brief" not in captured.err, "the top-level usage would name every verb"


# --- links -------------------------------------------------------------------------


def test_reads_entries_resolve_or_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An anchor no heading has and one two headings share are both errors."""

    root = checkout(
        tmp_path,
        document("#1", reads=[f"{SPECS}/tickets/notes.md#present"]),
        document("#2", reads=[f"{SPECS}/tickets/notes.md#absent"]),
        document("#3", reads=[f"{SPECS}/tickets/notes.md#shared"]),
        document("#4", reads=[f"{SPECS}/tickets/gone.md#present"]),
    )
    write(
        root,
        f"{SPECS}/tickets/notes.md",
        "# Present\n\nText.\n\n## Shared\n\nOne.\n\n## Shared\n\nTwo.\n",
    )

    found = report(root, capsys=capsys, expect=1)

    assert codes(found, "#1") == []
    assert codes(found, "#2") == ["READS_UNRESOLVED"]
    assert codes(found, "#3") == ["READS_AMBIGUOUS"]
    assert codes(found, "#4") == ["READS_UNRESOLVED"]


# --- git ---------------------------------------------------------------------------


def test_check_asks_git_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """This verb makes no git call, so a checkout that is no repository is judged
    like any other."""

    root = checkout(tmp_path, document("#1"))
    asked: list[object] = []

    def refuse(*arguments: object, **named: object) -> None:
        asked.append(arguments)
        raise AssertionError("check asked git something")

    # Every git call this engine's ticket layer makes goes through `tickets_git`'s
    # `subprocess.run` or `Popen`, so a call swallowed by its caller still leaves its trace.
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)

    found = report(root, capsys=capsys, expect=0)

    assert asked == []
    assert every_code(found) == []


# --- claims ------------------------------------------------------------------------


def test_claim_planned_on_an_open_ticket(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unknown claim is a warning on an open ticket; a defined one says nothing."""

    root = checkout(
        tmp_path,
        document("#1", done_when=["unknown-claim"]),
        document("#3", done_when=[CLAIM]),
    )

    found = report(root, capsys=capsys, expect=0)

    assert codes(found, "#1") == ["CLAIM_PLANNED"]
    assert codes(found, "#3") == []


def test_closed_and_dropped_tickets_are_history(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A closed or dropped ticket's links are not resolved and it has no row; it still
    resolves the relation an open ticket names, and still counts."""

    root = checkout(
        tmp_path,
        document("#1", blocked_by=["#2"]),
        document("#2", done_when=["unknown-claim"], status="closed", brief=()),
        document("#4", reads=["docs/gone.md#nowhere"], status="dropped"),
        document("#5", status="closed", blocked_by=["#6"], parent="#6"),
        document("#6", status="closed", blocked_by=["#5"]),
    )

    found = report(root, capsys=capsys, expect=0)

    assert [row["id"] for row in rows(found)] == ["#1"]
    assert every_code(found) == [], "no knot among closed tickets, no link resolved"
    assert found["counts"] == {"tickets": 5, "ignored": 0, "open": 1, "closed": 3, "dropped": 1}


def test_a_human_item_is_an_error_where_a_ticket_is_still_to_be_worked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A `human:` item is a form this engine does not read. It is an error on an open
    ticket and on a draft, before either is worked or published; a closed ticket's is
    history."""

    item = "seen: human: a person sees it"
    root = checkout(
        tmp_path,
        document("#1", done_when=[CLAIM, item]),
        document("#2", done_when=[CLAIM, item], status="closed"),
    )

    found = report(root, capsys=capsys, expect=1)

    assert codes(found, "#1") == ["VALUE_INVALID"]
    assert [row["id"] for row in rows(found)] == ["#1"]

    drafted, written = drafts(tmp_path / "drafts", one=draft_text(done_when=[CLAIM, item]))
    linted = report(drafted, "--draft", *written, capsys=capsys, expect=1)
    assert codes(linted, "one") == ["VALUE_INVALID"]


def test_claim_cwd_outside_is_an_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A plan whose working directory resolves out of the checkout is ERROR."""

    outside = tmp_path / "elsewhere"
    outside.mkdir()
    root = checkout(tmp_path, document("#1"), cwd="link")
    (root / "link").symlink_to(outside, target_is_directory=True)

    found = report(root, capsys=capsys, expect=1)

    assert run_codes(found) == ["CLAIM_CWD_OUTSIDE"], "it is a fact about the run, not a ticket"
    assert any(str(outside.resolve()) in one for one in said(found, "CLAIM_CWD_OUTSIDE"))
    assert found["result"] == "FAIL"


def test_an_absent_claims_plan_is_a_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A plan that is not there is `CLAIMS_UNREADABLE`, exit 1 and no report."""

    root = checkout(tmp_path, document("#1"))
    (root / CLAIMS_PATH).unlink()

    code, out, err = run(root, capsys=capsys)

    assert (code, out) == (1, "")
    assert err.startswith("CLAIMS_UNREADABLE: ")


def test_a_claims_plan_whose_cwd_holds_a_nul_is_a_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A top-level `cwd` holding a NUL byte is `CLAIMS_UNREADABLE`, exit 1 and no
    report, never a traceback."""

    root = checkout(tmp_path, document("#1"), cwd="a\0b")

    code, out, err = run(root, capsys=capsys)

    assert (code, out) == (1, "")
    assert err.startswith("CLAIMS_UNREADABLE: ")
    assert "the top-level cwd contains a NUL byte" in err


def test_a_malformed_declaration_is_a_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A declaration that is not JSON is `DECLARATION_INVALID`, exit 1 and no report."""

    root = checkout(tmp_path)
    write(root, DECLARATION_PATH, "{not json")

    code, out, err = run(root, capsys=capsys)

    assert (code, out) == (1, "")
    assert err.startswith("DECLARATION_INVALID: ")


# --- relations ---------------------------------------------------------------------


def test_cycle_is_an_error_on_each_ticket(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A knot of three reads `DEPENDENCY_CYCLE` on each of its tickets."""

    root = checkout(
        tmp_path,
        document("#1", blocked_by=["#2"]),
        document("#2"),
        document("#3", parent="#2", blocked_by=["#1"]),
        document("#4"),
    )

    found = report(root, capsys=capsys, expect=1)

    for id in ("#1", "#2", "#3"):
        assert codes(found, id) == ["DEPENDENCY_CYCLE"], id
        assert all("#4" not in one for one in said(found, "DEPENDENCY_CYCLE"))
    assert codes(found, "#4") == []


def test_discovered_from_absent_warns_and_makes_no_knot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An id the input does not hold warns, and the key is no edge of the graph."""

    root = checkout(
        tmp_path,
        document("#1", discovered_from="#99"),
        document("#2", discovered_from="#3"),
        document("#3", discovered_from="#2"),
    )

    found = report(root, capsys=capsys, expect=0)

    assert codes(found, "#1") == ["DISCOVERED_FROM_ABSENT"]
    assert codes(found, "#2") == []
    assert codes(found, "#3") == []
    assert "DEPENDENCY_CYCLE" not in every_code(found)


# --- what the reader said ----------------------------------------------------------


def test_reader_messages_reach_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A lifecycle key the tracker holds natively is an error on its ticket's row and
    decides it; a message the reader stamped on an issue that is no ticket has no
    row to sit on and is the run's."""

    in_the_block = issue(2, text="\n".join([*BRIEF, *block(status="open")]) + "\n")
    no_ticket = issue(3, labels=())
    no_ticket["labels"] = {"nodes": [], "pageInfo": {"hasNextPage": True}}
    root = checkout(tmp_path, document("#1"), in_the_block, no_ticket)

    found = report(root, capsys=capsys, expect=1)

    assert codes(found, "#1") == []
    assert codes(found, "#2") == ["KEY_UNKNOWN"]
    assert "EXPORT_TRUNCATED" in run_codes(found)
    assert about(found, "#2")["result"] == "FAIL"
    assert found["result"] == "FAIL"


def test_bounds_findings_reach_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A `bounds` entry with an empty last segment grants nothing and is an error;
    one whose literal part is the whole repository is a warning.

    A ticket is linted through `check`, so this is pinned where `check` carries
    it and not only where the model decides it.
    """

    root = checkout(
        tmp_path,
        document("#1", bounds=["docs/"]),
        document("#2", bounds=["."]),
        document("#3", bounds=["docs/specs"]),
    )

    found = report(root, capsys=capsys, expect=1)

    assert codes(found, "#1") == ["BOUNDS_INVALID"]
    assert codes(found, "#2") == ["BOUNDS_WHOLE_REPOSITORY"]
    assert codes(found, "#3") == [], "a directory is written without a trailing separator"
    assert any("docs/" in one for one in said(found, "BOUNDS_INVALID"))


# --- the seam, the schema and two runs ---------------------------------------------


def test_check_is_the_verbs_own_seam(tmp_path: Path) -> None:
    """`check(target, declaration, options)` is every verb's signature, and parses no option."""

    root = checkout(tmp_path, document("#1", brief=()))
    source = str(tmp_path / "export.json")
    options = build_parser().parse_args(["check", str(root), "--input", source])

    built = check(root, load_declaration(root), options)

    assert built.verb == "check"
    assert built.store == "github"
    assert [item.code for item in built.tickets[0].messages] == ["BRIEF_THIN"]


def test_a_store_already_read_is_judged_without_being_read_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`check_loaded` judges the store and the plan a caller already holds.

    A verb that reads the store for its own reasons and then wants this verb's
    judgement — `brief` — hands over what it read. Reading it a second time is
    at best two openings of one file and at worst a stream that is empty the
    second time, so nothing here reads either again.
    """

    root = checkout(tmp_path, document("#1", brief=()))
    declaration = load_declaration(root)
    source = str(tmp_path / "export.json")
    options = build_parser().parse_args(["check", str(root), "--input", source])
    read = read_store(root, declaration, source)
    plan = load_claims(root, declaration)
    itself = check(root, declaration, options)

    def refuse(*arguments: object, **keys: object) -> ReadResult:
        raise AssertionError("what the caller handed over was read again")

    monkeypatch.setattr("outcomebound_tools.tickets_check.read_store", refuse)
    monkeypatch.setattr("outcomebound_tools.tickets_check.load_claims", refuse)

    built = check_loaded(root, declaration, options, read, plan)

    assert built.verb == "check"
    assert [item.code for item in built.tickets[0].messages] == ["BRIEF_THIN"]
    assert built == itself, "one verb, whoever read the store"


def test_report_is_stable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Two runs over one input render identically, and the JSON is what the schema describes."""

    root = checkout(
        tmp_path,
        document("#1", brief=()),
        document("#2", done_when=["unknown-claim"], blocked_by=["#1"]),
    )

    first = run(root, capsys=capsys)
    second = run(root, capsys=capsys)
    assert first == second

    text_first, text_second = (run(root, "--json", capsys=capsys) for _ in range(2))
    assert text_first == text_second

    schema = json.loads(REPORT_SCHEMA.read_text(encoding="utf-8"))
    assert validate(json.loads(text_first[1]), schema) == []


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
    assert reached == 8, "this file imports exactly the seam it tests"
