"""`outcomebound review check`: each FAIL code has a file that triggers it and, beside it, the
clean file that does not (the negative control); WARN does not change the verdict; every line
says what it does not establish; the JSON report matches its schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from outcomebound_tools import review_check
from outcomebound_tools.schemacheck import validate
from tests.portable import needs_symlinks

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schemas/review-report.schema.json").read_text("utf-8"))

HEAD = "# Review\n\nReviewed: v1.2.0\n\nSome prose.\n\n"
CLEAN = (
    HEAD
    + "### F1 · Off by one\n\nDisposition: fixed — commit abc1234\n\n"
    + "### F-2 · Naming\n\nDisposition: rejected — the name matches the schema\n\n"
    + "### f3 · Later\n\nDisposition: deferred — ticket 12\n"
)


def run(tmp_path: Path, capsys, text: str, *extra: str) -> tuple[int, str]:
    path = tmp_path / "review.md"
    path.write_text(text, "utf-8")
    code = review_check.main(["check", str(path), *extra])
    return code, capsys.readouterr().out


def codes(out: str) -> set[str]:
    return {line.split()[1] for line in out.splitlines()[1:]}


def test_a_clean_file_passes_and_says_what_it_does_not_establish(tmp_path, capsys):
    code, out = run(tmp_path, capsys, CLEAN, "--verbose")
    assert code == 0 and out.startswith("PASS; ")
    assert out.splitlines()[0] == "PASS; 8 PASS, 0 FAIL, 0 WARN, 0 INFO"
    assert all("Does not establish:" in line for line in out.splitlines()[1:])


@pytest.mark.parametrize(
    ("text", "code"),
    [
        (CLEAN.replace("Reviewed: v1.2.0\n", ""), "REVIEWED_MISSING"),
        (CLEAN.replace("Reviewed: v1.2.0", "Reviewed:"), "REVIEWED_MISSING"),
        (CLEAN + "\n### F1 · Again\n\nDisposition: fixed — x\n", "ID_DUPLICATE"),
        (CLEAN + "\n### f1 · Case\n\nDisposition: fixed — x\n", "ID_DUPLICATE"),
        (CLEAN + "\n### Missing\n\nDisposition: fixed — x\n", "FINDING_MALFORMED"),
        (CLEAN + "\n### bad id · T\n\nDisposition: fixed — x\n", "FINDING_MALFORMED"),
        (CLEAN + "\n### F9 · No line\n\nText.\n", "DISPOSITION_MISSING"),
        (
            CLEAN + "\n### F9 · Two\n\nDisposition: fixed — a\nDisposition: fixed — b\n",
            "DISPOSITION_DUPLICATE",
        ),
        (CLEAN + "\n### F9 · Yes\n\nDisposition: accepted — will do\n", "DISPOSITION_ACCEPTED"),
        (CLEAN + "\n### F9 · Yes\n\nDisposition: accepted\n", "DISPOSITION_ACCEPTED"),
        (CLEAN + "\n### F9 · ?\n\nDisposition: wontfix — no\n", "DISPOSITION_UNKNOWN"),
        (CLEAN + "\n### F9 · ?\n\nDisposition: fixed\n", "DISPOSITION_EMPTY"),
        (CLEAN + "\n### F9 · ?\n\nDisposition: rejected —  \n", "DISPOSITION_EMPTY"),
        (CLEAN + "\n### F9 · ?\n\nDisposition:\n", "DISPOSITION_UNKNOWN"),
        (CLEAN + "\n ### F9 · Indented, still a heading\n\nText.\n", "DISPOSITION_MISSING"),
        (
            CLEAN + "\n   ### Indented and malformed\n\nDisposition: fixed — x\n",
            "FINDING_MALFORMED",
        ),
        (
            CLEAN + "\n```\ncode\n```python\n```\n\n### F9 · After a mismatched fence\n\nText.\n",
            "DISPOSITION_MISSING",
        ),
        (CLEAN + "\n- ### F9 · In a list item\n\nText.\n", "FINDING_MALFORMED"),
        (CLEAN + "\n1. ### F9 · In a numbered item\n\nText.\n", "FINDING_MALFORMED"),
        (CLEAN + "\n> ### F9 · In a quote\n\nText.\n", "FINDING_MALFORMED"),
        (CLEAN + "\n> - ### F9 · In a list in a quote\n\nText.\n", "FINDING_MALFORMED"),
    ],
)
def test_each_failure_is_named_and_the_clean_file_beside_it_passes(tmp_path, capsys, text, code):
    assert run(tmp_path, capsys, CLEAN)[0] == 0
    exit_code, out = run(tmp_path, capsys, text)
    assert exit_code == 1 and out.startswith("FAIL; ")
    assert code in codes(out)
    line = next(line for line in out.splitlines() if f"FAIL {code} " in line)
    assert "Does not establish:" in line and " next: " in line


def test_text_between_headings_is_data_and_fences_hide_nothing_and_add_nothing(tmp_path, capsys):
    text = (
        HEAD
        + "Disposition: accepted — in the preamble\n"
        + "### F1 · A\n\nDisposition: fixed — x\n\n"
        + "```\n### F2 · Inside a fence\nDisposition: accepted\n```\n\n"
        + "#### Detail\nDisposition: accepted — not a finding's own line\n"
        + "## Summary\n\nDisposition: accepted — a section after the findings\n"
    )
    code, out = run(tmp_path, capsys, text)
    # The `####` line stays inside F1, so F1 holds two lines; the rest adds none.
    assert code == 1 and codes(out) == {"DISPOSITION_DUPLICATE"}


def test_a_review_with_no_finding_passes_and_says_so(tmp_path, capsys):
    code, out = run(tmp_path, capsys, HEAD)
    assert code == 0 and "INFO FINDINGS_NONE" in out


def test_at_warns_on_another_ref_and_leaves_the_verdict(tmp_path, capsys):
    code, out = run(tmp_path, capsys, CLEAN, "--at", "v1.3.0")
    assert code == 0 and out.startswith("PASS; ") and "WARN REVIEWED_REF" in out
    code, out = run(tmp_path, capsys, CLEAN, "--at", "v1.2.0")
    assert code == 0 and "WARN REVIEWED_REF" not in out


def test_json_report_matches_its_schema_and_carries_the_same_verdict(tmp_path, capsys):
    code, out = run(tmp_path, capsys, CLEAN + "\n### F9 · ?\n\nText.\n", "--json", "--at", "x")
    document = json.loads(out)
    assert code == 1 and document["verdict"] == "FAIL" and document["reviewed"] == "v1.2.0"
    assert validate(document, SCHEMA) == []
    assert all(f["does_not_establish"] for f in document["findings"])
    clean = json.loads(run(tmp_path, capsys, CLEAN, "--json")[1])
    assert clean["verdict"] == "PASS" and validate(clean, SCHEMA) == []


def test_output_escapes_what_the_file_holds(tmp_path, capsys):
    text = CLEAN + "\n### F9 · ?\n\nDisposition: ‮evil — x\n"
    code, out = run(tmp_path, capsys, text)
    assert code == 1 and "‮" not in out and "DISPOSITION_UNKNOWN" in out


def test_an_unreadable_file_is_a_refusal_and_usage_is_exit_2(tmp_path, capsys):
    assert review_check.main(["check", str(tmp_path / "none.md")]) == 1
    assert "REVIEW_UNREADABLE" in capsys.readouterr().err
    with pytest.raises(SystemExit) as usage:
        review_check.main(["check"])
    assert usage.value.code == 2


def test_a_long_run_of_list_or_quote_markers_is_read_in_linear_time(tmp_path, capsys):
    import time

    text = CLEAN + "\n" + "> " * 30_000 + "x\n" + "- " * 30_000 + "x\n"
    started = time.perf_counter()
    run(tmp_path, capsys, text)
    assert time.perf_counter() - started < 2


def test_a_long_whitespace_run_in_a_disposition_is_read_in_linear_time(tmp_path, capsys):
    import time

    text = CLEAN + "\n### F9 · Long\n\nDisposition: fixed" + " " * 60_000 + "x\n"
    started = time.perf_counter()
    run(tmp_path, capsys, text)
    assert time.perf_counter() - started < 2


@pytest.mark.parametrize(
    ("value", "verdict"),
    [
        ("fixed — x", None),
        ("fixed -- x", None),
        ("fixed\t—\tx", None),
        ("fixed — x — y", None),
        ("fixed", "DISPOSITION_EMPTY"),
        ("fixed — ", "DISPOSITION_EMPTY"),
        ("rejected —  ", "DISPOSITION_EMPTY"),
        ("fixed—x", "DISPOSITION_UNKNOWN"),
        ("a — b — c", "DISPOSITION_UNKNOWN"),
    ],
)
def test_the_disposition_separator_splits_on_a_spaced_dash(tmp_path, capsys, value, verdict):
    code, out = run(tmp_path, capsys, CLEAN + f"\n### F9 · ?\n\nDisposition: {value}\n")
    if verdict is None:
        assert code == 0, out
    else:
        assert code == 1 and verdict in codes(out), out


# --- review sweep: every review file of a work folder -------------------------------------

OPEN = "Reviewed: abc\n\n### R1 · one\n\n### R2 · two\nDisposition: fixed — c1\n"
CLOSED = "Reviewed: abc\n\n### R1 · one\nDisposition: rejected — the line holds\n"


def tree(root: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def sweep(capsys, folder: Path, *extra: str) -> tuple[int, str]:
    code = review_check.main(["sweep", str(folder), *extra])
    return code, capsys.readouterr().out


def test_sweep_fails_on_an_open_finding_anywhere_under_the_work_folder(tmp_path, capsys):
    """Breaks if a review another session left in its own task folder, three levels down, is not
    read before a release."""

    work = tree(
        tmp_path / "work",
        {"a/review.md": CLOSED, "b/reviews/x.md": OPEN, "c/v1/round/y.md": OPEN},
    )

    code, out = sweep(capsys, work)

    assert code == 1
    first = out.splitlines()[0]
    assert first == "FAIL 2 failing line(s) in 2 of 3 review file(s)"
    assert str(Path("b/reviews/x.md")) in out and str(Path("c/v1/round/y.md")) in out
    assert "R1 has no Disposition" in out


def test_sweep_passes_when_every_finding_has_a_disposition(tmp_path, capsys):
    code, out = sweep(capsys, tree(tmp_path / "work", {"a/review.md": CLOSED}))
    assert code == 0
    assert out.startswith("PASS 1 review file(s), every finding has a disposition\n")


def test_sweep_reads_a_file_that_says_it_is_a_review_however_its_headings_read(tmp_path, capsys):
    """Breaks if a review whose finding headings are not in the form drops out of the sweep, or
    if a brief with finding-like headings and no `Reviewed:` line is read as a review."""

    work = tree(
        tmp_path / "work",
        {
            "a/review.md": "# Review\n\nReviewed: abc\n\n## Findings\n\n### Blocker\n\ntext\n",
            "a/brief.md": "### D1 · a question\n- Recommend: A\n",
            "a/fenced.md": "```\nReviewed: abc\n```\n### R1 · x\n",
        },
    )

    code, out = sweep(capsys, work)

    assert code == 1 and "1 of 1 review file(s)" in out
    assert "FINDING_MALFORMED" in out and "brief.md" not in out and "fenced.md" not in out


@needs_symlinks
def test_sweep_enters_no_linked_folder_and_reads_no_linked_or_deeper_file(tmp_path, capsys):
    """NEGATIVE CONTROL: a link out of the folder, and a file five levels down, are not read; a
    linked file is counted as not read."""

    outside = tree(tmp_path / "outside", {"r/x.md": OPEN})
    work = tree(tmp_path / "work", {"a/b/c/d/deep.md": OPEN, "a/ok.md": CLOSED})
    (work / "linked").symlink_to(outside / "r", target_is_directory=True)
    (work / "a" / "link.md").symlink_to(outside / "r" / "x.md")

    code, out = sweep(capsys, work)

    assert code == 0, out
    assert out.splitlines()[0] == (
        "PASS 1 review file(s), every finding has a disposition; 1 file(s) not read"
    )
    assert "not read:" in sweep(capsys, work, "--verbose")[1]


def test_sweep_without_the_folder_is_a_refusal(tmp_path, capsys):
    assert review_check.main(["sweep", str(tmp_path / "absent")]) == 1
    assert "REVIEW_FOLDER_MISSING" in capsys.readouterr().err


def test_sweep_json_matches_the_review_report_schema(tmp_path, capsys):
    work = tree(tmp_path / "work", {"a/review.md": OPEN})

    code, out = sweep(capsys, work, "--json")

    document = json.loads(out)
    assert validate(document, SCHEMA) == []
    assert (code, document["verdict"], document["files"]) == (
        1,
        "FAIL",
        {"read": 1, "failed": 1, "unread": 0},
    )
