#!/usr/bin/env python3
"""Run a plan of eval cells, one `evals/run.py` call each, so arms are compared side by side.

`python3 evals/loop.py PLAN.json [--dry-run] [--max-runs N]`. The plan is a JSON object:

    {"name": "loop1", "model": "MODEL", "effort": "medium",
     "results": "/abs/results", "workspaces": "/abs/workspaces",
     "repetitions": [1, 2, 3], "fixtures": ["FIXTURE", ...],
     "arms": [{"label": "none", "arm": "none"},
              {"label": "current-minus-x", "arm": "current", "drop": ["fragment:x"]},
              {"label": "none-plus-kernel", "arm": "none", "add": ["kernel"]},
              {"label": "edited", "arm": "current", "edits": "/abs/edits.json"}]}

A cell is one (repetition, fixture, arm). For each repetition and each fixture every arm runs,
in the plan's arm order rotated by the repetition's index plus the fixture's index, so no arm
always runs first and the arms of one fixture run close together in time. Each cell writes
`<results>/<name>/<label>-r<repetition>-<fixture>`, with the call's stdout and stderr in the
`.log` file beside it, and keeps its workspaces under `<workspaces>/<name>`. A relative path in
the plan is read from the plan's folder.

A cell whose directory holds a STATUS.json of `ran` or `ran with failures` is done and is
skipped. A cell directory in any other state stops the loop before it starts anything: run.py
refuses an existing directory, and this never deletes or overwrites one. A cell that exits
non-zero is counted as failed and the loop goes on, except after run.py's preflight exit (no
login observed), which stops it. Only this tool, run by a person without `--dry-run`, starts
model runs.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, NamedTuple

REPO = Path(__file__).resolve().parent.parent
RUN_SCRIPT = REPO / "evals" / "run.py"
PLAN_KEYS = frozenset(
    ("name", "model", "effort", "results", "workspaces", "repetitions", "fixtures", "arms")
)
REQUIRED_KEYS = PLAN_KEYS - {"effort"}
ARM_KEYS = frozenset(("label", "arm", "drop", "add", "edits"))
DONE = ("ran", "ran with failures")
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
REFUSED = 2


class Arm(NamedTuple):
    """One arm of the plan: its label, the run.py arm it builds on, and its changes."""

    label: str
    arm: str
    drop: tuple[str, ...]
    add: tuple[str, ...]
    edits: str


class Plan(NamedTuple):
    name: str
    model: str
    effort: str
    results: Path
    workspaces: Path
    repetitions: tuple[int, ...]
    fixtures: tuple[str, ...]
    arms: tuple[Arm, ...]


class Cell(NamedTuple):
    repetition: int
    fixture: str
    arm: Arm
    out: Path
    argv: tuple[str, ...]


class PlanError(Exception):
    """A plan this tool refuses."""


def load_runner() -> ModuleType:
    """`evals/run.py` as a module, for the arms, repetitions, fixtures and preflight exit it
    accepts; loading it runs nothing."""

    spec = importlib.util.spec_from_file_location("eval_run_for_loop", RUN_SCRIPT)
    if spec is None or spec.loader is None:
        raise PlanError(f"cannot load {RUN_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strings(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise PlanError(f"{where} is a list of non-empty strings")
    return tuple(value)


def _path(value: Any, where: str, base: Path) -> Path:
    if not isinstance(value, str) or not value:
        raise PlanError(f"{where} is a path")
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def _arm(entry: Any, arms: tuple[str, ...], kinds: tuple[str, str], base: Path) -> Arm:
    current, none = kinds
    if not isinstance(entry, dict):
        raise PlanError("each arm is an object")
    unknown = sorted(set(entry) - ARM_KEYS)
    if unknown:
        raise PlanError(f"unknown arm key {', '.join(unknown)}")
    label, kind = entry.get("label"), entry.get("arm")
    if not isinstance(label, str) or not NAME.match(label):
        raise PlanError(f"arm label {label!r} is letters, digits, '.', '_' and '-'")
    if kind not in arms:
        raise PlanError(f"arm {label}: arm {kind!r} is not one of {', '.join(arms)}")
    drop = _strings(entry["drop"], f"arm {label}: drop") if "drop" in entry else ()
    add = _strings(entry["add"], f"arm {label}: add") if "add" in entry else ()
    if drop and kind != current:
        raise PlanError(f"arm {label}: drop applies to the {current} arm only")
    if add and kind != none:
        raise PlanError(f"arm {label}: add applies to the {none} arm only")
    edits = str(_path(entry["edits"], f"arm {label}: edits", base)) if "edits" in entry else ""
    return Arm(label, str(kind), drop, add, edits)


def read_plan(path: Path, runner: ModuleType) -> Plan:
    """The plan in `path`, checked against what run.py accepts; PlanError says what is wrong."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        raise PlanError(f"cannot read {path}: {problem}") from None
    if not isinstance(document, dict):
        raise PlanError("the plan is a JSON object")
    unknown = sorted(set(document) - PLAN_KEYS)
    if unknown:
        raise PlanError(f"unknown key {', '.join(unknown)}")
    missing = sorted(REQUIRED_KEYS - set(document))
    if missing:
        raise PlanError(f"missing key {', '.join(missing)}")
    base = path.resolve().parent
    name, model = document["name"], document["model"]
    effort = document.get("effort", "medium")
    if not isinstance(name, str) or not NAME.match(name):
        raise PlanError(f"name {name!r} is letters, digits, '.', '_' and '-'")
    if not isinstance(model, str) or not model or not isinstance(effort, str) or not effort:
        raise PlanError("model and effort are non-empty strings")
    plan = Plan(
        name,
        model,
        effort,
        _path(document["results"], "results", base),
        _path(document["workspaces"], "workspaces", base),
        _repetitions(document["repetitions"], tuple(runner.REPETITIONS)),
        _fixtures(document["fixtures"], set(runner.fixture_names())),
        _arms(document["arms"], runner, base),
    )
    _elements_fit(plan, runner)
    return plan


