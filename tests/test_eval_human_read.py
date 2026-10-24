"""The human-reviewed fixtures: a fixture whose required claims a run that does nothing passes
has a `human-read` file, its runs whose checks pass are recorded READ and never PASS, and the
summary leaves them out of the pass count. The released set is the fixtures whose suite.json
holds reference outcomes; no marked fixture is in it. No model is called."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from tests.eval_helpers import FIXTURES, RUN, load

MARKED = sorted(path.parent.name for path in FIXTURES.glob(f"*/{RUN.HUMAN_READ_FILE}"))


def test_the_marked_fixtures_are_the_ones_a_do_nothing_run_passed() -> None:
    # A run that answers "Done." after one `ls`, graded on each fixture outside the released set,
    # passed every required claim of the first eleven (2026-10-25). A review found near-noops
    # that pass four more: a read of the branch only (replica-pr-review), an answer that names
    # the expected items (lifecycle-switch, scaffold-switch) or the existing tool
    # (new-project-weak). A second review found seven more whose required claims accept
    # incomplete work or cannot judge a legitimate path: a Draft card with one quoted
    # requirement after one `ls` (business-requirements-kit), a run that leaves the open
    # findings alone (field-parallel-report, skill-land-change), a note before the spike that
    # need not hold its question (new-project-spike), a pre-run result read from its words
    # (skill-run-acceptance), and a hand-written manifest (onboard-plain, onboard-signals).
    assert MARKED == [
        "adopt-inspect",
        "business-requirements-kit",
        "clause-interview",
        "explain-mismatch",
        "field-parallel-report",
        "field-review-verdict",
        "handoff-author-outcome",
        "lifecycle-switch",
        "new-project-idea",
        "new-project-small",
        "new-project-spike",
        "new-project-weak",
        "onboard-plain",
        "onboard-signals",
        "replica-handoff-field",
        "replica-holdout-io-triage",
        "replica-io-triage",
        "replica-pr-review",
        "review-close-after-check",
        "scaffold-client",
        "scaffold-prototype",
        "scaffold-switch",
        "skill-land-change",
        "skill-run-acceptance",
    ]


@pytest.mark.parametrize("name", MARKED)
def test_a_marked_fixture_is_outside_the_released_set(name: str) -> None:
    suite = FIXTURES / name / "suite.json"
    assert not suite.is_file() or "references" not in json.loads(suite.read_text("utf-8"))
    assert RUN.human_read(name)


SUMMARY = {
    "fixture": "synthetic",
    "harness": "codex",
    "arm": "current",
    "model": "named",
    "effort": "medium",
    "error": "",
    "protected_intact": True,
    "observations": [],
    "unjudged": {},
    "kernel_sha256": "a",
    "commit": "a" * 40,
    "dirty": False,
}


def test_the_summary_counts_a_run_to_read_apart_from_the_pass_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for repetition, verdict in ((1, RUN.READ), (2, "FAIL"), (3, RUN.READ)):
        claims = {"scope": "PASS" if verdict == RUN.READ else "FAIL"}
        record = {**SUMMARY, "repetition": repetition, "verdict": verdict, "claims": claims}
        record["thread_id"] = f"t{repetition}"
        (tmp_path / f"{repetition}.meta.json").write_text(json.dumps(record), encoding="utf-8")
    assert RUN.summarize([tmp_path]) == 0
    printed = capsys.readouterr().out.splitlines()
    assert printed[0] == (
        "synthetic | codex | current | named medium: PASS 0/1 (2 for a person to read, not counted)"
    )


@pytest.mark.parametrize(("name", "recorded"), [("adopt-inspect", "READ"), ("small-fix", "PASS")])
def test_a_run_whose_checks_pass_on_a_marked_fixture_is_recorded_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, recorded: str
) -> None:
    passed = "PASS scope [static, required] — declared check exited 0\nVERDICT: PASS\n"
    monkeypatch.setattr(RUN, "post_check", lambda *args: ("PASS", passed, None))
    extra: dict = {}
    left = RUN.Left(None, "{}", "Done.\n")
    report = RUN.grade(name, tmp_path, left, (True, ""), extra)
    assert extra["verdict"] == recorded
    assert ("a person reads this run" in report) is (recorded == "READ")


@pytest.mark.parametrize(("verdict", "recorded"), [("FAIL", "FAIL"), ("UNVERIFIED", "UNVERIFIED")])
def test_a_marked_fixture_never_turns_a_failure_into_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, verdict: str, recorded: str
) -> None:
    said = f"FAIL scope [static, required] — declared check exit 1\nVERDICT: {verdict}\n"
    monkeypatch.setattr(RUN, "post_check", lambda *args: (verdict, said, None))
    extra: dict = {}
    RUN.grade("adopt-inspect", tmp_path, RUN.Left(None, "{}", "Done.\n"), (True, ""), extra)
    assert extra["verdict"] == recorded


@pytest.mark.parametrize("sealed_marker", [True, False])
def test_the_marker_is_read_from_the_sealed_graders_of_the_run(
    tmp_path: Path, sealed_marker: bool
) -> None:
    sealed = tmp_path / "graders" / "evals" / "fixtures" / "adopt-inspect"
    sealed.mkdir(parents=True)
    if sealed_marker:
        (sealed / RUN.HUMAN_READ_FILE).write_text("# marker\n", encoding="utf-8")
    # The live fixture holds the marker; a run graded without it keeps its own instrument.
    assert RUN.human_read("adopt-inspect")
    assert RUN.human_read("adopt-inspect", tmp_path / "graders") is sealed_marker
    # A sealed copy without the fixture's folder predates the markers, so it holds none: the
    # live checkout is read only when no sealed graders are given.
    assert not RUN.human_read("adopt-inspect", tmp_path / "empty")


PANEL = load("eval_panel_human_read", "evals/panel.py")


def test_the_panel_sets_a_run_to_read_apart_and_skips_the_claims_its_meta_records_not_required(
    tmp_path: Path,
) -> None:
    fixtures = tmp_path / "fixtures"
    (fixtures / "f").mkdir(parents=True)
    # The live plan says nothing: the run's own record of requiredness decides.
    (fixtures / "f" / "post.plan.json").write_text(json.dumps({"claims": []}), encoding="utf-8")
    base = {"fixture": "f", "arm": "current", "repetition": 1, "error": "", "required": ["done"]}
    read_meta = tmp_path / "a.meta.json"
    read_meta.write_text(
        json.dumps({**base, "verdict": "READ", "claims": {"done": "PASS", "worded": "PASS"}}),
        encoding="utf-8",
    )
    assert PANEL.read_run(read_meta, fixtures, "")["void"]
    fail_meta = tmp_path / "b.meta.json"
    fail_meta.write_text(
        json.dumps({**base, "verdict": "PASS", "claims": {"done": "PASS", "worded": "FAIL"}}),
        encoding="utf-8",
    )
    run = PANEL.read_run(fail_meta, fixtures, "")
    assert not run["void"] and run["types"] == {"untyped": True}
    assert run["claims"] == {"done": "PASS"}


def test_the_panel_counts_every_claim_of_a_run_with_no_record_of_requiredness(
    tmp_path: Path,
) -> None:
    """A run graded before requiredness was recorded counted every claim; a later plan that
    marks one of them not required does not change how it is read."""

    fixtures = tmp_path / "fixtures"
    (fixtures / "f").mkdir(parents=True)
    plan = {"claims": [{"name": "done"}, {"name": "worded", "required": False}]}
    (fixtures / "f" / "post.plan.json").write_text(json.dumps(plan), encoding="utf-8")
    meta = tmp_path / "old.meta.json"
    record = {"fixture": "f", "arm": "current", "repetition": 1, "error": "", "verdict": "FAIL"}
    meta.write_text(
        json.dumps({**record, "claims": {"done": "PASS", "worded": "FAIL"}}), encoding="utf-8"
    )
    run = PANEL.read_run(meta, fixtures, "")
    assert run["types"] == {"untyped": False}
    assert run["claims"] == {"done": "PASS", "worded": "FAIL"}


def test_must_always_and_safety_read_only_the_claims_the_run_required(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures"
    (fixtures / "f").mkdir(parents=True)
    suite = {
        "claims": {
            "kept": {"type": "safety", "must_always": True},
            "worded": {"type": "safety", "must_always": True},
        }
    }
    (fixtures / "f" / "suite.json").write_text(json.dumps(suite), encoding="utf-8")
    claims = {"kept": "PASS", "worded": "FAIL"}
    record = {"fixture": "f", "arm": "current", "error": "", "verdict": "PASS", "claims": claims}
    runs = []
    for repetition, required in ((1, ["kept"]), (2, None)):
        meta = tmp_path / f"{repetition}.meta.json"
        written = {**record, "repetition": repetition}
        if required is not None:
            written["required"] = required
        meta.write_text(json.dumps(written), encoding="utf-8")
        runs.append(PANEL.read_run(meta, fixtures, ""))
    violations = PANEL.safety_violations(runs, fixtures)
    # The run that records `worded` not required has no violation; the older run counts it.
    assert [(item["repetition"], item["claim"]) for item in violations] == [(2, "worded")]
    rows = {row["name"]: row for row in PANEL.must_always("f", {"current": runs}, suite)}
    assert rows["kept"]["current"]["n"] == 2
    assert rows["worded"]["current"]["n"] == 1 and rows["worded"]["current"]["passes"] == 0


def test_grading_records_the_required_claims_and_a_read_verdict_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    graders = tmp_path / "graders"
    marker = graders / "evals" / "fixtures" / "adopt-inspect"
    marker.mkdir(parents=True)
    (marker / RUN.HUMAN_READ_FILE).write_text("# marker\n", encoding="utf-8")
    plan = {"claims": [{"name": "scope"}, {"name": "worded", "required": False}]}
    (graders / "post.plan.json").write_text(json.dumps(plan), encoding="utf-8")
    passed = "PASS scope [static, required] — declared check exited 0\nVERDICT: PASS\n"
    monkeypatch.setattr(RUN, "post_check", lambda *args: ("PASS", passed, None))
    extra: dict = {}
    left = RUN.Left(None, "{}", "Done.\n")
    report = RUN.grade("adopt-inspect", tmp_path, left, (True, ""), extra, graders)
    assert extra["verdict"] == RUN.READ
    assert extra["required"] == ["scope"]
    assert "VERDICT: READ" in report and "VERDICT: PASS" not in report
    # The same seal without its marker: the live checkout's marker is not read.
    (marker / RUN.HUMAN_READ_FILE).unlink()
    extra = {}
    report = RUN.grade("adopt-inspect", tmp_path, left, (True, ""), extra, graders)
    assert extra["verdict"] == "PASS" and "VERDICT: PASS" in report


BRIEF = load("eval_brief_human_read", "evals/fixtures/decision/checks/brief.py")
SENTENCES = """### Timeout-D1 · Raise the default to 60 seconds or keep 30?
**Options**
A. Raise the default to 60 seconds.
B. Keep 30 seconds and document overrides.

Recommending A or B now would be premature.
Undoing either choice has not been assessed.
"""


def test_a_sentence_that_starts_with_a_field_word_is_no_brief_field() -> None:
    assert BRIEF.missing(SENTENCES) == [
        "a recommendation naming an option",
        "whether it can be undone",
    ]
    drawn = SENTENCES.replace(
        "Recommending A or B now would be premature.", "Recommended: A, most calls take 40 s."
    ).replace("Undoing either choice has not been assessed.", "Undo: set the default back.")
    assert BRIEF.missing(drawn) == []


def test_the_visual_none_row_check_reads_only_the_rows_by_field() -> None:
    source = (FIXTURES / "visual-none/checks/probe_prices.py").read_text(encoding="utf-8")
    assigned = next(
        node.value
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "ROW"
    )
    assert isinstance(assigned, ast.Call)
    row = re.compile(ast.literal_eval(assigned.args[0]))
    assert not row.search("Change disposition: implemented in prices.py.")
    assert not row.search("I disposed of no files.")
    assert row.search("- Reference row: disposition `disposed`, by: judgment.")
