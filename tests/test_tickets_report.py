"""The one report value, the message table, the exit rule and the command skeleton.

Everything here is driven through the module's public seam: the names
`tickets_report` exports, and `tickets.main(argv)` with the streams captured.
Nothing spawns a subprocess and nothing touches a repository, because none of
these decisions needs one.
"""

from __future__ import annotations

import ast
import importlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from outcomebound_tools.schemacheck import validate
from outcomebound_tools.tickets import VERBS, build_parser, main
from outcomebound_tools.tickets_report import (
    MESSAGES,
    Counts,
    EngineError,
    Level,
    Message,
    PlanningError,
    Refusal,
    Report,
    ReportError,
    TicketResult,
    exit_code,
    message,
    render_json,
    render_text,
    result,
)

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas/tickets-report.schema.json"
# Results from best to worst. The module's own table is private, so the order a
# test compares against is written out here.
RESULT_ORDER = ("PASS", "UNVERIFIED", "FAIL")


@dataclass(frozen=True, slots=True)
class _Export:
    """The report's `input` object, as a reader hands it over.

    The report names the shape it needs structurally, as
    `tickets_report.InputSource`, so this stand-in has the shape of the reader's
    value, `tickets_model.InputInfo`, and this file imports nothing from the reader.
    """

    path: str
    modified: str | None
    age_seconds: int | None
    ids: tuple[int, int] | None = None


def _schema() -> dict[str, object]:
    document: dict[str, object] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return document


def _report(
    *,
    tickets: tuple[TicketResult, ...] = (),
    messages: tuple[Message, ...] = (),
) -> Report:
    """A report with every key filled in, before a test varies one thing."""

    return Report(
        verb="check",
        store="github",
        input=_Export(path="issues.json", modified="2026-09-20T09:00:00Z", age_seconds=120),
        counts=Counts(tickets=21, ignored=4, open=9, closed=11, dropped=1),
        tickets=tickets,
        messages=messages,
    )


def _ticket(*messages: Message) -> TicketResult:
    return TicketResult(
        id="#42",
        title="Reports exit by the ratified convention",
        state="closed",
        messages=messages,
    )


# --- the message table ----------------------------------------------------------


def test_every_code_in_the_table_is_emitted_somewhere() -> None:
    """A code stays in the table only while a module spells it, so none outlives its caller."""

    engine = ROOT / "outcomebound_tools"
    spelled = "".join(
        path.read_text(encoding="utf-8")
        for path in engine.glob("tickets*.py")
        if path.name != "tickets_report.py"
    )
    assert [code for code in MESSAGES if f'"{code}"' not in spelled] == []


def test_unknown_code_raises() -> None:
    with pytest.raises(ReportError) as raised:
        message("NOT_A_CODE", "#42", "nothing defines this")
    assert "NOT_A_CODE" in str(raised.value)


def test_levels_are_ordered_worst_last() -> None:
    assert Level.INFO < Level.WARNING < Level.UNVERIFIED < Level.ERROR


def _a_code_of(level: Level) -> str:
    """One code the table gives that level, so a test can raise the level it means."""

    return next(code for code, found in MESSAGES.items() if found is level)


def test_a_worse_level_never_reads_better() -> None:
    """The level a message carries and the result it makes rise together.

    A table that read a WARNING as FAIL and an ERROR as PASS would satisfy
    every single-level test above; what makes the worst level decide a ticket
    is that the result never falls.
    """

    reads = [
        RESULT_ORDER.index(
            result(_report(tickets=(_ticket(message(_a_code_of(level), "#42", "…")),)))
        )
        for level in sorted(Level)
    ]
    named = dict(zip([level.name for level in sorted(Level)], reads, strict=True))
    assert reads == sorted(reads), named
    assert reads[0] == 0, "an INFO message alone never moves a verdict"
    assert reads[-1] == RESULT_ORDER.index("FAIL"), "an ERROR always reads FAIL"


# --- verdicts and the exit rule --------------------------------------------------


def test_a_report_with_nothing_in_it_passes() -> None:
    report = _report()
    assert result(report) == "PASS"
    assert exit_code(report) == 0


