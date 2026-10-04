#!/usr/bin/env python3
"""The `public-text` gate of this repository's floor: text that leaves this machine names no
local path, and, with the local list, no private name.

Two parts:

1. Home paths, with no list: a path under `/Users` or `/home`, or a leading home-relative
   path, in every text file Git tracks and in each commit message of the range. A
   home-relative path that this repository documents on purpose is in `DOCUMENTED`, with
   its reason. The floor runs this part, so it reads PASS or FAIL wherever it runs.
2. The local list, with `--private`: each term of the file that `OB_SCRUB_LIST` names, one
   term a line, `#` for a comment, matched whole-word and case-insensitively in the same
   text. Without the list, this part reads UNVERIFIED. The list is private, so it stays
   outside this repository.

A hit is reported by its place and its kind, never by the text it matched, so the output can
go to a public log. The first line printed is the verdict, as the floor shows only that line.

The range: `--range <a>..<b>`, as the floor passes it; else `--base <ref>`, read as
`<ref>..HEAD`; else `OUTCOMEBOUND_BASE`, where it names a commit; else no commit message is
read. `--stdin` reads only what it is given, such as a pull request's title and body.

Exit 0: no hit; 1: a hit; 2: UNVERIFIED (no local list for `--private`), or Git cannot read
the files or the range.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import unicodedata
from collections.abc import Iterator
from pathlib import Path

NAME = "public-text"
LIST_ENV = "OB_SCRUB_LIST"
BASE_ENV = "OUTCOMEBOUND_BASE"
# A path under a home folder. The character before it is not part of a word, a host or a
# longer path segment, so a URL path such as example.org/home/page is not one.
HOME = re.compile(r"(?<![\w.-])/(?:Users|home)/[^/\s]+")
# A home-relative path: a tilde that starts a path, then the path up to the first character
# that ends a path in prose or code.
TILDE = re.compile(r"(?<![\w.])~(?=/)[^\s`'\"()<>\[\]{},;]*")
# The home-relative paths this repository names on purpose, each with its reason. A path
# matches an entry exactly, or as a path below it.
DOCUMENTED = {
    "~/.outcomebound/research": "the link `outcomebound research clone` makes, documented",
    "~/.claude/CLAUDE.md": "Claude Code's user memory file, named as outside what adopt reads",
    "~/.gitconfig": "Git's user configuration, named in SECURITY.md",
    "~/x": "a synthetic home-relative path that tests and a docstring show as refused",
    "~/x.md": "a synthetic home-relative path that a test shows as refused",
    "~/empty": "a synthetic clone destination in a test",
}
# How much of a file the binary probe reads, as Git's own probe does.
PROBE = 8000


class Unreadable(Exception):
    """Git cannot list the files or read the range."""


def _git(root: Path, *arguments: str) -> bytes:
    try:
        done = subprocess.run(
            ["git", "-C", str(root), *arguments], capture_output=True, check=False
        )
    except OSError as error:
        raise Unreadable(f"git could not run: {error}") from error
    if done.returncode != 0:
        message = done.stderr.decode("utf-8", "replace").strip() or "git failed"
        raise Unreadable(message.splitlines()[0])
    return done.stdout


def _commit(root: Path, ref: str) -> bool:
    try:
        _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    except Unreadable:
        return False
    return True


def tracked_texts(root: Path) -> Iterator[tuple[str, str]]:
    """Each tracked regular file that is text, as (path, text); a binary file is one with a
    NUL byte in its first `PROBE` bytes."""

    listed = _git(root, "ls-files", "-z").decode("utf-8", "surrogateescape").split("\0")
    for path in filter(None, listed):
        full = root / path
        if full.is_symlink() or not full.is_file():
            continue
        data = full.read_bytes()
        if b"\0" in data[:PROBE]:
            continue
        yield path, data.decode("utf-8", "replace")


def commit_messages(root: Path, span: str) -> Iterator[tuple[str, str]]:
    """Each commit message in `span`, as (`commit <short id>`, message)."""

    raw = _git(root, "log", "-z", "--format=%h%n%B", span).decode("utf-8", "replace")
    for entry in filter(None, raw.split("\0")):
        short, _, message = entry.partition("\n")
        yield f"commit {short}", message


def load_list(path: Path | None) -> list[re.Pattern[str]]:
    """Whole-word, case-insensitive patterns, one per term of the local list; empty when there
    is no list. Terms and text are compared in Unicode NFC form."""

    if path is None or not path.is_file():
        return []
    patterns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        term = unicodedata.normalize("NFC", line.strip())
        if term and not term.startswith("#"):
            patterns.append(re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE))
    return patterns


def _documented(path: str) -> bool:
    token = path.rstrip(".:")
    return any(token == entry or token.startswith(entry + "/") for entry in DOCUMENTED)


def hits(where: str, text: str, terms: list[re.Pattern[str]]) -> Iterator[str]:
    """One line per hit in `text`: its place and its kind, never the matched text."""

    for number, line in enumerate(text.splitlines(), start=1):
        normal = unicodedata.normalize("NFC", line)
        tilde = (match.group(0) for match in TILDE.finditer(line))
        if HOME.search(line) or any(not _documented(path) for path in tilde):
            yield f"{where}:{number}: a home path"
        if any(term.search(normal) for term in terms):
            yield f"{where}:{number}: matches the local list"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _span(root: Path, given_range: str | None, base: str | None) -> tuple[str | None, str]:
    """The commit range to read, and a note on where it came from when it reads none."""

    if given_range is not None:
        return given_range, ""
    if base is not None:
        if not _commit(root, base):
            raise Unreadable(f"--base {base} names no commit")
        return f"{base}..HEAD", ""
    fallback = os.environ.get(BASE_ENV, "").strip()
    if fallback and _commit(root, fallback):
        return f"{fallback}..HEAD", ""
    if fallback:
        return None, f"; {BASE_ENV} names no commit here, so no commit message was read"
    return None, ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that the text Git tracks, the commit messages of a range and, with "
        "--stdin, the given text name no home path; with --private, also no term of the local "
        f"list that {LIST_ENV} names. Exit 0: no hit; 1: a hit; 2: UNVERIFIED (no local list "
        "for --private), or Git cannot read the files or the range."
    )
    parser.add_argument("root", nargs="?", default=".", help="the repository root (default: .)")
    span = parser.add_mutually_exclusive_group()
    span.add_argument("--range", help="the commits whose messages are read, as <a>..<b>")
    span.add_argument("--base", help=f"read the messages of <base>..HEAD (default: ${BASE_ENV})")
    parser.add_argument(
        "--stdin", action="store_true", help="read only standard input, not the files or commits"
    )
    parser.add_argument(
        "--private", action="store_true", help=f"also apply the local list that ${LIST_ENV} names"
    )
    args = parser.parse_args(argv)
    root = Path(args.root)

    named = os.environ.get(LIST_ENV, "").strip()
    terms = load_list(Path(named).expanduser()) if args.private and named else []
    found: list[str] = []
    try:
        if args.stdin:
            found += hits("stdin", sys.stdin.read(), terms)
            read, note = "standard input", ""
        else:
            files = commits = 0
            for path, text in tracked_texts(root):
                files += 1
                found += hits(path, text, terms)
            chosen, note = _span(root, args.range, args.base)
            for where, message in commit_messages(root, chosen) if chosen else ():
                commits += 1
                found += hits(where, message, terms)
            read = f"{_plural(files, 'file')}, {_plural(commits, 'commit')}"
    except Unreadable as error:
        print(f"UNVERIFIED {NAME}: {error}")
        return 2

    missing = args.private and not terms
    what = "no home path" + (" and no term of the local list" if terms else "")
    if found:
        print(f"FAIL {NAME}: {_plural(len(found), 'hit')} ({read}{note})")
        print("\n".join(f"  {line}" for line in found))
        if missing:
            print(f"  the local list was not applied: no list in {LIST_ENV}")
        return 1
    if missing:
        print(f"UNVERIFIED {NAME}: no local list ({LIST_ENV}); {what} ({read}{note})")
        return 2
    print(f"PASS {NAME}: {what} ({read}{note})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
