"""`outcomebound review check`: whether every finding of a review file ends in a disposition
(`docs/specs/review/design.md`, `schemas/review-report.schema.json`).

What this module decides: the file's format (a `Reviewed: <ref>` line before the first finding;
a finding is a `### <id> · <title>` heading with one `Disposition:` line of `fixed`, `rejected` or
`deferred`, then ` — `, then where or why), the checks below, each with a name, and for each line
what it does not establish. The verdict is FAIL where any line fails, else PASS. A WARN line does
not change the verdict. Exits: 0 PASS; 1 FAIL or a refusal; 2 a usage error.

What it does not decide: whether a fix is right, whether a rejection is right, whether `where`
holds what it says, whether the review found what it should have. It reads the one file it is
given, runs nothing and writes nothing. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from outcomebound_tools import instruction_audit, textio

PASS, FAIL, WARN, INFO = "PASS", "FAIL", "WARN", "INFO"
VERSION = 1
KINDS = ("fixed", "rejected", "deferred")
_FENCE = re.compile(r"[ ]{0,3}(`{3,}|~{3,})")
_CLOSING = re.compile(r"[ ]{0,3}(`{3,}|~{3,})[ \t]*")
_HEADING = re.compile(r"[ ]{0,3}(#{1,6})(?:[ \t]+(.*))?")
# A `###` heading inside a list item or a block quote: Markdown shows it as a heading, so it is
# read as a malformed finding heading, never as text that a finding could hide in.
_NESTED = re.compile(r"[ ]{0,3}(?:(?:[-*+]|\d{1,9}[.)])[ \t]+|>[ \t]?)+[ \t]*###(?:[ \t]|$)")
_FINDING = re.compile(r"([A-Za-z0-9-]+)[ \t]+·[ \t]+(\S.*?)")
_REVIEWED = re.compile(r"Reviewed:[ \t]*(.*)")
_DISPOSITION = re.compile(r"Disposition:[ \t]*(.*)")
_SEPARATOR = re.compile(r"(?<=[ \t])(?:—|--)(?:[ \t]+|$)")

# One line each: what the code's PASS or FAIL does not establish.
LIMITS = {
    "REVIEWED_MISSING": "that the ref names what the reviewer read; only that a ref is written",
    "FINDING_MALFORMED": "that a well-formed heading is a finding worth acting on",
    "ID_DUPLICATE": "that two findings with different ids are not about one thing",
    "DISPOSITION_MISSING": "that a finding with a disposition was read or acted on",
    "DISPOSITION_DUPLICATE": "which of the lines was meant",
    "DISPOSITION_ACCEPTED": "whether the finding was right; accepted is not an end state",
    "DISPOSITION_UNKNOWN": "what the writer meant",
    "DISPOSITION_EMPTY": "that a written reason or place is true",
    "REVIEWED_REF": (
        "that the two refs name different revisions; they are compared as text, and no "
        "revision is looked up"
    ),
    "FINDINGS_NONE": "that the reviewer found nothing; only that the file holds no finding",
}
NEXT = {
    "REVIEWED_MISSING": "write `Reviewed: <revision, branch or tag>` before the first finding",
    "FINDING_MALFORMED": "write the heading as `### <id> · <title>`; the id holds letters, "
    "digits and `-`",
    "ID_DUPLICATE": "give each finding its own id",
    "DISPOSITION_MISSING": "add `Disposition: fixed — <where>`, `rejected — <reason>` or "
    "`deferred — <where it is recorded>`",
    "DISPOSITION_DUPLICATE": "keep one Disposition line for the finding",
    "DISPOSITION_ACCEPTED": "fix it and write `fixed`, or record it elsewhere and write `deferred`",
    "DISPOSITION_UNKNOWN": "use fixed, rejected or deferred",
    "DISPOSITION_EMPTY": "say where (fixed, deferred) or why (rejected) after the dash",
    "REVIEWED_REF": "read the revision under check, or pass the ref the review read",
}
ORDER = tuple(LIMITS)
HELD = {
    "REVIEWED_MISSING": "a `Reviewed:` ref is written",
    "FINDING_MALFORMED": "every `###` heading is a finding heading",
    "ID_DUPLICATE": "every id is used once",
    "DISPOSITION_MISSING": "every finding has a Disposition line",
    "DISPOSITION_DUPLICATE": "no finding has two",
    "DISPOSITION_ACCEPTED": "no finding ends at accepted",
    "DISPOSITION_UNKNOWN": "every disposition is fixed, rejected or deferred",
    "DISPOSITION_EMPTY": "every disposition says where or why",
}


@dataclass(frozen=True)
class Finding:
    code: str
    verdict: str
    subject: str
    text: str

    @property
    def limit(self) -> str:
        return LIMITS[self.code]

    @property
    def next(self) -> str | None:
        return NEXT.get(self.code) if self.verdict == FAIL else None


def display(text: str) -> str:
    """`text` with every character outside printable ASCII escaped, as the other verbs print
    text that came from a file."""

    return instruction_audit.plain(text)


@dataclass
class _Entry:
    id: str
    line: int
    dispositions: list[tuple[int, str]]


def _lines(text: str) -> list[tuple[int, str]]:
    """The lines outside code fences, with their numbers; a fence's own lines are not read."""

    kept: list[tuple[int, str]] = []
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        mark = _FENCE.match(line)
        if fence is None and mark:
            fence = mark.group(1)
            continue
        if fence is not None:
            closing = _CLOSING.fullmatch(line)
            if closing and closing.group(1)[0] == fence[0] and len(closing.group(1)) >= len(fence):
                fence = None
            continue
        kept.append((number, line))
    return kept


