"""The explorable source: its header, and what its content may hold.

What this module decides: how a source file is read (a JSON header first, then an HTML fragment),
the header's rules (the schema `schemas/explorable-source.schema.json`, and beside it: `brief` is
required for a decision and refused for the other kinds, and is a bounded path), and which elements
and attributes a fragment may not hold: the elements the shell owns, and every attribute that
loads or sends anything but a fragment (`#...`) or a `data:` URL. The one exception is an `a`
element whose `href` is an `https:` URL, a citation, which `build` gives `rel` and
`referrerpolicy`. `check` reads a built page's content through the same scan, so that the two
agree.

What it does not decide: what the content says, whether a script is right, or the shell around
it, which `explorable_shell` holds. A scan is a static read: it cannot see an address that page
code builds when it runs.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from outcomebound_tools import home, paths, schemacheck, textio

__all__ = [
    "KINDS",
    "SOURCE_SUFFIX",
    "Finding",
    "Scan",
    "Source",
    "SourceRefusal",
    "page_name",
    "parse_source",
    "scan",
]

KINDS = ("decision", "learning", "interview")
SOURCE_SUFFIX = ".source.html"
HEADER_ATTRIBUTE = "data-explorable"
SCHEMA = home.ROOT / "schemas" / "explorable-source.schema.json"

# The elements the shell owns, which a source never holds.
FORBIDDEN_ELEMENTS = frozenset(
    {
        "html",
        "head",
        "body",
        "meta",
        "link",
        "base",
        "style",
        "form",
        "iframe",
        "object",
        "embed",
    }
)
# The attributes that load or send.
LOADING_ATTRIBUTES = (
    "src",
    "href",
    "xlink:href",
    "srcset",
    "srcdoc",
    "action",
    "formaction",
    "poster",
    "data",
    "ping",
    "cite",
    "background",
)
_CITATION = re.compile(r"https://[^\s/?#]", re.IGNORECASE)
_CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)
_HEADER_END = re.compile(r"</script[^>]*>", re.IGNORECASE)
# What a browser reads differently from this module's parser, or that can swallow the shell's
# own markup after the content: no comment, declaration, CDATA section or processing instruction
# anywhere after the header (script text included), and these elements and end tags.
_MARKUP_OPENERS = re.compile(r"<[!?]")
REFUSED_START = frozenset({"title", "plaintext", "xmp", "noembed", "noframes"})
REFUSED_END = frozenset({*FORBIDDEN_ELEMENTS, "title", "main"})
RESERVED_PREFIXES = ("explorable-", "brief-")
_CITATION_REL = ("noopener", "noreferrer")
_CITATION_POLICY = "no-referrer"


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing the scan refuses, and the line it is on."""

    line: int
    text: str


class SourceRefusal(ValueError):
    """A source `build` refuses. `findings` name each cause, a line each."""

    def __init__(self, findings: list[Finding]) -> None:
        super().__init__("; ".join(f"line {item.line}: {item.text}" for item in findings))
        self.findings = findings


@dataclass(slots=True)
class Scan:
    """What one pass over an HTML text found."""

    findings: list[Finding] = field(default_factory=list)
    # Each page script (not the header, not JSON data): its first line and its text.
    scripts: list[tuple[int, str]] = field(default_factory=list)
    # `(start, end, text)` of each citation's start tag, as `build` rewrites it.
    edits: list[tuple[int, int, str]] = field(default_factory=list)
    # Where the header's element ends, and its JSON text, with its first line.
    header_end: int | None = None
    header_text: str | None = None
    header_line: int = 1
    # The names of the `data-` attributes that appear, for what a kind needs.
    attributes: set[str] = field(default_factory=set)


def page_name(source: str) -> str | None:
    """The page's file name for a source's: the same without `.source`; None for any other."""

    if not source.endswith(SOURCE_SUFFIX) or source == SOURCE_SUFFIX:
        return None
    return source[: -len(SOURCE_SUFFIX)] + ".html"


def _normal(value: str) -> str:
    """A URL as a browser reads its start: tabs and line breaks gone, leading and trailing
    control characters and spaces stripped."""

    return re.sub(r"[\t\r\n]", "", value).strip("".join(chr(code) for code in range(33)))


