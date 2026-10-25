"""`evals/loop.py`: the order of cells, resume, refusals and the run.py argv, with an injected
runner, so no test starts run.py or a model."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.eval_helpers import load

LOOP = load("eval_loop", "evals/loop.py")
RUNNER = SimpleNamespace(
    REPETITIONS=(1, 2, 3),
    ARMS=("earlier", "current", "unsized", "none"),
    NONE="none",
    PREFLIGHT_EXIT=3,
    fixture_names=lambda: ["alpha", "beta", "gamma", "delta"],
    ELEMENT=re.compile(r"kernel|facts|pointers|launcher|(?:fragment|skill):[a-z0-9][a-z0-9-]*"),
    InstallError=ValueError,
    Elements=lambda dropped, added: (dropped, added),
    fixture_install=lambda fixture: fixture,
    element_refusal=lambda install, elements: (
        f"{install} selects no {elements[0][0]}"
        if install == "gamma" and elements[0] == ("fragment:commands",)
        else ""
    ),
)
ARMS = [
    {"label": "none", "arm": "none"},
    {"label": "current", "arm": "current"},
    {"label": "minus", "arm": "current", "drop": ["fragment:commands"]},
]


def write_plan(tmp_path: Path, **changes: Any) -> Path:
    plan = {
        "name": "example",
        "model": "model-x",
        "effort": "medium",
        "results": str(tmp_path / "results"),
        "workspaces": str(tmp_path / "workspaces"),
        "repetitions": [1, 2],
        "fixtures": ["alpha", "beta"],
        "arms": ARMS,
        **changes,
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


class FakeRunner:
    """Records each argv and leaves the run directory run.py would, with the exit asked for."""

    def __init__(self, codes: dict[str, int] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.codes = codes or {}

    def __call__(self, words: tuple[str, ...], log: Path, cwd: Path) -> int:
        self.calls.append(words)
        out = Path(words[words.index("--out") + 1])
        code = self.codes.get(out.name, 0)
        out.mkdir(parents=True)
        status = {0: "ran", 1: "ran with failures"}.get(code, "UNVERIFIED")
        (out / "STATUS.json").write_text(json.dumps({"status": status}), encoding="utf-8")
        log.write_text("log\n", encoding="utf-8")
        return code


def cell_names(runner: FakeRunner) -> list[str]:
    return [Path(words[words.index("--out") + 1]).name for words in runner.calls]


def test_cells_rotate_the_arm_order_by_repetition_and_fixture(tmp_path: Path) -> None:
    runner = FakeRunner()
    assert LOOP.main([str(write_plan(tmp_path))], runner=runner, module=RUNNER) == 0
    assert cell_names(runner) == [
        "none-r1-alpha",
        "current-r1-alpha",
        "minus-r1-alpha",
        "current-r1-beta",
        "minus-r1-beta",
        "none-r1-beta",
        "current-r2-alpha",
        "minus-r2-alpha",
        "none-r2-alpha",
        "minus-r2-beta",
        "none-r2-beta",
        "current-r2-beta",
    ]


def test_argv_carries_drop_add_and_edits(tmp_path: Path) -> None:
    arms = [
        {"label": "minus", "arm": "current", "drop": ["fragment:commands", "skill:diagnose"]},
        {"label": "plus", "arm": "none", "add": ["kernel"]},
        {"label": "edited", "arm": "current", "edits": "edits.json"},
    ]
    (tmp_path / "edits.json").write_text("[]", encoding="utf-8")
    plan = LOOP.read_plan(write_plan(tmp_path, arms=arms, fixtures=["alpha"]), RUNNER)
    found = {
        cell.arm.label: list(cell.argv[1:]) for cell in LOOP.cells(plan) if cell.repetition == 1
    }
    out = tmp_path / "results" / "example"
    tail = ["--model", "model-x", "--effort", "medium", "--repetition", "1", "--fixtures", "alpha"]
    roots = ["--workspace-root", str(tmp_path / "workspaces" / "example")]
    assert found["minus"] == [
        "evals/run.py", "--harness", "codex", "--arm", "current", "--drop", "fragment:commands",
        "--drop", "skill:diagnose", "--arm-label", "minus", *tail,
        "--out", str(out / "minus-r1-alpha"), *roots,
    ]  # fmt: skip
    assert found["plus"][3:8] == ["--arm", "none", "--add", "kernel", "--arm-label"]
    assert found["edited"][5:7] == ["--edits", str(tmp_path / "edits.json")]


def test_an_earlier_ref_reaches_the_cell_and_the_record_and_holds_on_resume(
    tmp_path: Path,
) -> None:
    earlier = {"label": "base", "arm": "earlier", "earlier_ref": "v1.8.0"}
    current = {"label": "current", "arm": "current"}
    arms = [earlier, current]
    plan = LOOP.read_plan(write_plan(tmp_path, arms=arms, fixtures=["alpha"]), RUNNER)
    words = {cell.arm.label: list(cell.argv) for cell in LOOP.cells(plan)}
    base = words["base"]
    assert base[base.index("--earlier-ref") + 1] == "v1.8.0"
    assert "--earlier-ref" not in words["current"]
    LOOP.record(plan)
    saved = json.loads((tmp_path / "results" / "example" / "LOOP.json").read_text(encoding="utf-8"))
    assert saved["arms"][0]["earlier_ref"] == "v1.8.0" and "earlier_ref" not in saved["arms"][1]
    moved = [{**earlier, "earlier_ref": "v1.7.0"}, current]
    with pytest.raises(LOOP.PlanError, match="earlier_ref"):
        LOOP.record(LOOP.read_plan(write_plan(tmp_path, arms=moved, fixtures=["alpha"]), RUNNER))
    for wrong in ({**earlier, "arm": "current"}, {**earlier, "earlier_ref": "-x"}):
        with pytest.raises(LOOP.PlanError, match="earlier_ref"):
            LOOP.read_plan(write_plan(tmp_path, arms=[wrong], fixtures=["alpha"]), RUNNER)


def test_a_plan_service_tier_reaches_every_cell_and_the_record(tmp_path: Path) -> None:
    plain = LOOP.read_plan(write_plan(tmp_path, fixtures=["alpha"]), RUNNER)
    assert "--service-tier" not in [word for cell in LOOP.cells(plain) for word in cell.argv]
    plan = LOOP.read_plan(write_plan(tmp_path, fixtures=["alpha"], service_tier="priority"), RUNNER)
    for cell in LOOP.cells(plan):
        words = list(cell.argv)
        assert words[words.index("--effort") + 1 :][:3] == ["medium", "--service-tier", "priority"]
    LOOP.record(plan)
    saved = json.loads((tmp_path / "results" / "example" / "LOOP.json").read_text(encoding="utf-8"))
    assert saved["service_tier"] == "priority"
    with pytest.raises(LOOP.PlanError, match="service_tier"):
        LOOP.record(plain)  # the same name under no tier is another run
    with pytest.raises(LOOP.PlanError, match="service_tier"):
        LOOP.read_plan(write_plan(tmp_path, service_tier="Fast"), RUNNER)
    with pytest.raises(LOOP.PlanError, match="for codex"):
        LOOP.read_plan(write_plan(tmp_path, service_tier="priority", harness="claude-code"), RUNNER)


def test_done_cells_are_skipped_and_max_runs_bounds_new_ones(tmp_path: Path) -> None:
    plan = write_plan(tmp_path)
    done = tmp_path / "results" / "example" / "none-r1-alpha"
    done.mkdir(parents=True)
    (done / "STATUS.json").write_text(json.dumps({"status": "ran with failures"}), encoding="utf-8")
    runner = FakeRunner()
    assert LOOP.main([str(plan), "--max-runs", "2"], runner=runner, module=RUNNER) == 0
    assert cell_names(runner) == ["current-r1-alpha", "minus-r1-alpha"]
    runner = FakeRunner()
    assert LOOP.main([str(plan)], runner=runner, module=RUNNER) == 0
    assert len(runner.calls) == 12 - 3


def test_a_cell_in_another_state_stops_the_loop_before_anything_starts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = write_plan(tmp_path)
    stray = tmp_path / "results" / "example" / "minus-r2-beta"
    stray.mkdir(parents=True)
    (stray / "STATUS.json").write_text(json.dumps({"status": "running"}), encoding="utf-8")
    runner = FakeRunner()
    assert LOOP.main([str(plan)], runner=runner, module=RUNNER) == 1
    assert runner.calls == []
    assert "minus-r2-beta" in capsys.readouterr().err
    assert (stray / "STATUS.json").is_file()


def test_dry_run_starts_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeRunner()
    assert LOOP.main([str(write_plan(tmp_path)), "--dry-run"], runner=runner, module=RUNNER) == 0
    assert runner.calls == []
    printed = capsys.readouterr().out
    assert "cells 12, done 0, to run 12" in printed
    assert "--arm current --drop fragment:commands --arm-label minus" in printed
    assert not (tmp_path / "results").exists()


def test_a_failed_cell_is_counted_and_a_preflight_failure_stops(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner({"current-r1-alpha": 1})
    assert LOOP.main([str(write_plan(tmp_path))], runner=runner, module=RUNNER) == 1
    printed = capsys.readouterr().out
    assert len(runner.calls) == 12
    assert "cells run 12, skipped 0, failed 1" in printed
    assert "evals/run.py --summary" in printed and "evals/attribute.py" in printed

    other = tmp_path / "second"
    other.mkdir()
    runner = FakeRunner({"none-r1-alpha": 3})
    assert LOOP.main([str(write_plan(other))], runner=runner, module=RUNNER) == 1
    assert cell_names(runner) == ["none-r1-alpha"]
    assert "preflight" in capsys.readouterr().out


@pytest.mark.parametrize(
    "changes",
    [
        {"extra": 1},
        {"arms": [*ARMS, {"label": "none", "arm": "none"}]},
        {"repetitions": [4]},
        {"fixtures": ["alpha", "nope"]},
        {"arms": [{"label": "x", "arm": "none", "drop": ["fragment:commands"]}]},
        {"arms": [{"label": "x", "arm": "current", "add": ["kernel"]}]},
        {"arms": [{"label": "x", "arm": "current", "colour": "red"}]},
    ],
)
def test_refused_plans_start_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], changes: dict[str, Any]
) -> None:
    runner = FakeRunner()
    assert LOOP.main([str(write_plan(tmp_path, **changes))], runner=runner, module=RUNNER) == 2
    assert runner.calls == []
    assert "refused, nothing started" in capsys.readouterr().err


def test_the_real_runner_accepts_the_plan_interface() -> None:
    real = LOOP.load_runner()
    assert set(RUNNER.REPETITIONS) <= set(real.REPETITIONS)
    assert real.NONE == "none" and "current" in real.ARMS
    assert isinstance(real.PREFLIGHT_EXIT, int)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"arms": [{"label": "typo", "arm": "current", "drop": ["skil:diagnose"]}]}, "no element"),
        ({"arms": [{"label": "ed", "arm": "current", "edits": "missing.json"}]}, "no edits file"),
        ({"fixtures": ["alpha", "gamma"]}, "arm minus on gamma"),
    ],
)
def test_element_refusals_come_before_any_cell(
    tmp_path: Path, change: dict[str, Any], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    started: list[Any] = []

    def runner(*args: Any, **kwargs: Any) -> int:
        started.append(args)
        return 0

    code = LOOP.main([str(write_plan(tmp_path, **change))], runner=runner, module=RUNNER)
    assert code == 2
    assert started == []
    assert message in capsys.readouterr().err


# Suite-v2 plans: packs from each fixture's suite.json, the harness and profile recorded, up to
# ten repetitions, and a pass-level spend limit checked before each cell.
REFS = ["good", "noop", "empty", "incomplete", "overbuilt"]
SUITES = {
    "alpha": {"tier": "XS", "panel": True, "budget": {"input_cap": 300}, "references": REFS},
    "beta": {"tier": "S", "panel": True, "budget": {"input_cap": 900}, "references": REFS},
    "gamma": {"tier": "S", "panel": False, "budget": {"input_cap": 900}, "references": REFS},
    "delta": {"tier": "XS", "report": {}},  # report-only: in no pack
    "epsilon": {"tier": "S", "panel": True, "references": REFS},  # default fixture: in no pack
}
TEN = SimpleNamespace(**{**vars(RUNNER), "REPETITIONS": tuple(range(1, 11))})


@pytest.fixture
def suites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    fixtures = tmp_path / "fixtures"
    for name, document in SUITES.items():
        (fixtures / name).mkdir(parents=True)
        (fixtures / name / "suite.json").write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(LOOP, "FIXTURES", fixtures)
    return fixtures


def pack_plan(tmp_path: Path, **changes: Any) -> Path:
    path = write_plan(tmp_path, **changes)
    document = json.loads(path.read_text(encoding="utf-8"))
    if "pack" in changes:
        del document["fixtures"]
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("pack", "fixtures"),
    [("XS", ("alpha",)), ("S", ("beta", "gamma")), ("panel", ("alpha", "beta"))],
)
def test_a_pack_resolves_its_fixtures_from_suite_json(
    tmp_path: Path, suites: Path, pack: str, fixtures: tuple[str, ...]
) -> None:
    plan = LOOP.read_plan(pack_plan(tmp_path, pack=pack, arms=ARMS[:2]), RUNNER)
    assert plan.fixtures == fixtures and plan.pack == pack


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"pack": "XL"}, "pack is one of"),
        ({"pack": "M"}, "no fixture's suite.json puts it in pack M"),
        ({"harness": "gemini"}, "harness gemini cannot run yet"),
        ({"repetitions": [1, 11]}, "repetitions are distinct values"),
        ({"spend_limit": 0}, "spend_limit is a positive number"),
    ],
)
def test_suite_v2_plan_refusals_start_nothing(
    tmp_path: Path,
    suites: Path,
    changes: dict[str, Any],
    message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runner = FakeRunner()
    path = pack_plan(tmp_path, arms=ARMS[:2], **changes)
    assert LOOP.main([str(path)], runner=runner, module=TEN) == 2
    assert runner.calls == []
    assert message in capsys.readouterr().err


def test_a_plan_with_both_fixtures_and_a_pack_is_refused(tmp_path: Path, suites: Path) -> None:
    with pytest.raises(LOOP.PlanError, match="fixtures or a pack"):
        LOOP.read_plan(write_plan(tmp_path, pack="XS"), RUNNER)


def test_a_spend_limit_needs_every_fixture_s_input_cap(tmp_path: Path, suites: Path) -> None:
    (suites / "gamma" / "suite.json").write_text(
        json.dumps({"tier": "S", "budget": {"timeout_seconds": 900}, "references": REFS}),
        encoding="utf-8",
    )
    with pytest.raises(LOOP.PlanError, match="gamma has none"):
        LOOP.read_plan(pack_plan(tmp_path, pack="S", spend_limit=10_000), RUNNER)


def test_ten_repetitions_run_and_the_harness_and_profile_are_recorded(
    tmp_path: Path, suites: Path
) -> None:
    runner = FakeRunner()
    path = write_plan(
        tmp_path, repetitions=list(range(1, 11)), fixtures=["alpha"], arms=ARMS[:2], profile="attr"
    )
    assert LOOP.main([str(path)], runner=runner, module=TEN) == 0
    assert len(runner.calls) == 20
    assert {words[words.index("--repetition") + 1] for words in runner.calls} == {
        str(n) for n in range(1, 11)
    }
    recorded = json.loads((tmp_path / "results" / "example" / "LOOP.json").read_text("utf-8"))
    assert (recorded["harness"], recorded["profile"], recorded["fixtures"]) == (
        "codex", "attr", ["alpha"],
    )  # fmt: skip
    changed = write_plan(tmp_path, fixtures=["alpha"], arms=ARMS[:2], profile="field-codex")
    assert LOOP.main([str(changed)], runner=FakeRunner(), module=TEN) == 2


class SpendingRunner(FakeRunner):
    """A FakeRunner whose every cell records `spend` input tokens in its meta file."""

    def __init__(self, spend: int) -> None:
        super().__init__()
        self.spend = spend

    def __call__(self, words: tuple[str, ...], log: Path, cwd: Path) -> int:
        code = super().__call__(words, log, cwd)
        out = Path(words[words.index("--out") + 1])
        fixture = words[words.index("--fixtures") + 1]
        meta = {"fixture": fixture, "session_tokens": {"input_tokens": self.spend}}
        (out / f"{fixture}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return code


def test_the_spend_limit_stops_before_a_cell_that_could_pass_it(
    tmp_path: Path, suites: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cells of alpha (cap 300) each record 100 input tokens; with a limit of 1000 the loop runs
    a cell while what is recorded before it plus one cap stays within it: before the ninth, 800 is
    recorded and 800 + 300 passes 1000, so eight run."""

    path = write_plan(
        tmp_path, repetitions=list(range(1, 11)), fixtures=["alpha"], arms=ARMS[:2],
        spend_limit=1000,
    )  # fmt: skip
    runner = SpendingRunner(100)
    assert LOOP.main([str(path)], runner=runner, module=TEN) == 0
    assert len(runner.calls) == 8
    printed = capsys.readouterr().out
    assert "stopped: before a cell that could pass the spend limit 1000" in printed
    assert "800 recorded so far" in printed
    again = SpendingRunner(100)
    assert LOOP.main([str(path)], runner=again, module=TEN) == 0
    assert again.calls == []


