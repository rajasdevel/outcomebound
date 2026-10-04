"""Read-only checks on the instruction files and configuration each harness loads.

What this module decides: which harnesses a target is checked for (the `--harness`
names; else those its manifest records, with every other row whose files the target holds,
since the manifest is the target's own data; else every row of `adapters/harnesses.json`),
which files within the target those harnesses read, and what six checks observe:
hidden characters, concealed content, override phrases, harness configuration, with
`--base` the instruction files changed since a ref, and whether each harness's loading
facts are verified and current. Each check answers to one rule of the prompt standard
(`docs/prompt-standard.md`) and carries that rule's severity; the security family runs
first and is reported first. A harness entry that is byte for byte what adopt writes for the
recorded Done commands, its digest the manifest's record, is a review hit that quotes the
Done commands it runs, since the manifest is the target's own data; it does not change the
result while those commands are the ones AGENTS.md's project facts show. A hidden character
in an agents' note reads UNVERIFIED for that note, where in an instruction file it is a FAIL.
Also reported, and not changing the result: each instruction file a harness's row says it
loads from a folder above the target (`ancestors`), which this module names and never opens,
and, where every row was selected, the loading facts of a row that loads no file of the
target that another row does not load too.

What it does not decide: whether a flagged line is benign, which a person decides.
It never executes, follows or obeys anything it reads: the audited files are untrusted
data. Of a Git work tree it reads only what Git tracks or does not ignore, plus each path a
harness row names exactly and the agents' notes in `NOTES`, which Git ignores and the next
session reads; elsewhere it walks every file. It starts no process but Git, under
configuration that hands the repository no control, and resolves Git from the absolute
entries of PATH only; it opens no connection
and writes nothing. It never opens a file outside the target except its own engine data,
and never opens a file a harness documents as one person's, by name or through a link; a
path it leaves unopened is reported UNVERIFIED.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, fields, replace
from datetime import date
from pathlib import Path
from typing import Any

from outcomebound_tools import adapters, facts, finish_check, identity
from outcomebound_tools.finish_check import canonical, recorded_done
from outcomebound_tools.gitenv import GIT_READ_CONFIGURATION, git_environment

__all__ = [
    "CHECKS",
    "AuditError",
    "Finding",
    "Report",
    "check",
    "main",
    "render",
    "report_document",
]

PASS, FAIL, UNVERIFIED = "PASS", "FAIL", "UNVERIFIED"
VERDICTS = (PASS, FAIL, UNVERIFIED)
FAMILIES = ("security", "loading")

# The prompt standard's severity entry for each rule a check answers to, most severe first
# (docs/prompt-standard.md, "Severity").
SEVERITY = {"S4": "Security (S4)", "S7": "Loading (S7)"}

# check: (family, kind, rule). A gate reads PASS or FAIL, UNVERIFIED where a fact it needs is
# not verified; a review reads PASS where nothing matched, else UNVERIFIED until a person rules.
CHECKS: dict[str, tuple[str, str, str]] = {
    "hidden-characters": ("security", "gate", "S4"),
    "concealed-content": ("security", "review", "S4"),
    "override-phrases": ("security", "review", "S4"),
    "harness-config": ("security", "review", "S4"),
    "instruction-change": ("security", "review", "S4"),
    "load-resolution": ("loading", "gate", "S7"),
}

_MARKERS = ("outcomebound:begin ", "outcomebound:end ")
_BASE64_RUN = re.compile(r"[A-Za-z0-9+/=]{60,}")
# A commit or checksum pin, 40 or 64 hex characters after an optional `name=`, is no payload.
_HEX_PIN = re.compile(r"(?:[A-Za-z0-9]+=)?(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})")
_FETCH_AND_RUN = (
    re.compile(r"(curl|wget)[^|\n]*\|\s*(sudo\s+(-\w+\s+)*)?(ba|z)?sh\b"),
    re.compile(r"((ba|z)?sh\s+-c|eval)\s+[\"']?\$\(\s*(curl|wget)"),
    re.compile(r"bash\s+<\(\s*(curl|wget)"),
    re.compile(r"iex\s*\(\s*(irm|iwr)"),
)
_OVERRIDE_PHRASES = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore (all |any )?(the )?(previous|prior|above|earlier) instructions",
        r"disregard (the |all |any )?(previous|prior|above|system) ",
        r"do not (tell|inform|show) the (user|operator)",
        r"keep (this|these) (secret|hidden)",
        r"you (have|are granted) (full|unrestricted) (autonomy|permission|access)",
        r"remember (this|that) (for|in) (all )?(future|later) (sessions|conversations)",
    )
)
_SECRETS = (
    ("a private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("a `gh?_` token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("an `AKIA` access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("an `xox?-` token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("an `sk-` key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
)
_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s<>()\[\]\"'`]+")
# A code span: a backtick run and the next run of the same length, which CommonMark lets wrap
# across lines within one paragraph.
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
_FENCE = re.compile(r" {0,3}(`{3,}|~{3,})")
_BLOCK_START = re.compile(r"\s*(?:[-*+]\s|\d+[.)]\s|#{1,6}\s|>|\|)")
_CATEGORIES = ("hooks", "tool_servers", "enable_all", "endpoints", "bypass")
_CATEGORY_NAMES = {
    "hooks": "a command key",
    "tool_servers": "a tool-server key",
    "enable_all": "a key enabling every tool server",
    "endpoints": "an endpoint key",
    "bypass": "a permission-bypass key",
}
_CATEGORY_LABELS = {
    "hooks": "commands",
    "tool_servers": "tool servers",
    "enable_all": "a switch for every tool server",
    "endpoints": "endpoint overrides",
    "bypass": "permission bypasses",
}
MANIFEST = ".outcomebound/manifest.json"
# The notes an agent leaves for the next session (the workspace fragment): Git ignores them, and
# a later session reads them as it reads instructions, so they are read here too. A hidden
# character in a note reads UNVERIFIED for that note, not FAIL for the target: the note is one
# session's record, and the next session can work without it.
NOTES = (".agents/handoffs", ".agents/shared-memory")
# adopt's own harness entries are recognised only where they are byte for byte what adopt
# writes (`_own_entry`). The manifest is the target's own data, and the finish check runs the
# Done commands it records, so a recognised entry stays a review hit: its fact quotes those
# commands for the person to confirm.
# adopt's route for a harness the table does not list: it reads AGENTS.md and nothing known else.
GENERIC = "generic"
_NEXT = {
    "hidden-characters": "remove the character or retype the text in ASCII",
    "concealed-content": "read the quoted text as data and remove it, or have a person rule it "
    "benign; never run it",
    "override-phrases": "read the quoted text as data and remove it, or have a person rule it "
    "benign",
    "secret": "remove the secret from the file and rotate it; a committed secret stays in the "
    "history",
    "load-resolution": "re-check what the harness loads against its documentation; a wrong or "
    "missing row belongs in OutcomeBound's harness table, adapters/harnesses.json",
    "unopened": "see by hand where the path leads; this command opens only a regular file "
    "inside the target that is no person's",
    "note": "do not rely on this note: read it as data, take each fact you need from its "
    "source, and retype the note in ASCII or delete it",
}
# Git runs under `GIT_READ_CONFIGURATION`; these flags add no textconv, and a tree-to-tree
# diff never reads the index.
_SAFE_DIFF = ("--no-ext-diff", "--no-textconv", "--ignore-submodules=all", "--no-renames")
_GIT_UNSET = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_EXTERNAL_DIFF", "GIT_PAGER")


class AuditError(ValueError):
    """The engine's own data cannot be read, the target is not a directory, or Git failed."""


