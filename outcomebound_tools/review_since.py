"""`outcomebound review since`: what changed since the ref a review file read, and which findings
cite a changed path (`docs/specs/review/design.md`, `schemas/review-since.schema.json`).

What this module decides: the ref (`--since REF`, else the file's `Reviewed:` line, the one
`review check` reads); the changes (tracked paths with their status, counts and hunks read with
no context lines, and untracked regular files, all against the work tree of the repository that
holds `--root`); and which references in a finding's text name a changed path. The result is a
report or UNVERIFIED with the reason, never PASS or FAIL. Exits: 0 a report; 1 UNVERIFIED; 2 a
usage error.

What it does not decide: whether a finding is stale, fixed or still holds, or whether the ref
names what the reviewer read. It writes nothing: it reads Git through `size`'s helpers, with
optional locks off, and changes no file or index. Standard library only. `review check` and
`review sweep` stay in `review_check`, free of Git.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from outcomebound_tools import review_check, size, textio

VERSION = 1
SHOWN = 12
STATUSES = {
    "M": "modified",
    "A": "added",
    "D": "deleted",
    "R": "renamed",
    "T": "type-changed",
}
LIMITS = (
    "that a changed path means a finding is stale or fixed, or that an unchanged one still holds",
    "that the ref names what the reviewer read",
    "anything about paths Git ignores",
    "a finding that names no path, text under a malformed finding heading, or a path named "
    "another way than by its text in the finding",
)
_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_RANGES = r"\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*"
_CITE = re.compile(rf"([A-Za-z0-9_.@+/-]+)(?::({_RANGES}))?")


@dataclass
class Change:
    path: str
    status: str
    added: int | None = None
    removed: int | None = None
    old_path: str | None = None
    hunks: list[tuple[int, int, int, int]] = field(default_factory=list)

    def lost(self, line: int) -> bool:
        """Whether `line` of the reviewed file lies in a span the work tree no longer has."""

        return any(count > 0 and start <= line < start + count for start, count, _, _ in self.hunks)


def _unverified(reason: str) -> dict[str, Any]:
    return {
        "version": VERSION,
        "result": "UNVERIFIED",
        "reason": reason,
        "does_not_establish": list(LIMITS),
    }


def _resolve(root: Path, ref: str) -> str:
    """The commit `ref` names, or a `size.SizeError` whose text is Git's own reason."""

    commit = None if ref.startswith("-") else size._commit_of(root, ref)
    if commit is not None:
        return commit
    if ref.startswith("-"):
        raise size.SizeError(f"the ref {textio.quote(ref)} starts with a dash")
    _, _, error = size._git(root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    message = error.decode("utf-8", "replace").strip() or "it names no commit"
    raise size.SizeError(
        f"Git does not resolve {textio.quote(ref)} to a commit: {textio.plain(message)}"
    )


def _moving(root: Path, ref: str) -> bool:
    status, out, _ = size._git(root, "rev-parse", "--symbolic-full-name", ref)
    name = out.decode("utf-8", "replace").strip() if status == 0 else ""
    return name == "HEAD" or name.startswith(("refs/heads/", "refs/remotes/"))


def _raw(root: Path, commit: str) -> list[tuple[str, str, str | None]]:
    """`(status word, path, old path)` for each tracked path that differs from `commit`."""

    out = size._git_ok(
        root, "diff-index", "--raw", "-z", "-M", "--no-ext-diff", "--no-textconv", commit, "--"
    )
    tokens = out.split(b"\0")
    found: list[tuple[str, str, str | None]] = []
    index = 0
    while index < len(tokens) and tokens[index].startswith(b":"):
        letter = tokens[index].split()[-1][:1].decode("ascii", "replace")
        if letter in "RC":
            found.append(
                ("renamed", os.fsdecode(tokens[index + 2]), os.fsdecode(tokens[index + 1]))
            )
            index += 3
        else:
            found.append((STATUSES.get(letter, "modified"), os.fsdecode(tokens[index + 1]), None))
            index += 2
    return found


def _hunks(root: Path, commit: str, change: Change) -> list[tuple[int, int, int, int]]:
    paths = [change.path] + ([change.old_path] if change.old_path else [])
    out = size._git_ok(
        root,
        "--literal-pathspecs",
        "diff-index",
        "-p",
        "--unified=0",
        "-M",
        "--no-ext-diff",
        "--no-textconv",
        commit,
        "--",
        *paths,
    ).decode("utf-8", "replace")
    found = []
    for line in out.splitlines():
        match = _HUNK.fullmatch(line.split(" @@", 1)[0] + " @@") if line.startswith("@@ ") else None
        if match:
            old_start, old_count, new_start, new_count = match.groups()
            found.append(
                (
                    int(old_start),
                    1 if old_count is None else int(old_count),
                    int(new_start),
                    1 if new_count is None else int(new_count),
                )
            )
    return found


def changes(root: Path, commit: str) -> tuple[list[Change], int]:
    """Each change against `commit`, and how many untracked entries were not regular files."""

    counts = {path: (added, removed) for path, added, removed in size.tracked_changes(root, commit)}
    found = []
    for status, path, old in _raw(root, commit):
        change = Change(path, status, old_path=old)
        change.added, change.removed = counts.get(path, (None, None))
        change.hunks = _hunks(root, commit, change)
        found.append(change)
    skipped = 0
    for path in size.untracked_paths(root):
        try:
            regular = stat.S_ISREG((root / path).lstat().st_mode)
        except OSError:
            regular = False
        if regular:
            found.append(Change(path, "untracked"))
        else:
            skipped += 1
    return sorted(found, key=lambda change: change.path), skipped


def _findings(text: str) -> list[tuple[str, int, list[str]]]:
    """Each finding's id, the line of its heading and its lines outside code fences."""

    found: list[tuple[str, int, list[str]]] = []
    current: list[str] | None = None
    for number, line in review_check._lines(text):
        if review_check._NESTED.match(line):
            current = None
            continue
        heading = review_check._HEADING.fullmatch(line)
        if heading and len(heading.group(1)) <= 3:
            current = None
            if len(heading.group(1)) == 3:
                match = review_check._FINDING.fullmatch((heading.group(2) or "").rstrip())
                if match:
                    current = []
                    found.append((match.group(1), number, current))
        elif current is not None:
            current.append(line)
    return found


def _references(lines: Sequence[str]) -> list[tuple[str, int | None, int | None]]:
    """`(path, line, line_end)` for each reference in `lines`: a path holding a `/` or a dotted
    suffix, with `:N`, `:N-M` or a comma list of those, or none, and not after `://`."""

    found: list[tuple[str, int | None, int | None]] = []
    for line in lines:
        for match in _CITE.finditer(line):
            path = match.group(1).rstrip(".,;")
            path = path[2:] if path.startswith("./") else path
            if (
                line[: match.start()].endswith("://")
                or path.startswith("/")
                or not ("/" in path or re.search(r"\w\.\w", path))
            ):
                continue
            if match.group(2) is None:
                found.append((path, None, None))
                continue
            for part in match.group(2).split(","):
                first, _, last = part.partition("-")
                found.append((path, int(first), int(last) if last else None))
    return found


def _cites(text: str, changed: Sequence[Change]) -> list[dict[str, Any]]:
    paths = {change.path: change for change in changed}
    olds = {change.old_path: change for change in changed if change.old_path}
    results = []
    for finding_id, number, lines in _findings(text):
        cites = []
        for path, first, last in _references(lines):
            if path in paths or path in olds:
                matched = [paths.get(path) or olds[path]]
                candidates: list[str] = []
            else:
                matched = [change for name, change in paths.items() if name.endswith("/" + path)]
                candidates = [change.path for change in matched] if len(matched) > 1 else []
            for change in matched:
                cite: dict[str, Any] = {"path": change.path, "line_changed": False}
                if first is not None:
                    cite["line"] = first
                    if last is not None:
                        cite["line_end"] = last
                    cite["line_changed"] = any(
                        change.lost(n) for n in range(first, (last or first) + 1)
                    )
                if candidates:
                    cite["candidates"] = candidates
                if cite not in cites:
                    cites.append(cite)
        if cites:
            results.append({"id": finding_id, "line": number, "cites": cites})
    return results


def build(path: Path, since: str | None, root: Path) -> dict[str, Any]:
    """The report for the review file at `path`, or an UNVERIFIED one with its reason."""

    try:
        text = textio.read_text(path)
    except (OSError, UnicodeDecodeError) as error:
        return _unverified(f"the review file cannot be read: {textio.plain(str(error))}")
    reviewed = review_check._parse(text)[0]
    ref = since if since is not None else reviewed
    if not ref:
        return _unverified("the file has no `Reviewed:` ref and none was given with --since")
    try:
        top = Path(
            size._git_ok(root, "rev-parse", "--show-toplevel").decode("utf-8", "replace").strip()
        )
        commit = _resolve(top, ref)
        moving = _moving(top, ref)
        changed, skipped = changes(top, commit)
    except size.SizeError as error:
        return _unverified(str(error))
    except (OSError, ValueError) as error:
        return _unverified(f"Git could not be read: {textio.plain(str(error))}")
    files = []
    for change in changed:
        entry: dict[str, Any] = {
            "path": change.path,
            "status": change.status,
            "added": change.added,
            "removed": change.removed,
            "hunks": [
                {"old_start": a, "old_count": b, "new_start": c, "new_count": d}
                for a, b, c, d in change.hunks
            ],
        }
        if change.old_path:
            entry["old_path"] = change.old_path
        files.append(entry)
    report: dict[str, Any] = {
        "version": VERSION,
        "result": "REPORT",
        "reviewed": ref,
        "ref_source": "--since" if since is not None else "Reviewed line",
        "commit": commit,
        "files": files,
        "findings": _cites(text, changed),
        "does_not_establish": list(LIMITS),
    }
    if moving:
        report["ref_is_moving"] = True
    if skipped:
        report["untracked_skipped"] = skipped
    return report


def render_text(report: dict[str, Any], *, verbose: bool = False) -> str:
    if report["result"] == "UNVERIFIED":
        return f"UNVERIFIED: {textio.visible(report['reason'])}\n"
    cited = {cite["path"] for item in report["findings"] for cite in item["cites"]}
    lines = [
        f"REPORT: {len(report['files'])} changed path(s), {len(report['findings'])} finding(s) "
        f"cite one; since {textio.visible(report['reviewed'])} ({report['ref_source']}), "
        f"commit {report['commit'][:SHOWN]}"
    ]
    if report.get("ref_is_moving"):
        lines.append(
            "note: the ref is a branch or HEAD; its tip now may not be what the review read "
            "(--since names another)"
        )
    if report.get("untracked_skipped"):
        lines.append(f"note: {report['untracked_skipped']} untracked entr(ies) that are not files")
    for file in report["files"]:
        counts = "" if file["added"] is None else f" +{file['added']} -{file['removed']}"
        old = f" (from {textio.visible(file['old_path'])})" if "old_path" in file else ""
        lines.append(f"{file['status']} {textio.visible(file['path'])}{old}{counts}")
        if verbose or file["path"] in cited:
            lines.extend(
                f"  @@ -{h['old_start']},{h['old_count']} +{h['new_start']},{h['new_count']} @@"
                for h in file["hunks"]
            )
    for item in report["findings"]:
        for cite in item["cites"]:
            where = textio.visible(cite["path"]) + (f":{cite['line']}" if "line" in cite else "")
            if "line_end" in cite:
                where += f"-{cite['line_end']}"
            flags = (" [line changed]" if cite["line_changed"] else "") + (
                f" [ambiguous: {', '.join(map(textio.visible, cite['candidates']))}]"
                if "candidates" in cite
                else ""
            )
            lines.append(
                f"finding {textio.visible(item['id'])} (line {item['line']}) cites {where}{flags}"
            )
    lines.append("Does not establish: " + "; ".join(report["does_not_establish"]) + ".")
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound review since",
        description=(
            "Print what changed between the ref a review file read and the work tree, and "
            "which findings cite a changed path. The ref is --since REF, else the file's "
            "`Reviewed:` line. Prints a report or UNVERIFIED with the reason; reads Git, "
            "writes nothing."
        ),
        epilog="Exits: 0 a report; 1 UNVERIFIED; 2 a usage error.",
    )
    parser.add_argument("path", metavar="FILE", help="the review file")
    parser.add_argument("--since", metavar="REF", help="the ref the review read, over the file's")
    parser.add_argument("--root", default=".", metavar="DIR", help="a folder inside the work tree")
    parser.add_argument("--json", action="store_true", help="print one JSON object, not text")
    parser.add_argument("--verbose", action="store_true", help="print every file's hunks")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    options = _parser().parse_args(argv)
    report = build(Path(options.path), options.since, Path(options.root))
    if options.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_text(report, verbose=options.verbose))
    return 0 if report["result"] == "REPORT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
