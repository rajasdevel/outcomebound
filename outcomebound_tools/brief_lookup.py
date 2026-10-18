"""`outcomebound brief lookup`: a decision brief by id or words, and the answer recorded for it
(`docs/specs/decision-support/design.md`, `schemas/brief-lookup.schema.json`).

What this module decides: where it looks (`--in` roots, else `.agents/work` and `.agents/handoffs`
of the current folder and of the main checkout of its worktree); which briefs match (every term is
the brief's id, whole, or is found in its heading, case folded); what an answer is (one `Decided:`
line of the form the design defines); and what it prints (each match with its source and every
answer recorded for its id, or UNANSWERED). Exits: 0 a match; 1 none, or a root it could not read;
2 a usage error.

What it does not decide: whether an answer is the person's, whether it is current, or whether a
brief it did not reach is unanswered. It reads and writes no store of its own; it writes nothing.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from outcomebound_tools import home, review_check, schemacheck, size, textio, walk

VERSION = 1
MAX_BYTES = 1024 * 1024
DEPTH = 4
DEFAULT_ROOTS = (".agents/work", ".agents/handoffs")
LIMITS = (
    "that an answer is the person's, or that a line is current",
    "that a Decided line of an id answers this brief and not another that took the same id in "
    "another folder",
    "that a brief the roots did not reach is unanswered",
    "that a brief inside a review file is found",
)
_ID = r"[A-Za-z][A-Za-z0-9-]*"
_HEADING = re.compile(rf"###[ \t]+({_ID})(?: · | \| )(\S.*?)[ \t]*")
_DECIDED = re.compile(r"[ \t]*(?:(?:[-*+]|\d{1,9}[.)]|>)[ \t]+)*(?:\*\*)?Decided:(?:\*\*)?(.*)")
_WAITING = re.compile(r"[ \t]*(?:⏳|\[wait\])[ \t]+Waiting on this:[ \t]*(\S.*?)[ \t]*")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_OPEN, _CLOSE = '"“', '"”'


@dataclass(frozen=True)
class Answer:
    id: str
    source: str
    line: int
    way: str
    who: str
    date: str
    words: str


@dataclass(frozen=True)
class Brief:
    id: str
    heading: str
    source: str
    line: int | None
    why_now: str = ""


def _answer(rest: str, source: str, number: int) -> Answer | None:
    """The answer a `Decided:` line holds, or None where its form is not the design's."""

    rest = rest.strip()
    sep = " · " if " · " in rest else " | "
    parts = rest.split(sep, 4)
    if len(parts) != 5:
        return None
    brief_id, way, who, when, quoted = (part.strip() for part in parts)
    if not re.fullmatch(_ID, brief_id) or not way or not who or not _DATE.fullmatch(when):
        return None
    try:
        date.fromisoformat(when)
    except ValueError:
        return None
    if len(quoted) < 2 or quoted[0] not in _OPEN or quoted[-1] not in _CLOSE:
        return None
    return Answer(brief_id, source, number, way, who, when, quoted[1:-1])


def _markdown(
    text: str, source: str
) -> tuple[list[Brief], list[Answer], list[tuple[str, int, str]]]:
    briefs: list[Brief] = []
    answers: list[Answer] = []
    malformed: list[tuple[str, int, str]] = []
    lines = review_check._lines(text)
    for index, (number, line) in enumerate(lines):
        decided = _DECIDED.fullmatch(line)
        if decided:
            answer = _answer(decided.group(1), source, number)
            if answer:
                answers.append(answer)
            else:
                malformed.append((source, number, line.strip()))
            continue
        heading = _HEADING.fullmatch(line)
        if not heading:
            continue
        finding = False
        waiting = ""
        for _, after in lines[index + 1 :]:
            if after.lstrip().startswith("#"):
                break
            if review_check._DISPOSITION.fullmatch(after):
                finding = True
                break
            if not waiting and (held := _WAITING.fullmatch(after)):
                waiting = held.group(1)
        if not finding:
            briefs.append(Brief(heading.group(1), heading.group(2), source, number, waiting))
    return briefs, answers, malformed