def _elements_fit(plan: Plan, runner: ModuleType) -> None:
    """Refuse, before any cell starts, what run.py would refuse only when a cell of the arm
    runs: an element it does not know, an edits file that is not there, or an element a
    fixture's install cannot give (no install.json, a fragment it does not select, a skill no
    install carries)."""

    for arm in plan.arms:
        strange = [item for item in (*arm.drop, *arm.add) if not runner.ELEMENT.fullmatch(item)]
        if strange:
            raise PlanError(f"arm {arm.label}: no element {', '.join(strange)}")
        if arm.edits and not Path(arm.edits).is_file():
            raise PlanError(f"arm {arm.label}: no edits file {arm.edits}")
        if not (arm.drop or arm.add):
            continue
        for fixture in plan.fixtures:
            try:
                install = runner.fixture_install(fixture)
            except runner.InstallError as problem:
                raise PlanError(f"{fixture}: {problem}") from None
            refusal = runner.element_refusal(install, runner.Elements(arm.drop, arm.add))
            if refusal:
                raise PlanError(f"arm {arm.label} on {fixture}: {refusal}")


def _repetitions(value: Any, accepted: tuple[int, ...]) -> tuple[int, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(type(item) is not int or item not in accepted for item in value)
        or len(set(value)) != len(value)
    ):
        raise PlanError(f"repetitions are distinct values of {list(accepted)}")
    return tuple(value)


def _fixtures(value: Any, known: set[str]) -> tuple[str, ...]:
    fixtures = _strings(value, "fixtures")
    strange = sorted(set(fixtures) - known)
    if strange or len(set(fixtures)) != len(fixtures):
        raise PlanError(f"fixtures run.py does not know or named twice: {', '.join(strange)}")
    return fixtures


def _arms(entries: Any, runner: ModuleType, base: Path) -> tuple[Arm, ...]:
    if not isinstance(entries, list) or not entries:
        raise PlanError("arms is a non-empty list")
    kinds = ("current", runner.NONE)
    arms = tuple(_arm(entry, tuple(runner.ARMS), kinds, base) for entry in entries)
    labels = [arm.label for arm in arms]
    twice = sorted({label for label in labels if labels.count(label) > 1})
    if twice:
        raise PlanError(f"duplicate label {', '.join(twice)}")
    return arms


def argv(plan: Plan, arm: Arm, repetition: int, fixture: str, out: Path) -> tuple[str, ...]:
    """The run.py call of one cell."""

    words = [sys.executable, "evals/run.py", "--arm", arm.arm]
    for entry in arm.drop:
        words += ["--drop", entry]
    for entry in arm.add:
        words += ["--add", entry]
    if arm.edits:
        words += ["--edits", arm.edits]
    words += [
        "--arm-label",
        arm.label,
        "--model",
        plan.model,
        "--effort",
        plan.effort,
        "--repetition",
        str(repetition),
        "--fixtures",
        fixture,
        "--out",
        str(out),
        "--workspace-root",
        str(plan.workspaces / plan.name),
    ]
    return tuple(words)


def cells(plan: Plan) -> list[Cell]:
    """Every cell in run order: for each repetition, each fixture, every arm, the arm order
    rotated by the repetition's index plus the fixture's index."""

    found = []
    count = len(plan.arms)
    for r_index, repetition in enumerate(plan.repetitions):
        for f_index, fixture in enumerate(plan.fixtures):
            turn = (r_index + f_index) % count
            for arm in plan.arms[turn:] + plan.arms[:turn]:
                out = plan.results / plan.name / f"{arm.label}-r{repetition}-{fixture}"
                found.append(
                    Cell(repetition, fixture, arm, out, argv(plan, arm, repetition, fixture, out))
                )
    return found


