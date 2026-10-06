"""The source manifest: what `outcomebound sources import` writes and `check` reads
(`docs/specs/sources/design.md`, `schemas/sources-manifest.schema.json`).

What this module decides: how a markdown or plain-text file becomes items (one per heading
section, the text before the first heading as `preamble`, or one per paragraph of a plain-text
file); an item's identity (`<name>:<file>:<section>`, from where it stands) apart from its
revision (the digest of its text), so a changed item keeps its id and shows a new revision; the
raw digest of the file; which items are partial or suspect; the manifest's bytes, which are the
same for the same input.

What it does not decide: whether an item holds a requirement, or what it means. It never runs,
follows or obeys what it reads. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from outcomebound_tools import hashing, home, instruction_audit, schemacheck, textio

VERSION = 1
KIND_BY_SUFFIX = {".md": "markdown", ".markdown": "markdown", ".txt": "text", ".text": "text"}
SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")
ITEM_ID = re.compile(r"[a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9-]*")
REVISION_SHOWN = 12
_HEADING = re.compile(r"(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*")
_FENCE = re.compile(r"[ ]{0,3}(`{3,}|~{3,})")
_PARTIAL_UNCLOSED = "unclosed-code-fence"
_PARTIAL_REPLACEMENT = "replacement-character"


class SourceRefusal(ValueError):
    """A refusal: the code (`SOURCE_...`) and the sentence that says what to do."""

    def __init__(self, code: str, text: str) -> None:
        super().__init__(f"{code}: {text}")
        self.code, self.text = code, text


@dataclass
class Item:
    id: str
    heading: str | None
    line_start: int
    line_end: int
    text: str
    partial: list[str] = field(default_factory=list)

    @property
    def revision(self) -> str:
        return hashing.sha256_text(self.text)


def slug(text: str, fallback: str = "section") -> str:
    """Lowercase ASCII words joined by `-`; `fallback` where nothing is left."""

    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-") or fallback


def _unique(base: str, seen: dict[str, int]) -> str:
    seen[base] = seen.get(base, 0) + 1
    return base if seen[base] == 1 else f"{base}-{seen[base]}"


def _markdown_sections(lines: Sequence[str]) -> list[tuple[str | None, int, int, bool]]:
    """(heading text or None, first line, last line, unclosed fence) per section, 1-based."""

    starts: list[tuple[str | None, int]] = []
    fence: str | None = None
    for number, line in enumerate(lines, 1):
        opening = _FENCE.match(line)
        if fence is not None:
            if opening and opening.group(1)[0] == fence[0] and len(opening.group(1)) >= len(fence):
                fence = None
            continue
        if opening:
            fence = opening.group(1)
            continue
        heading = _HEADING.fullmatch(line)
        if heading:
            starts.append((heading.group(2), number))
    sections: list[tuple[str | None, int, int, bool]] = []
    if not starts or starts[0][1] > 1:
        end = (starts[0][1] - 1) if starts else len(lines)
        sections.append((None, 1, end, False))
    for index, (title, first) in enumerate(starts):
        last = starts[index + 1][1] - 1 if index + 1 < len(starts) else len(lines)
        sections.append((title, first, last, False))
    unclosed = fence is not None
    if unclosed and sections:
        title, first, last, _ = sections[-1]
        sections[-1] = (title, first, last, True)
    return sections


def _markdown_items(lines: Sequence[str], name: str, file_slug: str) -> list[Item]:
    items: list[Item] = []
    seen: dict[str, int] = {}
    for title, first, last, unclosed in _markdown_sections(lines):
        body = lines[first - 1 : last]
        while body and not body[-1].strip():
            body = body[:-1]
        if not body:
            continue
        section = "preamble" if title is None else slug(title)
        item = Item(
            f"{name}:{file_slug}:{_unique(section, seen)}",
            title,
            first,
            first + len(body) - 1,
            "\n".join(body),
        )
        if unclosed:
            item.partial.append(_PARTIAL_UNCLOSED)
        items.append(item)
    return items


def _text_items(lines: Sequence[str], name: str, file_slug: str) -> list[Item]:
    items: list[Item] = []
    first: int | None = None
    for number, line in enumerate([*lines, ""], 1):
        if line.strip():
            first = number if first is None else first
        elif first is not None:
            body = "\n".join(lines[first - 1 : number - 1])
            identifier = f"{name}:{file_slug}:p{len(items) + 1}"
            items.append(Item(identifier, None, first, number - 1, body))
            first = None
    return items


def split_items(text: str, kind: str, name: str, file_slug: str) -> list[Item]:
    """The items of one file's text, in file order, ids unique within the file."""

    lines = text.split("\n")
    items = (_markdown_items if kind == "markdown" else _text_items)(lines, name, file_slug)
    for item in items:
        if "\ufffd" in item.text:
            item.partial.append(_PARTIAL_REPLACEMENT)
    return items


