"""`outcomebound sources check`: one ledger against the manifests of the declared input set
(`docs/specs/sources/design.md`, `schemas/sources-report.schema.json`).

What this module decides: the checks below, each with a name, and for each line the report
prints what it does not establish. A verdict is FAIL where any line fails, else UNVERIFIED where
any line is, else PASS. A manifest that is absent or partial reads UNVERIFIED and hides no FAIL.

What it does not decide: whether a carried requirement keeps what its source meant, whether a
drop is right, whether an item is safe. It opens the manifests, the ledger file and each
manifest's source files, only to read; it runs nothing and writes nothing. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from outcomebound_tools import sources_ledger as ledger_module
from outcomebound_tools import sources_manifest as manifest_module
from outcomebound_tools import textio
from outcomebound_tools.sources_manifest import display

PASS, FAIL, UNVERIFIED, INFO = "PASS", "FAIL", "UNVERIFIED", "INFO"
VERSION = 1

# One line each: what the code's PASS or FAIL does not establish.
LIMITS = {
    "MANIFEST_INVALID": "that a manifest is complete; only that it has the manifest's shape",
    "LEDGER_MISSING": "anything about the ledger's content",
    "ROW_MALFORMED": "that a well-formed row is true",
    "ITEM_UNDISPOSED": (
        "that a constraint inside a row's item reached a requirement; one item may hold several"
    ),
    "ITEM_UNKNOWN": "that a row's id is the item the row means",
    "ITEM_DUPLICATE": "that two rows are not both wrong",
    "TARGET_MISSING": "that the requirement a row names says what the item says",
    "REQUIREMENT_DUPLICATE": "that each requirement is stated once in substance",
    "QUOTE_NOT_FOUND": (
        "quote occurrence only: the words are in the item; not that the requirement keeps their "
        "meaning, nor that the item is an authority"
    ),
    "ITEM_CHANGED": "that an item with the same revision still means what it meant",
    "SOURCE_CHANGED": "anything about a source with no file to read, or items the file adds later",
    "MANIFEST_DIFFERS": (
        "anything about a source with no file to read; the manifest's items are then unverified"
    ),
    "SOURCE_FRESHNESS": "that the manifest's items are the ones its source file splits into",
    "MANIFEST_ABSENT": "anything about the items of that manifest",
    "SOURCE_PARTIAL": "what the partial item left out",
    "RANGE_CANDIDATES": (
        "lexical candidates only (English modal and decision words); a requirement the list "
        "misses is not shown"
    ),
    "SUSPECT": (
        "that a flagged item is an attack, nor that an unflagged item is safe; the flags are "
        "the instruction audit's lexical classes"
    ),
    "DROP_ASSUMED": "that the drop is right; the person may reverse it",
    "REQUIREMENT_UNSOURCED": "that the requirement is wrong; it may rest on the person's word",
    "SOURCE_CONVERTED": "how faithful the conversion to text was",
}
# What settles a line that did not pass, after `next:`. A line with no entry has no next step.
NEXT = {
    "MANIFEST_INVALID": "import the source again, or name the right manifest",
    "LEDGER_MISSING": "add a `## Sources` section; `--skeleton` prints one",
    "ROW_MALFORMED": "write the row in the shape the design gives",
    "ITEM_UNDISPOSED": "give the item one row with a disposition",
    "ITEM_UNKNOWN": "use an id the manifest holds; `--skeleton` lists them",
    "ITEM_DUPLICATE": "keep one row for the item",
    "TARGET_MISSING": "define the requirement in `## Requirements`, or name the right id",
    "REQUIREMENT_DUPLICATE": "define the id once",
    "QUOTE_NOT_FOUND": "quote words that are in the item",
    "ITEM_CHANGED": "read the item again and give it its disposition again",
    "SOURCE_CHANGED": "import the file again, then check again",
    "MANIFEST_DIFFERS": "import the source again; do not edit a manifest by hand",
    "MANIFEST_ABSENT": "name the manifest, or import the source",
    "SOURCE_FRESHNESS": "run the check where the source file is, or pass --root",
    "SOURCE_PARTIAL": "read the source itself for what the partial item left out",
    "RANGE_CANDIDATES": "give each candidate its own row, or read them and say so",
}
ORDER = tuple(LIMITS)
_PLAIN = str.maketrans(
    {0x201C: '"', 0x201D: '"', 0x2019: "'", 0x2018: "'", ord("*"): None, ord("`"): None}
)
_MODAL = re.compile(
    r"\b(must|shall|should|required?|need(?:s)? to|will|deadline|we decided|action item)\b",
    re.IGNORECASE,
)


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
        return NEXT.get(self.code) if self.verdict in (FAIL, UNVERIFIED) else None


def normalise(text: str) -> str:
    """Text for a quote occurrence: case folded, whitespace folded, curly quotes straight, and
    `*` and backticks dropped, so markup around a phrase does not hide it."""

    plain = text.translate(_PLAIN)
    return " ".join(plain.casefold().split())


def range_revision(revisions: Sequence[str]) -> str:
    """The digest a ledger records for a range: the items' revisions in order, so an item added
    to the range, or one changed in it, moves it."""

    return hashlib.sha256("\n".join(revisions).encode()).hexdigest()


Row = ledger_module.Row
ItemMap = dict[str, tuple[dict[str, Any], dict[str, Any]]]


class _Run:
    """One check's state: the manifests read, the ledger, and the findings so far."""

    def __init__(self, ledger_path: Path, root: Path) -> None:
        self.ledger_path, self.root = ledger_path, root
        self.findings: list[Finding] = []
        self.manifests: dict[str, dict[str, Any]] = {}
        self.absent: dict[str, str] = {}
        self.items: ItemMap = {}
        self.covered: dict[str, list[Row]] = {}
        self.unchecked = 0
        self.resplit = 0
        self.ledger = ledger_module.parse(textio.read_text(ledger_path))

    def add(self, code: str, verdict: str, subject: str, text: str) -> None:
        self.findings.append(Finding(code, verdict, display(subject), display(text)))

    def where(self, row: Row) -> str:
        return f"{self.ledger_path.as_posix()}:{row.line}"

    def load(self, paths: Sequence[Path]) -> None:
        for path in paths:
            if not path.is_file():
                self.absent[path.stem] = path.as_posix()
                self.add("MANIFEST_ABSENT", UNVERIFIED, path.as_posix(), "no such file; unread")
                continue
            try:
                document = manifest_module.load(path)
            except ValueError as error:
                self.add("MANIFEST_INVALID", FAIL, path.as_posix(), str(error))
                continue
            if document["name"] in self.manifests:
                text = f"name {document['name']} is already read"
                self.add("MANIFEST_INVALID", FAIL, path.as_posix(), text)
                continue
            self.manifests[document["name"]] = document
        for document in self.manifests.values():
            for item in document["items"]:
                self.items[item["id"]] = (document, item)

    def rows(self) -> None:
        if not self.ledger.present:
            self.add("LEDGER_MISSING", FAIL, self.ledger_path.as_posix(), "no `## Sources` section")
        for row in self.ledger.rows:
            if row.problem:
                self.add("ROW_MALFORMED", FAIL, self.where(row), row.problem)
                continue
            prefix = row.first.split(":", 1)[0]
            if prefix in self.absent and prefix not in self.manifests:
                self.unchecked += 1
                continue
            members = self.members(row)
            if members is None:
                continue
            self.revision(row, members)
            self.disposition(row, members)
            for member in members:
                self.covered.setdefault(member["id"], []).append(row)
        for _, number in self.ledger.duplicate_requirements:
            where = f"{self.ledger_path.as_posix()}:{number}"
            self.add("REQUIREMENT_DUPLICATE", FAIL, where, "id defined twice")

    def members(self, row: Row) -> list[dict[str, Any]] | None:
        """The items a row covers, or None where it names one no manifest holds, or a bad range."""

        first = self.items.get(row.first)
        if first is None:
            self.add("ITEM_UNKNOWN", FAIL, self.where(row), f"no manifest holds {row.first}")
            return None
        if row.last is None:
            return [first[1]]
        last = self.items.get(row.last)
        if last is None:
            self.add("ITEM_UNKNOWN", FAIL, self.where(row), f"no manifest holds {row.last}")
            return None
        ids = [item["id"] for item in first[0]["items"]]
        if last[0] is not first[0] or ids.index(row.last) < ids.index(row.first):
            text = "a range runs forward within one manifest"
            self.add("ROW_MALFORMED", FAIL, self.where(row), text)
            return None
        return first[0]["items"][ids.index(row.first) : ids.index(row.last) + 1]

    def revision(self, row: Row, members: list[dict[str, Any]]) -> None:
        revisions = [item["revision"] for item in members]
        recorded = revisions[0] if row.last is None else range_revision(revisions)
        if not recorded.startswith(row.revision):
            now = recorded[: len(row.revision)]
            self.add(
                "ITEM_CHANGED",
                FAIL,
                self.where(row),
                f"the ledger records #{row.revision}; the manifest holds #{now} now",
            )

    def disposition(self, row: Row, members: list[dict[str, Any]]) -> None:
        kind = row.disposition
        if row.last is not None and kind not in ("carried", "not requirement-bearing"):
            text = f"only a not requirement-bearing row may name a range, not a {kind} row"
            self.add("ROW_MALFORMED", FAIL, self.where(row), text)
        if kind == "carried":
            self.carried(row, members)
        elif kind in ("dropped (assumed)", "dropped (decided)", "not requirement-bearing"):
            if not row.basis:
                self.add("ROW_MALFORMED", FAIL, self.where(row), f"a {kind} row gives its reason")
        elif kind == "deferred" and not row.where_text:
            text = "a deferred row names a ticket or a later design in Where"
            self.add("ROW_MALFORMED", FAIL, self.where(row), text)

    def carried(self, row: Row, members: list[dict[str, Any]]) -> None:
        where = self.where(row)
        if row.last is not None:
            self.add("ROW_MALFORMED", FAIL, where, "a carried row names one item, not a range")
        if not row.where:
            self.add("ROW_MALFORMED", FAIL, where, "a carried row names a requirement id in Where")
        for identifier in row.where:
            if identifier not in self.ledger.requirements:
                self.add("TARGET_MISSING", FAIL, where, f"{identifier} is not in `## Requirements`")
        basis = row.basis.lower()
        if not basis.startswith(("stated", "inferred")):
            text = "a carried row's Basis starts with stated or inferred"
            self.add("ROW_MALFORMED", FAIL, where, text)
        elif basis.startswith("stated"):
            self.quotes(row, members, where)

    def quotes(self, row: Row, members: list[dict[str, Any]], where: str) -> None:
        quotes = row.quotes()
        if not quotes:
            self.add(
                "ROW_MALFORMED", FAIL, where, 'a stated Basis holds a quote in "double quotes"'
            )
        for quote in quotes:
            if not normalise(quote):
                self.add("ROW_MALFORMED", FAIL, where, "a stated quote holds words")
            elif row.last is None and normalise(quote) not in normalise(members[0]["text"]):
                self.add("QUOTE_NOT_FOUND", FAIL, where, f'"{quote}" is not in {members[0]["id"]}')

    def coverage(self) -> None:
        for identifier, rows in self.covered.items():
            live = [row for row in rows if row.disposition != "todo"]
            if len(live) > 1:
                lines = ", ".join(str(row.line) for row in live)
                self.add("ITEM_DUPLICATE", FAIL, identifier, f"{len(live)} rows (lines {lines})")
        for identifier in self.items:
            rows = self.covered.get(identifier, [])
            if all(row.disposition == "todo" for row in rows):
                self.add("ITEM_UNDISPOSED", FAIL, identifier, "no row gives it a disposition")

    def notes(self) -> None:
        for identifier, (_, item) in self.items.items():
            if item["partial"]:
                self.add("SOURCE_PARTIAL", UNVERIFIED, identifier, ", ".join(item["partial"]))
            if item["suspect"]:
                held = ", ".join(
                    sorted({row.disposition for row in self.covered.get(identifier, [])})
                )
                flags = "; ".join(item["suspect"])
                text = f"flagged: {flags}; disposition: {held or 'none'}"
                self.add("SUSPECT", INFO, identifier, text)
        for identifier, rows in self.covered.items():
            if any(row.disposition == "dropped (assumed)" for row in rows):
                self.add("DROP_ASSUMED", INFO, identifier, "dropped on an assumption")
        cited = {
            requirement
            for rows in self.covered.values()
            for row in rows
            if row.disposition == "carried"
            for requirement in row.where
        }
        for requirement, number in sorted(self.ledger.requirements.items(), key=lambda p: p[1]):
            if requirement not in cited and requirement not in self.ledger.assumed:
                text = f"{requirement} is carried from no item and is not marked [assumed]"
                self.add(
                    "REQUIREMENT_UNSOURCED", INFO, f"{self.ledger_path.as_posix()}:{number}", text
                )
        self.add_all(
            ("SOURCE_CONVERTED", INFO, source["file"], "imported as converted text")
            for document in self.manifests.values()
            for source in document["sources"]
            if source["converted"]
        )

    def add_all(self, found: Iterable[tuple[str, str, str, str]]) -> None:
        for code, verdict, subject, text in found:
            self.add(code, verdict, subject, text)

    def freshness(self) -> None:
        """Read each source file once. Where its digest matches the manifest's, split it as
        `import` does and compare the items with the manifest's; the file's text then stands for
        the manifest's wherever a quote is checked. Run before the rows."""

        for document in self.manifests.values():
            slugs: dict[str, int] = {}
            for index, source in enumerate(document["sources"]):
                file_slug = manifest_module.unique(
                    manifest_module.slug(Path(source["file"]).stem, "file"), slugs
                )
                try:
                    data = (self.root / source["file"]).read_bytes()
                except OSError:
                    where = display(self.root.as_posix())
                    self.add(
                        "SOURCE_FRESHNESS",
                        UNVERIFIED,
                        source["file"],
                        f"not found under {where}; the manifest's items are not checked "
                        "against the source",
                    )
                    continue
                if hashlib.sha256(textio.fold(data)).hexdigest() != source["raw_sha256"]:
                    text = "the file differs from the one imported"
                    self.add("SOURCE_CHANGED", FAIL, source["file"], text)
                    continue
                self.compare(document, index, source, file_slug)

    def compare(
        self, document: dict[str, Any], index: int, source: dict[str, Any], file_slug: str
    ) -> None:
        try:
            _, text, _ = manifest_module.read_source(self.root / source["file"], source["format"])
        except ValueError as error:
            self.add("MANIFEST_DIFFERS", FAIL, source["file"], f"cannot be read as text ({error})")
            return
        expected = manifest_module.split_items(text, source["format"], document["name"], file_slug)
        held = {item["id"]: item for item in document["items"] if item["source"] == index}
        self.resplit += 1
        missing = [item.id for item in expected if item.id not in held]
        known = {item.id for item in expected}
        added = [identifier for identifier in held if identifier not in known]
        changed = []
        for item in expected:
            found = held.get(item.id)
            if found is not None and (
                found["revision"] != item.revision or found["text"] != item.text
            ):
                changed.append(item.id)
                found["text"] = item.text  # quotes are checked against the file's own text
        if missing or added or changed:
            parts = [
                f"{label}: {', '.join(ids)}"
                for label, ids in (
                    ("missing from the manifest", missing),
                    ("not in the file", added),
                    ("text differs", changed),
                )
                if ids
            ]
            self.add("MANIFEST_DIFFERS", FAIL, source["file"], "; ".join(parts))

    def candidates(self) -> None:
        for row in self.ledger.rows:
            if row.problem or row.last is None or row.disposition != "not requirement-bearing":
                continue
            span = self.range_items(row)
            hits = [item["id"] for item in span if _MODAL.search(item["text"])]
            if hits:
                text = (
                    f"{len(hits)} of {len(span)} items read like requirements: {', '.join(hits)}; "
                    "give each its own row, or read them and say so"
                )
                self.add("RANGE_CANDIDATES", UNVERIFIED, f"{row.first}..{row.last}", text)

    def range_items(self, row: Row) -> list[dict[str, Any]]:
        first = self.items.get(row.first)
        if first is None or row.last not in self.items:
            return []
        ids = [item["id"] for item in first[0]["items"]]
        if row.last not in ids or ids.index(row.last) < ids.index(row.first):
            return []
        return first[0]["items"][ids.index(row.first) : ids.index(row.last) + 1]

    def passes(self) -> None:
        """A PASS line for each check that ran and found nothing, so a clean report says what
        held. None where no manifest was read: nothing was checked."""

        failed = {found.code for found in self.findings if found.verdict == FAIL}
        skipped = f" ({self.unchecked} row(s) unchecked: manifest absent)" if self.unchecked else ""
        held = {
            "MANIFEST_INVALID": f"{len(self.manifests)} manifest(s) read",
            "LEDGER_MISSING": "the `## Sources` section is there",
            "ROW_MALFORMED": f"{len(self.ledger.rows)} row(s) read",
            "ITEM_UNDISPOSED": f"{len(self.items)} item(s) each have a row",
            "ITEM_UNKNOWN": "every row's id is in a manifest read" + skipped,
            "ITEM_DUPLICATE": "no item has two rows",
            "TARGET_MISSING": "every carried requirement id is defined",
            "REQUIREMENT_DUPLICATE": "no requirement id is defined twice",
            "QUOTE_NOT_FOUND": "every stated quote occurs in its item",
            "ITEM_CHANGED": "every recorded revision matches",
            "SOURCE_CHANGED": "every source file read matches its manifest",
            "MANIFEST_DIFFERS": f"{self.resplit} source file(s) split into the manifest's items",
        }
        if not self.manifests:
            return
        if not self.resplit:
            del held["MANIFEST_DIFFERS"]
        self.findings.extend(
            Finding(code, PASS, "all", text) for code, text in held.items() if code not in failed
        )