def state(cell: Cell) -> str:
    """`new` where the cell's directory does not exist, `done` where its STATUS.json says it
    ran, else what stops the loop."""

    if not cell.out.exists():
        return "new"
    try:
        status = json.loads((cell.out / "STATUS.json").read_text(encoding="utf-8")).get("status")
    except (OSError, ValueError, AttributeError):
        status = None
    if status in DONE:
        return "done"
    return f"blocked: {cell.out} exists with status {status or 'unreadable'}"


def log_path(cell: Cell) -> Path:
    return cell.out.with_name(cell.out.name + ".log")


def run_cell(words: tuple[str, ...], log: Path, cwd: Path) -> int:
    """Start one run.py call, its stdout and stderr appended to `log`, and give its exit."""

    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as stream:
        return subprocess.run(
            list(words), cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, check=False
        ).returncode


Runner = Callable[[tuple[str, ...], Path, Path], int]


def follow_up(directories: list[Path]) -> list[str]:
    joined = " ".join(shlex.quote(str(path)) for path in directories)
    return [f"python3 evals/run.py --summary {joined}", f"python3 evals/attribute.py {joined}"]


def dry_run(ordered: list[Cell], states: list[str]) -> int:
    """Print each cell with its state and argv, and the counts; exit 1 where a cell blocks."""

    for n, (cell, found) in enumerate(zip(ordered, states, strict=True), start=1):
        print(f"{n:>4} {found:<6} {cell.arm.label} r{cell.repetition} {cell.fixture}")
        print(f"       {shlex.join(cell.argv)}")
    blocked = sum(found.startswith("blocked") for found in states)
    to_run = states.count("new")
    print(f"cells {len(ordered)}, done {states.count('done')}, to run {to_run}, blocked {blocked}")
    return 1 if blocked else 0


def execute(
    ordered: list[Cell], states: list[str], runner: Runner, max_runs: int | None, preflight: int
) -> int:
    """Start each new cell in order, at most `max_runs`, and print what happened."""

    ran, failed, stopped = 0, 0, ""
    for cell, found in zip(ordered, states, strict=True):
        if found == "done":
            continue
        if max_runs is not None and ran >= max_runs:
            stopped = f"--max-runs {max_runs} reached"
            break
        print(f"loop: {cell.arm.label} r{cell.repetition} {cell.fixture}", flush=True)
        code = runner(cell.argv, log_path(cell), REPO)
        ran += 1
        if code != 0:
            failed += 1
            sys.stderr.write(f"loop: {cell.out.name} exited {code}; see {log_path(cell)}\n")
        if code == preflight:
            stopped = "run.py's preflight observed no login; log in and run the loop again"
            break
    left = sum(1 for cell in ordered if state(cell) == "new")
    print(f"cells run {ran}, skipped {states.count('done')}, failed {failed}, left {left}")
    if stopped:
        print(f"stopped: {stopped}")
    kept = [cell.out for cell in ordered if cell.out.is_dir()]
    if kept:
        print("next:")
        for line in follow_up(kept):
            print(f"  {line}")
    return 1 if failed else 0


def main(
    argv_list: list[str] | None = None, runner: Runner = run_cell, module: ModuleType | None = None
) -> int:
    """The command line; `runner` starts one cell and `module` stands for run.py, both
    replaceable so a test starts nothing."""

    parser = argparse.ArgumentParser(
        prog="evals/loop.py",
        description="Run a plan of eval cells through evals/run.py; see the module docstring.",
    )
    parser.add_argument("plan", metavar="PLAN.json")
    parser.add_argument(
        "--dry-run", action="store_true", help="print the cells and their argv; start nothing"
    )
    parser.add_argument(
        "--max-runs", type=int, default=None, metavar="N", help="start at most N new cells"
    )
    args = parser.parse_args(argv_list)
    if args.max_runs is not None and args.max_runs < 0:
        parser.error("--max-runs is zero or more")
    try:
        runner_module = module or load_runner()
        plan = read_plan(Path(args.plan), runner_module)
    except PlanError as problem:
        sys.stderr.write(f"loop: refused, nothing started: {problem}\n")
        return REFUSED
    ordered = cells(plan)
    states = [state(cell) for cell in ordered]
    if args.dry_run:
        return dry_run(ordered, states)
    blocked = [found for found in states if found.startswith("blocked")]
    for found in blocked:
        sys.stderr.write(f"loop: stopped before starting anything: {found}\n")
    if blocked:
        return 1
    preflight = int(getattr(runner_module, "PREFLIGHT_EXIT", 3))
    return execute(ordered, states, runner, args.max_runs, preflight)


if __name__ == "__main__":
    raise SystemExit(main())
