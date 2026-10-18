"""`outcomebound brief open`: the decision briefs that have no recorded answer
(`docs/specs/decision-support/design.md`, `schemas/brief-open.schema.json`).

What this module decides: where it looks (the paths given, else `brief lookup`'s default roots);
which briefs are open (an id, case folded, with no well-formed `Decided:` line in any file read);
the order (newest source file first); when one id is two briefs (a collision); and what it prints.
Exits: 0 with a count; 1 a path it could not read; 2 a usage error.

What it does not decide: whether an answer is the person's or current, or that a brief the paths
did not reach is answered. It reads with `brief_lookup`'s readers, writes nothing and runs
nothing. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from outcomebound_tools import brief_lookup, textio

VERSION = 1
LIMITS = (
    "that an answer is the person's, or that a line is current",
    "that a brief the paths did not reach is answered or open",
    "that the date is when the brief was drawn: it is the source file's last change",
    "that a brief inside a review file is found",
)


def _date(source: str) -> str:
    try:
        return datetime.fromtimestamp(Path(source).stat().st_mtime).date().isoformat()
    except OSError:
        return ""


def _question(heading: str) -> str:
    return re.sub(r"\s+", " ", heading).casefold()


def _entry(brief: brief_lookup.Brief) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": brief.id,
        "question": brief.heading,
        "source": brief.source,
        "date": _date(brief.source),
    }
    if brief.line is not None:
        entry["line"] = brief.line
    if brief.why_now:
        entry["why_now"] = brief.why_now
    return entry


def _newest(entry: dict[str, Any]) -> tuple[Any, ...]:
    return (entry["date"], entry["source"], -entry.get("line", 0))


def split(
    briefs: Sequence[brief_lookup.Brief], answers: Sequence[brief_lookup.Answer]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The open briefs, newest first, and the ids that two different questions share."""

    answered = {a.id.casefold() for a in answers}
    by_id: dict[str, list[brief_lookup.Brief]] = {}
    for brief in briefs:
        if brief.id.casefold() not in answered:
            by_id.setdefault(brief.id.casefold(), []).append(brief)
    listed: list[dict[str, Any]] = []
    collisions: list[dict[str, Any]] = []
    for same in by_id.values():
        entries = sorted((_entry(b) for b in same), key=_newest, reverse=True)
        if len({_question(b.heading) for b in same}) > 1:
            collisions.append({"id": same[0].id, "briefs": entries})
        else:
            listed.append(entries[0])
    listed.sort(key=_newest, reverse=True)
    collisions.sort(key=lambda c: _newest(c["briefs"][0]), reverse=True)
    return listed, collisions


def find_open(roots: Sequence[Path]) -> dict[str, Any]:
    briefs, answers, _, unread, unreadable = brief_lookup.scan(roots)
    listed, collisions = split(briefs, answers)
    return {
        "version": VERSION,
        "searched": [str(root) for root in roots],
        "count": len(listed),
        "open": listed,
        "collisions": collisions,
        "not_read": sorted(unread),
        "unreadable": unreadable,
        "does_not_establish": list(LIMITS),
    }


def render_text(report: dict[str, Any]) -> str:
    see = textio.visible
    if report["unreadable"]:
        first = f"OPEN_UNREADABLE: {see(', '.join(report['unreadable']))}"
    else:
        first = f"{report['count']} open brief(s); {len(report['collisions'])} collision(s)"
    lines = [first]
    for e in report["open"]:
        where = see(e["source"]) + (f":{e['line']}" if "line" in e else "")
        waits = f" · waits: {see(e['why_now'])}" if "why_now" in e else ""
        lines.append(f"{see(e['id'])} · {see(e['question'])} ({where}, {e['date']}){waits}")
    for c in report["collisions"]:
        lines.append(f"COLLISION {see(c['id'])}: one id, different questions")
        for e in c["briefs"]:
            where = see(e["source"]) + (f":{e['line']}" if "line" in e else "")
            lines.append(f"  {see(e['question'])} ({where}, {e['date']})")
    lines += [f"not read: {see(path)}" for path in report["not_read"]]
    lines.append("Does not establish: " + "; ".join(report["does_not_establish"]) + ".")
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound brief open",
        description=(
            "List the decision briefs with no recorded answer, newest first: id, question, "
            "source and date, and what waits on it where the brief says. A brief is answered "
            "when a `Decided:` line of its id is found in any file read. One id on briefs with "
            "different questions is reported as a collision. Reads PATH files and folders, "
            "default .agents/work and .agents/handoffs. Writes nothing."
        ),
        epilog="Exits: 0 with a count; 1 a path it could not read; 2 a usage error.",
    )
    parser.add_argument("paths", nargs="*", metavar="PATH")
    parser.add_argument("--json", action="store_true", help="print one JSON object, not text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    options = _parser().parse_args(argv)
    roots = [Path(p) for p in options.paths] or brief_lookup.default_roots(Path.cwd())
    report = find_open(roots)
    if options.json:
        document = {k: v for k, v in report.items() if k != "unreadable"}
        document["not_read"] = sorted([*report["not_read"], *report["unreadable"]])
        sys.stdout.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_text(report))
    return 1 if report["unreadable"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
