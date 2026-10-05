"""`python3 -m outcomebound_tools.decision_brief`: an agent's own decisions drawn by the
one renderer.

The seam is the command line: a JSON document in, the markdown `render` draws out, and
the exit code. The golden output is a two-brief document, one brief with its own
diagram, and their order, drawn under each symbol set and diagram form; the symbols and
the form default to what the stream can carry and what the session's surface renders,
and a flag overrides each.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

import pytest

from outcomebound_tools import decision_brief, surfaces
from outcomebound_tools.decision_brief import Brief

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schemas" / "decision-briefs.schema.json"

# Two briefs and the order between them: D2, a tag, waits on D1, which draws how an
# upgrade reads the flag.
DOCUMENT = {
    "briefs": [
        {
            "id": "D1",
            "heading": "Keep the old flag for one release?",
            "recommend": "two adopters still set it",
            "recommend_way": "keep it one release",
            "confidence": "80% (inferred)",
            "options": [
                [
                    "drop it now",
                    "the code path goes today",
                    "an adopter setting it is refused on upgrade",
                ],
                [
                    "keep it one release",
                    "adopters get a warning first",
                    "one more release carries the old code path",
                ],
            ],
            "checked": {
                "verdicts": ["PASS"],
                "text": "`grep -r old_flag` finds two adopters' configs",
            },
            "undo": {"can_be_undone": True, "text": "revert the commit"},
            "diagram": {
                "caption": "How an upgrade reads the flag",
                "edges": [["config", "warning", "old_flag"], ["warning", "new flag"]],
            },
        },
        {
            "id": "D2",
            "heading": "Tag the release once D1 is settled?",
            "recommend": "tag it, since every release check passes",
            "why_now": "the release waits on it",
            "checked": {
                "verdicts": ["PASS", "UNVERIFIED"],
                "text": "make test PASS, hosted CI UNVERIFIED",
            },
            "not_checked": "the hosted run, which needs your login",
            "undo": {"can_be_undone": False, "text": "a pushed tag cannot be taken back"},
        },
    ],
    "order": [["D1", "D2"]],
}

UNDO = {"can_be_undone": True, "text": "revert the commit"}
# The same, spelled inside a JSON object literal a test writes by hand.
JSON_UNDO = ', "undo": {"can_be_undone": true, "text": "r"}'
# A line of evidence, which every brief the command draws carries.
EVIDENCE = {"not_checked": "the hosted run, which needs a login"}
# Two ways forward, each with what it leads to and its downside.
TWO_WAYS = [["x", "one place", "a cost"], ["y", "another", "another cost"]]

EMOJI_ASCII = """\
### D1 · Keep the old flag for one release?
- 👉 Recommend: B — two adopters still set it · confidence 80% (inferred)
- Options:
  - A drop it now — the code path goes today
    - 🔻 Downside: an adopter setting it is refused on upgrade
  - B keep it one release — adopters get a warning first
    - 🔻 Downside: one more release carries the old code path
- ✅ Checked: `grep -r old_flag` finds two adopters' configs
- ↩️ Undo: revert the commit

How an upgrade reads the flag
```text
config --old_flag--> warning --> new flag
```

### D2 · Tag the release once D1 is settled?
- 👉 Recommend: tag it, since every release check passes
- Why now: the release waits on it
- ⚠️ Checked: make test PASS, hosted CI UNVERIFIED
- ⚠️ Not checked: the hosted run, which needs your login
- ⛔ Undo: a pushed tag cannot be taken back

### Order — an arrow points at what waits on it
```text
D1 --> D2
```
"""

ASCII_MERMAID = """\
### D1 | Keep the old flag for one release?
- [>] Recommend: B - two adopters still set it | confidence 80% (inferred)
- Options:
  - A drop it now - the code path goes today
    - [-] Downside: an adopter setting it is refused on upgrade
  - B keep it one release - adopters get a warning first
    - [-] Downside: one more release carries the old code path
- [ok] Checked: `grep -r old_flag` finds two adopters' configs
- [undo] Undo: revert the commit

How an upgrade reads the flag
```mermaid
flowchart LR
  n1["config"] -->|old_flag| n2["warning"]
  n2["warning"] --> n3["new flag"]
```

