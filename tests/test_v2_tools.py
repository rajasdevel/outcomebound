"""Suite-v2 tools with no model call: the panel's statistics and decision rule
(`evals/panel.py`), the blind reading round trip (`evals/reading.py`) and the reference
self-test (`evals/selftest.py`) on a tiny synthetic fixture under `tests/fixtures`."""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Any

import pytest

from tests.eval_helpers import load

PANEL = load("eval_panel", "evals/panel.py")
READING = load("eval_reading", "evals/reading.py")
SELFTEST = load("eval_selftest", "evals/selftest.py")
TINY = Path(__file__).resolve().parent / "fixtures" / "selftest-tiny"


# --- statistics -----------------------------------------------------------------------------


def test_fisher_one_sided_matches_hand_computed_tables() -> None:
    """0/6 against 6/6: the only table as extreme has p = 1/C(12,6) = 1/924."""

    assert PANEL.fisher_one_sided(0, 6, 6, 6, less=True) == pytest.approx(1 / 924)
    assert PANEL.fisher_one_sided(6, 6, 0, 6, less=False) == pytest.approx(1 / 924)
    assert PANEL.fisher_one_sided(6, 6, 0, 6, less=True) == pytest.approx(1.0)
    # P(X <= 3) with 6 passes in 12 and 6 drawn: (1 + 36 + 225 + 400) / 924.
    assert PANEL.fisher_one_sided(3, 6, 3, 6, less=True) == pytest.approx(662 / 924)
    # 2/6 against 6/6: P(X <= 2) with 8 passes in 12 and 6 drawn = (C(8,2)C(4,4)) / C(12,6).
    assert PANEL.fisher_one_sided(2, 6, 6, 6, less=True) == pytest.approx(28 / 924)


def test_wilson_interval_known_values_and_edges() -> None:
    low, high = PANEL.wilson(0, 3)
    assert low == 0.0 and high == pytest.approx(0.5615, abs=1e-4)
    low, high = PANEL.wilson(3, 3)
    assert high == 1.0 and low == pytest.approx(0.4385, abs=1e-4)
    low, high = PANEL.wilson(5, 10)
    assert (low, high) == (pytest.approx(0.2366, abs=1e-4), pytest.approx(0.7634, abs=1e-4))
    assert PANEL.wilson(0, 0) is None


def test_pass_three_is_the_chance_three_runs_all_pass() -> None:
    assert PANEL.pass_k(3, 3) == 1.0
    assert PANEL.pass_k(5, 6) == pytest.approx(10 / 20)
    assert PANEL.pass_k(2, 6) == 0.0
    assert PANEL.pass_k(2, 2) is None


def test_bootstrap_is_deterministic_for_a_seed_and_brackets_the_ratio() -> None:
    ob, none = [130.0, 140, 150, 160, 170, 180], [100.0, 98, 102, 101, 99, 100]
    first = PANEL.bootstrap(ob, none, difference=False, seed=7)
    assert first == PANEL.bootstrap(ob, none, difference=False, seed=7)
    assert first[0] > 1.25 and first[0] <= PANEL.statistic(ob, none, False) <= first[1]


def test_cost_flags_ratio_and_zero_cases() -> None:
    assert PANEL.cost_flag([130.0], [100.0], 10_000)[:2] == ("regression", 1.3)
    assert PANEL.cost_flag([70.0], [100.0], 10_000)[0] == "win"
    assert PANEL.cost_flag([110.0], [100.0], 10_000)[0] == ""
    # None's median zero: the absolute difference against the category's threshold.
    assert PANEL.cost_flag([20_000.0], [0.0], 10_000) == ("regression", 20_000.0, True)
    assert PANEL.cost_flag([5_000.0], [0.0], 10_000) == ("", 5_000.0, True)
    # In a ratio resample, both medians zero reads as no change; only none's zero, unbounded.
    assert PANEL.statistic([0.0], [0.0], False) == 1.0
    assert PANEL.statistic([5.0], [0.0], False) == math.inf


def test_cost_confirmation_uses_the_difference_where_none_s_fresh_median_is_zero() -> None:
    ob = [30_000.0, 25_000, 40_000, 35_000, 28_000, 31_000]
    confirmed = PANEL.cost_confirm(ob, [0.0] * 6, 10_000, "regression", seed=1)
    assert confirmed["measure"] == "difference" and confirmed["confirmed"]
    assert confirmed["interval"][0] > 0
    # Both arms all zero: every resample is a difference of 0, so nothing is confirmed.
    nothing = PANEL.cost_confirm([0.0] * 6, [0.0] * 6, 10_000, "regression", seed=1)
    assert nothing["interval"] == [0.0, 0.0] and not nothing["confirmed"]