def check(manifest_paths: Sequence[Path], ledger_path: Path, root: Path) -> list[Finding]:
    """Every finding of one check, in the order of `ORDER`. Raises `OSError` and
    `UnicodeDecodeError` where the ledger file cannot be read."""

    run = _Run(ledger_path, root)
    run.load(manifest_paths)
    run.freshness()
    run.rows()
    run.coverage()
    run.notes()
    run.candidates()
    run.passes()
    rank = {code: index for index, code in enumerate(ORDER)}
    return sorted(run.findings, key=lambda found: rank[found.code])  # stable within a code


def verdict(findings: Sequence[Finding]) -> str:
    kinds = {found.verdict for found in findings}
    if FAIL in kinds:
        return FAIL
    return UNVERIFIED if UNVERIFIED in kinds else PASS


def exit_code(result: str) -> int:
    return {PASS: 0, FAIL: 1, UNVERIFIED: 2}[result]


def render_text(findings: Sequence[Finding], *, verbose: bool = False) -> str:
    """The verdict and its counts first, then each line that did not pass; the passing lines
    only under `verbose`, as `instructions check` prints."""

    counts = {
        kind: sum(f.verdict == kind for f in findings) for kind in (FAIL, UNVERIFIED, INFO, PASS)
    }
    tally = ", ".join(f"{counts[kind]} {kind}" for kind in counts)
    lines = [f"{verdict(findings)}; {tally}"]
    for found in findings:
        if found.verdict == PASS and not verbose:
            continue
        line = f"{found.verdict} {found.code} {found.subject}: {found.text}. "
        line += f"Does not establish: {found.limit}."
        if found.next:
            line += f" next: {found.next}."
        lines.append(line)
    return "\n".join(lines) + "\n"


def render_json(findings: Sequence[Finding]) -> str:
    counts = {
        kind: sum(f.verdict == kind for f in findings) for kind in (PASS, FAIL, UNVERIFIED, INFO)
    }
    document = {
        "version": VERSION,
        "verdict": verdict(findings),
        "counts": counts,
        "findings": [
            {
                "code": f.code,
                "verdict": f.verdict,
                "subject": f.subject,
                "text": f.text,
                "does_not_establish": f.limit,
                **({"next": f.next} if f.next else {}),
            }
            for f in findings
        ],
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"