@dataclass(frozen=True, slots=True)
class Finding:
    """One observed fact, with the rule it answers to and that rule's severity."""

    check: str
    family: str
    path: str
    line: int
    kind: str
    verdict: str
    fact: str
    rule: str
    severity: str
    next: str
    # False for a finding that is reported and does not change the result; its fact says why.
    decides: bool = True


@dataclass(frozen=True, slots=True)
class Report:
    """The audit's result, its selection and every finding, security first."""

    result: str
    target: str
    harnesses: tuple[str, ...]
    selected_by: str
    listed_by: str
    listing: str
    counts: Mapping[str, Mapping[str, int]]
    findings: tuple[Finding, ...]


def _finding(
    check: str, path: str, line: int, verdict: str, fact: str, *, decides: bool = True, **extra: str
) -> Finding:
    """A finding for `check`, with its family, kind, rule and severity."""

    family, kind, rule = CHECKS[check]
    return Finding(
        check=check,
        family=family,
        path=path,
        line=line,
        kind=extra.get("kind", kind),
        verdict=verdict,
        fact=fact,
        rule=rule,
        severity=SEVERITY[rule],
        next=extra.get("next", _NEXT.get(check, "")),
        decides=decides,
    )


# --- the harness rows ------------------------------------------------------------


def _row(harness: str) -> dict[str, Any] | None:
    row = adapters.table().get(harness)
    return row if isinstance(row, dict) else None


def _today() -> date:
    return date.today()


def _row_state(harness: str, row: Mapping[str, Any] | None, today: date) -> tuple[str, str] | None:
    """Why a row's loading facts read UNVERIFIED, and the next step; None where they are
    current."""

    step = _NEXT["load-resolution"]
    if row is None and harness == GENERIC:
        fact = (
            "generic stands for any harness that reads AGENTS.md; what else it loads is UNVERIFIED"
        )
        return fact, step
    if row is None:
        return (
            f"no row of adapters/harnesses.json names {harness}; what it loads is UNVERIFIED",
            step,
        )
    if row.get("verified") is not True:
        return f"the {harness} row is not verified; its loading facts read UNVERIFIED", step
    recheck = row.get("recheck_on")
    if not isinstance(recheck, str):
        return (
            f"the {harness} row records no re-check date; its loading facts read UNVERIFIED",
            step,
        )
    if recheck < today.isoformat():
        verified = row.get("verified_on") or "a date the row does not record"
        fact = (
            f"the {harness} row's loading facts were verified on {verified}; only their "
            f"re-check, due {recheck}, is outstanding, so they read UNVERIFIED"
        )
        overdue = (
            f"take the row as verified on {verified} and go on with the work; the re-check "
            "compares the harness's documentation with OutcomeBound's adapters/harnesses.json"
        )
        return fact, overdue
    return None


def ancestor_files(target: Path, harness: str) -> list[tuple[Path, str]]:
    """The instruction files `harness` loads at session start from the folders above `target`,
    nearest first, as its row's `ancestors` records; none where the row records none. A name
    ending in `AGENTS.md` loads only where none of the row's `reads_agents_md` files is in
    `target` or above it, the default setting. The person's own `~/.claude/CLAUDE.md` is user
    memory, not a folder's instructions, and is left out. Each is (the folder, the name under
    it); only existence is looked at, and no file is opened."""

    row = _row(harness) or {}
    record = row.get("ancestors")
    if not isinstance(record, dict) or record.get("loads") is not True:
        return []
    names = [name for name in record.get("names") or [] if isinstance(name, str)]
    unless = ((row.get("reads_agents_md") or {}).get("unless")) or []
    home = Path.home().resolve()
    root = Path(target).resolve()

    def present(folder: Path, name: str) -> bool:
        return not (folder == home and name == ".claude/CLAUDE.md") and (folder / name).is_file()

    hidden = any(present(folder, name) for folder in (root, *root.parents) for name in unless)
    return [
        (folder, name)
        for folder in root.parents
        for name in names
        if present(folder, name) and not (hidden and name.endswith("AGENTS.md"))
    ]


def _ancestors(root: Path, harnesses: Sequence[str]) -> list[Finding]:
    """One finding per instruction file a selected harness loads from above the target: it is
    reported, never opened, and does not change the result, since it lies outside the target."""

    found = []
    for harness in harnesses:
        for above, name in ancestor_files(root, harness):
            folder = os.path.relpath(above, root).replace(os.sep, "/")
            relative = f"{folder}/{name}"
            fact = (
                f"{harness} also loads {relative} at session start, from a folder above the "
                "target (its row's ancestors); this check does not read it, and the paths it "
                "names resolve from that folder, not from the target, which is all this check "
                "reads"
            )
            step = (
                f"run outcomebound instructions check {folder} to read it, or work where no "
                f"folder above holds instructions for {harness}"
            )
            found.append(
                _finding(
                    "load-resolution",
                    relative,
                    0,
                    UNVERIFIED,
                    fact,
                    kind="review",
                    next=step,
                    decides=False,
                )
            )
    return found


def _glob_pattern(glob: str) -> re.Pattern[str]:
    """A target-relative glob as a regular expression: `**/` spans directories."""

    out, index = [], 0
    while index < len(glob):
        if glob.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
        elif glob.startswith("**", index):
            out.append(".*")
            index += 2
        elif glob[index] == "*":
            out.append("[^/]*")
            index += 1
        elif glob[index] == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(glob[index]))
            index += 1
    return re.compile("".join(out) + r"\Z")


@dataclass(frozen=True, slots=True)
class _Scope:
    exact: frozenset[str]
    patterns: tuple[re.Pattern[str], ...]
    person: frozenset[str]
    config: Mapping[str, tuple[str, ...]]

    def personal(self, relative: str) -> bool:
        return relative in self.person or relative.rsplit("/", 1)[-1] in self.person

    def wants(self, relative: str) -> bool:
        if self.personal(relative):
            return False
        return relative in self.exact or any(p.match(relative) for p in self.patterns)