def _json(text: str, source: str, schema: Any) -> tuple[list[Brief], str | None]:
    """The briefs of a briefs document; a defect where it does not fit the schema; nothing for a
    JSON file that is no briefs document."""

    try:
        document = json.loads(text)
    except ValueError:
        return [], None
    if not isinstance(document, dict) or not isinstance(document.get("briefs"), list):
        return [], None
    defects = schemacheck.validate(document, schema)
    if defects:
        return [], defects[0]
    return [
        Brief(b["id"], b["heading"], source, None, b.get("why_now", "")) for b in document["briefs"]
    ], None


def _files(root: Path, unread: list[str]) -> list[Path]:
    if root.is_file():
        return [root]
    found: list[Path] = []
    for entered in walk.folders(root, depth=DEPTH):
        depth = 0 if entered.relative == "." else len(Path(entered.relative).parts)
        if depth >= DEPTH:
            continue
        for name in entered.files:
            if not name.endswith((".md", ".json")):
                continue
            path = entered.path / name
            try:
                big = path.is_symlink() or path.stat().st_size > MAX_BYTES
            except OSError:
                big = True
            if big:
                unread.append(str(path))
            else:
                found.append(path)
    return sorted(found)


def main_checkout(here: Path) -> Path | None:
    """The main checkout of the worktree `here` is in, or None where `here` is it or Git does not
    say."""

    try:
        common = size._git_ok(here, "rev-parse", "--path-format=absolute", "--git-common-dir")
        parent = Path(common.decode("utf-8", "replace").strip()).parent
    except (size.SizeError, OSError):
        return None
    return parent if parent.name and parent.resolve() != here.resolve() else None


def default_roots(here: Path) -> list[Path]:
    roots = [here / name for name in DEFAULT_ROOTS]
    main = main_checkout(here)
    if main is not None:
        roots += [main / name for name in DEFAULT_ROOTS]
    return [root for root in roots if root.exists()]


def scan(
    roots: Sequence[Path],
) -> tuple[list[Brief], list[Answer], list[Any], list[str], list[str]]:
    """Every brief and answer under `roots`, the malformed `Decided:` lines, the paths not read
    and the roots that do not exist."""

    schema = json.loads((home.ROOT / "schemas" / "decision-briefs.schema.json").read_text("utf-8"))
    briefs: list[Brief] = []
    answers: list[Answer] = []
    malformed: list[Any] = []
    unread: list[str] = []
    unreadable: list[str] = []
    for root in roots:
        if not root.exists():
            unreadable.append(str(root))
            continue
        for path in _files(root, unread):
            try:
                text = textio.read_text(path)
            except (OSError, UnicodeDecodeError):
                unread.append(str(path))
                continue
            if path.suffix == ".json":
                found, defect = _json(text, str(path), schema)
                briefs += found
                if defect:
                    unread.append(f"{path}: {defect}")
            else:
                found, said, bad = _markdown(text, str(path))
                briefs += found
                answers += said
                malformed += bad
    return briefs, answers, malformed, unread, unreadable


def search(terms: Sequence[str], roots: Sequence[Path]) -> dict[str, Any]:
    briefs, answers, malformed, unread, unreadable = scan(roots)
    wanted = [term.casefold() for term in terms]
    matches = []
    for brief in briefs:
        folded = brief.heading.casefold()
        if all(t == brief.id.casefold() or t in folded for t in wanted):
            matches.append(_match(brief.id, brief.heading, brief.source, brief.line, answers))
    seen = {brief.id.casefold() for brief in briefs}
    for answer_id in sorted({a.id for a in answers if a.id.casefold() not in seen}):
        if all(t == answer_id.casefold() for t in wanted):
            first = next(a for a in answers if a.id == answer_id)
            matches.append(_match(answer_id, None, first.source, first.line, answers))
    names = [m["id"].casefold() for m in matches] + wanted
    return {
        "version": VERSION,
        "terms": list(terms),
        "searched": [str(root) for root in roots],
        "matches": matches,
        "malformed": [
            {"source": s, "line": n, "text": t}
            for s, n, t in malformed
            if any(name in t.casefold() for name in names)
        ],
        "not_read": sorted(unread),
        "unreadable": unreadable,
        "does_not_establish": list(LIMITS),
    }