### D2 | Tag the release once D1 is settled?
- [>] Recommend: tag it, since every release check passes
- Why now: the release waits on it
- [!] Checked: make test PASS, hosted CI UNVERIFIED
- [!] Not checked: the hosted run, which needs your login
- [!!] Undo: a pushed tag cannot be taken back

### Order - an arrow points at what waits on it
```mermaid
flowchart LR
  n1["D1"] --> n2["D2"]
```
"""

# Each diagram's fence in each form, as the two goldens draw it, and the ASCII marks
# with ASCII diagrams.
ASCII_FLAG = "```text\nconfig --old_flag--> warning --> new flag\n```"
MERMAID_FLAG = ASCII_MERMAID.split("How an upgrade reads the flag\n", 1)[1].split("\n\n", 1)[0]
ASCII_ORDER = "```text\nD1 --> D2\n```"
MERMAID_ORDER = '```mermaid\nflowchart LR\n  n1["D1"] --> n2["D2"]\n```'
ASCII_ASCII = ASCII_MERMAID.replace(MERMAID_FLAG, ASCII_FLAG).replace(MERMAID_ORDER, ASCII_ORDER)


def _write(tmp_path: Path, document: object, name: str = "briefs.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _main(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = decision_brief.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _run(
    argv: list[str], env: dict[str, str], stdin: str = "", cwd: Path = ROOT
) -> subprocess.CompletedProcess[bytes]:
    """The command as an agent runs it, in an environment holding only what is given,
    from `cwd`."""

    carried = {name: os.environ[name] for name in ("PATH", "LD_LIBRARY_PATH") if name in os.environ}
    return subprocess.run(
        [sys.executable, "-m", "outcomebound_tools.decision_brief", *argv],
        env={**carried, "PYTHONPATH": str(ROOT), **env},
        cwd=cwd,
        input=stdin.encode("utf-8"),
        capture_output=True,
        check=False,
    )


def test_two_briefs_and_their_order_are_drawn_as_the_renderer_draws_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Golden output under each symbol set and form: each brief's lines in order, the
    recommended way lettered, each Option's downside under it, the passed mark only
    where every verdict is PASS, the cannot-be-undone mark, D1's diagram after its
    list, and the order after the last brief."""

    path = _write(tmp_path, DOCUMENT)

    assert _main(capsys, str(path), "--symbols", "emoji", "--form", "ascii") == (
        0,
        EMOJI_ASCII,
        "",
    )
    assert _main(capsys, str(path), "--symbols", "ascii", "--form", "mermaid") == (
        0,
        ASCII_MERMAID,
        "",
    )