def _person_files() -> frozenset[str]:
    """Every file any row documents as one person's, never opened whoever is selected."""

    names: set[str] = set()
    for row in adapters.table().values():
        for override in row.get("overrides", []) if isinstance(row, dict) else []:
            if override.get("owner") == "person":
                names.add(str(override["path"]))
                names.add(str(override["path"]).rsplit("/", 1)[-1])
    return frozenset(names)


def _row_scope(row: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """The exact paths and the globs one row says its harness reads."""

    exact = [read["path"] for read in row.get("reads", [])]
    exact += [str(r["import"]).lstrip("@") for r in row.get("reads", []) if r.get("import")]
    exact += [o["path"] for o in row.get("overrides", []) if o.get("owner") == "project"]
    exact += list((row.get("config") or {}).get("paths", []))
    nested = row.get("nested") or {}
    globs = list(nested.get("globs", [])) if nested.get("loads") is not False else []
    for directory in (row.get("skill_install_path"), row.get("rules_path")):
        if directory:
            base = str(directory).rstrip("/")
            globs += [f"{base}/**/*.md", f"{base}/**/*.mdc"]
    return exact, globs


def _scope(harnesses: Sequence[str]) -> _Scope:
    exact: set[str] = set()
    globs: set[str] = set()
    config: dict[str, list[str]] = {}
    for harness in harnesses:
        row = _row(harness)
        if row is None:
            continue
        paths, patterns = _row_scope(row)
        exact.update(paths)
        globs.update(patterns)
        for path in (row.get("config") or {}).get("paths", []):
            config.setdefault(path, []).append(harness)
    return _Scope(
        exact=frozenset(exact),
        patterns=tuple(_glob_pattern(glob) for glob in sorted(globs)),
        person=_person_files(),
        config={path: tuple(names) for path, names in config.items()},
    )


# --- reading safely ----------------------------------------------------------------


def _inside(root: Path, candidate: Path) -> bool:
    """Whether `candidate`, links resolved, is a regular file under `root`."""

    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    return resolved.is_relative_to(root) and resolved.is_file()


def _unopened(root: Path, relative: str, scope: _Scope) -> str | None:
    """Why the file at `relative` is left unopened, or None where it may be read: it must
    resolve, links followed, to a regular file inside `root` that is no person's."""

    try:
        resolved = (root / relative).resolve(strict=True)
    except (OSError, RuntimeError):
        return "a link that resolves to nothing; not opened"
    if not resolved.is_relative_to(root):
        return "a link out of the target; not opened, so what it loads is UNVERIFIED"
    target = resolved.relative_to(root).as_posix()
    if scope.personal(target):
        return f"a link to {target}, one person's file; not opened"
    if not resolved.is_file():
        return "not a regular file; not opened"
    return None


def _listed(root: Path) -> tuple[list[str] | None, str]:
    """What Git tracks, or holds untracked and unignored, under `root`; or None, and why the
    files are walked instead. A nested repository's files are not listed."""

    walked = "every file under the target was walked"
    try:
        inside, answer, _ = _git_status(root, "rev-parse", "--is-inside-work-tree")
        if inside != 0 or answer.strip() != b"true":
            return None, f"not a Git work tree, so {walked}"
        ignored, _, _ = _git_status(root, "check-ignore", "-q", ".")
        if ignored == 0:
            return None, f"in a directory its Git repository ignores, so {walked}"
        raw = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    except AuditError:
        return None, f"not listed by Git, so {walked}"
    paths = {os.fsdecode(item) for item in raw.split(b"\0") if item and not item.endswith(b"/")}
    return sorted(paths), "what Git tracks or does not ignore"


def _walk(root: Path, scope: _Scope, listed: Sequence[str] | None) -> list[str]:
    """Every path in scope under `root`, a link or not: of those Git lists, or, where `listed`
    is None, of every file, nested repositories and `.git` not entered. A path the scope names
    exactly is looked up too, ignored or under a linked directory."""

    found: list[str] = [path for path in listed or () if scope.wants(path)]
    for directory, dirnames, filenames in os.walk(root) if listed is None else ():
        here = Path(directory)
        dirnames[:] = sorted(
            name for name in dirnames if name != ".git" and not (here / name / ".git").exists()
        )
        found.extend(
            relative
            for name in sorted(filenames)
            if scope.wants(relative := (here / name).relative_to(root).as_posix())
        )
    exact = [path for path in sorted(scope.exact) if scope.wants(path)]
    return sorted(path for path in {*found, *exact} if os.path.lexists(root / path))


def _notes(root: Path) -> list[str]:
    """Every file in the note folders, nested repositories and `.git` not entered; a folder
    reached through a link, at the top or below, is listed itself, so it reads UNVERIFIED
    unopened."""

    found: list[str] = []
    for folder in NOTES:
        if not (root / folder).is_dir():
            continue
        if any((root / part).is_symlink() for part in (".agents", folder)):
            found.append(folder)
            continue
        for directory, dirnames, filenames in os.walk(root / folder):
            here = Path(directory)
            linked = sorted(name for name in dirnames if (here / name).is_symlink())
            dirnames[:] = sorted(
                name
                for name in dirnames
                if name not in linked and name != ".git" and not (here / name / ".git").exists()
            )
            found.extend(
                (here / name).relative_to(root).as_posix() for name in [*linked, *filenames]
            )
    return found


def _read(root: Path, relative: str) -> tuple[str | None, str]:
    """The file's text, or None and why no check could read it. Opened only after `_inside`."""

    try:
        data = (root / relative).read_bytes()
    except OSError as error:
        return None, f"not read ({error.strerror or error}); no check read it"
    try:
        return data.decode("utf-8"), ""
    except UnicodeDecodeError:
        return None, "not UTF-8 text; no check read it"


def _plain(text: str) -> str:
    """Text with every character outside printable ASCII escaped, so nothing hides or steers
    the terminal it is printed to."""

    return "".join(
        c if " " <= c <= "~" else (f"\\u{ord(c):04x}" if ord(c) <= 0xFFFF else f"\\U{ord(c):08x}")
        for c in text
    )


def _quote(text: str, limit: int = 160) -> str:
    """Quoted text, escaped as `_plain` escapes it and cut at `limit` characters."""

    shown = _plain(text.strip())
    if len(shown) > limit:
        shown = shown[: limit - 3] + "..."
    return f'"{shown}"'


def _lines(text: str) -> Iterator[tuple[int, str]]:
    for number, line in enumerate(text.split("\n"), 1):
        yield number, line.rstrip("\r")


# --- the security checks -----------------------------------------------------------


def _describe(c: str) -> str:
    return f"U+{ord(c):04X} {unicodedata.name(c, 'UNNAMED')} ({unicodedata.category(c)})"


def _hidden_reason(c: str, before: str) -> str | None:
    """Why one character is hidden, or None where it may stand."""

    point, category = ord(c), unicodedata.category(c)
    if 0xE0000 <= point <= 0xE007F:
        return "a tag character"
    if 0xFE00 <= point <= 0xFE0F or 0xE0100 <= point <= 0xE01EF:
        after_symbol = point == 0xFE0F and bool(before) and unicodedata.category(before) == "So"
        return None if after_symbol else "a variation selector"
    if category in ("Cf", "Co", "Cs", "Cn"):
        return "an invisible or unassigned character"
    if category.startswith("M") and before and ord(before) < 128:
        return "a combining mark after an ASCII character"
    return None


def _urls(line: str) -> Iterator[tuple[int, str]]:
    """(start, text) for each URL in a line, trailing punctuation left out."""

    for match in _URL.finditer(line):
        span = match.group(0)
        while span and unicodedata.category(span[-1]).startswith("P"):
            span = span[:-1]
        yield match.start(), span


def _blocks(lines: Sequence[tuple[int, str]]) -> Iterator[list[tuple[int, str]]]:
    """The paragraphs a code span can wrap within: runs of lines outside fenced code, split at
    a blank line and where a list item, heading, quote or table row starts."""

    block: list[tuple[int, str]] = []
    fence = ""
    for number, line in lines:
        opening = _FENCE.match(line)
        if fence:
            if opening and opening.group(1)[0] == fence[0] and len(opening.group(1)) >= len(fence):
                fence = "" if not line[opening.end() :].strip() else fence
            continue
        if opening or not line.strip() or (block and _BLOCK_START.match(line)):
            yield block
            block = []
            fence = opening.group(1) if opening else ""
            if opening or not line.strip():
                continue
        block.append((number, line))
    yield block


def _span_characters(lines: Sequence[tuple[int, str]]) -> Iterator[tuple[int, int, str]]:
    """(line, column, character) for each non-ASCII character inside a code span."""

    for block in _blocks(lines):
        starts, offset = [], 0
        for _number, line in block:
            starts.append(offset)
            offset += len(line) + 1
        joined = "\n".join(line for _number, line in block)
        for match in _CODE_SPAN.finditer(joined):
            for index in range(match.start(), match.end()):
                if ord(joined[index]) > 127:
                    row = bisect.bisect_right(starts, index) - 1
                    yield block[row][0], index - starts[row], joined[index]


def _hidden_characters(path: str, text: str) -> list[Finding]:
    lines = list(_lines(text))
    facts: dict[int, list[str]] = {number: [] for number, _line in lines}
    reported: set[tuple[int, int]] = set()

    def report(number: int, column: int, fact: str) -> None:
        if (number, column) not in reported:
            reported.add((number, column))
            facts[number].append(fact)

    for number, line in lines:
        for column, c in enumerate(line):
            reason = _hidden_reason(c, line[column - 1] if column else "")
            if reason:
                report(number, column, f"{_describe(c)}: {reason}")
        for start, url in _urls(line):
            for offset, c in enumerate(url):
                if ord(c) > 127:
                    report(
                        number,
                        start + offset,
                        f"{_describe(c)}: a non-ASCII character inside a URL",
                    )
    for number, column, c in _span_characters(lines):
        report(number, column, f"{_describe(c)}: a non-ASCII character inside a code span")
    return [
        _finding("hidden-characters", path, number, FAIL, fact)
        for number, found in facts.items()
        for fact in found
    ]


def _is_marker(line: str) -> bool:
    """A line that is only one of OutcomeBound's managed-block marker comments."""

    marker = re.fullmatch(r"\s*<!--(.*?)-->\s*", line)
    return marker is not None and marker.group(1).strip().startswith(_MARKERS)


def _comments(text: str) -> Iterator[tuple[int, str]]:
    """Each HTML comment's first line and text, OutcomeBound's block markers excepted."""

    for match in re.finditer(r"<!--(.*?)(-->|\Z)", text, re.DOTALL):
        number = text.count("\n", 0, match.start()) + 1
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        whole = text[line_start : line_end if line_end >= 0 else len(text)].strip()
        inner = match.group(1).strip()
        if whole == match.group(0).strip() and inner.startswith(_MARKERS):
            continue
        yield number, match.group(0)


def _concealed_content(path: str, text: str) -> list[Finding]:
    found = [
        _finding("concealed-content", path, n, UNVERIFIED, f"an HTML comment: {_quote(c)}")
        for n, c in _comments(text)
    ]
    for number, line in _lines(text):
        if _is_marker(line):
            continue
        for run in _BASE64_RUN.finditer(line):
            if _HEX_PIN.fullmatch(run.group(0)):
                continue
            fact = f"a base64-shaped run with no space: {_quote(run.group(0)[:40] + '...')}"
            found.append(_finding("concealed-content", path, number, UNVERIFIED, fact))
        if any(pattern.search(line) for pattern in _FETCH_AND_RUN):
            fact = f"a fetch-and-run line: {_quote(line)}"
            found.append(_finding("concealed-content", path, number, UNVERIFIED, fact))
    return found


def _override_phrases(path: str, text: str) -> list[Finding]:
    return [
        _finding("override-phrases", path, n, UNVERIFIED, f"an override phrase: {_quote(line)}")
        for n, line in _lines(text)
        if any(pattern.search(line) for pattern in _OVERRIDE_PHRASES)
    ]


# --- harness configuration ---------------------------------------------------------


def _json_values(
    value: Any, segments: Sequence[str], keys: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], Any]]:
    """(keys, value) for a dotted key, a literal dotted key and `*` both honoured."""

    if not segments:
        yield keys, value
        return
    if not isinstance(value, dict):
        return
    if segments[0] == "*":
        for key in sorted(value):
            yield from _json_values(value[key], segments[1:], (*keys, key))
        return
    for cut in range(len(segments), 0, -1):
        literal = ".".join(segments[:cut])
        if literal in value:
            yield from _json_values(value[literal], segments[cut:], (*keys, literal))