def test_worst_ticket_decides_the_run() -> None:
    failing = _ticket(message("DEPENDENCY_CYCLE", "#42", "#42 stands in a cycle"))
    unverified = TicketResult(
        id="#43",
        title="Another",
        state="open",
        messages=(message("EXPORT_TRUNCATED", "#43", "a further page"),),
    )
    passing = TicketResult(id="#44", title="Third", state="closed")
    report = _report(tickets=(passing, unverified, failing))
    assert result(report) == "FAIL"
    assert exit_code(report) == 1
    assert result(_report(tickets=(passing, unverified))) == "UNVERIFIED"
    assert result(_report(tickets=(passing,))) == "PASS"


def test_a_run_level_message_counts_as_a_ticket_of_its_own() -> None:
    report = _report(messages=(message("EXPORT_TRUNCATED", "", "a further page"),))
    assert result(report) == "UNVERIFIED"
    assert exit_code(report) == 2


@pytest.mark.parametrize(
    "code, expected, code_exit",
    [
        ("DEPENDENCY_CYCLE", "FAIL", 1),
        ("RELATION_EXTERNAL", "UNVERIFIED", 2),
        ("BRIEF_THIN", "PASS", 0),
        ("HOLD_SURFACES_DIFFER", "PASS", 0),
    ],
)
def test_exit_codes(code: str, expected: str, code_exit: int) -> None:
    report = _report(tickets=(_ticket(message(code, "#42", "…")),))
    assert result(report) == expected
    assert exit_code(report) == code_exit


# --- rendering -------------------------------------------------------------------


def _json_subject() -> Report:
    return _report(
        tickets=(_ticket(message("RELATION_EXTERNAL", "#42", "#9 is elsewhere", next="move it")),),
        messages=(message("HOLD_SURFACES_DIFFER", "", "the block and the labels differ"),),
    )


def _text_subject() -> Report:
    return _report(
        tickets=(_ticket(message("BRIEF_THIN", "#42", "#42 says nothing")),),
        messages=(message("RELATION_EXTERNAL", "#44", "#9 is elsewhere", next="move it"),),
    )


def _rendered_elsewhere(subject: str, renderer: str, seed: str) -> str:
    """The same report rendered by a fresh interpreter under another hash seed.

    One process renders a set in one order however often it is asked, so stability
    is only shown across interpreters whose string hashing differs.
    """

    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r}); "
        f"from tests.test_tickets_report import {subject}; "
        f"from outcomebound_tools.tickets_report import {renderer}; "
        f"sys.stdout.write({renderer}({subject}()))"
    )
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONHASHSEED": seed},
    ).stdout


def test_json_report_validates_and_is_stable() -> None:
    report = _json_subject()
    rendered = render_json(report)
    assert {_rendered_elsewhere("_json_subject", "render_json", seed) for seed in "123"} == {
        rendered
    }
    assert rendered.endswith("\n")
    document = json.loads(rendered)
    assert validate(document, _schema()) == []
    assert document["result"] == "UNVERIFIED"
    assert list(document) == [
        "result",
        "verb",
        "store",
        "input",
        "counts",
        "tickets",
        "messages",
    ]
    assert document["tickets"][0]["result"] == "UNVERIFIED"
    assert document["messages"][0] == {
        "level": "INFO",
        "code": "HOLD_SURFACES_DIFFER",
        "ticket": "",
        "text": "the block and the labels differ",
        "next": "",
    }


def test_a_report_that_read_no_export_renders_null() -> None:
    report = Report(verb="check", store="github")
    document = json.loads(render_json(report))
    assert document["input"] is None
    assert validate(document, _schema()) == []


def test_a_draft_reported_before_it_has_an_id_validates() -> None:
    """`check --draft` reports a ticket file that has no id yet, by its file stem."""

    report = _report(
        tickets=(TicketResult(id="tk-08-check", title="The check verb", state="open"),)
    )
    document = json.loads(render_json(report))
    assert document["tickets"][0]["id"] == "tk-08-check"
    assert validate(document, _schema()) == []
    empty = json.loads(render_json(_report(tickets=(TicketResult("", "Nameless", "open"),))))
    assert validate(empty, _schema()) != [], "a ticket with no id at all is still refused"


