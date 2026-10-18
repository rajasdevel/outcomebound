"""`outcomebound sources links`: report each reference in Markdown files that does not hold
(`docs/specs/sources/design.md`, "Links").

What this module decides: which references it reads (inline links and images, reference
definitions, `path:line` code spans, and a code span a word such as `commit` marks as a Git ref),
what makes each one broken, and what it lists as not checked instead (an external link, a target
outside the root, a ref where Git cannot be asked).

What it does not decide: whether a target still means what its text says, or whether a line holds
what a person meant. It reads files and runs no process but `git`, which it runs only to resolve
a ref. It writes nothing and opens no connection. Standard library only.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from outcomebound_tools import textio, tickets_git, tickets_links

VERSION = 1
MARKDOWN_SUFFIXES = (".md", ".markdown")

LINK_FILE_MISSING = "LINK_FILE_MISSING"
LINK_ANCHOR_MISSING = "LINK_ANCHOR_MISSING"
LINE_PAST_END = "LINE_PAST_END"
REF_MISSING = "REF_MISSING"
REF_UNRESOLVED = "REF_UNRESOLVED"

LIMITS = {
    LINK_FILE_MISSING: "that the file means what the link text says",
    LINK_ANCHOR_MISSING: "that the section under a heading says what the link text says",
    LINE_PAST_END: "that a line within the file holds what the reference meant",
    REF_MISSING: "that a file named by another path is not the one meant",
    REF_UNRESOLVED: "that a ref which resolves names the commit the text meant",
}
NEXT = {
    LINK_FILE_MISSING: "fix the path, or restore the file",
    LINK_ANCHOR_MISSING: "fix the anchor to a heading the file holds, or restore the heading",
    LINE_PAST_END: "re-read the file and cite a line it holds",
    REF_MISSING: "fix the path, or restore the file",
    REF_UNRESOLVED: "name a ref or commit this repository holds, or fetch it",
}

# A link ends in `](destination "title")`; the opening bracket is not matched, so that an image
# nested in a link text does not hide the outer link.
_DESTINATION = r"<[^<>\n]*>|(?:[^\s()\\<]|\\.|\([^\s()]*\))+"
_INLINE = re.compile(
    r"(?<!\\)\]\(\s*(?P<dest>" + _DESTINATION + r")"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)"
)
_DEFINITION = re.compile(r" {0,3}\[[^\]\n]+\]:[ \t]*(?P<dest>" + _DESTINATION + r")")
_AUTOLINK = re.compile(r"<(?P<dest>[A-Za-z][A-Za-z0-9+.-]*:[^<>\s]*)>")
_SPAN = re.compile(r"(?<!`)(?P<ticks>`+)(?!`)(?P<body>.+?)(?<!`)(?P=ticks)(?!`)")
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]+:")
_LINES = r"\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*"
_PATH_LINE = re.compile(r"(?P<path>\.{0,2}/?[A-Za-z0-9_.@+/-]+):(?P<lines>" + _LINES + r")")
_LINE_ANCHOR = re.compile(r"L(?P<first>\d+)(?:-L(?P<last>\d+))?", re.IGNORECASE)
_SOURCE_SUFFIXES = frozenset(
    (
        "py",
        "md",
        "json",
        "sh",
        "toml",
        "yml",
        "yaml",
        "txt",
        "js",
        "ts",
        "tsx",
        "jsx",
        "go",
        "rs",
        "c",
        "h",
        "cpp",
        "java",
        "rb",
        "html",
        "css",
        "mk",
        "cfg",
        "ini",
        "tmpl",
        "markdown",
    )
)
_REF_WORD = re.compile(r"\b(?:commit|ref|branch|tag|sha|rev)\s+(?:at\s+|of\s+)?$", re.IGNORECASE)
_REF_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/@~^{}-]*")
_SETEXT = re.compile(r" {0,3}(?:=+|-+)[ \t]*")
_HTML_TAG = re.compile(r"</?[A-Za-z][^<>]*>")
_HEADING_LINK = re.compile(r"!?\[(?P<text>[^\]]*)\]\([^)]*\)")


@dataclass(frozen=True, order=True)
class Item:
    """One reference that did not hold, or one that was not checked."""

    file: str
    line: int
    code: str
    target: str
    text: str

    @property
    def limit(self) -> str:
        return LIMITS.get(self.code, "")

    @property
    def next(self) -> str:
        return NEXT.get(self.code, "")


@dataclass
class Report:
    broken: list[Item] = field(default_factory=list)
    not_checked: list[Item] = field(default_factory=list)
    checked: int = 0

    @property
    def verdict(self) -> str:
        return "FAIL" if self.broken else "PASS"


class LinksRefusal(Exception):
    """A usage error: an input that is not there or cannot be read."""


def markdown_files(inputs: Iterable[Path]) -> list[Path]:
    """The Markdown files the inputs name: each file as given, each folder's `.md` and
    `.markdown` files, in path order. Symbolic links to folders and `.git` are not entered."""

    found: dict[str, Path] = {}
    for given in inputs:
        if given.is_dir():
            for directory, names, files in os.walk(given):
                names[:] = sorted(
                    n for n in names if n != ".git" and not os.path.islink(Path(directory, n))
                )
                for name in sorted(files):
                    if name.lower().endswith(MARKDOWN_SUFFIXES):
                        found.setdefault(str(Path(directory, name)), Path(directory, name))
        elif given.is_file():
            found.setdefault(str(given), given)
        else:
            raise LinksRefusal(f"{given.as_posix()} is not a file or a folder that is there")
    if not found:
        raise LinksRefusal("no Markdown file under the paths given")
    return [found[key] for key in sorted(found)]


def _read(path: Path) -> str:
    try:
        return textio.decode(path.read_bytes()).replace("\r\n", "\n")
    except (OSError, UnicodeDecodeError) as error:
        raise LinksRefusal(f"{path.as_posix()} could not be read ({error})") from error


def _blank_spans(line: str) -> tuple[str, list[re.Match[str]]]:
    """`line` with each code span replaced by spaces of its length, and the spans."""

    spans = list(_SPAN.finditer(line))
    text = line
    for span in spans:
        text = text[: span.start()] + " " * (span.end() - span.start()) + text[span.end() :]
    return text, spans


def _strip_markup(heading: str) -> str:
    """A heading line with link syntax and HTML tags reduced to the text GitHub slugs."""

    return _HTML_TAG.sub("", _HEADING_LINK.sub(lambda m: m.group("text"), heading))


def anchors_of(text: str) -> set[str]:
    """Every anchor the headings of `text` give, GitHub's way: `#` and setext headings outside a
    fence, a repeated slug suffixed `-1`, `-2`, in document order."""

    lines = text.split("\n")
    fenced = tickets_links.fenced_lines(text)
    atx = {index for index, _ in tickets_links.heading_slugs(text)}
    entries: list[tuple[int, str]] = [
        (index, tickets_links.anchor_of(_strip_markup(lines[index]))) for index in sorted(atx)
    ]
    start = 0
    if lines and lines[0].strip() == "---":
        start = next((i + 1 for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
    for index in range(max(start, 1), len(lines)):
        previous = lines[index - 1]
        if (
            _SETEXT.fullmatch(lines[index])
            and not fenced[index]
            and not fenced[index - 1]
            and index - 1 not in atx
            and previous.strip()
            and not _SETEXT.fullmatch(previous)
            and not previous.lstrip().startswith((">", "-", "*", "+", "|"))
            and "|" not in previous
        ):
            entries.append((index - 1, tickets_links.anchor_of(_strip_markup(previous))))
    seen: dict[str, int] = {}
    anchors: set[str] = set()
    for _, slug in sorted(entries):
        if not slug:
            continue
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def _line_count(data: bytes) -> int:
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


class _Checker:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.real_root = root.resolve()
        self.report = Report()
        self._anchors: dict[Path, set[str] | None] = {}
        self._counts: dict[Path, int] = {}
        self._refs: dict[str, bool | None] = {}
        self._repository: bool | None = None

    # -- paths ------------------------------------------------------------------------------

    def _inside(self, path: Path) -> Path | None:
        """`path` resolved, where it is under the root; else None."""

        try:
            resolved = path.resolve()
            resolved.relative_to(self.real_root)
        except (OSError, ValueError, RuntimeError):
            return None
        return resolved

    def _exact(self, path: Path) -> bool:
        """Whether `path` exists with the case written, as a case-sensitive checkout has it."""

        try:
            parts = Path(os.path.normpath(path)).relative_to(Path(os.path.normpath(self.root)))
        except ValueError:
            return path.exists()
        here = self.root
        for part in parts.parts:
            if part == "..":
                return path.exists()
            try:
                if part not in os.listdir(here):
                    return False
            except OSError:
                return False
            here = here / part
        return here.exists()

    def _count(self, path: Path) -> int | None:
        if path not in self._counts:
            try:
                self._counts[path] = _line_count(path.read_bytes())
            except OSError:
                return None
        return self._counts[path]

    def _anchors_for(self, path: Path) -> set[str] | None:
        if path not in self._anchors:
            try:
                self._anchors[path] = anchors_of(
                    textio.decode(path.read_bytes()).replace("\r\n", "\n")
                )
            except (OSError, UnicodeDecodeError):
                self._anchors[path] = None
        return self._anchors[path]

    # -- results ----------------------------------------------------------------------------

    def _fail(self, file: str, line: int, code: str, target: str, text: str) -> None:
        self.report.broken.append(Item(file, line, code, target, text))

    def _skip(self, file: str, line: int, kind: str, target: str, text: str) -> None:
        self.report.not_checked.append(Item(file, line, kind, target, text))

    # -- references -------------------------------------------------------------------------

    def link(self, doc: Path, name: str, line: int, raw: str) -> None:
        target = raw[1:-1] if raw.startswith("<") and raw.endswith(">") else raw
        target = re.sub(r"\\(.)", r"\1", target).strip()
        if not target:
            return
        if _SCHEME.match(target) or target.startswith("//"):
            self._skip(name, line, "external", target, "an external link is not opened")
            return
        path_part, _, fragment = target.partition("#")
        path_part = unquote(path_part.partition("?")[0])
        fragment = unquote(fragment)
        if not path_part:
            destination = doc
        else:
            base = self.root if path_part.startswith("/") else doc.parent
            destination = base / path_part.lstrip("/")
        inside = self._inside(destination)
        if inside is None:
            self._skip(name, line, "outside_root", target, "the target is outside --root")
            return
        self.report.checked += 1
        if path_part and not self._exact(destination):
            self._fail(name, line, LINK_FILE_MISSING, target, "no such file or folder")
            return
        if fragment and inside.is_file():
            self._fragment(name, line, target, fragment, inside)

    def _fragment(self, name: str, line: int, target: str, fragment: str, file: Path) -> None:
        if file.name.lower().endswith(MARKDOWN_SUFFIXES):
            anchors = self._anchors_for(file)
            if anchors is None:
                self._skip(name, line, "unreadable", target, "the file is not readable text")
            elif fragment.lower() not in anchors:
                self._fail(
                    name, line, LINK_ANCHOR_MISSING, target, f"no heading anchors #{fragment}"
                )
            return
        wanted = _LINE_ANCHOR.fullmatch(fragment)
        if wanted:
            last = int(wanted.group("last") or wanted.group("first"))
            self._lines(name, line, target, file, max(int(wanted.group("first")), last))

    def _lines(self, name: str, line: int, target: str, file: Path, last: int) -> None:
        count = self._count(file)
        if count is not None and last > count:
            self._fail(name, line, LINE_PAST_END, target, f"line {last}, but the file has {count}")

    def path_line(self, doc: Path, name: str, line: int, body: str) -> None:
        match = _PATH_LINE.fullmatch(body)
        if match is None:
            return
        path = match.group("path")
        suffix = path.rsplit(".", 1)[-1].lower() if "." in Path(path).name else ""
        if "/" not in path and suffix not in _SOURCE_SUFFIXES:
            return
        numbers = [int(n) for n in re.findall(r"\d+", match.group("lines"))]
        if min(numbers) < 1:
            return
        for base in (self.root, doc.parent):
            candidate = base / path.lstrip("/")
            if self._exact(candidate) and candidate.is_file():
                inside = self._inside(candidate)
                if inside is None:
                    self._skip(name, line, "outside_root", body, "the path is outside --root")
                    return
                self.report.checked += 1
                self._lines(name, line, body, inside, max(numbers))
                return
        if self._inside(self.root / path.lstrip("/")) is None:
            self._skip(name, line, "outside_root", body, "the path is outside --root")
            return
        if "/" not in path:
            self._skip(name, line, "unresolved_name", body, "a bare file name that is not found")
            return
        self.report.checked += 1
        self._fail(name, line, REF_MISSING, body, "no such file")

    def ref(self, name: str, line: int, ref: str) -> None:
        if not _REF_NAME.fullmatch(ref):
            return
        if self._repository is None:
            try:
                self._repository = tickets_git.git(self.root, "rev-parse", "--git-dir").status == 0
            except tickets_git.GitError:
                self._repository = False
        if not self._repository:
            self._skip(name, line, "git_unavailable", ref, "Git cannot be asked here")
            return
        if ref not in self._refs:
            self._refs[ref] = (
                tickets_git.git(
                    self.root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"
                ).status
                == 0
            )
        self.report.checked += 1
        if not self._refs[ref]:
            self._fail(name, line, REF_UNRESOLVED, ref, "names no commit in this repository")

    # -- one file ---------------------------------------------------------------------------

    def file(self, doc: Path) -> None:
        text = _read(doc)
        name = doc.as_posix()
        fenced = tickets_links.fenced_lines(text)
        for number, line in enumerate(text.split("\n"), start=1):
            if fenced[number - 1]:
                continue
            blanked, spans = _blank_spans(line)
            for span in spans:
                body = span.group("body").strip()
                self.path_line(doc, name, number, body)
                if _REF_WORD.search(line[: span.start()]):
                    self.ref(name, number, body)
            definition = _DEFINITION.match(blanked)
            if definition:
                self.link(doc, name, number, definition.group("dest"))
            for match in _INLINE.finditer(blanked):
                self.link(doc, name, number, match.group("dest"))
            for match in _AUTOLINK.finditer(blanked):
                self.link(doc, name, number, match.group("dest"))


def check(inputs: Sequence[Path], root: Path) -> Report:
    checker = _Checker(root)
    for doc in markdown_files(inputs):
        checker.file(doc)
    checker.report.broken.sort()
    checker.report.not_checked.sort()
    return checker.report


def exit_code(report: Report) -> int:
    return 1 if report.broken else 0


def _counts(report: Report) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in report.not_checked:
        counts[item.code] = counts.get(item.code, 0) + 1
    return counts


def _safe(text: str) -> str:
    """`text` with each character outside printable ASCII escaped, so a target copied from a
    file cannot carry a control character into a terminal."""

    return textio.visible(text)


def render_text(report: Report, *, verbose: bool = False) -> str:
    lines = [
        f"{_safe(item.file)}:{item.line}: {item.code} {_safe(item.target)}: {item.text}. "
        f"Does not establish: {item.limit}. next: {item.next}."
        for item in report.broken
    ]
    counts = _counts(report)
    if counts:
        lines.append(
            "not checked: "
            + ", ".join(f"{n} {kind}" for kind, n in sorted(counts.items()))
            + " (no network is opened; Git or the root bounds the rest)."
        )
    if verbose:
        lines.extend(
            f"not checked {_safe(item.file)}:{item.line}: {item.code} "
            f"{_safe(item.target)}: {item.text}."
            for item in report.not_checked
        )
    lines.append(
        f"VERDICT: {report.verdict}; {len(report.broken)} broken, "
        f"{len(report.not_checked)} not checked, {report.checked} checked"
    )
    return "\n".join(lines) + "\n"


def render_json(report: Report) -> str:
    def row(item: Item, *, with_limit: bool) -> dict[str, object]:
        entry: dict[str, object] = {
            "file": item.file,
            "line": item.line,
            "code": item.code,
            "target": item.target,
            "text": item.text,
        }
        if with_limit:
            entry["does_not_establish"] = item.limit
            entry["next"] = item.next
        return entry

    document = {
        "version": VERSION,
        "verdict": report.verdict,
        "counts": {
            "broken": len(report.broken),
            "not_checked": len(report.not_checked),
            "checked": report.checked,
        },
        "broken": [row(item, with_limit=True) for item in report.broken],
        "not_checked": [row(item, with_limit=False) for item in report.not_checked],
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"