def _line_of(text: str, keys: Sequence[str]) -> int:
    """The line of the last of `keys` found, each looked for after the one before it."""

    index = 0
    for key in keys:
        found = text.find(json.dumps(key), index)
        if found < 0:
            break
        index = found
    return text.count("\n", 0, index) + 1


def _key_matches(full: str, spec: str) -> bool:
    spec_parts, parts = spec.split("."), full.split(".")
    if len(parts) < len(spec_parts):
        return False
    return all(s in ("*", p) for s, p in zip(spec_parts, parts, strict=False))


@dataclass(frozen=True, slots=True)
class _TomlEntry:
    line: int
    key: str
    value: str | None
    unsettled: str | None
    header: bool


def _toml_key(raw: str) -> str:
    return ".".join(part.strip().strip("\"'") for part in raw.split("."))


def _toml_entries(text: str) -> Iterator[_TomlEntry]:
    """`[table]` headers and `key = value` lines, read lexically: the oldest Python this
    engine supports has no TOML reader."""

    table, skip_until = "", None
    for number, raw in _lines(text):
        line = raw.strip()
        if skip_until is not None:
            if skip_until(line):
                skip_until = None
            continue
        if not line or line.startswith("#"):
            continue
        header = re.fullmatch(r"\[\[?([^\]]+)\]\]?(\s*#.*)?", line)
        if header:
            table = _toml_key(header.group(1))
            yield _TomlEntry(number, table, None, None, True)
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        full = ".".join(filter(None, (table, _toml_key(key))))
        value = value.strip()
        unsettled, skip_until = _toml_unsettled(value)
        yield _TomlEntry(number, full, value, unsettled, False)


