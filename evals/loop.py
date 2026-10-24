#!/usr/bin/env python3
"""Run a plan of eval cells, one `evals/run.py` call each, so arms are compared side by side.

`python3 evals/loop.py PLAN.json [--dry-run] [--max-runs N]`. The plan is a JSON object:

    {"name": "example", "model": "MODEL", "effort": "medium", "service_tier": "priority",
     "harness": "codex", "profile": "attr",
     "results": "/abs/results", "workspaces": "/abs/workspaces",
     "repetitions": [1, 2, 3], "fixtures": ["FIXTURE", ...],
     "spend_limit": 50000000,
     "arms": [{"label": "none", "arm": "none"},
              {"label": "current-minus-x", "arm": "current", "drop": ["fragment:x"]},
              {"label": "none-plus-kernel", "arm": "none", "add": ["kernel"]},
              {"label": "edited", "arm": "current", "edits": "/abs/edits.json"},
              {"label": "facts-only", "arm": "facts-only"},
              {"label": "facts-only-noskills", "arm": "facts-only-noskills"},
              {"label": "keep-dd", "arm": "facts-only-noskills",
               "keep_skills": ["diagnose", "decision-brief"]},
              {"label": "bare", "arm": "bare"}]}

An arm of kind `facts-only-noskills` may give `keep_skills`, a list of distinct skill names that
adopt carries: it keeps those skills' files and removes the others (each is passed to run.py as
`--keep-skills`). Arms that keep different skills need different labels, which name their result
folders. LOOP.json records the list when it is set, and a plan name that ran under another list
for the same label is refused like one that ran under another model.

A Claude Code plan names `"harness": "claude-code"`, and may give an arm a plugin from a pinned
clone: `{"label": "ponytail-plugin", "arm": "none", "plugin_dir": "/abs/third-party/ponytail"}`.
The folder must resolve inside the evals home's `third-party/` folder (run.py's
`plugin_dir_refusal`), never a plugin cache, and run.py records its commit.

In place of `fixtures`, `pack` names a pack: `XS`, `S`, `M` or `L` is every fixture whose
`suite.json` gives that tier, `panel` every fixture whose `suite.json` says `panel: true`; a
report-only suite.json (one with no `references`) and a default fixture's (references and no
`budget`, named by `fixtures` instead) put their fixture in no pack.
Repetitions are distinct values from 1 to 10 that run.py accepts. `harness` (default `codex`,
or `claude-code`) and `profile` (default empty) are recorded in `<results>/<name>/LOOP.json`;
only a harness run.py can run is accepted. A profile in PROFILES (`attr`, `field-codex`,
`claude-mid`, `claude-top`, `small`) must name its own harness; any other profile is a free label.

`service_tier`, optional and for `codex` only, is passed to each cell as `--service-tier`
(`priority` is codex's fast mode); each cell's native session must show it. It is recorded in
LOOP.json when set, and a plan name that ran under another tier is refused like one that ran
under another model.

`spend_limit`, optional, is the pass's limit on input tokens (cached input among them). Before
each new cell the loop adds the input every cell of the plan has recorded so far (its
`session_tokens`, else its budget record, else, for a cell that ran and recorded neither, its
fixture's cap) to the cell's worst case, its fixture's `budget.input_cap` from `suite.json`, and
stops before a cell whose worst case would pass the limit. A plan with a limit is refused where
a fixture has no input cap. The cap is the runner's best-effort stop, so a cell can overshoot it
by the turn in flight; the limit leaves that headroom to the person who sets it.

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
import os
import re
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, NamedTuple

REPO = Path(__file__).resolve().parent.parent
RUN_SCRIPT = REPO / "evals" / "run.py"
FIXTURES = REPO / "evals" / "fixtures"
PLAN_KEYS = frozenset(
    (
        "name",
        "model",
        "effort",
        "service_tier",
        "harness",
        "profile",
        "results",
        "workspaces",
        "repetitions",
        "fixtures",
        "pack",
        "spend_limit",
        "arms",
    )
)
# The shape run.py accepts for `--service-tier` (evals.harnesses.SERVICE_TIER).
SERVICE_TIER = re.compile(r"[a-z][a-z0-9_-]*")
REQUIRED_KEYS = frozenset(("name", "model", "results", "workspaces", "repetitions", "arms"))
PACKS = ("XS", "S", "M", "L", "panel")
MAX_REPETITION = 10
# The harnesses this loop can start a cell with; another is recorded in a plan only once run.py
# runs it.
RUNNABLE = ("codex", "claude-code")
# The named profiles of the suite's design and the harness each runs on; a plan's model and
# effort are its own.
PROFILES = {
    "attr": "codex",
    "field-codex": "codex",
    "claude-mid": "claude-code",
    "claude-top": "claude-code",
    "small": "claude-code",
}
ARM_KEYS = frozenset(("label", "arm", "drop", "add", "edits", "plugin_dir", "keep_skills"))
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
    plugin_dir: str = ""
    keep_skills: tuple[str, ...] = ()


class Plan(NamedTuple):
    name: str
    model: str
    effort: str
    results: Path
    workspaces: Path
    repetitions: tuple[int, ...]
    fixtures: tuple[str, ...]
    arms: tuple[Arm, ...]
    harness: str = "codex"
    profile: str = ""
    pack: str = ""
    spend_limit: int | None = None
    caps: tuple[tuple[str, int], ...] = ()
    service_tier: str = ""

    def cap(self, fixture: str) -> int:
        return dict(self.caps)[fixture]


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


def _keep(
    entry: dict[str, Any], label: str, kind: Any, noskills: str, skills: tuple[str, ...]
) -> tuple[str, ...]:
    """An arm's `keep_skills`: for the skill-less facts-only arm only, each a skill adopt carries
    and named once."""

    if "keep_skills" not in entry:
        return ()
    keep = _strings(entry["keep_skills"], f"arm {label}: keep_skills")
    if kind != noskills:
        raise PlanError(f"arm {label}: keep_skills applies to the {noskills} arm only")
    unknown = [item for item in keep if item not in skills]
    if unknown or len(set(keep)) != len(keep):
        raise PlanError(
            f"arm {label}: keep_skills names a skill adopt does not carry or names one twice: "
            f"{', '.join(unknown) or 'a repeat'}; the skills are {', '.join(skills)}"
        )
    return keep


def _arm(
    entry: Any,
    arms: tuple[str, ...],
    kinds: tuple[str, str, str],
    base: Path,
    skills: tuple[str, ...],
) -> Arm:
    current, none, _noskills = kinds
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
    if edits and kind != current and not (kind == none and add):
        raise PlanError(
            f"arm {label}: edits apply to the {current} arm, or the {none} arm with add"
        )
    plugin = entry.get("plugin_dir")
    folder = str(_path(plugin, f"arm {label}: plugin_dir", base)) if "plugin_dir" in entry else ""
    keep = _keep(entry, label, kind, kinds[2], skills)
    return Arm(label, str(kind), drop, add, edits, folder, keep)


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
    if ("fixtures" in document) == ("pack" in document):
        raise PlanError("the plan names fixtures or a pack, not both and not neither")
    base = path.resolve().parent
    name, model = document["name"], document["model"]
    effort = document.get("effort", "medium")
    if not isinstance(name, str) or not NAME.match(name):
        raise PlanError(f"name {name!r} is letters, digits, '.', '_' and '-'")
    if not isinstance(model, str) or not model or not isinstance(effort, str) or not effort:
        raise PlanError("model and effort are non-empty strings")
    harness, profile = document.get("harness", "codex"), document.get("profile", "")
    if not isinstance(profile, str):
        raise PlanError("profile is a string")
    _harness(harness, runner)
    service_tier = _service_tier(document.get("service_tier", ""), harness)
    if profile in PROFILES and PROFILES[profile] != harness:
        raise PlanError(f"profile {profile} runs on {PROFILES[profile]}, not {harness}")
    known = set(runner.fixture_names())
    pack = document.get("pack", "")
    fixtures = _pack(pack, known) if "pack" in document else _fixtures(document["fixtures"], known)
    limit = _spend_limit(document.get("spend_limit"))
    plan = Plan(
        name,
        model,
        effort,
        _path(document["results"], "results", base),
        _path(document["workspaces"], "workspaces", base),
        _repetitions(document["repetitions"], _accepted(runner)),
        fixtures,
        _arms(document["arms"], runner, base),
        harness,
        profile,
        pack,
        limit,
        _caps(fixtures) if limit is not None else (),
        service_tier,
    )
    _elements_fit(plan, runner)
    _plugins_fit(plan, runner)
    return plan


def _plugins_fit(plan: Plan, runner: ModuleType) -> None:
    """Refuse, before any cell starts, an arm's plugin on a harness that takes none, or a
    plugin folder run.py refuses (one outside the evals home's third-party clones)."""

    for arm in plan.arms:
        if not arm.plugin_dir:
            continue
        if plan.harness != "claude-code":
            raise PlanError(f"arm {arm.label}: plugin_dir needs harness claude-code")
        refusal = runner.plugin_dir_refusal(arm.plugin_dir)
        if refusal:
            raise PlanError(f"arm {arm.label}: {refusal}")


def suite(fixture: str) -> dict[str, Any]:
    """The fixture's suite.json, or an empty object where it has none."""

    path = FIXTURES / fixture / "suite.json"
    if not path.is_file():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        raise PlanError(f"{fixture}: suite.json unreadable: {problem}") from None
    return document if isinstance(document, dict) else {}


def _pack(pack: Any, known: set[str]) -> tuple[str, ...]:
    """The fixtures of a pack: a tier's, or the panel's, from each suite.json with a budget."""

    if pack not in PACKS:
        raise PlanError(f"pack is one of {', '.join(PACKS)}")
    chosen = tuple(
        name
        for name in sorted(known)
        if "references" in suite(name)
        and "budget" in suite(name)
        and (
            suite(name).get("panel") is True if pack == "panel" else suite(name).get("tier") == pack
        )
    )
    if not chosen:
        raise PlanError(f"no fixture's suite.json puts it in pack {pack}")
    return chosen


def _service_tier(value: Any, harness: str) -> str:
    if not isinstance(value, str) or (value and not SERVICE_TIER.fullmatch(value)):
        raise PlanError("service_tier is one lower-case word, such as priority")
    if value and harness != "codex":
        raise PlanError(f"service_tier is for codex; {harness} has no serving tier")
    return value


def _harness(harness: Any, runner: ModuleType) -> None:
    if not isinstance(harness, str) or not harness:
        raise PlanError("harness is a non-empty string")
    accepted = tuple(getattr(runner, "HARNESSES", RUNNABLE))
    if harness not in RUNNABLE or harness not in accepted:
        raise PlanError(
            f"harness {harness} cannot run yet: run.py runs {', '.join(accepted)}, and this loop "
            f"starts {', '.join(RUNNABLE)} only"
        )


def _spend_limit(value: Any) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value <= 0:
        raise PlanError("spend_limit is a positive number of input tokens")
    return value


def _caps(fixtures: tuple[str, ...]) -> tuple[tuple[str, int], ...]:
    """Each fixture's input cap, the worst case of one of its cells."""

    caps = []
    for fixture in fixtures:
        cap = (suite(fixture).get("budget") or {}).get("input_cap")
        if type(cap) is not int or cap <= 0:
            raise PlanError(
                f"spend_limit needs each fixture's budget.input_cap; {fixture} has none"
            )
        caps.append((fixture, cap))
    return tuple(caps)


def _accepted(runner: ModuleType) -> tuple[int, ...]:
    """The repetitions a plan may name: 1 to 10, as far as run.py accepts them."""

    offered = getattr(runner, "REPETITIONS", range(1, MAX_REPETITION + 1))
    return tuple(value for value in offered if 1 <= value <= MAX_REPETITION)


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


def _keeps(entries: Any) -> bool:
    """Whether any arm entry names `keep_skills`, which needs the runner's list of skills."""

    return any(isinstance(entry, dict) and "keep_skills" in entry for entry in entries)


def _arms(entries: Any, runner: ModuleType, base: Path) -> tuple[Arm, ...]:
    if not isinstance(entries, list) or not entries:
        raise PlanError("arms is a non-empty list")
    kinds = ("current", runner.NONE, getattr(runner, "FACTS_ONLY_NOSKILLS", "facts-only-noskills"))
    skills = tuple(runner.carried_skills(runner.REPO)) if _keeps(entries) else ()
    arms = tuple(_arm(entry, tuple(runner.ARMS), kinds, base, skills) for entry in entries)
    labels = [arm.label for arm in arms]
    twice = sorted({label for label in labels if labels.count(label) > 1})
    if twice:
        raise PlanError(f"duplicate label {', '.join(twice)}")
    return arms


def argv(plan: Plan, arm: Arm, repetition: int, fixture: str, out: Path) -> tuple[str, ...]:
    """The run.py call of one cell."""

    words = [sys.executable, "evals/run.py", "--harness", plan.harness, "--arm", arm.arm]
    for entry in arm.drop:
        words += ["--drop", entry]
    for entry in arm.add:
        words += ["--add", entry]
    if arm.edits:
        words += ["--edits", arm.edits]
    if arm.plugin_dir:
        words += ["--plugin-dir", arm.plugin_dir]
    if arm.keep_skills:
        words += ["--keep-skills", ",".join(arm.keep_skills)]
    words += [
        "--arm-label",
        arm.label,
        "--model",
        plan.model,
        "--effort",
        plan.effort,
        *(("--service-tier", plan.service_tier) if plan.service_tier else ()),
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
    """Start one run.py call, its stdout and stderr appended to `log`, and give its exit.

    The options after the script go in a file of their own beside the log, named at random,
    and run.py reads them from it (`@FILE`): the process title a call's `ps` can show then names
    no fixture and no arm. The file is removed when run.py exits."""

    log.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=".run-args-", dir=log.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as listing:
            listing.write("".join(f"{word}\n" for word in words[2:]))
        with open(log, "a", encoding="utf-8") as stream:
            return subprocess.run(
                [*words[:2], f"@{name}"],
                cwd=cwd,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            ).returncode
    finally:
        Path(name).unlink(missing_ok=True)


Runner = Callable[[tuple[str, ...], Path, Path], int]


def follow_up(directories: list[Path]) -> list[str]:
    joined = " ".join(shlex.quote(str(path)) for path in directories)
    return [f"python3 evals/run.py --summary {joined}", f"python3 evals/attribute.py {joined}"]


def spent(cell: Cell, cap: int) -> int:
    """The input tokens a cell that ran recorded: its session's, else its budget record's, else,
    where it recorded neither, its cap. Zero for a cell that has not run."""

    if not cell.out.exists():
        return 0
    total, recorded = 0, False
    for meta_path in cell.out.glob("*.meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        tokens, budget = meta.get("session_tokens"), meta.get("budget")
        if isinstance(tokens, dict) and type(tokens.get("input_tokens")) is int:
            total, recorded = total + tokens["input_tokens"], True
        elif isinstance(budget, dict) and type(budget.get("input")) is int:
            total, recorded = total + budget["input"], True
    return total if recorded else cap


def spent_so_far(plan: Plan, ordered: list[Cell]) -> int:
    return sum(spent(cell, plan.cap(cell.fixture)) for cell in ordered)


def over_limit(plan: Plan, ordered: list[Cell], cell: Cell) -> str:
    """Why the cell would pass the plan's spend limit, or an empty string."""

    if plan.spend_limit is None:
        return ""
    so_far, worst = spent_so_far(plan, ordered), plan.cap(cell.fixture)
    if so_far + worst <= plan.spend_limit:
        return ""
    return (
        f"spend limit {plan.spend_limit} input tokens: {so_far} recorded so far, and "
        f"{cell.arm.label} r{cell.repetition} {cell.fixture} could take up to {worst}"
    )


def record(plan: Plan) -> None:
    """Write what the plan ran with, harness and profile among it, beside its cells."""

    folder = plan.results / plan.name
    path = folder / "LOOP.json"
    if path.is_file():
        try:
            before = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            before = {}
        for key in ("harness", "profile", "model", "effort", "service_tier"):
            if before.get(key, "" if key == "service_tier" else None) != getattr(plan, key):
                raise PlanError(
                    f"{path} records {key} {before.get(key)!r}, the plan {getattr(plan, key)!r}; "
                    "name the plan anew"
                )
        recorded = {
            item.get("label"): tuple(item.get("keep_skills") or ())
            for item in before.get("arms") or ()
            if isinstance(item, dict)
        }
        for arm in plan.arms:
            if arm.label in recorded and recorded[arm.label] != arm.keep_skills:
                raise PlanError(
                    f"{path} records keep_skills {list(recorded[arm.label])} for arm "
                    f"{arm.label}, the plan {list(arm.keep_skills)}; name the plan anew"
                )
    folder.mkdir(parents=True, exist_ok=True)
    document = {
        "name": plan.name,
        "harness": plan.harness,
        "profile": plan.profile,
        "model": plan.model,
        "effort": plan.effort,
        "pack": plan.pack,
        "fixtures": list(plan.fixtures),
        "repetitions": list(plan.repetitions),
        "arms": [
            {key: value for key, value in arm._asdict().items() if key != "keep_skills" or value}
            for arm in plan.arms
        ],
        "spend_limit": plan.spend_limit,
        **({"service_tier": plan.service_tier} if plan.service_tier else {}),
    }
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def dry_run(ordered: list[Cell], states: list[str], plan: Plan | None = None) -> int:
    """Print each cell with its state and argv, and the counts; exit 1 where a cell blocks."""

    for n, (cell, found) in enumerate(zip(ordered, states, strict=True), start=1):
        print(f"{n:>4} {found:<6} {cell.arm.label} r{cell.repetition} {cell.fixture}")
        print(f"       {shlex.join(cell.argv)}")
    blocked = sum(found.startswith("blocked") for found in states)
    to_run = states.count("new")
    print(f"cells {len(ordered)}, done {states.count('done')}, to run {to_run}, blocked {blocked}")
    if plan is not None:
        print(f"harness {plan.harness}, profile {plan.profile or '(none)'}")
    if plan is not None and plan.spend_limit is not None:
        so_far = spent_so_far(plan, ordered)
        worst = sum(plan.cap(c.fixture) for c, f in zip(ordered, states, strict=True) if f == "new")
        print(
            f"spend limit {plan.spend_limit} input tokens: {so_far} recorded so far, "
            f"worst case of the cells to run {worst}"
        )
    return 1 if blocked else 0


def execute(
    ordered: list[Cell],
    states: list[str],
    runner: Runner,
    max_runs: int | None,
    preflight: int,
    plan: Plan | None = None,
) -> int:
    """Start each new cell in order, at most `max_runs` and within the plan's spend limit, and
    print what happened."""

    ran, failed, stopped = 0, 0, ""
    for cell, found in zip(ordered, states, strict=True):
        if found == "done":
            continue
        if max_runs is not None and ran >= max_runs:
            stopped = f"--max-runs {max_runs} reached"
            break
        over = over_limit(plan, ordered, cell) if plan is not None else ""
        if over:
            stopped = f"before a cell that could pass the {over}"
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
        return dry_run(ordered, states, plan)
    blocked = [found for found in states if found.startswith("blocked")]
    for found in blocked:
        sys.stderr.write(f"loop: stopped before starting anything: {found}\n")
    if blocked:
        return 1
    preflight = int(getattr(runner_module, "PREFLIGHT_EXIT", 3))
    try:
        record(plan)
    except PlanError as problem:
        sys.stderr.write(f"loop: refused, nothing started: {problem}\n")
        return REFUSED
    return execute(ordered, states, runner, args.max_runs, preflight, plan)


if __name__ == "__main__":
    raise SystemExit(main())