class _Scanner(HTMLParser):
    def __init__(self, text: str, *, source: bool, first_line: int, reserved: bool) -> None:
        super().__init__(convert_charrefs=True)
        self.text = text
        self.source = source
        self.reserved = reserved
        self.first_line = first_line
        self.result = Scan()
        self.starts = [0]
        for found in re.finditer("\n", text):
            self.starts.append(found.end())
        self.begun = False
        self.unclosed_line = 1
        self._header_seen = False
        self._header: list[str] | None = None
        self._script: tuple[int, list[str]] | None = None

    # Positions.

    def unclosed(self) -> bool:
        """Whether a script element was opened and never closed."""

        if self._script is not None:
            self.unclosed_line = self._script[0]
        return self._script is not None

    def line(self) -> int:
        return self.getpos()[0] + self.first_line - 1

    def here(self) -> int:
        line, column = self.getpos()
        return self.starts[line - 1] + column

    def refuse(self, text: str) -> None:
        self.result.findings.append(Finding(self.line(), text))

    # Events.

    def _first(self, what: str) -> None:
        """In a source, nothing comes before the header."""

        if self.source and not self.begun:
            self.begun = True
            self.refuse(
                f"{what} comes before the header; the header is the first thing in a source"
            )

    def handle_decl(self, decl: str) -> None:
        self._first("a doctype")
        self.refuse("a doctype: the shell owns it")

    def unknown_decl(self, data: str) -> None:
        self.refuse("a declaration: the shell owns the document's frame")

    def handle_pi(self, data: str) -> None:
        self.refuse("a processing instruction")

    def handle_comment(self, data: str) -> None:
        self._first("a comment")

    def handle_data(self, data: str) -> None:
        if self._header is not None:
            self._header.append(data)
        elif self._script is not None:
            self._script[1].append(data)
        elif data.strip():
            self._first("text")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, closed=True)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, closed=False)

    def handle_endtag(self, tag: str) -> None:
        if tag in REFUSED_END:
            self.refuse(f"</{tag}> end tag: the shell owns it, and a source holds none")
        if tag != "script":
            return
        if self._header is not None:
            self.result.header_text = "".join(self._header)
            ended = _HEADER_END.match(self.text, self.here())
            self.result.header_end = ended.end() if ended else self.here()
            self._header = None
        elif self._script is not None:
            line, chunks = self._script
            self.result.scripts.append((line, "".join(chunks)))
            self._script = None

    def _start(self, tag: str, attrs: list[tuple[str, str | None]], *, closed: bool) -> None:
        names = {name for name, _ in attrs}
        header = tag == "script" and HEADER_ATTRIBUTE in names
        if self.source and not self.begun:
            self.begun = True
            if header:
                self._open_header(attrs, closed)
                return
            self.refuse(
                f"<{tag}> comes before the header; the header is the first thing in a source"
            )
        elif header and self._header_seen:
            self.refuse("a second header: a source has one header, `data-explorable`, first")
        self.result.attributes.update(name for name in names if name.startswith("data-"))
        if tag in FORBIDDEN_ELEMENTS or tag in REFUSED_START:
            self.refuse(f"<{tag}> element: the shell owns it, and a source holds none")
        for name, value in attrs:
            self._attribute(tag, name, value or "")
            if self.reserved:
                self._reserved(tag, name, value or "")
        if tag == "a":
            self._citation(attrs, closed)
        if tag == "script" and not closed and not _is_data(attrs):
            self._script = (self.line(), [])

    def _open_header(self, attrs: list[tuple[str, str | None]], closed: bool) -> None:
        kind = dict(attrs).get("type") or ""
        if kind.strip().lower() != "application/json":
            self.refuse('the header is `<script type="application/json" data-explorable>`')
        self._header_seen = True
        self.result.header_line = self.line()
        if not closed:
            self._header = []

    # Attributes.

    def _reserved(self, tag: str, name: str, value: str) -> None:
        """The names the shell, the brief drawing and the runtime own."""

        lowered = value.strip().lower()
        if name == "id" and lowered.startswith(RESERVED_PREFIXES):
            self.refuse(f"id={value!r} is a name the shell and the brief drawing own")
        elif name in ("id", "name") and lowered == "explorable":
            self.refuse(f"{name}={value!r} would shadow the runtime's `explorable` object")
        elif name == HEADER_ATTRIBUTE and tag != "script":
            self.refuse("data-explorable belongs to the header alone")

    def _attribute(self, tag: str, name: str, value: str) -> None:
        if name in LOADING_ATTRIBUTES:
            self._loading(tag, name, value)
        elif name == "style":
            self._style(value)

    def _loading(self, tag: str, name: str, value: str) -> None:
        candidates = re.split(r",\s+", value) if name == "srcset" else [value]
        for candidate in candidates:
            address = _normal(candidate.strip().split(" ")[0] if name == "srcset" else candidate)
            lowered = address.lower()
            if lowered.startswith("javascript:"):
                self.refuse(f"{name}={value!r} is a javascript: URL, which is refused everywhere")
            elif (
                address.startswith("#")
                or lowered.startswith("data:")
                or (tag == "a" and name == "href" and _CITATION.match(address))
            ):
                continue
            else:
                allowed = "a fragment (#...), a data: URL, or on an `a` an https: URL"
                self.refuse(f"{name}={value!r} loads or sends: it may hold only {allowed}")

    def _style(self, value: str) -> None:
        if "\\" in value or "image-set(" in value.lower():
            self.refuse("a style attribute holds a backslash or image-set(), which can hide a URL")
            return
        for found in _CSS_URL.finditer(value):
            address = _normal(found.group(2)).lower()
            if not address.startswith(("data:", "#")):
                self.refuse(
                    f"a style attribute holds url({found.group(2)!r}); only data: is allowed"
                )

    # Citations.

    def _citation(self, attrs: list[tuple[str, str | None]], closed: bool) -> None:
        given = dict(attrs)
        if not _CITATION.match(_normal(given.get("href") or "")):
            return
        if self.source:
            self.result.edits.append((self.here(), *self._rewrite(attrs, closed)))
            return
        tokens = (given.get("rel") or "").lower().split()
        if not all(word in tokens for word in _CITATION_REL):
            self.refuse('a citation (`a href="https:..."`) lacks rel="noopener noreferrer"')
        if (given.get("referrerpolicy") or "").lower() != _CITATION_POLICY:
            self.refuse('a citation (`a href="https:..."`) lacks referrerpolicy="no-referrer"')

    def _rewrite(self, attrs: list[tuple[str, str | None]], closed: bool) -> tuple[int, str]:
        """The end of the start tag at this position, and the tag as `build` writes it."""

        original = self.get_starttag_text() or ""
        kept = [(name, value) for name, value in attrs if name not in ("rel", "referrerpolicy")]
        words = [
            name if value is None else f'{name}="{_attribute_value(value)}"' for name, value in kept
        ]
        words += ['rel="noopener noreferrer"', 'referrerpolicy="no-referrer"']
        tag = "<a " + " ".join(words) + (" />" if closed else ">")
        return self.here() + len(original), tag