def _toml_unsettled(value: str) -> tuple[str | None, Any]:
    """Why the lexical reader cannot settle a value, and how to find where it ends."""

    for quote in ('"""', "'''"):
        if value.startswith(quote):
            closed = value.count(quote) >= 2
            return "a multi-line string", None if closed else (lambda line, q=quote: q in line)
    if value.startswith("{"):
        return "an inline table", None
    if value.startswith("[") and value.count("[") > value.count("]"):
        depth = [value.count("[") - value.count("]")]

        def until(line: str) -> bool:
            depth[0] += line.count("[") - line.count("]")
            return depth[0] <= 0

        return "an array spanning lines", until
    return None, None


def _toml_hits(text: str, specs: Sequence[tuple[str, str]]) -> list[tuple[int, str, str]]:
    hits: list[tuple[int, str, str]] = []
    matched_tables: list[str] = []
    for entry in _toml_entries(text):
        if entry.unsettled:
            fact = f"key {entry.key}: {entry.unsettled} the lexical reader cannot settle"
            hits.append((entry.line, UNVERIFIED, fact))
        if any(entry.key.startswith(table + ".") for table in matched_tables):
            continue
        category = next((c for c, spec in specs if _key_matches(entry.key, spec)), None)
        if category is None:
            continue
        if entry.header:
            matched_tables.append(entry.key)
        shown = "(table)" if entry.header else _quote(entry.value or "", 120)
        hits.append((entry.line, UNVERIFIED, f"{_CATEGORY_NAMES[category]}: {entry.key} = {shown}"))
    return hits


def _own_entry(
    value: object, own: frozenset[str], harness: str, path: str, done: Sequence[str] | None
) -> bool:
    """Whether a group under a hook event is the one adopt writes for `harness` at `path`: its
    canonical JSON is byte for byte `finish_check.entry` for the row whose `finish_hook` names
    this file, the recorded Done commands' digest and the timeout the hook carries, where the row
    admits it; and a manifest `hook` record for this file holds that digest. Any other key, hook
    type, argument or Done digest makes it an ordinary entry."""

    hook = finish_check.hook_of(_row(harness))
    hooks = value.get("hooks") if isinstance(value, dict) else None
    if done is None or hook is None or hook.get("file") != path or not isinstance(hooks, list):
        return False
    first = hooks[0] if hooks and isinstance(hooks[0], dict) else {}
    timeout = first.get("timeout")
    if not isinstance(timeout, int) or not finish_check.admits_timeout(timeout):
        return False
    expected = canonical(finish_check.entry(harness, finish_check.done_digest(done), timeout))
    written = canonical(value)
    return written == expected and hashlib.sha256(written).hexdigest() in own


def _without_own(
    value: dict[str, Any],
    own: frozenset[str],
    harness: str,
    path: str,
    done: Sequence[str] | None,
) -> tuple[dict[str, Any], list[tuple[str, int, str]]]:
    """A hooks object without adopt's own groups, and (event, index, command) for each one."""

    rest: dict[str, Any] = {}
    found: list[tuple[str, int, str]] = []
    for event, groups in value.items():
        if not isinstance(groups, list):
            rest[event] = groups
            continue
        kept = []
        for index, group in enumerate(groups):
            if _own_entry(group, own, harness, path, done):
                found.append((event, index, " ".join(h["command"] for h in group["hooks"])))
            else:
                kept.append(group)
        if kept:
            rest[event] = kept
    return rest, found


def _config_hits(
    path: str,
    text: str,
    harness: str,
    own: frozenset[str] = frozenset(),
    done: Sequence[str] | None = None,
    done_shown: bool = False,
) -> list[tuple[int, str, str, bool]]:
    """(line, verdict, fact, decides) for each key `harness`'s row lists present, or each value left
    unsettled; each entry adopt wrote, its digest in `own`, is one review hit quoting the Done
    commands it runs, and it decides the result only where AGENTS.md does not show those
    commands (`done_shown`)."""

    keys = ((_row(harness) or {}).get("config") or {}).get("keys") or {}
    specs = [(category, spec) for category in _CATEGORIES for spec in keys.get(category) or []]
    if path.endswith(".toml"):
        return [(*hit, True) for hit in _toml_hits(text, specs)]
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        return [(error.lineno, UNVERIFIED, f"not read as JSON: {error.msg}", True)]
    hits: list[tuple[int, str, str, bool]] = []
    settled = (
        "; they are the Done commands AGENTS.md's project facts show"
        if done_shown
        else "; AGENTS.md's project facts do not show these Done commands"
    )
    for category, spec in specs:
        for path_keys, value in _json_values(document, spec.split(".")):
            if category == "hooks" and own and isinstance(value, dict):
                value, recognised = _without_own(value, own, harness, path, done)
                key = ".".join(path_keys)
                commands = (
                    _quote(json.dumps(list(done)), 240)
                    if done is not None
                    else "unreadable from the manifest"
                )
                hits.extend(
                    (
                        _line_of(text, (*path_keys, event)),
                        UNVERIFIED,
                        f"adopt's finish-check entry {key}.{event}[{index}] "
                        f"({_quote(command, 120)}) runs the Done commands the manifest records: "
                        f"{commands}{settled}",
                        not done_shown,
                    )
                    for event, index, command in recognised
                )
                if recognised and not value:
                    continue
            shown = _quote(json.dumps(value, sort_keys=True), 120)
            fact = f"{_CATEGORY_NAMES[category]}: {'.'.join(path_keys)} = {shown}"
            hits.append((_line_of(text, path_keys), UNVERIFIED, fact, True))
    return hits


