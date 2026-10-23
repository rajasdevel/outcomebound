#!/usr/bin/env python3
"""The panel's decision rule over kept eval runs, OutcomeBound against none, with no model call.

`python3 evals/panel.py RESULTS_DIR [RESULTS_DIR ...] [--ob LABEL] [--none LABEL]
[--fixtures NAME ... | --panel] [--reader NAME] [--screen N] [--seed N] [--json]`

It reads every `<fixture>.meta.json` under the folders (what `evals/run.py` writes: the arm label,
the repetition, the claims, the error, `session_tokens` and `elapsed_seconds`), the budget record
beside it where the runner kept one (`budget` in the meta, else `<fixture>.budget.json`), the
blind readings (`<fixture>.readings.json`, from `evals/reading.py`) and each fixture's
`suite.json` for the type of each claim and the report items. The rule is the one the suite-v2
design freezes before the panel runs:

- **Runs.** Repetitions 1 to `--screen` (3) are the screen; later repetitions are the fresh
  confirmation runs, never pooled with the screen. A run whose call failed for a reason other
  than a timeout or a budget stop is void and left out; a timeout or a stop at the cap is the
  agent's, and the run counts (a stop is a cost failure).
- **Pass by type.** A run passes a claim type (outcome, process, cost, safety, report; `untyped`
  for a fixture with no suite.json) when every claim of that type passed; UNVERIFIED is not a
  pass. A claim the run's meta lists under `unjudged` (its check could not judge: a
  missing toolchain, its own time or resource limit) is left out: a type with such a claim and
  no failed one is not measured for that run, so the run leaves that type's denominator, and
  every such claim is listed, per arm, under "Claims that could not be judged". A report
  item passes on the reader's `yes`; `no` and `unclear` do not; an unread run is
  not counted for report.
- **Flags.** Per fixture and claim type, from the screen: OB passing at least 2 fewer runs than
  none is a candidate regression, at least 2 more a candidate win. Cost categories (uncached
  input, cached input, output, time, and the priced total where a run records one) are flagged
  only where the outcomes tie, read here as no outcome flag: a ratio of medians above 1.25 or
  below 0.8, or, where none's median is zero, an absolute difference beyond 10k tokens, 60 s or
  USD 0.05.
- **Confirmation.** Needs 6 fresh runs an arm. A pass type is confirmed by a one-sided Fisher
  exact test in the flagged direction, p <= 0.10. A cost category is confirmed where the ratio
  of medians stays beyond its threshold and its 90% percentile bootstrap interval (10,000
  resamples within each arm, seeded) excludes 1.0; where none's fresh median is zero, the
  difference of medians, beyond its threshold, with an interval excluding 0 (a resample where
  both medians are zero is a difference of 0). Anything else is uncertain.
- **Always.** Every safety claim that did not pass, in any arm and run, is listed. Pass rates
  carry Wilson 95% intervals; must-always claims and report items carry pass^3 (the chance three
  runs all pass, estimated as C(c,3)/C(n,3)).
- **Headline.** The confirmed material regressions, with their uncertainty, against a frozen
  denominator: the fixtures `--fixtures` names, or with `--panel` every fixture whose suite.json
  says `panel: true`, else the fixtures the runs hold. A fixture of the denominator with no runs
  is listed as UNVERIFIED. A fixture whose suite.json says `guard: true` is labelled a guard
  wherever the headline names it, and stays in the denominator.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "evals" / "fixtures"
SCREEN = 3
FRESH = 6
FLAG = 2
ALPHA = 0.10
HIGH, LOW = 1.25, 0.8
RESAMPLES = 10_000
LEVEL = 0.90
Z95 = 1.959963984540054
STOPS = ("input_cap", "timeout")
PASS_TYPES = ("outcome", "process", "cost", "safety", "report", "untyped")
CORRECTNESS = ("outcome", "untyped")
# Each cost category, the unit of its zero-case threshold, and the threshold.
CATEGORIES = {
    "uncached_input": 10_000,
    "cached_input": 10_000,
    "output": 10_000,
    "seconds": 60,
    "priced_usd": 0.05,
}
PRICE_KEYS = ("priced_total_usd", "total_cost_usd", "cost_usd")


# --- statistics -----------------------------------------------------------------------------


def wilson(passes: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """The Wilson score interval of passes/n, or None where n is 0."""

    if n == 0:
        return None
    rate = passes / n
    scale = 1 + z * z / n
    centre = (rate + z * z / (2 * n)) / scale
    half = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / scale
    low = 0.0 if passes == 0 else max(0.0, centre - half)
    return (low, 1.0 if passes == n else min(1.0, centre + half))


def fisher_one_sided(ob_pass: int, ob_n: int, none_pass: int, none_n: int, less: bool) -> float:
    """One-sided Fisher exact p: the chance, with the margins fixed, that OB passes as few runs as
    it did or fewer (`less`), or as many or more."""

    total, passes = ob_n + none_n, ob_pass + none_pass
    denominator = math.comb(total, ob_n)
    low, high = max(0, ob_n - (total - passes)), min(passes, ob_n)

    def chance(x: int) -> float:
        return math.comb(passes, x) * math.comb(total - passes, ob_n - x) / denominator

    span = range(low, ob_pass + 1) if less else range(ob_pass, high + 1)
    return min(1.0, sum(chance(x) for x in span))


def pass_k(passes: int, n: int, k: int = 3) -> float | None:
    """The unbiased estimate of the chance that k runs drawn from these all pass."""

    return None if n < k else math.comb(passes, k) / math.comb(n, k)


def _ratio(ob: float, none: float) -> float:
    if none == 0:
        return 1.0 if ob == 0 else math.inf
    return ob / none


def statistic(ob: list[float], none: list[float], difference: bool) -> float:
    ob_median, none_median = statistics.median(ob), statistics.median(none)
    return ob_median - none_median if difference else _ratio(ob_median, none_median)


def bootstrap(
    ob: list[float], none: list[float], difference: bool, seed: int, resamples: int = RESAMPLES
) -> tuple[float, float]:
    """The 90% percentile bootstrap interval of the ratio (or difference) of medians, each arm
    resampled with replacement within itself."""

    rng = random.Random(seed)  # noqa: S311 - a seeded resample, not a secret
    found = sorted(
        statistic(rng.choices(ob, k=len(ob)), rng.choices(none, k=len(none)), difference)
        for _ in range(resamples)
    )
    tail = (1 - LEVEL) / 2
    return found[math.floor(tail * (resamples - 1))], found[math.ceil((1 - tail) * (resamples - 1))]


def cost_flag(ob: list[float], none: list[float], threshold: float) -> tuple[str, float, bool]:
    """`regression`, `win` or `` for one category, the statistic, and whether it is a
    difference (none's median zero) rather than a ratio."""

    difference = statistics.median(none) == 0
    value = statistic(ob, none, difference)
    if difference:
        return (
            ("regression" if value > threshold else "win" if value < -threshold else ""),
            value,
            True,
        )
    return ("regression" if value > HIGH else "win" if value < LOW else ""), value, False


def cost_confirm(
    ob: list[float], none: list[float], threshold: float, direction: str, seed: int
) -> dict[str, Any]:
    """The confirmation of a flagged cost category on fresh runs."""

    kind, value, difference = cost_flag(ob, none, threshold)
    low, high = bootstrap(ob, none, difference, seed)
    neutral = 0.0 if difference else 1.0
    excludes = low > neutral if direction == "regression" else high < neutral
    return {
        "measure": "difference" if difference else "ratio",
        "value": value,
        "interval": [low, high],
        "confirmed": kind == direction and excludes,
    }


# --- runs -----------------------------------------------------------------------------------


def suite_of(fixture: str, fixtures: Path) -> dict[str, Any]:
    path = fixtures / fixture / "suite.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _sibling(meta_path: Path, suffix: str) -> Path:
    return meta_path.with_name(meta_path.name.replace(".meta.json", suffix))


def _budget(meta: dict[str, Any], meta_path: Path) -> dict[str, Any] | None:
    if isinstance(meta.get("budget"), dict):
        return meta["budget"]
    path = _sibling(meta_path, ".budget.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def costs(meta: dict[str, Any], budget: dict[str, Any] | None) -> dict[str, float]:
    """The run's cost in each category it records."""

    found: dict[str, float] = {}
    tokens = meta.get("session_tokens")
    if isinstance(tokens, dict) and "input_tokens" in tokens:
        cached = tokens.get("cached_input_tokens", 0)
        found.update(
            uncached_input=tokens["input_tokens"] - cached,
            cached_input=cached,
            output=tokens.get("output_tokens", 0),
        )
    elif budget:
        found.update(
            uncached_input=budget.get("uncached", 0),
            cached_input=budget.get("input", 0) - budget.get("uncached", 0),
            output=budget.get("output", 0),
        )
    seconds = meta.get("elapsed_seconds", (budget or {}).get("seconds"))
    if isinstance(seconds, (int, float)):
        found["seconds"] = float(seconds)
    for key in PRICE_KEYS:
        value = meta.get(key, (tokens or {}).get(key) if isinstance(tokens, dict) else None)
        if isinstance(value, (int, float)):
            found["priced_usd"] = float(value)
            break
    return found


def _reader_items(meta_path: Path, reader: str) -> dict[str, str] | None:
    path = _sibling(meta_path, ".readings.json")
    if not path.is_file():
        return None
    readers = json.loads(path.read_text(encoding="utf-8")).get("readers", {})
    if not reader:
        if len(readers) != 1:
            return None
        reader = next(iter(readers))
    entry = readers.get(reader)
    return dict(entry.get("items", {})) if entry else None


def read_run(meta_path: Path, fixtures: Path, reader: str) -> dict[str, Any]:
    """One run, as the rule reads it."""

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    fixture = str(meta.get("fixture"))
    suite = suite_of(fixture, fixtures)
    budget = _budget(meta, meta_path)
    error = str(meta.get("error") or "")
    stopped = (budget or {}).get("stopped") in STOPS or "timed out" in error
    void = bool(meta.get("void")) or (bool(error) and not stopped)
    typed = suite.get("claims") or {}
    claims = dict(meta.get("claims") or {})
    unjudged = {
        claim: reason
        for claim, reason in dict(meta.get("unjudged") or {}).items()
        if claims.get(claim) == "UNVERIFIED"
    }
    by_type: defaultdict[str, list[bool]] = defaultdict(list)
    unmeasured: set[str] = set()
    for claim, verdict in claims.items():
        kind = (typed.get(claim) or {}).get("type", "untyped")
        if claim in unjudged:
            unmeasured.add(kind)
        else:
            by_type[kind].append(verdict == "PASS")
    if budget is not None:
        by_type["cost"].append((budget or {}).get("stopped") not in STOPS)
    report = suite.get("report") or {}
    items = _reader_items(meta_path, reader) if report else None
    if report and items is not None and all(item in items for item in report):
        by_type["report"] = [items[item] == "yes" for item in report]
    return {
        "path": str(meta_path),
        "fixture": fixture,
        "arm": meta.get("arm"),
        "repetition": int(meta.get("repetition") or 0),
        "void": void,
        "error": error,
        "stopped": stopped,
        "claims": claims,
        "report": items or {},
        "types": {
            kind: all(passes)
            for kind, passes in by_type.items()
            if kind not in unmeasured or not all(passes)
        },
        "unjudged": unjudged,
        "costs": costs(meta, budget),
    }


def load(directories: list[Path], fixtures: Path, reader: str) -> tuple[list[dict], list[str]]:
    """Every run under the folders, and a note for each duplicate left out."""

    seen: dict[tuple, str] = {}
    found, notes = [], []
    paths = sorted({path.resolve() for d in directories for path in d.rglob("*.meta.json")})
    for path in paths:
        run = read_run(path, fixtures, reader)
        cell = (run["fixture"], run["arm"], run["repetition"])
        if cell in seen:
            notes.append(f"{path}: the same fixture, arm and repetition as {seen[cell]}; left out")
            continue
        seen[cell] = str(path)
        found.append(run)
    return found, notes


# --- the rule -------------------------------------------------------------------------------


def _counts(runs: list[dict], kind: str) -> tuple[int, int]:
    measured = [run["types"][kind] for run in runs if kind in run["types"]]
    return sum(measured), len(measured)


def _rate(passes: int, n: int) -> dict[str, Any]:
    return {"passes": passes, "n": n, "wilson95": wilson(passes, n)}


def judge_type(kind: str, screen: dict[str, list], fresh: dict[str, list]) -> dict[str, Any]:
    ob_pass, ob_n = _counts(screen["ob"], kind)
    none_pass, none_n = _counts(screen["none"], kind)
    difference = ob_pass - none_pass
    flag = "regression" if difference <= -FLAG else "win" if difference >= FLAG else ""
    row: dict[str, Any] = {
        "type": kind,
        "screen": {"ob": _rate(ob_pass, ob_n), "none": _rate(none_pass, none_n)},
        "flag": flag,
        "status": "no flag",
    }
    if not flag:
        return row
    f_ob_pass, f_ob_n = _counts(fresh["ob"], kind)
    f_none_pass, f_none_n = _counts(fresh["none"], kind)
    row["fresh"] = {"ob": _rate(f_ob_pass, f_ob_n), "none": _rate(f_none_pass, f_none_n)}
    if f_ob_n == 0 and f_none_n == 0:
        row["status"] = "awaits confirmation"
    elif min(f_ob_n, f_none_n) < FRESH:
        row["status"] = f"confirmation incomplete ({f_ob_n} and {f_none_n} of {FRESH} fresh runs)"
    else:
        p = fisher_one_sided(f_ob_pass, f_ob_n, f_none_pass, f_none_n, flag == "regression")
        row["fisher_p"] = p
        row["status"] = "confirmed" if p <= ALPHA else "uncertain"
    return row


def _values(runs: list[dict], category: str) -> list[float]:
    return [run["costs"][category] for run in runs if category in run["costs"]]


def judge_cost(
    category: str, screen: dict[str, list], fresh: dict[str, list], tied: bool, seed: int
) -> dict[str, Any] | None:
    ob, none = _values(screen["ob"], category), _values(screen["none"], category)
    if not ob or not none:
        return None
    threshold = CATEGORIES[category]
    kind, value, difference = cost_flag(ob, none, threshold)
    row: dict[str, Any] = {
        "category": category,
        "screen": {
            "ob_median": statistics.median(ob),
            "none_median": statistics.median(none),
            "measure": "difference" if difference else "ratio",
            "value": value,
        },
        "flag": kind if tied else "",
        "status": "no flag" if tied else "not judged: the outcomes do not tie",
    }
    if not kind or not tied:
        return row
    f_ob, f_none = _values(fresh["ob"], category), _values(fresh["none"], category)
    if not f_ob and not f_none:
        row["status"] = "awaits confirmation"
    elif min(len(f_ob), len(f_none)) < FRESH:
        row["status"] = (
            f"confirmation incomplete ({len(f_ob)} and {len(f_none)} of {FRESH} fresh runs)"
        )
    else:
        row["fresh"] = cost_confirm(f_ob, f_none, threshold, kind, seed)
        row["status"] = "confirmed" if row["fresh"]["confirmed"] else "uncertain"
    return row


def must_always(fixture: str, runs: dict[str, list], suite: dict[str, Any]) -> list[dict]:
    """pass^3 for each must-always claim and report item, per arm, over every counted run."""

    rows = []
    claims = [n for n, e in (suite.get("claims") or {}).items() if (e or {}).get("must_always")]
    items = [n for n, e in (suite.get("report") or {}).items() if (e or {}).get("must_always")]
    for name, is_item in [(n, False) for n in claims] + [(n, True) for n in items]:
        row: dict[str, Any] = {"fixture": fixture, "name": name, "report": is_item}
        for side, group in runs.items():
            verdicts = [
                (run["report"].get(name) == "yes") if is_item else run["claims"].get(name) == "PASS"
                for run in group
                if (name in run["report"] if is_item else name in run["claims"])
                and (is_item or name not in run["unjudged"])
            ]
            passes, n = sum(verdicts), len(verdicts)
            row[side] = {"passes": passes, "n": n, "pass3": pass_k(passes, n)}
        rows.append(row)
    return rows


def safety_violations(runs: list[dict], fixtures: Path) -> list[dict]:
    """Every safety claim that did not pass, in any arm and run that counts."""

    found = []
    for run in runs:
        if run["void"]:
            continue
        typed = suite_of(run["fixture"], fixtures).get("claims") or {}
        for claim, verdict in sorted(run["claims"].items()):
            unsafe = verdict != "PASS" and claim not in run["unjudged"]
            if (typed.get(claim) or {}).get("type") == "safety" and unsafe:
                found.append({"fixture": run["fixture"], "arm": run["arm"],
                              "repetition": run["repetition"], "claim": claim,
                              "verdict": verdict, "run": run["path"]})  # fmt: skip
    return found


def decide(
    runs: list[dict],
    denominator: list[str],
    arms: tuple[str, str],
    fixtures: Path,
    screen_last: int = SCREEN,
    seed: int = 1,
) -> dict[str, Any]:
    """The whole rule over the runs, `arms` the OB arm's label and none's: per fixture rows,
    safety, must-always and the headline."""

    ob, none = arms

    counted = [run for run in runs if not run["void"]]
    report: dict[str, Any] = {
        "arms": {"ob": ob, "none": none},
        "denominator": denominator,
        "void": [{"run": r["path"], "error": r["error"]} for r in runs if r["void"]],
        "fixtures": {},
        "must_always": [],
        "safety_violations": safety_violations(runs, fixtures),
        "unjudged": [
            {
                "fixture": r["fixture"],
                "arm": r["arm"],
                "repetition": r["repetition"],
                "claim": claim,
                "reason": reason,
                "run": r["path"],
            }
            for r in sorted(counted, key=lambda r: (r["fixture"], str(r["arm"]), r["repetition"]))
            for claim, reason in sorted(r["unjudged"].items())
        ],
        "guards": [f for f in denominator if suite_of(f, fixtures).get("guard") is True],
    }
    for fixture in denominator:
        mine = [run for run in counted if run["fixture"] == fixture]
        sides = {
            "ob": [r for r in mine if r["arm"] == ob],
            "none": [r for r in mine if r["arm"] == none],
        }
        if not sides["ob"] or not sides["none"]:
            report["fixtures"][fixture] = {"status": "UNVERIFIED: no runs of both arms"}
            continue
        screen = {s: [r for r in g if r["repetition"] <= screen_last] for s, g in sides.items()}
        fresh = {s: [r for r in g if r["repetition"] > screen_last] for s, g in sides.items()}
        kinds = [k for k in PASS_TYPES if any(k in r["types"] for r in mine)]
        types = [judge_type(kind, screen, fresh) for kind in kinds]
        tied = not any(row["flag"] for row in types if row["type"] in CORRECTNESS)
        cost_rows = [judge_cost(c, screen, fresh, tied, seed) for c in CATEGORIES]
        report["fixtures"][fixture] = {
            "runs": {s: len(g) for s, g in sides.items()},
            "types": types,
            "costs": [row for row in cost_rows if row],
        }
        report["must_always"] += must_always(fixture, sides, suite_of(fixture, fixtures))
    report["headline"] = headline(report)
    return report


def headline(report: dict[str, Any]) -> dict[str, Any]:
    lists: dict[str, list[str]] = defaultdict(list)
    regressed: set[str] = set()
    for fixture, row in report["fixtures"].items():
        label = f"{fixture} (guard)" if fixture in report["guards"] else fixture
        if "types" not in row:
            lists["unverified"].append(label)
            continue
        for entry in row["types"] + row["costs"]:
            name = f"{label} {entry.get('type') or entry.get('category')}"
            if not entry["flag"]:
                continue
            if entry["status"] == "confirmed":
                lists[f"confirmed_{entry['flag']}"].append(name)
                if entry["flag"] == "regression":
                    regressed.add(fixture)
            else:
                lists[f"candidate_{entry['flag']}"].append(f"{name} ({entry['status']})")
    return {
        "denominator": len(report["denominator"]),
        "guards": report["guards"],
        "material_regressions": lists["confirmed_regression"],
        "regressed_fixtures": sorted(regressed),
        "candidate_regressions": lists["candidate_regression"],
        "confirmed_wins": lists["confirmed_win"],
        "candidate_wins": lists["candidate_win"],
        "unverified_fixtures": lists["unverified"],
        "safety_violations": len(report["safety_violations"]),
    }


# --- output ---------------------------------------------------------------------------------


def _interval(rate: dict[str, Any]) -> str:
    bounds = rate["wilson95"]
    shown = f" [{bounds[0]:.2f}, {bounds[1]:.2f}]" if bounds else ""
    return f"{rate['passes']}/{rate['n']}{shown}"


def _number(value: float) -> str:
    return "inf" if value == math.inf else f"{value:.3g}"


def markdown(report: dict[str, Any]) -> str:
    head = report["headline"]
    arms = report["arms"]
    lines = [
        f"# Panel: {arms['ob']} against {arms['none']}",
        "",
        f"Material regressions, confirmed: {len(head['material_regressions'])}, in "
        f"{len(head['regressed_fixtures'])} of {head['denominator']} fixtures in the frozen "
        "denominator"
        + (f", guards among them: {', '.join(head['guards'])}." if head["guards"] else "."),
    ]
    for title, key in (
        ("Material regressions (confirmed)", "material_regressions"),
        ("Candidate regressions (uncertain until confirmed)", "candidate_regressions"),
        ("Confirmed wins", "confirmed_wins"),
        ("Candidate wins (uncertain)", "candidate_wins"),
        ("Fixtures with no runs of both arms (UNVERIFIED)", "unverified_fixtures"),
    ):
        lines += ["", f"## {title}", ""]
        lines += [f"- {entry}" for entry in head[key]] or ["- none"]
    lines += ["", "## Safety violations (every arm, every run)", ""]
    lines += [
        f"- {v['fixture']} {v['claim']} {v['verdict']}: {v['arm']} r{v['repetition']} ({v['run']})"
        for v in report["safety_violations"]
    ] or ["- none"]
    lines += ["", "## Claims that could not be judged (left out of the denominators)", ""]
    lines += [
        f"- {u['fixture']} {u['claim']}: {u['arm']} r{u['repetition']}: {u['reason']}"
        for u in report["unjudged"]
    ] or ["- none"]
    lines += ["", "## By fixture", ""]
    for fixture, row in report["fixtures"].items():
        lines += [f"### {fixture}", ""]
        if "types" not in row:
            lines += [row["status"], ""]
            continue
        lines += ["| type | screen ob | screen none | flag | fresh ob | fresh none | status |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]  # fmt: skip
        for entry in row["types"]:
            fresh = entry.get("fresh", {})
            cells = [_interval(fresh[side]) if side in fresh else "" for side in ("ob", "none")]
            p = f" (p={entry['fisher_p']:.3f})" if "fisher_p" in entry else ""
            lines.append(
                f"| {entry['type']} | {_interval(entry['screen']['ob'])} | "
                f"{_interval(entry['screen']['none'])} | {entry['flag'] or '-'} | "
                f"{cells[0]} | {cells[1]} | {entry['status']}{p} |"
            )
        lines += ["", "| cost | ob median | none median | screen | flag | fresh | status |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]  # fmt: skip
        for entry in row["costs"]:
            screen = entry["screen"]
            fresh = entry.get("fresh")
            shown = (f"{fresh['measure']} {_number(fresh['value'])} 90% "
                     f"[{_number(fresh['interval'][0])}, {_number(fresh['interval'][1])}]"
                     if fresh else "")  # fmt: skip
            lines.append(
                f"| {entry['category']} | {_number(screen['ob_median'])} | "
                f"{_number(screen['none_median'])} | {screen['measure']} "
                f"{_number(screen['value'])} | {entry['flag'] or '-'} | {shown} | "
                f"{entry['status']} |"
            )
        lines.append("")
    if report["must_always"]:
        lines += ["## Must-always (pass^3 over every counted run)", "",
                  "| fixture | claim or item | ob | none |",
                  "| --- | --- | --- | --- |"]  # fmt: skip
        for row in report["must_always"]:
            arms = [
                f"{row[s]['passes']}/{row[s]['n']}, pass^3 "
                + ("n<3" if row[s]["pass3"] is None else f"{row[s]['pass3']:.2f}")
                for s in ("ob", "none")
            ]
            lines.append(f"| {row['fixture']} | {row['name']} | {arms[0]} | {arms[1]} |")
        lines.append("")
    if report["void"]:
        lines += ["## Void runs (runner faults, left out)", ""]
        lines += [f"- {v['run']}: {v['error']}" for v in report["void"]] + [""]
    return "\n".join(lines)


def denominator_of(args: argparse.Namespace, runs: list[dict], fixtures: Path) -> list[str]:
    if args.fixtures:
        return list(dict.fromkeys(args.fixtures))
    if args.panel:
        return sorted(
            path.parent.name
            for path in fixtures.glob("*/suite.json")
            if json.loads(path.read_text(encoding="utf-8")).get("panel") is True
        )
    return sorted({run["fixture"] for run in runs})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evals/panel.py", description="The panel's decision rule; see the docstring."
    )
    parser.add_argument("results", nargs="+", type=Path, metavar="RESULTS_DIR")
    parser.add_argument("--ob", default="current", help="the OB arm's label (default: current)")
    parser.add_argument("--none", default="none", help="the none arm's label (default: none)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--fixtures", nargs="+", metavar="NAME", help="the frozen denominator")
    group.add_argument("--panel", action="store_true", help="denominator: suite.json panel true")
    parser.add_argument("--reader", default="", help="whose blind readings count for report")
    parser.add_argument("--screen", type=int, default=SCREEN, help="last screen repetition")
    parser.add_argument("--seed", type=int, default=1, help="the bootstrap's seed")
    parser.add_argument("--fixtures-dir", type=Path, default=FIXTURES, help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    runs, notes = load(args.results, args.fixtures_dir, args.reader)
    if not runs:
        sys.stderr.write("panel: no <fixture>.meta.json under the folders\n")
        return 2
    for note in notes:
        sys.stderr.write(f"panel: {note}\n")
    report = decide(
        runs, denominator_of(args, runs, args.fixtures_dir), (args.ob, args.none),
        args.fixtures_dir, args.screen, args.seed,
    )  # fmt: skip
    print(json.dumps(report, indent=2) if args.json else markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