def _attribute_value(value: str) -> str:
    return html.escape(value, quote=False).replace('"', "&quot;")


def _is_data(attrs: list[tuple[str, str | None]]) -> bool:
    """Whether a script's `type` makes it data, not code."""

    kind = (dict(attrs).get("type") or "").strip().lower()
    return bool(kind) and kind not in ("text/javascript", "module", "application/javascript")


def scan(text: str, *, source: bool, first_line: int = 1, reserved: bool | None = None) -> Scan:
    """One pass over `text`. With `source`, the header must come first and is read, and each
    citation is queued for rewriting; otherwise `text` is a built page's content, and a citation
    must already carry what `build` gives it. `first_line` is the number of `text`'s first line.
    `reserved` (by default, `source`) also refuses the names the shell owns."""

    scanner = _Scanner(
        text,
        source=source,
        first_line=first_line,
        reserved=source if reserved is None else reserved,
    )
    scanner.feed(text)
    scanner.close()
    result = scanner.result
    if scanner.unclosed():
        result.findings.append(Finding(scanner.unclosed_line, "a script element is never closed"))
    start = (result.header_end or 0) if source else 0
    for found in _MARKUP_OPENERS.finditer(text, start):
        line = first_line + text.count("\n", 0, found.start())
        result.findings.append(
            Finding(
                line,
                f"`{found.group()}` opens a comment, declaration, CDATA section or processing "
                "instruction; a page needs none, and script code uses // or /* */",
            )
        )
    for found in re.finditer("\x00", text):
        line = first_line + text.count("\n", 0, found.start())
        result.findings.append(Finding(line, "a NUL character"))
    return result


def _header(raw: str, line: int) -> tuple[dict[str, Any], list[Finding]]:
    """The header's fields, and what refuses them."""

    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        return {}, [Finding(line, f"the header is not JSON ({error})")]
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceRefusal([Finding(1, f"the header schema cannot be read ({error})")]) from error
    defects = schemacheck.validate(document, schema)
    if defects:
        return {}, [Finding(line, f"the header breaks its schema: {item}") for item in defects]
    problems = []
    if document["kind"] == "decision" and "brief" not in document:
        problems.append("a decision's header names its brief document, `brief`")
    if document["kind"] != "decision" and "brief" in document:
        problems.append("only a decision's header holds `brief`")
    if "brief" in document and not paths.admits(document["brief"]):
        problems.append(
            "`brief` is a path relative to the source's folder and inside it: no `..`, "
            "no leading slash, no backslash, no `:`"
        )
    return document, [Finding(line, text) for text in problems]


@dataclass(frozen=True, slots=True)
class Source:
    """A source read: its header, its content with each citation given its `rel` and
    `referrerpolicy`, and the first line of the content."""

    header: dict[str, Any]
    content: str
    first_line: int


def parse_source(text: str) -> Source:
    """The source in `text`, or `SourceRefusal` naming each cause."""

    found = scan(text, source=True)
    findings = list(found.findings)
    header: dict[str, Any] = {}
    if found.header_text is None or found.header_end is None:
        if not findings:
            findings.append(
                Finding(
                    1,
                    "the source has no header: its first element is "
                    '`<script type="application/json" data-explorable>`',
                )
            )
    else:
        header, problems = _header(found.header_text, found.header_line)
        findings.extend(problems)
    if findings:
        raise SourceRefusal(sorted(findings, key=lambda item: item.line))
    if found.header_end is None:
        raise SourceRefusal([Finding(1, "the source has no header")])
    content = text
    for start, end, replacement in sorted(found.edits, reverse=True):
        content = content[:start] + replacement + content[end:]
    body = content[found.header_end :]
    skipped = len(body) - len(body.lstrip("\n"))
    first = text.count("\n", 0, found.header_end) + 1 + skipped
    return Source(header, body.strip("\n"), first)


def read_text(path: Path) -> str:
    """The source file's text, UTF-8 with any byte-order mark dropped and LF line ends."""

    return textio.read_text(path)