def _harness_config(
    path: str,
    text: str,
    harnesses: Sequence[str],
    own: frozenset[str] = frozenset(),
    done: Sequence[str] | None = None,
    done_shown: bool = False,
) -> list[Finding]:
    """Secret-shaped values (a gate) and each listed key present (a review), per harness; an
    entry adopt wrote, its digest in `own`, is a review hit that quotes its Done commands."""

    findings: list[Finding] = [
        _finding(
            "harness-config",
            path,
            number,
            FAIL,
            f"a value shaped like {shape}",
            kind="gate",
            next=_NEXT["secret"],
        )
        for number, line in _lines(text)
        for shape, pattern in _SECRETS
        if pattern.search(line)
    ]
    for harness in harnesses:
        config = (_row(harness) or {}).get("config") or {}
        docs = config.get("docs") or "none recorded"
        step = (
            f"carry this to your handoff, where a person confirms that {harness} should load "
            f"it, and go on with the work; its permissions and hooks documentation: {docs}"
        )
        hits = _config_hits(path, text, harness, own, done, done_shown)
        findings.extend(
            _finding(
                "harness-config",
                path,
                number,
                verdict,
                fact,
                next="" if verdict == PASS else step,
                decides=decides,
            )
            for number, verdict, fact, decides in hits
        )
    return findings


# --- instruction-change ------------------------------------------------------------