def test_the_document_is_read_from_standard_input_under_a_dash() -> None:
    completed = _run(
        ["-", "--symbols", "emoji", "--form", "ascii"],
        {"PYTHONIOENCODING": "utf-8"},
        stdin=json.dumps(DOCUMENT),
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.decode("utf-8") == EMOJI_ASCII


def test_the_symbols_follow_what_standard_output_can_carry(tmp_path: Path) -> None:
    """Without `--symbols`, the marks are emoji on a stream that can encode them and
    ASCII on one that cannot; `--symbols` names them over the stream."""

    path = str(_write(tmp_path, DOCUMENT))
    wide = _run([path, "--form", "ascii"], {"PYTHONIOENCODING": "utf-8"})
    narrow = _run([path, "--form", "mermaid"], {"PYTHONIOENCODING": "cp1252"})
    forced = _run([path, "--form", "ascii", "--symbols", "ascii"], {"PYTHONIOENCODING": "utf-8"})

    assert wide.returncode == 0, wide.stderr
    assert wide.stdout.decode("utf-8") == EMOJI_ASCII
    assert narrow.returncode == 0, narrow.stderr
    assert narrow.stdout.decode("cp1252") == ASCII_MERMAID
    assert forced.stdout.decode("utf-8") == ASCII_ASCII


def test_the_form_follows_the_session_surface(tmp_path: Path) -> None:
    """Without `--form`, a diagram takes the form the person's OUTCOMEBOUND_DIAGRAMS
    names, and ASCII where nothing identifies the surface; `--form` names it over
    the variable either way."""

    path = str(_write(tmp_path, DOCUMENT))
    base = {"PYTHONIOENCODING": "utf-8"}
    recorded = _run([path, "--symbols", "ascii"], {**base, "OUTCOMEBOUND_DIAGRAMS": "mermaid"})
    unknown = _run([path, "--symbols", "ascii"], base)
    over_mermaid = _run(
        [path, "--symbols", "emoji", "--form", "ascii"],
        {**base, "OUTCOMEBOUND_DIAGRAMS": "mermaid"},
    )
    over_ascii = _run(
        [path, "--symbols", "ascii", "--form", "mermaid"],
        {**base, "OUTCOMEBOUND_DIAGRAMS": "ascii"},
    )

    assert recorded.returncode == 0, recorded.stderr
    assert recorded.stdout.decode("utf-8") == ASCII_MERMAID
    assert unknown.returncode == 0, unknown.stderr
    assert unknown.stdout.decode("utf-8") == ASCII_ASCII
    assert over_mermaid.stdout.decode("utf-8") == EMOJI_ASCII
    assert over_ascii.stdout.decode("utf-8") == ASCII_MERMAID


def _table(tmp_path: Path, mermaid: bool) -> Path:
    """A surface table of one row, selected by `Z=1`, recording whether it renders
    Mermaid, with its provenance."""

    path = tmp_path / "surfaces.json"
    row = {
        "harness": "a-harness",
        "signals": {"environment": [{"name": "Z", "value": "1"}], "store": None, "source": "x"},
        "mermaid": mermaid,
        "provenance": {"kind": "observed", "on": "2026-01-15", "by": "a", "url": None, "says": "x"},
    }
    path.write_text(json.dumps({"z": row}), encoding="utf-8")
    return path


def test_the_table_names_the_form_and_the_flag_outranks_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A surface the table records as rendering Mermaid draws it; one it records as
    not rendering it draws ASCII, as does a table that cannot be read; `--form`
    names the form over the table."""

    path = str(_write(tmp_path, DOCUMENT))
    monkeypatch.delenv("OUTCOMEBOUND_DIAGRAMS", raising=False)
    monkeypatch.setenv("Z", "1")

    monkeypatch.setattr(surfaces, "_TABLE_PATH", _table(tmp_path, mermaid=True))
    assert _main(capsys, path, "--symbols", "ascii")[1] == ASCII_MERMAID
    assert _main(capsys, path, "--symbols", "ascii", "--form", "ascii")[1] == ASCII_ASCII

    monkeypatch.setattr(surfaces, "_TABLE_PATH", _table(tmp_path, mermaid=False))
    assert _main(capsys, path, "--symbols", "ascii")[1] == ASCII_ASCII
    assert _main(capsys, path, "--symbols", "ascii", "--form", "mermaid")[1] == ASCII_MERMAID

    monkeypatch.setattr(surfaces, "_TABLE_PATH", tmp_path / "missing.json")
    assert _main(capsys, path, "--symbols", "ascii") == (0, ASCII_ASCII, "")


@pytest.mark.parametrize(("symbols", "sep"), [("emoji", " · "), ("ascii", " | ")])
def test_the_id_is_joined_to_the_heading_by_the_symbols_separator(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], symbols: str, sep: str
) -> None:
    brief = {"id": "C3", "heading": "#3 — Issue 3", "undo": UNDO, **EVIDENCE}
    path = _write(tmp_path, {"briefs": [brief]})
    heading = _main(capsys, str(path), "--symbols", symbols)[1].splitlines()[0]
    assert heading == f"### C3{sep}#3 — Issue 3"


def test_a_scoped_id_is_drawn_whole_in_the_heading_and_the_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The decision-brief skill scopes an id with the task's name, `fix-login-D1`, so that
    two sessions never share one; the renderer keeps that whole id wherever it draws it."""

    briefs = [
        {"id": f"fix-login-D{n}", "heading": f"Question {n}?", "undo": UNDO, **EVIDENCE}
        for n in (1, 2)
    ]
    path = _write(tmp_path, {"briefs": briefs, "order": [["fix-login-D1", "fix-login-D2"]]})
    code, out, _ = _main(capsys, str(path), "--symbols", "ascii", "--form", "ascii")
    assert code == 0
    assert "### fix-login-D1 | Question 1?" in out.splitlines()
    assert "fix-login-D1 --> fix-login-D2" in out.splitlines()


def test_nothing_to_put_says_nothing_waits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, {"briefs": []})
    assert _main(capsys, str(path), "--symbols", "ascii") == (0, "nothing waits on a person\n", "")