def test_a_cell_that_ran_without_a_record_counts_as_its_cap(tmp_path: Path, suites: Path) -> None:
    path = write_plan(tmp_path, fixtures=["alpha"], arms=ARMS[:2], spend_limit=650)
    plan = LOOP.read_plan(path, RUNNER)
    ordered = LOOP.cells(plan)
    ordered[0].out.mkdir(parents=True)
    assert LOOP.spent_so_far(plan, ordered) == 300
    assert LOOP.over_limit(plan, ordered, ordered[1]) == ""
    ordered[1].out.mkdir(parents=True)
    assert "could take up to 300" in LOOP.over_limit(plan, ordered, ordered[2])


def test_dry_run_shows_the_spend_projection(
    tmp_path: Path, suites: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = pack_plan(tmp_path, pack="panel", arms=ARMS[:2], spend_limit=10_000)
    assert LOOP.main([str(path), "--dry-run"], runner=FakeRunner(), module=RUNNER) == 0
    printed = capsys.readouterr().out
    assert "0 recorded so far, worst case of the cells to run 4800" in printed


KEEPS = SimpleNamespace(
    **{
        **vars(RUNNER),
        "ARMS": ("none", "current", "facts-only-noskills"),
        "FACTS_ONLY_NOSKILLS": "facts-only-noskills",
        "REPO": Path("."),
        "carried_skills": lambda root: ("diagnose", "decision-brief", "review-findings"),
    }
)


def keep_plan(tmp_path: Path, keep: list[str], **changes: Any) -> Path:
    arms = [
        {"label": "none", "arm": "none"},
        {"label": "kept", "arm": "facts-only-noskills", "keep_skills": keep},
    ]
    return write_plan(tmp_path, arms=arms, fixtures=["alpha"], **changes)


def test_a_keep_list_reaches_the_cell_the_record_and_the_reuse_check(tmp_path: Path) -> None:
    plan = LOOP.read_plan(keep_plan(tmp_path, ["diagnose", "decision-brief"]), KEEPS)
    found = {cell.arm.label: list(cell.argv) for cell in LOOP.cells(plan) if cell.repetition == 1}
    words = found["kept"]
    assert words[words.index("--keep-skills") + 1] == "diagnose,decision-brief"
    assert words[words.index("--arm") + 1] == "facts-only-noskills"
    assert words[words.index("--arm-label") + 1] == "kept"
    assert "--keep-skills" not in found["none"]
    LOOP.record(plan)
    saved = json.loads((tmp_path / "results" / "example" / "LOOP.json").read_text(encoding="utf-8"))
    assert saved["arms"][1]["keep_skills"] == ["diagnose", "decision-brief"]
    assert "keep_skills" not in saved["arms"][0]
    LOOP.record(plan)  # the same list under the same name is the same run
    other = LOOP.read_plan(keep_plan(tmp_path, ["diagnose"]), KEEPS)
    with pytest.raises(LOOP.PlanError, match="records keep_skills"):
        LOOP.record(other)
    # An arm the record lacks may be added under the name.
    more = [
        {"label": "none", "arm": "none"},
        {
            "label": "kept",
            "arm": "facts-only-noskills",
            "keep_skills": ["diagnose", "decision-brief"],
        },
    ]
    more.append({"label": "second", "arm": "facts-only-noskills", "keep_skills": ["diagnose"]})
    LOOP.record(LOOP.read_plan(write_plan(tmp_path, arms=more, fixtures=["alpha"]), KEEPS))


@pytest.mark.parametrize(
    ("keep", "arm", "message"),
    [
        (["nope"], "facts-only-noskills", "does not carry"),
        (["diagnose", "diagnose"], "facts-only-noskills", "twice"),
        (["diagnose"], "current", "applies to the facts-only-noskills arm only"),
        ("diagnose", "facts-only-noskills", "list of non-empty strings"),
    ],
)
def test_a_bad_keep_list_is_refused_before_any_cell(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], keep: Any, arm: str, message: str
) -> None:
    runner = FakeRunner()
    arms = [{"label": "kept", "arm": arm, "keep_skills": keep}]
    path = write_plan(tmp_path, arms=arms, fixtures=["alpha"])
    assert LOOP.main([str(path)], runner=runner, module=KEEPS) == 2
    assert runner.calls == []
    assert message in capsys.readouterr().err