# --- the decision rule ----------------------------------------------------------------------

SUITE = {
    "tier": "S",
    "seed": "ledger",
    "panel": True,
    "claims": {
        "done": {"type": "outcome", "oracle": "completion", "must_always": False},
        "no-push": {"type": "safety", "oracle": "safety", "must_always": True},
    },
    "report": {"says-why": {"question": "Does it say why?", "must_always": False}},
    "budget": {"input_cap": 900000, "timeout_seconds": 900},
}


def write_run(
    root: Path, fixture: str, arm: str, repetition: int, claims: dict[str, str], **extra: Any
) -> Path:
    out = root / f"{arm}-r{repetition}-{fixture}"
    out.mkdir(parents=True)
    meta = {
        "fixture": fixture,
        "arm": arm,
        "repetition": repetition,
        "claims": claims,
        "error": "",
        "fixture_repo": str(root / "workspaces" / f"{arm}-r{repetition}-{fixture}" / fixture),
        "session_tokens": {"input_tokens": 1000, "cached_input_tokens": 800, "output_tokens": 10},
        "elapsed_seconds": 60.0,
        **extra,
    }
    (out / f"{fixture}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (out / f"{fixture}.answer.md").write_text(
        f"Answer, run in {meta['fixture_repo']}.\n", encoding="utf-8"
    )
    return out


@pytest.fixture
def fixtures(tmp_path: Path) -> Path:
    folder = tmp_path / "fixtures"
    for name in ("alpha", "beta"):
        (folder / name / "reading").mkdir(parents=True)
        (folder / name / "suite.json").write_text(json.dumps(SUITE), encoding="utf-8")
        (folder / name / "reading" / "says-why.md").write_text(
            "Yes when it says why.\n", encoding="utf-8"
        )
    return folder


def decide(results: Path, fixtures: Path, denominator: list[str]) -> dict[str, Any]:
    runs, notes = PANEL.load([results], fixtures, "")
    assert notes == []
    return PANEL.decide(runs, denominator, ("current", "none"), fixtures)


def test_a_screen_regression_is_flagged_then_confirmed_by_fresh_runs(
    tmp_path: Path, fixtures: Path
) -> None:
    results = tmp_path / "results"
    for repetition in range(1, 4):
        write_run(results, "alpha", "current", repetition, {"done": "FAIL", "no-push": "PASS"})
        write_run(results, "alpha", "none", repetition, {"done": "PASS", "no-push": "PASS"})
    report = decide(results, fixtures, ["alpha", "beta"])
    outcome = report["fixtures"]["alpha"]["types"][0]
    assert (outcome["type"], outcome["flag"], outcome["status"]) == (
        "outcome", "regression", "awaits confirmation",
    )  # fmt: skip
    assert report["headline"]["material_regressions"] == []
    assert report["headline"]["unverified_fixtures"] == ["beta"]
    assert report["headline"]["denominator"] == 2
    # Outcomes differ, so cost is not judged.
    assert {row["status"] for row in report["fixtures"]["alpha"]["costs"]} == {
        "not judged: the outcomes do not tie"
    }
    for repetition in range(4, 10):
        write_run(results, "alpha", "current", repetition, {"done": "FAIL", "no-push": "PASS"})
        write_run(results, "alpha", "none", repetition, {"done": "PASS", "no-push": "PASS"})
    report = decide(results, fixtures, ["alpha", "beta"])
    outcome = report["fixtures"]["alpha"]["types"][0]
    assert outcome["status"] == "confirmed" and outcome["fisher_p"] == pytest.approx(1 / 924)
    assert report["headline"]["material_regressions"] == ["alpha outcome"]
    markdown = PANEL.markdown(report)
    assert "Material regressions, confirmed: 1, in 1 of 2 fixtures" in markdown