def _parse(text: str) -> tuple[str | None, list[_Entry], list[int]]:
    """The ref the file says it read, its findings, and the lines of malformed finding headings."""

    reviewed: str | None = None
    entries: list[_Entry] = []
    malformed: list[int] = []
    current: _Entry | None = None
    for number, line in _lines(text):
        if _NESTED.match(line):
            malformed.append(number)
            continue
        heading = _HEADING.fullmatch(line)
        if heading and len(heading.group(1)) <= 3:
            current = None
            if len(heading.group(1)) == 3:
                match = _FINDING.fullmatch((heading.group(2) or "").rstrip())
                if match is None:
                    malformed.append(number)
                else:
                    current = _Entry(match.group(1), number, [])
                    entries.append(current)
        elif current is not None:
            disposition = _DISPOSITION.fullmatch(line)
            if disposition:
                current.dispositions.append((number, disposition.group(1).rstrip()))
        elif not entries and reviewed is None:
            ref = _REVIEWED.fullmatch(line)
            reviewed = (ref.group(1).rstrip() or None) if ref else None
    return reviewed, entries, malformed


def _disposition(entry: _Entry, path: str, add: Callable[[str, str, str, str], None]) -> None:
    number, value = entry.dispositions[0]
    parts = _SEPARATOR.split(value, maxsplit=1)
    kind = parts[0].strip().casefold()
    reason = parts[1].strip() if len(parts) > 1 else ""
    where = f"{path}:{number}"
    if kind == "accepted":
        add("DISPOSITION_ACCEPTED", FAIL, where, f"{entry.id} is accepted, not fixed or deferred")
    elif kind not in KINDS:
        add("DISPOSITION_UNKNOWN", FAIL, where, f"{entry.id}: {parts[0].strip() or 'empty'}")
    elif not reason:
        noun = "reason" if kind == "rejected" else "place"
        add("DISPOSITION_EMPTY", FAIL, where, f"{entry.id} is {kind} with no {noun}")


def _entry(
    entry: _Entry, seen: dict[str, _Entry], path: str, add: Callable[[str, str, str, str], None]
) -> None:
    where = f"{path}:{entry.line}"
    first = seen.setdefault(entry.id.casefold(), entry)
    if first is not entry:
        add("ID_DUPLICATE", FAIL, where, f"{entry.id} is the id of line {first.line}")
    if not entry.dispositions:
        add("DISPOSITION_MISSING", FAIL, where, f"{entry.id} has no Disposition line")
        return
    if len(entry.dispositions) > 1:
        lines = ", ".join(str(number) for number, _ in entry.dispositions)
        add("DISPOSITION_DUPLICATE", FAIL, where, f"{entry.id} has Disposition lines {lines}")
    _disposition(entry, path, add)