def suspect_reasons(text: str) -> list[str]:
    """Why a text is flagged, by the instruction audit's own lexical classes. Advisory: a text
    with no reason is not thereby safe."""

    reasons: list[str] = []
    hidden: dict[str, str] = {}
    previous = ""
    for char in text:
        why = instruction_audit.hidden_reason(char, previous)
        if why is not None:
            hidden.setdefault(f"U+{ord(char):04X}", why)
        previous = char
    reasons.extend(f"{why} ({point})" for point, why in sorted(hidden.items()))
    if any(p.search(line) for line in text.split("\n") for p in instruction_audit.OVERRIDE_PHRASES):
        reasons.append("an override phrase")
    return reasons


def display(text: str, limit: int | None = None) -> str:
    """`text` with every character outside printable ASCII escaped, as the instruction audit
    prints quoted text, cut at `limit` characters."""

    shown = instruction_audit.plain(text)
    return shown if limit is None or len(shown) <= limit else shown[: limit - 3] + "..."


def read_source(path: Path, kind: str | None) -> tuple[str, str, bytes]:
    """(kind, text, bytes) of one file, or an `SourceRefusal`."""

    shown = display(str(path))
    resolved = kind or KIND_BY_SUFFIX.get(path.suffix.lower())
    if resolved is None:
        raise SourceRefusal(
            "SOURCE_KIND_UNKNOWN",
            f"{shown} is not .md, .markdown, .txt or .text; name its kind with --as markdown "
            "or --as text, or convert it to markdown first",
        )
    try:
        data = path.read_bytes()
    except OSError as error:
        raise SourceRefusal("SOURCE_UNREADABLE", f"{shown}: {error.strerror or error}") from error
    try:
        text = textio.universal(textio.decode(data))
    except UnicodeDecodeError as error:
        raise SourceRefusal(
            "SOURCE_ENCODING", f"{shown} is not UTF-8 text ({error.reason})"
        ) from error
    if "\x00" in text:
        raise SourceRefusal("SOURCE_ENCODING", f"{shown} holds a NUL byte, so it is not text")
    return resolved, text, data


def relative_name(path: Path, base: Path) -> str:
    """The path as the manifest records it: relative to `base` with `/` where the file is under
    it, else its file name alone, so a manifest holds no machine's folder."""

    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.name


def _item_document(item: Item, source: int) -> dict[str, Any]:
    return {
        "id": item.id,
        "source": source,
        "heading": item.heading,
        "line_start": item.line_start,
        "line_end": item.line_end,
        "revision": item.revision,
        "text": item.text,
        "partial": item.partial,
        "suspect": suspect_reasons(item.text),
    }


def build(
    name: str,
    files: Sequence[Path],
    *,
    kind: str | None = None,
    converted: bool = False,
    base: Path,
) -> dict[str, Any]:
    """The manifest document for `files`, read in sorted order of the names recorded."""

    if not SLUG.fullmatch(name):
        raise SourceRefusal(
            "SOURCE_NAME_INVALID",
            f"--name {display(name)!r} is not lowercase letters, digits and -",
        )
    if not files:
        raise SourceRefusal("SOURCE_UNREADABLE", "no file was named")
    named = sorted((relative_name(path, base), path) for path in files)
    if len({recorded for recorded, _ in named}) != len(named):
        raise SourceRefusal("SOURCE_DUPLICATE", "one file was named twice")
    sources: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    slugs: dict[str, int] = {}
    for recorded, path in named:
        file_kind, text, data = read_source(path, kind)
        file_slug = _unique(slug(path.stem, "file"), slugs)
        found = split_items(text, file_kind, name, file_slug)
        if not found:
            raise SourceRefusal("SOURCE_EMPTY", f"{display(recorded)} holds no text to read")
        sources.append(
            {
                "file": recorded,
                "format": file_kind,
                "raw_sha256": hashlib.sha256(textio.fold(data)).hexdigest(),
                "bytes": len(textio.fold(data)),
                "converted": converted,
            }
        )
        items.extend(_item_document(item, len(sources) - 1) for item in found)
    return {
        "version": VERSION,
        "name": name,
        "partial": any(item["partial"] for item in items),
        "sources": sources,
        "items": items,
    }


def serialize(document: Mapping[str, Any]) -> bytes:
    """The manifest's bytes: sorted keys, two-space indent, UTF-8, LF, one final newline, no
    timestamp, so one input gives one file."""

    return (json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def schema(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((home.ROOT / "schemas" / name).read_text(encoding="utf-8"))
    return loaded


def load(path: Path) -> dict[str, Any]:
    """A manifest read and checked against its schema, or a `ValueError` with the defects."""

    try:
        document = json.loads(textio.read_text(path))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValueError(f"cannot be read as JSON ({error})") from error
    defects = schemacheck.validate(document, schema("sources-manifest.schema.json"))
    if not defects:
        count = len(document["sources"])
        defects = [
            f"$.items[{i}].source is not a source index"
            for i, item in enumerate(document["items"])
            if not 0 <= item["source"] < count
        ]
        seen: set[str] = set()
        for item in document["items"]:
            if item["id"] in seen:
                defects.append(f"id {item['id']} appears twice")
            seen.add(item["id"])
    if defects:
        raise ValueError("; ".join(defects[:5]))
    loaded: dict[str, Any] = document
    return loaded