def _match(
    brief_id: str, heading: str | None, source: str, line: int | None, answers: Sequence[Answer]
) -> dict[str, Any]:
    mine = sorted(
        (a for a in answers if a.id.casefold() == brief_id.casefold()),
        key=lambda a: (a.date, a.source, a.line),
    )
    match: dict[str, Any] = {
        "id": brief_id,
        "source": source,
        "status": ("BRIEF_NOT_FOUND" if heading is None else "ANSWERED" if mine else "UNANSWERED"),
        "answers": [
            {
                "source": a.source,
                "line": a.line,
                "way": a.way,
                "who": a.who,
                "date": a.date,
                "words": a.words,
            }
            for a in mine
        ],
    }
    if heading is not None:
        match["heading"] = heading
    if line is not None:
        match["line"] = line
    return match


def render_text(report: dict[str, Any]) -> str:
    see = textio.visible
    roots = ", ".join(map(see, report["searched"])) or "none"
    if report["unreadable"]:
        first = f"LOOKUP_UNREADABLE: {see(', '.join(report['unreadable']))}"
    else:
        first = f"{len(report['matches'])} match(es); searched {roots}"
    lines = [first]
    for m in report["matches"]:
        where = see(m["source"]) + (f":{m['line']}" if "line" in m else "")
        title = f" · {see(m['heading'])}" if "heading" in m else ""
        lines.append(f"{see(m['id'])}{title} ({where}) {m['status']}")
        lines += [
            f"  Decided: {see(a['way'])} · {see(a['who'])} · {a['date']} · "
            f'"{see(a["words"])}" ({see(a["source"])}:{a["line"]})'
            for a in m["answers"]
        ]
    lines += [
        f"MALFORMED {see(b['source'])}:{b['line']}: {see(b['text'])}" for b in report["malformed"]
    ]
    lines += [f"not read: {see(path)}" for path in report["not_read"]]
    lines.append("Does not establish: " + "; ".join(report["does_not_establish"]) + ".")
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound brief lookup",
        description=(
            "Find a decision brief by id or words and print the answer recorded for it, or "
            "UNANSWERED. Every argument is a term: it is the brief's id, or found in its "
            "heading; every term must hold. An answer is one line, `Decided: <brief id> · "
            '<way> · <who> · <YYYY-MM-DD> · "<their words>"` (` | ` may separate). Searches '
            "JSON briefs documents and Markdown `### <id> · <heading>` headings. Writes nothing."
        ),
        epilog="Exits: 0 a match; 1 none, or a root it could not read; 2 a usage error.",
    )
    parser.add_argument("terms", nargs="+", metavar="TERM")
    parser.add_argument(
        "--in",
        dest="roots",
        action="append",
        default=[],
        metavar="PATH",
        help="a file or folder to search; repeat it; default .agents/work and .agents/handoffs",
    )
    parser.add_argument("--json", action="store_true", help="print one JSON object, not text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    options = _parser().parse_args(argv)
    roots = [Path(root) for root in options.roots] or default_roots(Path.cwd())
    report = search(options.terms, roots)
    if options.json:
        document = {k: v for k, v in report.items() if k != "unreadable"}
        document["not_read"] = sorted([*report["not_read"], *report["unreadable"]])
        sys.stdout.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_text(report))
    return 0 if report["matches"] and not report["unreadable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