def _git_status(root: Path, *arguments: str) -> tuple[int, bytes, bytes]:
    """One read-only git command's exit status and both streams; a git that cannot run raises
    `AuditError`. Git comes from PATH's absolute entries only, so the target cannot supply its
    own."""

    inherited = {key: value for key, value in os.environ.items() if key not in _GIT_UNSET}
    inherited["PATH"] = os.pathsep.join(
        part for part in inherited.get("PATH", "").split(os.pathsep) if os.path.isabs(part)
    )
    inherited["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        completed = subprocess.run(
            ["git", *GIT_READ_CONFIGURATION, *arguments],
            cwd=root,
            env=git_environment(inherited),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise AuditError(f"git could not run: {error}") from error
    return completed.returncode, completed.stdout, completed.stderr


def _git(root: Path, *arguments: str) -> bytes:
    """What one read-only git command printed in `root`; a failure raises `AuditError`."""

    status, output, error = _git_status(root, *arguments)
    if status != 0:
        raise AuditError(error.decode("utf-8", "replace").strip() or f"git exited {status}")
    return output


def _changed(root: Path, base: str) -> tuple[list[str] | None, str]:
    """Paths changed between `base` and HEAD, from a tree-to-tree diff, or why not."""

    if base.startswith("-"):
        return None, f"--base {base} names no commit"
    try:
        commit = _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
        raw = _git(
            root,
            "diff",
            *_SAFE_DIFF,
            "--name-only",
            "-z",
            "--relative",
            commit.decode("ascii").strip(),
            "HEAD",
        )
    except AuditError as error:
        return None, f"--base {base} could not be compared with HEAD ({_plain(str(error))})"
    return sorted({os.fsdecode(item) for item in raw.split(b"\0") if item}), ""


def _instruction_change(
    root: Path, base: str, files: Sequence[str], scope: _Scope
) -> list[Finding]:
    changed, why = _changed(root, base)
    if changed is None:
        return [
            _finding(
                "instruction-change",
                ".",
                0,
                UNVERIFIED,
                why,
                next="name a commit this repository has; no working-tree diff is "
                "taken in its place",
            )
        ]
    listed = set(files)
    hits = [path for path in changed if path in listed or path == MANIFEST or scope.wants(path)]
    if not hits:
        return [
            _finding(
                "instruction-change",
                ".",
                0,
                PASS,
                f"no instruction or configuration file in scope changed since {base}",
            )
        ]
    return [
        _finding(
            "instruction-change",
            path,
            0,
            UNVERIFIED,
            f"changed between {base} and HEAD",
            next=f"review the change as code before a harness loads it: "
            f"git diff {base} HEAD -- {path}",
        )
        for path in hits
    ]


# --- the report --------------------------------------------------------------------


def _order(finding: Finding) -> tuple[int, int, str, int]:
    return (
        FAMILIES.index(finding.family),
        list(CHECKS).index(finding.check),
        finding.path,
        finding.line,
    )


def _result(findings: Sequence[Finding]) -> str:
    findings = [f for f in findings if f.decides]
    if any(f.verdict == FAIL and f.kind == "gate" for f in findings):
        return FAIL
    if any(f.verdict in (FAIL, UNVERIFIED) for f in findings):
        return UNVERIFIED
    return PASS


def _counts(findings: Sequence[Finding]) -> dict[str, dict[str, int]]:
    counts = {family: dict.fromkeys(VERDICTS, 0) for family in FAMILIES}
    for finding in findings:
        counts[finding.family][finding.verdict] += 1
    return counts


def _is_note(relative: str, scope: _Scope) -> bool:
    """Whether `relative` is an agents' note and no harness loads it as an instruction file."""

    in_notes = any(relative == folder or relative.startswith(f"{folder}/") for folder in NOTES)
    return in_notes and not scope.wants(relative)


def _note_finding(finding: Finding) -> Finding:
    """A hidden character in a note: UNVERIFIED for that note, never FAIL for the target."""

    if finding.check != "hidden-characters" or finding.verdict != FAIL:
        return finding
    return replace(finding, verdict=UNVERIFIED, next=_NEXT["note"])


def _file_findings(
    root: Path,
    relative: str,
    scope: _Scope,
    harnesses: Sequence[str],
    own: Mapping[str, frozenset[str]] | None = None,
) -> list[Finding]:
    text, why = _read(root, relative)
    if text is None:
        return [_finding("hidden-characters", relative, 0, UNVERIFIED, why)]
    found: list[Finding] = []
    for name, run in (
        ("hidden-characters", _hidden_characters),
        ("concealed-content", _concealed_content),
        ("override-phrases", _override_phrases),
    ):
        found.extend(run(relative, text) or [_finding(name, relative, 0, PASS, "nothing matched")])
    if _is_note(relative, scope):
        found = [_note_finding(finding) for finding in found]
    owners = [h for h in scope.config.get(relative, ()) if h in harnesses]
    if owners:
        done = recorded_done(root) if (own or {}).get(relative) else None
        found.extend(
            _harness_config(
                relative,
                text,
                owners,
                (own or {}).get(relative, frozenset()),
                done,
                _done_shown(root, done),
            )
            or [
                _finding(
                    "harness-config", relative, 0, PASS, "no listed key and no secret-shaped value"
                )
            ]
        )
    return found


def _done_shown(root: Path, done: Sequence[str] | None) -> bool:
    """Whether the project-facts block of the target's AGENTS.md shows exactly these Done
    commands, as adopt renders them: then the finish check runs only what the instructions an
    agent loads already name. An AGENTS.md that resolves outside the target shows none."""

    if not done or not _inside(root, root / "AGENTS.md"):
        return False
    text, _ = _read(root, "AGENTS.md")
    if text is None:
        return False
    line = f"- Done: {facts.both([facts.code(command) for command in done])}"
    return any(
        line in text[block.begin_offset : block.end_offset].splitlines()
        for block in identity.find_managed_blocks(text)
        if block.block_id == facts.FACTS
    )


def _loading(
    harnesses: Sequence[str], configured: set[str], unused: frozenset[str] = frozenset()
) -> list[Finding]:
    """Per harness, whether its row's loading facts are verified and current, and, where its
    configuration was read, which of its key categories the table leaves unsettled. A harness
    in `unused`, selected only because every row was and loading no file the target holds, is
    reported and does not change the result."""

    found = []
    for harness in harnesses:
        row = _row(harness) or {}
        state = _row_state(harness, _row(harness), _today())
        fact, step = state or (
            f"the {harness} row is verified; re-check due {row.get('recheck_on')}",
            "",
        )
        verdict = UNVERIFIED if state else PASS
        decides = True
        if state and harness in unused:
            fact += "; the target holds no file this harness loads"
            decides = False
        found.append(
            _finding(
                "load-resolution",
                "adapters/harnesses.json",
                0,
                verdict,
                fact,
                next=step,
                decides=decides,
            )
        )
        keys = (row.get("config") or {}).get("keys") or {}
        unsettled = [_CATEGORY_LABELS[c] for c in _CATEGORIES if keys.get(c) is None]
        if not state and harness in configured and unsettled:
            fact = (
                f"the table does not say which {harness} keys hold "
                f"{adapters.or_list(tuple(unsettled))}; its configuration was read for the rest"
            )
            found.append(
                _finding("load-resolution", "adapters/harnesses.json", 0, UNVERIFIED, fact)
            )
    return found


def _audit(
    root: Path,
    files: Sequence[str],
    harnesses: Sequence[str],
    base: str | None,
    own: Mapping[str, frozenset[str]] | None = None,
    unused: frozenset[str] = frozenset(),
) -> list[Finding]:
    """Every finding for `files` under `root` and the named harnesses, unordered.

    Each file is opened only where it resolves, links followed, to a regular file
    inside `root` that is no person's; one that does not is reported and left unopened.
    `own` maps a configuration file to the digests of the entries adopt recorded writing there.
    """

    scope = _scope(harnesses)
    findings: list[Finding] = []
    seen: list[str] = []
    configured: set[str] = set()
    for relative in dict.fromkeys(files):
        why = "one person's file; not opened" if scope.personal(relative) else None
        why = why or _unopened(root, relative, scope)
        if why:
            findings.append(
                _finding("hidden-characters", relative, 0, UNVERIFIED, why, next=_NEXT["unopened"])
            )
            continue
        seen.append(relative)
        findings.extend(_file_findings(root, relative, scope, harnesses, own))
        configured.update(scope.config.get(relative, ()))
    findings.extend(_loading(harnesses, configured, unused))
    findings.extend(_ancestors(root, harnesses))
    if base is not None:
        findings.extend(_instruction_change(root, base, seen, scope))
    return findings


# --- selection ---------------------------------------------------------------------


def _artifacts(root: Path) -> list[Any]:
    """The records of the target's manifest; none where it is absent or unreadable."""

    candidate = root / MANIFEST
    if not _inside(root, candidate):
        return []
    try:
        manifest = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    artifacts = manifest.get("artifacts") if isinstance(manifest, dict) else None
    return artifacts if isinstance(artifacts, list) else []


def _manifest_entries(root: Path) -> dict[str, frozenset[str]]:
    """Per configuration file, the digests of the harness entries adopt recorded writing there.

    The manifest is the target's own data, so a digest exempts nothing: a recognised entry is
    still a review hit, its fact the Done commands it runs, and with `--base` a changed manifest
    is itself an `instruction-change` hit."""

    entries: dict[str, set[str]] = {}
    for artifact in _artifacts(root):
        if not isinstance(artifact, dict) or artifact.get("kind") != "hook":
            continue
        path, digest = artifact.get("path"), artifact.get("sha256")
        if isinstance(path, str) and isinstance(digest, str):
            entries.setdefault(path, set()).add(digest)
    return {path: frozenset(digests) for path, digests in entries.items()}


def _manifest_harnesses(root: Path) -> list[str]:
    """The harnesses the target's manifest records a skill copy for, in recorded order."""

    names: list[str] = []
    for artifact in _artifacts(root):
        if not isinstance(artifact, dict) or artifact.get("kind") != "skill":
            continue
        recorded = artifact.get("harnesses")
        for name in recorded if isinstance(recorded, list) else []:
            if isinstance(name, str) and name and name not in names:
                names.append(name)
    return names


def _generic_reads(names: Sequence[str], path: str) -> bool:
    """Whether `generic`, adopt's route for a harness the table does not list, is selected and
    `path` is an `AGENTS.md`, which such a harness reads by definition."""

    return GENERIC in names and path.rsplit("/", 1)[-1] == "AGENTS.md"


def _selection(
    root: Path, named: Sequence[str], present: Sequence[str]
) -> tuple[tuple[str, ...], str]:
    """The harnesses to check for, and where they came from.

    The manifest is the target's own data, so it cannot narrow the scope: after its harnesses,
    each other row, in table order, is added where a file present in the target loads in it
    and in none selected so far."""

    if named:
        return tuple(dict.fromkeys(named)), "flag"
    recorded = _manifest_harnesses(root)
    if not recorded:
        return tuple(adapters.table()), "table"
    names = list(recorded)
    for harness in adapters.table():
        covered, own = _scope(names), _scope([harness])
        if harness not in names and any(
            own.wants(path) and not covered.wants(path) and not _generic_reads(names, path)
            for path in present
        ):
            names.append(harness)
    return tuple(names), "manifest" if names == recorded else "manifest+present"


def _only(harness: str, names: Sequence[str], present: Sequence[str]) -> bool:
    """Whether the target holds a file that `harness` loads and no other of `names` does:
    a file every harness loads, such as AGENTS.md, does not make a row one the target uses."""

    own, others = _scope([harness]), _scope([name for name in names if name != harness])
    return any(own.wants(path) and not others.wants(path) for path in present)


def check(target: Path, harnesses: Sequence[str] = (), base: str | None = None) -> Report:
    """Select the harnesses, find what they load under `target`, and check it."""

    root = Path(target).resolve()
    if not root.is_dir():
        raise AuditError(f"{target} is not a directory")
    listed, listing = _listed(root)
    present = _walk(root, _scope([*adapters.table(), *harnesses]), listed)
    names, selected_by = _selection(root, harnesses, present)
    scope = _scope(names)
    notes = _notes(root)
    files = [path for path in present if scope.wants(path)] + notes
    own = _manifest_entries(root)
    unused = frozenset(
        harness
        for harness in names
        if selected_by == "table" and not _only(harness, names, present)
    )
    ordered = tuple(sorted(_audit(root, files, names, base, own, unused), key=_order))
    if notes:
        listing += "; and the agents' notes in .agents/handoffs/ and .agents/shared-memory/"
    return Report(
        result=_result(ordered),
        target=str(target),
        harnesses=names,
        selected_by=selected_by,
        listed_by="walk" if listed is None else "git",
        listing=listing,
        counts=_counts(ordered),
        findings=ordered,
    )


# --- output ------------------------------------------------------------------------


def _steps(report: Report) -> list[str]:
    """What a person runs to see what this command cannot; it runs none of them."""

    steps = [
        "run the project's completion check once; a tool it needs that is missing reads UNVERIFIED",
        "copy the target to a scratch directory, plant a defect there (a zero-width joiner in "
        "an instruction file) and see this command report FAIL on the copy",
    ]
    unrecorded = []
    for harness in report.harnesses:
        evidence = ((_row(harness) or {}).get("loading_evidence") or {}).get("instruction")
        if evidence:
            steps.append(f"see what {harness} loaded: {evidence}")
        else:
            unrecorded.append(harness)
    if unrecorded:
        names = ", ".join(unrecorded)
        steps.append(f"see what {names} loaded: no loading-evidence command is recorded")
    return steps


def report_document(report: Report) -> dict[str, Any]:
    """The report as `schemas/instruction-audit-report.schema.json` describes it."""

    # The report's fields are its JSON keys, so the dataclass and the schema cannot drift.
    document: dict[str, Any] = {field.name: getattr(report, field.name) for field in fields(report)}
    document.update(
        harnesses=list(report.harnesses),
        counts={family: dict(counts) for family, counts in report.counts.items()},
        findings=[asdict(finding) for finding in report.findings],
        steps=_steps(report),
    )
    return document


def _line(finding: Finding) -> str:
    line = (
        f"{finding.check} {finding.path}:{finding.line} {finding.verdict}: {finding.fact} "
        f"[{finding.severity}]"
    )
    line = line if finding.verdict == PASS else f"{line} next: {finding.next}"
    return line if finding.decides else f"{line} (does not change the result)"


def render(report: Report, *, verbose: bool = False) -> str:
    files = len({f.path for f in report.findings if f.check == "hidden-characters"})
    counts = "; ".join(
        f"{family} " + " ".join(f"{report.counts[family][v]} {v}" for v in VERDICTS)
        for family in FAMILIES
    )
    lines = [
        f"{report.result} {files} files; {counts}",
        f"harnesses: {', '.join(report.harnesses) or 'none'} (selected by {report.selected_by})",
        f"files: {report.listing}",
    ]
    lines.extend(_line(f) for f in report.findings if f.verdict != PASS)
    if verbose:
        lines.extend(_line(f) for f in report.findings if f.verdict == PASS)
    lines.append(
        "for the person to run, sandboxed, without network or credentials; "
        "this command runs none of them:"
    )
    lines.extend(f"- {step}" for step in _steps(report))
    return "\n".join(_plain(line) for line in lines)


_DESCRIPTION = (
    "Read-only checks on the instruction files and configuration each selected harness loads, "
    "security first. check reads, under the target: the instruction files, nested and rules "
    "files, skills and project configuration that adapters/harnesses.json says each selected "
    "harness loads, and .outcomebound/manifest.json to select harnesses, adding any harness "
    "whose files the target holds. It never opens a file a harness documents as one person's, "
    "nor anything outside the target but this engine's own data, and reports a path it leaves "
    "unopened as UNVERIFIED. Of a Git work tree it reads only what Git tracks or does not "
    "ignore, each path a harness row names exactly, and the agents' notes in .agents/handoffs/ "
    "and .agents/shared-memory/, which Git ignores and the next session reads. It starts no "
    "process but git, to list the files and for --base, opens no connection, "
    "runs nothing the files name, and writes nothing. Each finding names the prompt standard's "
    "rule it answers to (S4 security, S7 loading) and whether it is a gate or asks a person to "
    "review."
)
_EXITS = (
    "exits: 0 PASS, 1 FAIL, 2 UNVERIFIED or a usage error. A finding marked (does not change "
    "the result) is reported and leaves the exit as it is."
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound instructions", description=_DESCRIPTION, epilog=_EXITS
    )
    verbs = parser.add_subparsers(dest="verb", required=True, metavar="check")
    check_parser = verbs.add_parser(
        "check",
        help="run the checks on what the selected harnesses load",
        description=_DESCRIPTION,
        epilog=_EXITS,
    )
    check_parser.add_argument("target", help="the checkout to check; read, never written")
    check_parser.add_argument(
        "--harness",
        action="append",
        default=[],
        metavar="<h>[,<h>]",
        help="a harness to check for, repeatable or comma-separated; default: those the manifest "
        "records plus any whose files the target holds, else every row of "
        "adapters/harnesses.json",
    )
    check_parser.add_argument(
        "--base",
        metavar="<ref>",
        help="also list each instruction or configuration file changed between <ref> and HEAD, "
        "from a git tree-to-tree diff",
    )
    check_parser.add_argument(
        "--json", action="store_true", help="print one JSON report instead of text"
    )
    check_parser.add_argument(
        "--strict", action="store_true", help="count a review hit or an UNVERIFIED fact as FAIL"
    )
    check_parser.add_argument(
        "--verbose", action="store_true", help="also print the checks that passed"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run `check` and print its report; the exit code is its result."""

    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:
        return stop.code if isinstance(stop.code, int) else 2
    try:
        named = [name.strip() for value in args.harness for name in value.split(",")]
        report = check(Path(args.target), [name for name in named if name], args.base)
    except (AuditError, adapters.AdapterError) as error:
        print(f"outcomebound instructions: {_plain(str(error))}", file=sys.stderr)
        return 2
    if args.strict and report.result == UNVERIFIED:
        report = replace(report, result=FAIL)
    if args.json:
        print(json.dumps(report_document(report), indent=2, sort_keys=True))
    else:
        print(render(report, verbose=args.verbose))
    return {PASS: 0, FAIL: 1}.get(report.result, 2)


if __name__ == "__main__":
    raise SystemExit(main())
