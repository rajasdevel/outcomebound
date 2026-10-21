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
    fixture_names=lambda: ["alpha", "beta", "gamma"],
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
        "name": "loop1",
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
    out = tmp_path / "results" / "loop1"
    tail = ["--model", "model-x", "--effort", "medium", "--repetition", "1", "--fixtures", "alpha"]
    roots = ["--workspace-root", str(tmp_path / "workspaces" / "loop1")]
    assert found["minus"] == [
        "evals/run.py", "--arm", "current", "--drop", "fragment:commands", "--drop",
        "skill:diagnose", "--arm-label", "minus", *tail,
        "--out", str(out / "minus-r1-alpha"), *roots,
    ]  # fmt: skip
    assert found["plus"][:6] == ["evals/run.py", "--arm", "none", "--add", "kernel", "--arm-label"]
    assert found["edited"][3:5] == ["--edits", str(tmp_path / "edits.json")]


def test_done_cells_are_skipped_and_max_runs_bounds_new_ones(tmp_path: Path) -> None:
    plan = write_plan(tmp_path)
    done = tmp_path / "results" / "loop1" / "none-r1-alpha"
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
    stray = tmp_path / "results" / "loop1" / "minus-r2-beta"
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
    tmp_path: Path, change: dict[str, Any], message: str
) -> None:
    started: list[Any] = []
    code = LOOP.main(
        [str(write_plan(tmp_path, **change))],
        runner=lambda *args, **kwargs: started.append(args) or 0,
        module=RUNNER,
    )
    assert code == 2
    assert started == []