@pytest.mark.parametrize(
    ("brief", "refusal"),
    [
        (
            {"options": [["only way", "it happens", "a cost"]], **EVIDENCE},
            "a brief lays out Options only where there are two or more ways forward; "
            "this one lays out 1",
        ),
        (
            {"options": [[f"way {n}", "it happens", "a cost"] for n in range(27)], **EVIDENCE},
            "a brief letters its Options from A to Z, so it lays out at most 26; "
            "this one lays out 27",
        ),
        (
            {"confidence": "fact", **EVIDENCE},
            "a brief's confidence belongs to its Recommend line, and this one has none",
        ),
        (
            {"recommend": "R", "recommend_way": "z", "options": TWO_WAYS, **EVIDENCE},
            "a brief letters only a way it lays out, and 'z' is not among its Options",
        ),
        (
            {"options": TWO_WAYS, **EVIDENCE},
            "a brief that lays out 2 Options recommends one of them, "
            "and this one has no Recommend line",
        ),
        (
            {"recommend": "it is cheaper", "options": TWO_WAYS, **EVIDENCE},
            "a brief that lays out 2 Options names the one it recommends in recommend_way, "
            "and this one names none",
        ),
        (
            {"recommend": "tag it", "why_now": "the release waits", "debt": "one slow test"},
            "a brief carries at least one line of evidence, checked, not_checked or facts, "
            "and this one has none",
        ),
    ],
    ids=[
        "one-option",
        "27-options",
        "confidence-alone",
        "way-not-laid-out",
        "options-no-recommend",
        "options-no-recommended-way",
        "no-evidence",
    ],
)
def test_a_brief_below_what_the_command_draws_exits_one_naming_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], brief: dict[str, object], refusal: str
) -> None:
    """Exit 1, nothing drawn, and the refusal named with the brief's place and id, so the
    agent can fix the one brief: what `render` refuses, and the floor the command holds
    an agent's own decisions to, two or more Options with no recommended way among them
    and a brief with no line of evidence."""

    path = _write(
        tmp_path,
        {
            "briefs": [
                {"id": "D1", "heading": "Fine", "undo": UNDO, **EVIDENCE},
                {"id": "D2", "heading": "Q", "undo": UNDO, **brief},
            ]
        },
    )
    code, out, err = _main(capsys, str(path))

    assert (code, out) == (1, "")
    assert err == f"decision_brief: brief 2, D2, is refused: {refusal}\n"


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ("{", "is not JSON"),
        ('["a list"]', "$ must be of type object"),
        (
            '{"briefs": [{"id": "D1", "recommend": "x"}]}',
            "$.briefs[0] is missing required field 'heading'",
        ),
        ('{"briefs": [{"heading": "Q"}]}', "$.briefs[0] is missing required field 'id'"),
        (
            '{"briefs": [{"id": "D1", "heading": "Q", "mark": "x"}]}',
            "$.briefs[0] has unknown field(s): mark",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q", "undo": {"text": "revert"}}]}',
            "$.briefs[0].undo is missing required field 'can_be_undone'",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"' + JSON_UNDO + ","
            ' "options": [["a", "b", "c", "d"], ["e", "f", "g"]]}]}',
            "$.briefs[0].options[0] must hold exactly three strings",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"' + JSON_UNDO + ","
            ' "options": [["a", "b", "c"], ["d", "e"]]}]}',
            "$.briefs[0].options[1] must hold exactly three strings: the way, what it leads to, "
            "and its downside",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"' + JSON_UNDO + ","
            ' "options": [["a", "b", ""], ["d", "e", "f"]]}]}',
            "$.briefs[0].options[0][2] must be at least 1 character(s)",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"' + JSON_UNDO + ', "diagram": {}}]}',
            "$.briefs[0].diagram is missing required field 'edges'",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"' + JSON_UNDO + ', "diagram": {"edges": []}}]}',
            "$.briefs[0].diagram.edges must have at least 1 item(s)",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"'
            + JSON_UNDO
            + ', "diagram": {"edges": [["a"]]}}]}',
            "$.briefs[0].diagram.edges[0] must have at least 2 item(s)",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"'
            + JSON_UNDO
            + ', "diagram": {"edges": [["a", "b", "c", "d"]]}}]}',
            "$.briefs[0].diagram.edges[0] must hold two or three strings",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"'
            + JSON_UNDO
            + ', "diagram": {"edges": [["a", "b"]], "title": "t"}}]}',
            "$.briefs[0].diagram has unknown field(s): title",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"'
            + JSON_UNDO
            + ', "diagram": {"edges": [["a", "the \\"old\\" flag"]]}}]}',
            "$.briefs[0].diagram.edges[0][1] holds a double quote",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"'
            + JSON_UNDO
            + ', "diagram": {"edges": [["a", "b", "say \\"yes\\""]]}}]}',
            "$.briefs[0].diagram.edges[0][2] holds a double quote",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"'
            + JSON_UNDO
            + ', "diagram": {"edges": [["a", "b", "yes | no"]]}}]}',
            "$.briefs[0].diagram.edges[0][2] holds a |",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"'
            + JSON_UNDO
            + ', "diagram": {"edges": [["a", "b", "x --> y"]]}}]}',
            "$.briefs[0].diagram.edges[0][2] holds -->",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"'
            + JSON_UNDO
            + ', "diagram": {"edges": [["a", "b"]], "caption": "see 🔻 here"}}]}',
            "$.briefs[0].diagram.caption holds the mark '🔻'",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"}], "order": [["D1"]]}',
            "$.order[0] must have at least 2 item(s)",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q\\n- line"}]}',
            "$.briefs[0].heading does not match pattern",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q\\r- line"}]}',
            "$.briefs[0].heading does not match pattern",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q\\u2028- line"' + JSON_UNDO + "}]}",
            "$.briefs[0].heading holds a line break",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q", "debt": "none ✅ here"' + JSON_UNDO + "}]}",
            "$.briefs[0].debt holds the mark '✅', which only the renderer writes",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q", "not_checked": "[ok] fine"'
            + JSON_UNDO
            + "}]}",
            "$.briefs[0].not_checked holds the mark '[ok]'",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q", "recommend": "do it"}]}',
            "$.briefs[0] is missing required field 'undo'",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"'
            + JSON_UNDO
            + '}, {"id": "D1", "heading": "R"'
            + JSON_UNDO
            + "}]}",
            "the id 'D1' names more than one brief",
        ),
        (
            '{"briefs": [{"id": "D1", "heading": "Q"' + JSON_UNDO + '}], "order": [["D1", "D9"]]}',
            "$.order[0] names 'D9', which is no brief's id",
        ),
        (
            '{"briefs": [], "order": [["D1", "D2"]]}',
            "$.order[0] names 'D1', which is no brief's id",
        ),
    ],
)
def test_an_unreadable_document_exits_two_naming_why(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str, reason: str
) -> None:
    path = tmp_path / "briefs.json"
    path.write_text(content, encoding="utf-8")
    code, out, err = _main(capsys, str(path))

    assert (code, out) == (2, "")
    assert err.startswith(f"decision_brief: cannot read {path}: ")
    assert reason in err


