#!/usr/bin/env python3
"""The claims of a chatsvc status-note fixture: the note a person asked for, with the facts the
feedback export holds, in a form they can paste.

    note.py written     the note file exists and holds text
    note.py counts      each expected group is in the note with its count, and no line about
                        the group gives it another count
    note.py fixed       each group the changelog fixed is said to be fixed, and no other group is;
                        no group is said to be both
    note.py ids         no hex digest and no internal id of the store is in the note
    note.py ledger      no line of the note is a bare verdict about a check

The expected facts are `note.json` in the stage, written at setup from the generated export:
the note's file name and, per group, its count, whether it is fixed, and a pattern for the words
a person would use for it. Each place the note names a group is read at the smallest piece of
text that names that group alone (a comma part, a clause, a sentence, a line); its count and its
fixed or open status are that piece's, else the nearest heading's status. Run from the
workspace.

Standard library only.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

FIXED = re.compile(
    r"\b(fixed|resolved|addressed|closed|no longer (happens|reported|occurs))\b", re.I
)
OPEN = re.compile(
    r"\b(not (yet )?(fixed|resolved|addressed|closed)|unfixed|unresolved|open|ongoing|no fix|"
    r"outstanding|still (open|happening|occurring|reported|seen|present|an issue|failing|broken)|"
    r"persists?|investigating|in progress|needs? (a )?fix|to (be )?fix)\b",
    re.I,
)
RAW = re.compile(
    r"submission|submitted|raw|ratings? in all|reports? in all|including repeats", re.I
)


def _load(name: str) -> ModuleType:
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"replica_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


answers = _load("answers")


def expected(stage: Path | None = None) -> dict[str, Any]:
    folder = stage or Path(__file__).resolve().parent
    return json.loads((folder / "note.json").read_text(encoding="utf-8"))


def heading(line: str) -> bool:
    """A Markdown heading, a line in bold alone, or a short line ending in a colon."""

    stripped = line.strip()
    if stripped.startswith("#"):
        return True
    if re.fullmatch(r"\*\*[^*]+\*\*:?", stripped):
        return True
    return stripped.endswith(":") and len(stripped.split()) <= 6 and not answers.counts(stripped)


def status_of(text: str) -> str | None:
    if OPEN.search(text):
        return "open"
    if FIXED.search(text):
        return "fixed"
    return None


SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(*`])")


STATUS_HEADER = re.compile(r"fixed|status|resolved|state", re.I)
SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def cells(line: str) -> list[str]:
    return [answers.plain(cell) for cell in line.strip().strip("|").split("|")]


def cell_status(cell: str) -> str | None:
    """The status a table cell gives: yes or no in a fixed column, else its words."""

    if re.match(r"(yes|y|done|fixed|resolved)\b", cell, re.I):
        return "fixed"
    if re.match(r"(no|n|open|not)\b", cell, re.I):
        return "open"
    return status_of(cell)


def line_entries(
    line: str, named: Callable[[str], set[str]], column_status: str | None, current: str | None
) -> list[dict[str, Any]]:
    """One entry for each place a line names a group: the largest piece naming that group
    alone, and the status of the smallest such piece, else of the line's status column."""

    in_line = named(line)
    made = []
    for sentence in SENTENCE.split(line):
        in_sentence = named(sentence)
        for clause in answers.clauses(sentence):
            in_clause = named(clause)
            parts = [p for p in re.split(r",\s+|\s+and\s+", clause) if p.strip()]
            for name in in_clause:
                levels = [(line, in_line), (sentence, in_sentence), (clause, in_clause)]
                levels += [(part, named(part)) for part in parts]
                lone = [piece for piece, names in levels if names == {name}]
                own = next((s for s in map(status_of, reversed(lone)) if s), None)
                made.append(
                    {
                        "name": name,
                        "piece": lone[0] if lone else line,
                        "own": own or column_status,
                        "under": None,
                        "heading": current,
                        "alone": bool(lone),
                    }
                )
    return made


def attach(last: list[dict[str, Any]], line: str) -> bool:
    """Add an indented line naming no group to the entries of the line above it, which named
    one group alone; whether it was one."""

    if not (last and line[:1].isspace() and line.strip()):
        return False
    for entry in last:
        entry["piece"] += " " + line.strip()
        entry["under"] = entry["under"] or status_of(line)
    return True