def test_input_read_from_standard_input_has_no_modification_time() -> None:
    report = Report(
        verb="check",
        store="github",
        input=_Export(path="-", modified=None, age_seconds=None),
    )
    document = json.loads(render_json(report))
    assert document["input"] == {"path": "-", "modified": None, "age_seconds": None}
    assert validate(document, _schema()) == []
    assert "age unknown" in render_text(report)


def test_the_input_line_names_the_ids_the_export_holds() -> None:
    """A ticket newer than the export is above the range the line names; the JSON
    report keeps its schema's three `input` keys."""

    held = Report(
        verb="check",
        store="github",
        input=_Export(
            path="issues.json", modified="2026-09-20T09:00:00Z", age_seconds=120, ids=(3, 42)
        ),
    )
    empty = Report(
        verb="check",
        store="github",
        input=_Export(path="issues.json", modified="2026-09-20T09:00:00Z", age_seconds=120),
    )

    assert (
        "input: issues.json; modified 2026-09-20T09:00:00Z; age 120s; holds #3 to #42"
        in render_text(held)
    )
    assert "age 120s; holds no issue" in render_text(empty)
    assert validate(json.loads(render_json(held)), _schema()) == []


def test_text_report_is_stable_and_names_every_subject() -> None:
    report = _text_subject()
    text = render_text(report)
    assert {_rendered_elsewhere("_text_subject", "render_text", seed) for seed in "123"} == {text}
    assert text.endswith("\n")
    lines = text.splitlines()
    assert lines[0] == "check: UNVERIFIED"
    assert "store: github" in lines
    assert "counts: tickets 21; ignored 4; open 9; closed 11; dropped 1" in lines
    assert "PASS\t#42\tReports exit by the ratified convention (closed)" in lines
    assert "WARNING\t#42\tBRIEF_THIN: #42 says nothing" in lines
    assert "UNVERIFIED\t#44\tRELATION_EXTERNAL: #9 is elsewhere; next: move it" in lines


def test_a_report_key_the_schema_does_not_declare_is_refused() -> None:
    """A change that adds a report key adds it to the schema in the same change."""

    document = json.loads(render_json(_report()))
    document["nothing_declares_this"] = "open"
    assert validate(document, _schema()) != []


# --- the command skeleton --------------------------------------------------------


def test_verbs_are_check_brief_publish_and_export() -> None:
    assert tuple(VERBS) == ("check", "brief", "publish", "export")
    parser = build_parser()
    for name in VERBS:
        assert parser.parse_args([name, "."]).verb == name


def test_an_unknown_verb_and_no_verb_are_usage_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for argv in ([], ["frobnicate"]):
        with pytest.raises(SystemExit) as raised:
            main(argv)
        assert raised.value.code == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "usage:" in captured.err


def test_the_target_defaults_to_the_current_directory() -> None:
    assert build_parser().parse_args(["check"]).target == "."