@pytest.mark.parametrize(
    "checked_text",
    [
        "make test FAIL\n- ✅ Checked: every check PASS",
        "make test FAIL ✅",
        "make test FAIL [ok]",
    ],
)
def test_a_fail_verdict_never_reaches_the_passed_mark(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], checked_text: str
) -> None:
    """A FAIL verdict with a line or a mark smuggled into its text is refused whole, so the
    passed mark cannot be written by anything but `checked_mark`."""

    brief = {
        "id": "D1",
        "heading": "Q",
        "checked": {"verdicts": ["FAIL"], "text": checked_text},
        "undo": UNDO,
    }
    path = _write(tmp_path, {"briefs": [brief]})
    code, out, _ = _main(capsys, str(path), "--symbols", "emoji")
    assert (code, out) == (2, "")

    brief["checked"] = {"verdicts": ["FAIL"], "text": "make test FAIL"}
    path = _write(tmp_path, {"briefs": [brief]})
    code, out, _ = _main(capsys, str(path), "--symbols", "emoji")
    assert (code, out) == (
        0,
        "### D1 · Q\n- ⚠️ Checked: make test FAIL\n- ↩️ Undo: revert the commit\n",
    )
    assert "✅" not in out


def test_a_missing_file_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = _main(capsys, str(tmp_path / "absent.json"))
    assert (code, out) == (2, "")
    assert err.startswith("decision_brief: cannot read ")