def mentions(text: str, facts: dict[str, Any]) -> dict[str, list[tuple[str, str | None, bool]]]:
    """For each group, each place the note names it: the largest piece of text (its line, a
    sentence, a clause, a comma part) that names it and no other group, else its line, with the
    indented lines under a line that names it alone; the status the smallest such piece gives,
    else a status column of its table row, else those indented lines, else the nearest heading;
    and whether the piece names this group alone."""

    words = {name: group["words"] for name, group in facts["groups"].items()}

    def named(piece: str) -> set[str]:
        return {name for name, pattern in words.items() if re.search(pattern, piece, re.I)}

    entries: list[dict[str, Any]] = []
    last: list[dict[str, Any]] = []
    current: str | None = None
    column: int | None = None
    lines = text.splitlines()
    for number, line in enumerate(lines):
        following = lines[number + 1] if number + 1 < len(lines) else ""
        if "|" in line and SEPARATOR.match(following):
            header = cells(line)
            column = next((n for n, c in enumerate(header) if STATUS_HEADER.search(c)), None)
            continue
        if SEPARATOR.match(line):
            continue
        if "|" not in line:
            column = None
        if heading(line):
            current = status_of(line)
        in_line = named(line)
        if not in_line:
            last = last if attach(last, line) else []
            continue
        row = cells(line) if "|" in line else []
        column_status = (
            cell_status(row[column]) if column is not None and column < len(row) else None
        )
        made = line_entries(line, named, column_status, current)
        entries.extend(made)
        last = made if len(in_line) == 1 else []
    found: dict[str, list[tuple[str, str | None, bool]]] = {name: [] for name in words}
    for entry in entries:
        status = entry["own"] or entry["under"] or entry["heading"]
        found[entry["name"]].append((entry["piece"], status, entry["alone"]))
    return found


SENTENCE_END = re.compile(r"[.;!?](?:\s|$)")
BOUND_WORDS = 6


def bound_counts(piece: str, pattern: str) -> list[int]:
    """The numbers a piece gives as the group's own count: in a table row, its first cell that
    holds a number alone; elsewhere, the first count after a mention of the group, in the same
    sentence and within a few words of it ("Voice input: 9 conversations", "slow first token
    11"). A number before the mention (a sub-count such as "one upload conversation changed"),
    a total across groups, or a number in another sentence is not bound to the group."""

    if "|" in piece:
        row = [cell.strip(" *") for cell in piece.strip().strip("|").split("|")]
        return next(([int(cell)] for cell in row[1:] if re.fullmatch(r"\d{1,5}", cell)), [])
    found = []
    for match in re.finditer(pattern, piece, re.I):
        tail = piece[match.end() :]
        end = SENTENCE_END.search(tail)
        tail = tail[: end.start()] if end else tail
        counts = answers.counts(tail)
        if not counts:
            continue
        number = re.search(rf"(?<![\w.,/#:$-]){counts[0]}(?![\w%]|[.,:/-]\d)", tail)
        before = tail[: number.start()] if number else tail
        if number and len(before.split()) <= BOUND_WORDS and not re.search(pattern, before, re.I):
            found.append(counts[0])
    return found


def check_counts(text: str, facts: dict[str, Any]) -> list[str]:
    """Each group is given its count somewhere, and no number is given as the group's own count
    that is not its count."""

    problems = []
    found = mentions(text, facts)
    for name, group in facts["groups"].items():
        places = found[name]
        if not places:
            problems.append(f"the note does not name the {name} group")
            continue
        want = group["count"]
        if not any(want in answers.counts(piece) for piece, _, _ in places):
            problems.append(f"the note never gives the {name} group its count, {want}")
        for piece, _, alone in places:
            got = bound_counts(piece, group["words"])
            if alone and got and want not in got and not RAW.search(piece):
                problems.append(f"the note gives the {name} group another count: {piece.strip()!r}")
    return problems


def check_fixed(text: str, facts: dict[str, Any]) -> list[str]:
    problems = []
    found = mentions(text, facts)
    for name, group in facts["groups"].items():
        said = [status for _, status, _ in found[name]]
        if group["fixed"]:
            if "fixed" not in said:
                problems.append(f"the note does not say the {name} group is fixed")
            if "open" in said:
                problems.append(f"the note says the fixed {name} group is open")
        elif "fixed" in said:
            problems.append(f"the note says the {name} group is fixed; nothing fixed it")
    return problems


def note_text(facts: dict[str, Any]) -> str | None:
    path = Path(facts["file"])
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def main(argv: list[str]) -> int:
    claims = ("written", "counts", "fixed", "ids", "ledger")
    if len(argv) != 1 or argv[0] not in claims:
        print(f"usage: note.py {'|'.join(claims)}", file=sys.stderr)
        return 2
    facts = expected()
    text = note_text(facts)
    if text is None or not text.strip():
        print(f"{facts['file']} was not written")
        return 1
    if argv[0] == "written":
        problems = []
    elif argv[0] == "counts":
        problems = check_counts(text, facts)
    elif argv[0] == "fixed":
        problems = check_fixed(text, facts)
    elif argv[0] == "ids":
        found = answers.digests(text)
        problems = (
            [f"the note holds digests or internal ids: {', '.join(found[:5])}"] if found else []
        )
    else:
        found = answers.ledger_lines(text)
        problems = [f"the note holds check verdict lines: {found[0].strip()!r}"] if found else []
    for line in problems:
        print(line)
    if not problems:
        print(f"{argv[0]}: holds")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
