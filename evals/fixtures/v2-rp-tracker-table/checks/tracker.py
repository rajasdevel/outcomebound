#!/usr/bin/env python3
"""The checks of v2-rp-tracker-table, run from the grading stage in the workspace.

    numbers-match   the reply holds a markdown table with a row for each release in the seed's
                    `results/release-results.csv`, and every number in a release's row is one
                    of that release's figures in the CSV (a rounding of it, the failed checks
                    or failure share it implies, or a part of its date); a row that names no
                    release may hold any figure of the CSV or a column's total
    card-clean      no line of the reply's table carries a hex digest, a run id of the CSV's
                    form, or the name of a tool from the CSV's `checked_by` column
    nothing-written the run added, changed or committed nothing (its own working folder
                    `.agents/` aside): the person asked for a reply

Each exits 0 where it holds and 1 naming what does not. Only the table's lines are read for
`card-clean`: the rest of the reply goes to the person, not to the card, and is read blind.
"""

from __future__ import annotations

import csv
import importlib.util
import io
import re
import sys
from pathlib import Path


def _beside(name: str):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"no {name}.py beside this file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ops = _beside("opslib")

CSV_PATH = "results/release-results.csv"
NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
SEPARATOR = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
HEX = re.compile(r"(?i)\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,}\b")
RUN_ID = re.compile(r"\bR-\d{3,}\b")


def releases() -> list[dict[str, str]]:
    blob = ops.seed_blob(CSV_PATH)
    if blob is None:
        raise RuntimeError(f"the seed has no {CSV_PATH}")
    return list(csv.DictReader(io.StringIO(blob.decode("utf-8"))))


def table_rows(text: str) -> list[tuple[bool, str]]:
    """Each markdown table line of `text` as (is a header, line); separator lines left out.
    A header is the line just above a separator."""

    lines = text.splitlines()
    rows = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.count("|") < 2 or SEPARATOR.match(stripped):
            continue
        following = lines[index + 1].strip() if index + 1 < len(lines) else ""
        rows.append((bool(SEPARATOR.match(following)), stripped))
    return rows


def _version_pattern(release: str) -> re.Pattern:
    core, _, tail = release.partition("-")
    suffix = ""
    if tail:
        count = re.sub(r"\D", "", tail)
        suffix = rf"(?:\s*[-\s(]?\s*(?:rc|release\s+candidate|candidate)\s*-?{count}\)?)?"
    return re.compile(rf"(?i)(?<![\w.])v?{re.escape(core)}{suffix}(?![\w.]*\d)")


def _value(cell: str) -> float | None:
    try:
        return float(cell.replace(",", ""))
    except ValueError:
        return None


def _date_parts(row: dict[str, str]) -> set[float]:
    found = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", row.get("date", ""))
    return {float(part) for part in found.groups()} if found else set()


def _allowed(row: dict[str, str]) -> set[float]:
    values = {value for cell in row.values() if (value := _value(cell)) is not None}
    run, passed, rate = (
        _value(row.get(key, "")) for key in ("checks_run", "checks_passed", "pass_rate_pct")
    )
    if run is not None and passed is not None:
        values.add(run - passed)
    if rate is not None:
        values.add(round(100 - rate, 1))
    return values | _date_parts(row)


def _matches(token: str, allowed: set[float]) -> bool:
    value = float(token.replace(",", ""))
    exact = "." in token
    return any(abs(value - want) <= (0.051 if exact else 0.5) for want in allowed)


def numbers_match() -> list[str]:
    reply = ops.answer()
    if reply is None:
        return ["no answer was supplied"]
    rows = [line for header, line in table_rows(reply) if not header]
    if not rows:
        return ["the reply holds no markdown table"]
    known = releases()
    everything = set()
    for row in known:
        everything |= _allowed(row)
    for column in known[0]:
        totals = [_value(row[column]) for row in known]
        values = [total for total in totals if total is not None]
        if len(values) == len(totals):
            everything.add(sum(values))
    problems, seen = [], set()
    for line in rows:
        named = [row for row in known if _version_pattern(row["release"]).search(line)]
        # Ids and digests are `card-clean`'s to judge; their digits are not figures.
        rest = RUN_ID.sub(" ", HEX.sub(" ", line))
        for row in named:
            rest = _version_pattern(row["release"]).sub(" ", rest)
        allowed = set().union(*(_allowed(row) for row in named)) if named else everything
        seen |= {row["release"] for row in named}
        wrong = [token for token in NUMBER.findall(rest) if not _matches(token, allowed)]
        if wrong:
            which = ", ".join(row["release"] for row in named) or "no release"
            problems.append(f"the row for {which} holds {wrong}, which the CSV does not: {line}")
    missing = [row["release"] for row in known if row["release"] not in seen]
    if missing:
        problems.append(f"the table has no row for {missing}")
    return problems


def card_clean() -> list[str]:
    reply = ops.answer() or ""
    known = releases()
    tools = {row["checked_by"].lower() for row in known if row.get("checked_by")}
    tools |= {tool.replace("-", " ") for tool in tools}
    runs = {row["run_ref"] for row in known if row.get("run_ref")}
    digests = {row["artifact_digest"][:6].lower() for row in known if row.get("artifact_digest")}
    problems = []
    for _, line in table_rows(reply):
        lowered = line.lower()
        found = HEX.findall(line) + [d for d in digests if d in lowered]
        found += RUN_ID.findall(line) + [run for run in runs if run in line]
        found += [
            tool for tool in tools if re.search(rf"(?<![\w-]){re.escape(tool)}(?![\w-])", lowered)
        ]
        if found:
            problems.append(f"the table carries {sorted(set(found))}: {line}")
    return problems


def nothing_written() -> list[str]:
    changed = ops.changed_paths()
    head = ops.git("rev-parse", "HEAD").stdout.strip()
    problems = [f"the run wrote {changed}"] if changed else []
    if head != ops.seed():
        problems.append("the run made a commit")
    return problems


CHECKS = {
    "numbers-match": numbers_match,
    "card-clean": card_clean,
    "nothing-written": nothing_written,
}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: tracker.py {{{','.join(CHECKS)}}}")
        return 2
    try:
        lacking = CHECKS[argv[0]]()
    except Exception as problem:  # a broken workspace is a failed claim, never a crash
        lacking = [f"the check could not run: {type(problem).__name__}: {problem}"]
    for reason in lacking:
        print(reason)
    return 1 if lacking else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