def check(text: str, path: str, *, at: str | None = None) -> tuple[str | None, list[Finding]]:
    """The ref the file says it read, or None, and every finding of one check, in the order of
    `ORDER`."""

    found: list[Finding] = []

    def add(code: str, verdict: str, subject: str, message: str) -> None:
        found.append(Finding(code, verdict, display(subject), display(message)))

    reviewed, entries, malformed = _parse(text)
    if reviewed is None:
        add("REVIEWED_MISSING", FAIL, path, "no `Reviewed: <ref>` line before the first finding")
    elif at is not None and reviewed != at:
        add("REVIEWED_REF", WARN, path, f"the review read {reviewed}; the check was given {at}")
    for number in malformed:
        add("FINDING_MALFORMED", FAIL, f"{path}:{number}", "not `### <id> · <title>`")
    seen: dict[str, _Entry] = {}
    for entry in entries:
        _entry(entry, seen, path, add)
    if not entries:
        add("FINDINGS_NONE", INFO, path, "the file holds no finding")
    failed = {item.code for item in found if item.verdict == FAIL}
    for code, held in HELD.items():
        if code not in failed and (entries or malformed or code == "REVIEWED_MISSING"):
            add(code, PASS, "all", held)
    rank = {code: index for index, code in enumerate(ORDER)}
    return reviewed, sorted(found, key=lambda item: rank[item.code])  # stable within a code


def verdict(findings: Sequence[Finding]) -> str:
    return FAIL if any(item.verdict == FAIL for item in findings) else PASS


def _counts(findings: Sequence[Finding]) -> dict[str, int]:
    return {
        kind: sum(item.verdict == kind for item in findings) for kind in (PASS, FAIL, WARN, INFO)
    }


def render_text(findings: Sequence[Finding], *, verbose: bool = False) -> str:
    """The verdict and its counts first, then each line that did not pass; the passing lines
    only under `verbose`."""

    counts = _counts(findings)
    lines = [f"{verdict(findings)}; " + ", ".join(f"{n} {kind}" for kind, n in counts.items())]
    for item in findings:
        if item.verdict == PASS and not verbose:
            continue
        line = f"{item.verdict} {item.code} {item.subject}: {item.text}. "
        line += f"Does not establish: {item.limit}."
        if item.next:
            line += f" next: {item.next}."
        lines.append(line)
    return "\n".join(lines) + "\n"


def render_json(reviewed: str | None, findings: Sequence[Finding]) -> str:
    document = {
        "version": VERSION,
        "verdict": verdict(findings),
        **({"reviewed": display(reviewed)} if reviewed else {}),
        "counts": _counts(findings),
        "findings": [
            {
                "code": item.code,
                "verdict": item.verdict,
                "subject": item.subject,
                "text": item.text,
                "does_not_establish": item.limit,
                **({"next": item.next} if item.next else {}),
            }
            for item in findings
        ],
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound review",
        description="Check a review file: every finding ends in a disposition.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    checked = commands.add_parser(
        "check",
        prog="outcomebound review check",
        help="check that each finding of a review file has a disposition",
        description=(
            "Check a Markdown review file. It has a `Reviewed: <ref>` line before the first "
            "finding, a revision, branch or tag. Each finding is a `### <id> · <title>` "
            "heading (id: letters, digits, `-`) with one line `Disposition: fixed — <where>`, "
            "`Disposition: rejected — <reason>` or `Disposition: deferred — <where it is "
            "recorded>`. Text between headings is data. FAIL codes: REVIEWED_MISSING, "
            "FINDING_MALFORMED, ID_DUPLICATE, DISPOSITION_MISSING, DISPOSITION_DUPLICATE, "
            "DISPOSITION_ACCEPTED, DISPOSITION_UNKNOWN, DISPOSITION_EMPTY. Each report line "
            "says what it does not establish: that a fix is right, that a rejection is right, "
            "that the place a disposition names holds what it says."
        ),
        epilog=(
            "With --at REF, a WARN line says where `Reviewed:` names another ref; refs are "
            "compared as text. A WARN does not change the verdict. "
            "Exits: 0 PASS; 1 FAIL or a refusal; 2 a usage error."
        ),
    )
    checked.add_argument("path", metavar="FILE", help="the review file")
    checked.add_argument("--at", metavar="REF", help="warn where the review read another ref")
    checked.add_argument("--json", action="store_true", help="print one JSON object, not text")
    checked.add_argument("--verbose", action="store_true", help="also print the checks that passed")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    options = _parser().parse_args(argv)
    try:
        text = textio.read_text(Path(options.path))
    except (OSError, UnicodeDecodeError) as error:
        sys.stderr.write(f"REVIEW_UNREADABLE: {display(options.path)}: {display(str(error))}\n")
        return 1
    reviewed, findings = check(text, options.path, at=options.at)
    if options.json:
        sys.stdout.write(render_json(reviewed, findings))
    else:
        sys.stdout.write(render_text(findings, verbose=options.verbose))
    return 0 if verdict(findings) == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