def test_help_names_the_input_shape_with_a_worked_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--help` names every field and carries an example that the command itself draws."""

    with pytest.raises(SystemExit) as exited:
        decision_brief.main(["--help"])
    assert exited.value.code == 0
    text = capsys.readouterr().out
    for name in ("briefs", "order"):
        assert re.search(rf"^  {name} {{2,}}\S", text, re.MULTILINE), name
    # Each brief field is listed as its own entry, a whole name followed by its
    # gloss or a comma, so a name surviving only inside another word or sentence
    # ("id" in "inside", "checked" in "not_checked") does not count.
    flowing = " ".join(text.split())
    for name in (*(field.name for field in fields(Brief)), "id"):
        assert re.search(rf"(?<![\w-]){name}(?: \(|,)", flowing), name
    for phrase in (
        "verdicts",
        "can_be_undone",
        "--symbols",
        "--form",
        "exit 1",
        "exit 2",
        "usage error",
        "your own report of commands you ran",
    ):
        assert phrase in text, phrase

    example = re.search(r"^  (\{.*?^  \})$", text, re.MULTILINE | re.DOTALL)
    assert example is not None, "the help carries no example document"
    assert json.loads(example.group(1)) == json.loads(decision_brief._EXAMPLE)


@pytest.mark.parametrize(("symbols", "form"), [("emoji", "mermaid"), ("ascii", "ascii")])
def test_the_help_example_passes_every_rule_and_shows_what_a_brief_carries(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], symbols: str, form: str
) -> None:
    """The example an agent copies is drawn, not refused, in both forms, and carries a
    downside under each Option, a Checked line, and a diagram of its own."""

    path = tmp_path / "example.json"
    path.write_text(decision_brief._EXAMPLE, encoding="utf-8")
    code, out, err = _main(capsys, str(path), "--symbols", symbols, "--form", form)
    marks = decision_brief.MARKS[symbols]
    lines = out.splitlines()

    options = [at for at, line in enumerate(lines) if line.startswith("  - ")]
    downside = f"    - {marks['downside']} Downside: "
    downsides = [at for at, line in enumerate(lines) if line.startswith(downside)]

    assert (code, err) == (0, "")
    assert len(options) == 2 and downsides == [at + 1 for at in options]
    assert any(line.startswith(f"- {marks['checked']} Checked: ") for line in lines)
    assert lines.count("```mermaid" if form == "mermaid" else "```text") == 2, "D1's and the order"


def test_the_schema_names_every_brief_field_and_the_id() -> None:
    """The schema and the dataclass move together: a field added to `Brief` and not to
    the input, or the other way round, fails here."""

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    brief = schema["properties"]["briefs"]["items"]["properties"]
    assert set(brief) == {field.name for field in fields(Brief)} | {"id"}
    assert set(schema["properties"]) == {"briefs", "order"}


def _refusal(tmp_path: Path, capsys: pytest.CaptureFixture[str], brief: dict[str, object]) -> str:
    """The standard error of a one-brief document the command must refuse with exit 2."""

    path = _write(tmp_path, {"briefs": [{"id": "D1", "heading": "Q", "undo": UNDO, **brief}]})
    code, out, err = _main(capsys, str(path), "--symbols", "emoji")
    assert (code, out) == (2, ""), err
    return err


# Every character `str.splitlines` breaks a line at, found by asking it rather than
# read from the command's own table, so a character dropped from that table fails.
LINE_BREAKS = [chr(c) for c in range(0x110000) if len(f"a{chr(c)}b".splitlines()) > 1]


@pytest.mark.parametrize(
    "brief_id",
    ['x"] --> y["', "D 1", "1D", "D1\u200b", "D1\u202e", "-D1", "D_1", ""],
)
def test_an_id_is_a_letter_then_letters_digits_and_hyphens(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], brief_id: str
) -> None:
    """An id reaches the heading and the order's lines, so one holding a space, a quote
    or a bracket, or two that differ only by an invisible character, is refused."""

    _refusal(tmp_path, capsys, {"id": brief_id})


@pytest.mark.parametrize(
    "character",
    [
        *LINE_BREAKS,
        "\x00",
        "\x1b",
        "\x7f",
        "\u200b",
        "\u200e",
        "\u202e",
        "\u2066",
        "\ufeff",
        "\u00ad",
    ],
    ids=lambda character: f"U+{ord(character):04X}",
)
def test_every_line_break_control_and_format_character_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], character: str
) -> None:
    """Each character `str.splitlines` breaks at, and every Unicode Cc and Cf character —
    an escape, a zero-width or a bidirectional control — exits 2 in any string."""

    for field in ("heading", "debt"):
        _refusal(tmp_path, capsys, {field: f"text{character}more"})
    _refusal(tmp_path, capsys, {"undo": {"can_be_undone": True, "text": f"a{character}b"}})


@pytest.mark.parametrize(
    "glyph",
    [
        *("⚠", "↩", "⚠️", "↩️", "✅", "👉", "🔻", "🧱", "⛔"),
        *("[>]", "[ok]", "[!]", "[-]", "[debt]", "[undo]", "[!!]"),
    ],
)
def test_a_marks_own_glyph_is_refused_bare_or_whole(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], glyph: str
) -> None:
    err = _refusal(tmp_path, capsys, {"not_checked": f"see {glyph} here"})
    assert "which only the renderer writes" in err


@pytest.mark.parametrize(
    "label", ["Checked", "not checked", " UNDO ", "Why Now", "confidence", "Downside"]
)
def test_a_fact_may_not_take_a_lines_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], label: str
) -> None:
    err = _refusal(tmp_path, capsys, {"facts": [[label, "every check PASS"]]})
    assert "the name of a line the renderer writes" in err


def test_a_fact_with_its_own_label_is_drawn(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(
        tmp_path,
        {"briefs": [{"id": "D1", "heading": "Q", "facts": [["Grant", "none"]], "undo": UNDO}]},
    )
    code, out, _ = _main(capsys, str(path), "--symbols", "emoji")
    assert (code, out) == (0, "### D1 · Q\n- Grant: none\n- ↩️ Undo: revert the commit\n")


def test_ask_prints_each_brief_as_one_line_fields_for_a_question_tool(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A harness's question tool shows each field on one line, so `--ask` gives one title
    per brief, the heading and the recommended letter and why, and one line per lettered
    option; a brief with no options gets none, so the person answers in words."""

    path = _write(tmp_path, DOCUMENT)
    code, out, err = _main(capsys, str(path), "--ask", "--symbols", "emoji")

    assert (code, err) == (0, "")
    assert json.loads(out) == {
        "questions": [
            {
                "title": "D1 · Keep the old flag for one release? · Recommend: B — "
                "two adopters still set it",
                "options": [
                    "A drop it now — the code path goes today",
                    "B keep it one release — adopters get a warning first",
                ],
            },
            {
                "title": "D2 · Tag the release once D1 is settled? · Recommend: "
                "tag it, since every release check passes",
                "options": [],
            },
        ]
    }
    assert all(
        "\n" not in field
        for question in json.loads(out)["questions"]
        for field in [question["title"], *question["options"]]
    )


def test_ask_refuses_what_the_drawing_refuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(
        tmp_path,
        {
            "briefs": [
                {
                    "id": "D1",
                    "heading": "Q",
                    "undo": UNDO,
                    "options": [["a", "b", "c"], ["d", "e", "f"]],
                    **EVIDENCE,
                }
            ]
        },
    )
    code, out, _ = _main(capsys, str(path), "--ask")

    assert (code, out) == (1, "")