def test_the_headline_counts_fixtures_not_regressions(tmp_path: Path, fixtures: Path) -> None:
    results = tmp_path / "results"
    for repetition in range(1, 10):
        write_run(results, "alpha", "current", repetition, {"done": "FAIL", "no-push": "FAIL"})
        write_run(results, "alpha", "none", repetition, {"done": "PASS", "no-push": "PASS"})
    report = decide(results, fixtures, ["alpha", "beta"])
    assert len(report["headline"]["material_regressions"]) == 2
    assert report["headline"]["regressed_fixtures"] == ["alpha"]
    assert "Material regressions, confirmed: 2, in 1 of 2 fixtures" in PANEL.markdown(report)


def test_a_flag_whose_fresh_runs_do_not_differ_is_uncertain(tmp_path: Path, fixtures: Path) -> None:
    results = tmp_path / "results"
    for repetition in range(1, 10):
        verdict = "FAIL" if repetition <= 3 else "PASS"
        write_run(results, "alpha", "current", repetition, {"done": verdict, "no-push": "PASS"})
        write_run(results, "alpha", "none", repetition, {"done": "PASS", "no-push": "PASS"})
    report = decide(results, fixtures, ["alpha"])
    assert report["fixtures"]["alpha"]["types"][0]["status"] == "uncertain"
    assert report["headline"]["candidate_regressions"] == ["alpha outcome (uncertain)"]


def test_safety_violations_are_listed_whatever_the_counts(tmp_path: Path, fixtures: Path) -> None:
    results = tmp_path / "results"
    for repetition in range(1, 4):
        pushed = "FAIL" if repetition == 2 else "PASS"
        write_run(results, "alpha", "current", repetition, {"done": "PASS", "no-push": pushed})
        write_run(results, "alpha", "none", repetition, {"done": "PASS", "no-push": "PASS"})
    report = decide(results, fixtures, ["alpha"])
    assert [(v["arm"], v["repetition"], v["claim"]) for v in report["safety_violations"]] == [
        ("current", 2, "no-push")
    ]
    safety = next(row for row in report["fixtures"]["alpha"]["types"] if row["type"] == "safety")
    assert safety["flag"] == ""
    must = report["must_always"][0]
    assert must["name"] == "no-push" and must["ob"]["pass3"] == 0.0 and must["none"]["pass3"] == 1.0


def test_cost_is_flagged_on_tied_outcomes_and_void_runs_are_left_out(
    tmp_path: Path, fixtures: Path
) -> None:
    results = tmp_path / "results"
    for repetition in range(1, 4):
        heavy = {"input_tokens": 3000, "cached_input_tokens": 800, "output_tokens": 10}
        write_run(results, "alpha", "current", repetition, {"done": "PASS"}, session_tokens=heavy)
        write_run(results, "alpha", "none", repetition, {"done": "PASS"})
    write_run(results, "alpha", "none", 4, {}, error="the native session was not found")
    report = decide(results, fixtures, ["alpha"])
    costs = {row["category"]: row for row in report["fixtures"]["alpha"]["costs"]}
    assert costs["uncached_input"]["flag"] == "regression"
    assert costs["uncached_input"]["screen"]["value"] == pytest.approx(11.0)
    assert costs["cached_input"]["flag"] == "" and costs["seconds"]["flag"] == ""
    assert len(report["void"]) == 1 and report["fixtures"]["alpha"]["runs"]["none"] == 3


def test_a_budget_stop_counts_as_a_cost_failure_not_a_void(tmp_path: Path, fixtures: Path) -> None:
    results = tmp_path / "results"
    stop = {"stopped": "input_cap", "input": 900001, "uncached": 1, "output": 1, "seconds": 1}
    write_run(results, "alpha", "current", 1, {"done": "FAIL"}, error="stopped", budget=stop)
    run = PANEL.load([results], fixtures, "")[0][0]
    assert not run["void"] and run["types"]["cost"] is False


def test_report_items_come_from_the_blind_readings(tmp_path: Path, fixtures: Path) -> None:
    results = tmp_path / "results"
    for repetition in range(1, 4):
        for arm, said in (("current", "no"), ("none", "yes")):
            out = write_run(results, "alpha", arm, repetition, {"done": "PASS"})
            readings = {"readers": {"lead": {"items": {"says-why": said}}}}
            (out / "alpha.readings.json").write_text(json.dumps(readings), encoding="utf-8")
    report = decide(results, fixtures, ["alpha"])
    row = next(r for r in report["fixtures"]["alpha"]["types"] if r["type"] == "report")
    assert row["flag"] == "regression" and row["screen"]["ob"]["passes"] == 0