def test_every_verb_that_reads_the_store_takes_the_export_as_input(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`export` prints the command that makes an export and reads none, so it
    refuses `--input` as a usage error rather than ignoring it."""

    parser = build_parser()
    for name in ("check", "brief", "publish"):
        assert parser.parse_args([name, ".", "--input", "issues.json"]).input == "issues.json"
    assert parser.parse_args(["check", "."]).input is None
    with pytest.raises(SystemExit) as raised:
        parser.parse_args(["export", ".", "--input", "issues.json"])
    assert raised.value.code == 2
    assert "--input" in capsys.readouterr().err


def test_every_verbs_options_are_total() -> None:
    """An option a verb does not offer is refused on the command line and still has
    its default in the namespace, so a verb reading `options.input` meets no gap."""

    parser = build_parser()
    for name in VERBS:
        parsed = parser.parse_args([name, "."])
        assert parsed.input is None, name
        assert parsed.json is False, name


def test_every_verb_that_reports_takes_json() -> None:
    parser = build_parser()
    assert parser.parse_args(["check", ".", "--json"]).json is True
    assert parser.parse_args(["check", "."]).json is False
    with pytest.raises(SystemExit) as raised:
        parser.parse_args(["brief", ".", "--json"])
    assert raised.value.code == 2


@pytest.fixture
def declared(tmp_path: Path) -> str:
    """A checkout that declares its store: what every verb needs before it runs."""

    path = tmp_path / ".outcomebound" / "tickets.json"
    path.parent.mkdir()
    document = {
        "version": 1,
        "store": "github",
        "repo": "owner/project",
        "label": "ob-ticket",
        "human_label": "human-only",
        "request_label": "human-requested",
        "claims": ".outcomebound/ticket-claims.json",
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(tmp_path)


def test_an_undeclared_project_is_refused_before_any_verb_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The target is named beside a ticket where the verb takes one: a lone
    positional is the ticket, and the target would then be wherever the suite
    happens to run — a project that may well have declared a store."""

    given = {"brief": ["#1"], "publish": ["--draft", str(tmp_path / "a.md")]}
    for name in VERBS:
        assert main([name, str(tmp_path), *given.get(name, [])]) == 1, name
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err.startswith("DECLARATION_MISSING: "), name


def test_refusal_prints_no_report(
    declared: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuses(target: Path, declaration: object, options: object) -> Report:
        raise Refusal("EXPORT_UNREADABLE", "the github export could not be read")

    monkeypatch.setattr("outcomebound_tools.tickets.VERBS", {**VERBS, "check": refuses})
    assert main(["check", declared]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "EXPORT_UNREADABLE: the github export could not be read\n"


def test_a_planning_error_prints_one_line_and_exits_two(
    declared: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A `github` store given no export is a run that cannot be planned."""

    def cannot_plan(target: Path, declaration: object, options: object) -> Report:
        raise PlanningError("INPUT_REQUIRED", "pass the export as --input <file>")

    monkeypatch.setattr("outcomebound_tools.tickets.VERBS", {**VERBS, "check": cannot_plan})
    assert main(["check", declared]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "INPUT_REQUIRED: pass the export as --input <file>\n"


def test_a_planning_error_carries_its_code_and_text() -> None:
    error = PlanningError("INPUT_REQUIRED", "no export was given")
    assert error.code == "INPUT_REQUIRED"
    assert error.text == "no export was given"
    assert str(error) == "INPUT_REQUIRED: no export was given"


def test_a_refusal_carries_its_code_and_text() -> None:
    refusal = Refusal("DECLARATION_MISSING", "no declaration at .outcomebound/tickets.json")
    assert refusal.code == "DECLARATION_MISSING"
    assert refusal.text == "no declaration at .outcomebound/tickets.json"
    assert str(refusal) == "DECLARATION_MISSING: no declaration at .outcomebound/tickets.json"


def test_every_verb_is_the_function_that_runs_it() -> None:
    """Each row of `VERBS` holds the function of that name, from its module.

    What each verb does is its own test file's to pin; what this file holds is
    that the table names each verb's function and no placeholder.
    """

    assert [verb.__name__ for verb in VERBS.values()] == list(VERBS)


def test_an_engine_error_is_one_named_line_and_no_traceback(
    declared: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The engine could not act. The module's own sentence is what is printed."""

    class CouldNot(EngineError):
        pass

    def cannot_act(target: Path, declaration: object, options: object) -> Report:
        raise CouldNot("git could not be run: no such file or directory")

    monkeypatch.setattr("outcomebound_tools.tickets.VERBS", {**VERBS, "check": cannot_act})
    assert main(["check", declared]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "ENGINE_ERROR: git could not be run: no such file or directory\n"


def test_a_defect_in_a_report_keeps_its_traceback(
    declared: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A report built wrong is this engine's defect, not something it could not act on."""

    def built_wrong(target: Path, declaration: object, options: object) -> Report:
        return Report(verb="check", store="github", messages=(message("NOT_A_CODE", "", "…"),))

    monkeypatch.setattr("outcomebound_tools.tickets.VERBS", {**VERBS, "check": built_wrong})
    with pytest.raises(ReportError):
        main(["check", declared])
    assert not issubclass(ReportError, EngineError)


# --- the seam --------------------------------------------------------------------


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
    assert reached >= 15, "the survey found fewer imported names than this file uses"