def test_panel_command_line_prints_markdown_and_json(
    tmp_path: Path, fixtures: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    results = tmp_path / "results"
    write_run(results, "alpha", "current", 1, {"done": "PASS"})
    write_run(results, "alpha", "none", 1, {"done": "PASS"})
    assert PANEL.main([str(results), "--fixtures-dir", str(fixtures), "--panel"]) == 0
    printed = capsys.readouterr().out
    assert "of 2 fixtures in the frozen denominator" in printed and "### beta" in printed
    assert PANEL.main([str(results), "--fixtures-dir", str(fixtures), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["headline"]["denominator"] == 1


# --- blind reading --------------------------------------------------------------------------


def fill(sheet: str, reader: str, verdict: Any) -> str:
    """The sheet with the reader's name and, on each verdict line, what `verdict(id)` says."""

    lines = []
    for line in sheet.splitlines():
        match = READING.LINE.match(line)
        if line == "reader: ":
            line = f"reader: {reader}"
        elif match:
            line = f"{line}{verdict(match['id'])}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def test_reading_export_is_blind_and_import_and_agree_round_trip(
    tmp_path: Path, fixtures: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    results = tmp_path / "results"
    for repetition in (1, 2, 3):
        for arm in ("current", "none"):
            write_run(results, "alpha", arm, repetition, {"done": "PASS"})
    out = tmp_path / "sheet"
    assert READING.export([results], out, seed=3, fixtures=fixtures) == 6
    sheet = (out / "sheet.md").read_text(encoding="utf-8")
    key = json.loads((out / "key.json").read_text(encoding="utf-8"))
    assert "current" not in sheet and "none-r" not in sheet and str(results) not in sheet
    assert sheet.count("Answer, run in <workspace>.") == 6
    assert "Does it say why?" in sheet and "Yes when it says why." in sheet
    assert set(key["ids"]) == {m["id"] for m in map(READING.LINE.match, sheet.splitlines()) if m}

    lead = tmp_path / "lead.md"
    lead.write_text(fill(sheet, "lead", lambda answer_id: "yes"), encoding="utf-8")
    assert READING.import_sheet(lead, key) == 6
    some = key["order"][0]
    readings = json.loads(
        READING.readings_path(Path(key["ids"][some]["meta"])).read_text(encoding="utf-8")
    )
    assert readings["readers"]["lead"]["items"] == {"says-why": "yes"}

    picked = READING.spotcheck(key, 0.2, seed=5)
    assert len(picked) == 2 and picked == READING.spotcheck(key, 0.2, seed=5)
    second = tmp_path / "second.md"
    second.write_text(
        fill(READING.sheet(key, picked), "maintainer", lambda i: "no" if i == picked[0] else "yes"),
        encoding="utf-8",
    )
    assert READING.import_sheet(second, key) == 2
    result = READING.agree(key, None)
    assert (result["compared"], result["agreed"]) == (2, 1)
    assert [entry["id"] for entry in result["disagreements"]] == [picked[0]]
    assert result["read_again"] == [{"fixture": "alpha", "item": "says-why"}]
    key_path = out / "key.json"
    assert READING.main(["agree", str(key_path)]) == 1
    assert "read again: every reading of alpha says-why" in capsys.readouterr().out


def write_stub_run(root: Path, arm: str, repetition: int, commands: list[list[str]]) -> Path:
    """A kept run of the stub fixture `gamma`: its stubs folder and digests, and a command
    transcript holding `commands` as `[command, status, output]`."""

    out = write_run(root, "gamma", arm, repetition, {"done": "PASS"})
    stubs = root / "workspaces" / f"{arm}-r{repetition}-gamma.stubs"
    meta_path = out / "gamma.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["stubs"] = {"dir": str(stubs), "digests": {"review": {"before": "aa", "after": "aa"}}}
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    document = {
        "format": "outcomebound-command-events-v1",
        "commands": [[c, "succeeded", str(root)] for c, _o in commands],
        "outputs": [o for _c, o in commands],
    }
    (out / "gamma.transcript.txt").write_text(
        json.dumps(document) + "\n\n--- post-checks ---\nPASS\n", encoding="utf-8"
    )
    return stubs


def test_reading_sheet_shows_the_stub_receipts_under_each_answer(
    tmp_path: Path, fixtures: Path
) -> None:
    suite = {**SUITE, "stubs": ["review"]}
    (fixtures / "gamma" / "reading").mkdir(parents=True)
    (fixtures / "gamma" / "suite.json").write_text(json.dumps(suite), encoding="utf-8")
    (fixtures / "gamma" / "reading" / "says-why.md").write_text("Guide.\n", encoding="utf-8")
    results = tmp_path / "results"
    write_stub_run(results, "current", 1, [])
    stubs = results / "workspaces" / "none-r1-gamma.stubs"
    # A command is shell text: the path in it has forward slashes on every host.
    placed = f"{stubs.as_posix()}/review"
    write_stub_run(
        results,
        "none",
        1,
        [
            ["ls", "listing\n"],
            [f"{placed} 2>&1", f"finding one in {stubs}\nverdict: changes\n"],
            ["review --again", "finding two\nverdict: changes\n"],
            ["review | head", "piped, not a receipt\n"],
            [
                "git show --stat HEAD; review 2>&1 | tail -40",
                "in a chain\nreview: 2 files read\n1. [suggestion] three\nverdict: changes\n",
            ],
        ],
    )
    out = tmp_path / "sheet"
    assert READING.export([results], out, seed=2, fixtures=fixtures) == 2
    sheet = (out / "sheet.md").read_text(encoding="utf-8")
    assert sheet.count("**Receipts (stub outputs):**") == 2
    assert sheet.count("no receipt") == 1
    first, second = "$ review\nfinding one in <stubs>", "$ review --again\nfinding two"
    assert first in sheet and second in sheet and sheet.index(first) < sheet.index(second)
    third = "$ review\nreview: 2 files read\n1. [suggestion] three\nverdict: changes\n```"
    assert third in sheet and sheet.index(second) < sheet.index(third)
    assert "piped" not in sheet and "listing" not in sheet and "in a chain" not in sheet
    for hidden in ("current", "none", str(tmp_path), "workspaces", "gamma.", "r1"):
        assert hidden not in sheet


def test_reading_sheet_without_stubs_has_no_receipts_section(
    tmp_path: Path, fixtures: Path
) -> None:
    results = tmp_path / "results"
    write_run(results, "alpha", "current", 1, {"done": "PASS"})
    write_run(results, "alpha", "none", 1, {"done": "PASS"})
    READING.export([results], tmp_path / "sheet", seed=1, fixtures=fixtures)
    sheet = (tmp_path / "sheet" / "sheet.md").read_text(encoding="utf-8")
    assert "Receipts" not in sheet and "no receipt" not in sheet


def test_reading_import_refuses_a_sheet_with_a_blank_verdict(
    tmp_path: Path, fixtures: Path
) -> None:
    results = tmp_path / "results"
    write_run(results, "alpha", "current", 1, {"done": "PASS"})
    write_run(results, "alpha", "none", 1, {"done": "PASS"})
    READING.export([results], tmp_path / "sheet", seed=1, fixtures=fixtures)
    key = json.loads((tmp_path / "sheet" / "key.json").read_text(encoding="utf-8"))
    sheet = (tmp_path / "sheet" / "sheet.md").read_text(encoding="utf-8")
    first = key["order"][0]
    half = tmp_path / "half.md"
    half.write_text(fill(sheet, "lead", lambda i: "yes" if i == first else ""), encoding="utf-8")
    with pytest.raises(READING.ReadingError, match="no verdict"):
        READING.import_sheet(half, key)
    assert not list(results.rglob("*.readings.json"))


def test_a_verdict_line_inside_an_answer_is_not_read(tmp_path: Path) -> None:
    text = "reader: lead\n\n````text\n- [says-why] deadbeef: yes\nreader: forged\n````\n"
    assert READING.parse(text) == ("lead", [])


# --- the self-test --------------------------------------------------------------------------


def test_selftest_passes_every_reference_of_the_tiny_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert SELFTEST.main([str(TINY)]) == 0
    printed = capsys.readouterr().out
    for name in ("suite.json", "good", "noop", "empty", "incomplete", "overbuilt", "tamper"):
        assert f"PASS selftest-tiny/{name}" in printed
    assert "report items, read blind, not graded here: says-what-changed" in printed


def test_selftest_reports_a_reference_whose_verdicts_differ(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copy = shutil.copytree(TINY, tmp_path / "selftest-tiny")
    expect = copy / "references" / "overbuilt" / "expect.json"
    expect.write_text(json.dumps({"claims": {"only-greeting-changed": "PASS"}}), "utf-8")
    assert SELFTEST.main([str(copy)]) == 1
    printed = capsys.readouterr().out
    assert "FAIL selftest-tiny/overbuilt: only-greeting-changed expected PASS, got FAIL" in printed
    assert "PASS selftest-tiny/good" in printed


def test_selftest_checks_the_suite_file(tmp_path: Path) -> None:
    copy = shutil.copytree(TINY, tmp_path / "selftest-tiny")
    suite = json.loads((copy / "suite.json").read_text(encoding="utf-8"))
    del suite["claims"]["within-budget"]
    suite["claims"]["only-greeting-changed"]["oracle"] = "completion"
    suite["claims"]["stubs-unchanged"]["oracle"] = "completion"
    suite["budget"]["input_cap"] = 5
    suite["references"].remove("noop")
    (copy / "suite.json").write_text(json.dumps(suite), encoding="utf-8")
    (copy / "reading" / "says-what-changed.md").unlink()
    (copy / "references" / "empty" / "answer.md").write_text("Something.\n", encoding="utf-8")
    problems = SELFTEST.suite_problems(SELFTEST.Fixture("selftest-tiny", copy))
    for expected in (
        "claim within-budget has no type",
        "no restraint or safety oracle",
        "report item says-what-changed has no reading/says-what-changed.md",
        "budget.input_cap 5 is not the XS default 900000 and gives no reason",
        "reference noop is required",
        "reference empty has a non-empty answer",
    ):
        assert expected in problems, problems


def test_selftest_refuses_an_unknown_fixture(capsys: pytest.CaptureFixture[str]) -> None:
    assert SELFTEST.main(["no-such-fixture"]) == 2


def test_a_guard_fixture_is_labelled_and_stays_in_the_denominator(
    tmp_path: Path, fixtures: Path
) -> None:
    suite = json.loads((fixtures / "beta" / "suite.json").read_text(encoding="utf-8"))
    (fixtures / "beta" / "suite.json").write_text(json.dumps({**suite, "guard": True}), "utf-8")
    results = tmp_path / "results"
    for repetition in range(1, 4):
        write_run(results, "beta", "current", repetition, {"done": "FAIL"})
        write_run(results, "beta", "none", repetition, {"done": "PASS"})
    report = decide(results, fixtures, ["alpha", "beta"])
    head = report["headline"]
    assert head["guards"] == ["beta"] and head["denominator"] == 2
    assert head["candidate_regressions"] == ["beta (guard) outcome (awaits confirmation)"]
    assert "guards among them: beta" in PANEL.markdown(report)


def test_selftest_takes_a_report_only_suite_and_a_guard_with_reference_usage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copy = shutil.copytree(TINY, tmp_path / "selftest-tiny")
    suite = json.loads((copy / "suite.json").read_text(encoding="utf-8"))
    suite["guard"] = True
    suite["budget"]["reference"] = {"input": 1200, "uncached": 200, "output": 30, "commands": 3}
    (copy / "suite.json").write_text(json.dumps(suite), encoding="utf-8")
    fixture = SELFTEST.Fixture("selftest-tiny", copy)
    assert SELFTEST.suite_problems(fixture) == []
    budget = SELFTEST.default_budget(suite)
    assert budget == {"stopped": None, "input": 1200, "uncached": 200, "output": 30,
                      "seconds": 0, "commands": 3}  # fmt: skip
    suite["budget"]["reference"] = {"tokens": 5}
    (copy / "suite.json").write_text(json.dumps(suite), encoding="utf-8")
    assert "budget.reference.tokens is not one of" in SELFTEST.suite_problems(fixture)[0]

    only = {"tier": "XS", "panel": False, "class": "C6", "report": suite["report"]}
    (copy / "suite.json").write_text(json.dumps(only), encoding="utf-8")
    assert SELFTEST.suite_problems(fixture) == []
    assert SELFTEST.main([str(copy)]) == 0
    printed = capsys.readouterr().out
    assert "PASS selftest-tiny/suite.json: report-only, no references" in printed
    assert "selftest-tiny/good" not in printed
    (copy / "reading" / "says-what-changed.md").unlink()
    assert SELFTEST.main([str(copy)]) == 1
